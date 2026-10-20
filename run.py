"""Pipeline orchestrator. One command per stage, or `all` for the full sequence.

Paid commands call Jev and need TYPESAFE_API_KEY in .env. Everything else is offline.
Add --dry-run to any paid command to use the offline simulator instead (free, results marked SIMULATED).

  python3 run.py all     --csv data/spotify_reviews_18months.csv --work runs/full --workers 8
  python3 run.py prepare --csv FILE.csv --work runs/NAME             (offline)
  python3 run.py enrich  --csv FILE.csv --work runs/NAME [--workers N] [--limit N] [--max-hours H]   (paid)
  python3 run.py verify  --csv FILE.csv --work runs/NAME --sample 1000   (paid)
  python3 run.py group   --work runs/NAME                              (paid: one call per issue)
  python3 run.py rank    --work runs/NAME                              (offline, rerunnable)
  python3 run.py memo    --work runs/NAME                              (paid: one call)
  python3 run.py checkpoint --work runs/NAME --name before             (offline)
  python3 run.py export  --csv FILE.csv --work runs/NAME --before ... --after ...   (offline)
  python3 run.py status  --work runs/NAME                              (offline)

Spending: one ledger (runs/spend_ledger.json) is shared by every run and stage. --cap sets the total
USD limit across all runs (default 10). A call is dispatched only if spent + reserved + its worst-case
estimate stays within the cap.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline import enrich, group, memo, prepare, rank, verify  # noqa: E402
from pipeline.common import SpendLedger, load_input_rate, log_event, read_jsonl, write_json  # noqa: E402

LEDGER = ROOT / "runs" / "spend_ledger.json"


def make_client(args):
    if args.dry_run:
        from pipeline.fake_jev import FakeJevClient
        print("DRY RUN: offline simulator, no API calls, results are SIMULATED and cannot be exported.")
        return FakeJevClient(), 0.0
    import config
    from pipeline.jev_client import JevClient
    client = JevClient(config.get_key(config.TYPESAFE))
    return client, load_input_rate(client.model)


def ledger_for(args):
    path = (Path(args.work) / "sim_ledger.json") if args.dry_run else LEDGER
    return SpendLedger(args.cap, path)


def cmd_prepare(args):
    report = prepare.prepare(args.csv, args.work)
    write_json(Path(args.work) / "run_meta.json", {"csv": str(Path(args.csv).resolve()),
                                                    "model": "jev-1.13.0",
                                                    "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    print(json.dumps(report, indent=2))


def cmd_enrich(args, client=None, rate=None, ledger=None):
    if not 1 <= args.batch_size <= 50:
        sys.exit("--batch-size must be between 1 and 50")
    if client is None:
        client, rate = make_client(args)
        ledger = ledger_for(args)
    stop = enrich.StopFlag()
    stop.install()
    max_seconds = args.max_hours * 3600 if args.max_hours else None
    s = enrich.run(args.work, args.csv, client, ledger, rate, workers=args.workers, limit=args.limit,
                   max_seconds=max_seconds, stop=stop, batch_size=args.batch_size)
    print(json.dumps(s, indent=2))
    return s


def cmd_verify(args, client=None, rate=None, ledger=None):
    if client is None:
        client, rate = make_client(args)
        ledger = ledger_for(args)
    return verify.run(args.work, args.csv, client, ledger, rate, n=args.sample)


def cmd_group(args, client=None, rate=None, ledger=None):
    if client is None:
        client, rate = make_client(args)
        ledger = ledger_for(args)
    return group.run(args.work, client, ledger, rate)


def cmd_rank(args):
    return rank.run(args.work)


def cmd_memo(args, client=None, rate=None, ledger=None):
    if client is None:
        client, rate = make_client(args)
        ledger = ledger_for(args)
    return memo.run(args.work, client, ledger, rate)


def cmd_all(args):
    started = time.time()
    if not (Path(args.work) / "pending.jsonl").exists():
        cmd_prepare(args)
    client, rate = make_client(args)
    ledger = ledger_for(args)
    stages = {}
    t = time.time()
    s = cmd_enrich(args, client, rate, ledger)
    stages["enrich"] = round(time.time() - t, 3)
    if s["stop_reason"] not in ("finished",):
        print(f"Enrichment stopped ({s['stop_reason']}). Rerun the same command to resume; later stages wait.")
        return
    for name, fn in (("verify", cmd_verify), ("group", cmd_group)):
        t = time.time()
        fn(args, client, rate, ledger)
        stages[name] = round(time.time() - t, 3)
    t = time.time()
    cmd_rank(args)
    stages["rank"] = round(time.time() - t, 3)
    t = time.time()
    cmd_memo(args, client, rate, ledger)
    stages["memo"] = round(time.time() - t, 3)
    total = round(time.time() - started, 3)
    log_event(Path(args.work) / "run_log.jsonl", event="all_done", stage_seconds=stages, wall_seconds=total,
              spent_usd_ledger=round(ledger.spent, 8))
    print(f"done in {total:.1f}s; stages {stages}; total spend so far ${ledger.spent:.4f} of ${ledger.cap:.2f}")


def cmd_checkpoint(args):
    path, n = enrich.snapshot(args.work, args.name)
    print(f"{n:,} completed IDs saved to {path}")


def cmd_export(args):
    from pipeline import export
    export.build(args.work, args.csv, args.out, args.before, args.after, allow_simulated=args.allow_simulated)


def cmd_status(args):
    work = Path(args.work)
    latest = {}
    for rec in read_jsonl(work / "results.jsonl"):
        latest[rec["review_id"]] = rec
    pending = sum(1 for _ in read_jsonl(work / "pending.jsonl"))
    c = Counter(r["status"] for r in latest.values())
    cached = sum(1 for r in latest.values() if r.get("cache_source_id"))
    spent = json.loads(LEDGER.read_text())["spent_usd"] if LEDGER.exists() else 0.0
    print(f"nonempty reviews: {pending:,} | completed: {c['completed']:,} (of which cache copies {cached:,}) | "
          f"quarantined: {c['quarantined']:,} | not yet done: {pending - c['completed'] - c['quarantined']:,}")
    print(f"total API spend recorded across all runs: ${spent:.4f}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, csv=False, paid=False):
        q = sub.add_parser(name)
        q.add_argument("--work", required=True)
        if csv:
            q.add_argument("--csv", required=True)
        if paid:
            q.add_argument("--cap", type=float, default=10.0, help="total USD cap across all runs (default 10)")
            q.add_argument("--dry-run", action="store_true", help="offline simulator, no API calls")
        return q

    add("prepare", csv=True)
    for name in ("enrich", "all"):
        q = add(name, csv=True, paid=True)
        q.add_argument("--workers", type=int, default=1)
        q.add_argument("--batch-size", type=int, default=20, help="reviews per enrich request (max 50)")
        q.add_argument("--limit", type=int, default=None, help="max distinct texts to send this session")
        q.add_argument("--max-hours", type=float, default=None)
        q.add_argument("--sample", type=int, default=1000, help="verification sample size")
    add("verify", csv=True, paid=True).add_argument("--sample", type=int, default=1000)
    add("group", paid=True)
    add("rank")
    add("memo", paid=True)
    add("checkpoint").add_argument("--name", required=True)
    q = add("export", csv=True)
    q.add_argument("--out", default="grading")
    q.add_argument("--before", required=True)
    q.add_argument("--after", required=True)
    q.add_argument("--allow-simulated", action="store_true", help="tests only")
    add("status")
    args = p.parse_args(argv)
    {"prepare": cmd_prepare, "enrich": cmd_enrich, "verify": cmd_verify, "group": cmd_group, "rank": cmd_rank,
     "memo": cmd_memo, "all": cmd_all, "checkpoint": cmd_checkpoint, "export": cmd_export,
     "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    main()
