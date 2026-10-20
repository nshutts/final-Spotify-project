"""100-review cost and runtime pilot (see COST_CALCULATOR.md).

Offline (default, no key, no calls): rebuild cost/report.md from saved measurements and editable rates.
    python3 -m cost.pilot report [--rates cost/rates.csv] [--assumptions cost/assumptions.json]

Paid (explicit): run the real pipeline on cost_100.csv twice in a fresh folder, one worker.
    python3 -m cost.pilot run --csv data/cost_100.csv
Cold run: empty result cache, all stages (enrich, verify sample of 20, group, rank, memo).
Warm run: same command again on the saved results; must make zero new enrichment calls.

Saved under cost/: pilot_records.jsonl, pilot_calls.jsonl, usage.csv, measurements.json, report.md.
Formulas: item_cost = billed_units x (price_per_million / 1,000,000); total = sum(item_cost).
Jev bills input tokens only (output price 0). Wall-clock times come from a clock, not summed call times.
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cost.calculator import cost_by_stage, load_rates, money  # noqa: E402

COST = ROOT / "cost"
WORK = COST / "pilot_work"
EXPECTED_SHA = None  # filled from manifest when available


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_pilot(csv_path, verify_sample=20):
    from pipeline import enrich, group, memo, prepare, rank, verify
    from pipeline.common import SpendLedger, load_input_rate, read_jsonl, write_json
    from pipeline.export import RECORD_KEYS
    import config
    from pipeline.jev_client import JevClient

    if WORK.exists() and any(WORK.iterdir()):
        sys.exit(f"{WORK} already exists. The cold run needs an empty result cache: move or delete it first.")
    client = JevClient(config.get_key(config.TYPESAFE))
    rate = load_input_rate(client.model)
    ledger = SpendLedger(10.0, ROOT / "runs" / "spend_ledger.json")
    meas = {"input_csv": str(csv_path), "input_sha256": file_sha(csv_path), "provider": "TypeSafe Jev",
            "model": client.model, "workers": 1, "reviews_per_request": 20, "verify_sample": verify_sample,
            "runs": {}}

    def calls_count():
        return sum(1 for _ in read_jsonl(WORK / "calls.jsonl"))

    for run_id in ("pilot-cold", "pilot-warm"):
        before = calls_count()
        t0 = time.time()
        stages = {}
        if run_id == "pilot-cold":
            t = time.time()
            prep = prepare.prepare(csv_path, WORK)
            write_json(WORK / "run_meta.json", {"csv": str(csv_path), "model": client.model})
            stages["prepare"] = round(time.time() - t, 3)
            meas["prepare"] = prep
        t = time.time()
        s = enrich.run(WORK, csv_path, client, ledger, rate, workers=1)
        stages["enrich"] = round(time.time() - t, 3)
        t = time.time()
        v = verify.run(WORK, csv_path, client, ledger, rate, n=verify_sample)
        stages["verify"] = round(time.time() - t, 3)
        t = time.time()
        g = group.run(WORK, client, ledger, rate)
        stages["group"] = round(time.time() - t, 3)
        t = time.time()
        rank.run(WORK)
        stages["rank"] = round(time.time() - t, 3)
        t = time.time()
        m = memo.run(WORK, client, ledger, rate)
        stages["memo"] = round(time.time() - t, 3)
        wall = round(time.time() - t0, 3)
        after = calls_count()
        meas["runs"][run_id] = {"wall_seconds": wall, "stage_seconds": stages, "call_log_lines": [before, after],
                                "enrich": {k: s[k] for k in ("requests", "attempts", "failed_attempts",
                                                             "completed_new", "cache_copies", "quarantined",
                                                             "skipped_done", "input_tokens", "output_tokens")},
                                "verify_new_calls": v.get("new_calls_this_run", 0),
                                "group_new_calls": g["new_calls"], "memo_new_calls": m["new_calls"]}
        print(f"{run_id}: {wall:.1f}s wall, {after - before} call-log lines")

    # Evidence files
    latest = {}
    for rec in read_jsonl(WORK / "results.jsonl"):
        latest[rec["review_id"]] = rec
    for rec in read_jsonl(WORK / "quarantine.jsonl"):
        latest.setdefault(rec["review_id"], rec)
    with (COST / "pilot_records.jsonl").open("w", encoding="utf-8") as f:
        for rid in sorted(latest):
            r = latest[rid]
            keep = {k: r[k] for k in RECORD_KEYS if k in r} if r["status"] == "completed" else \
                {"review_id": rid, "source_sha256": r["source_sha256"], "status": "quarantined", "reason": r.get("reason")}
            f.write(json.dumps(keep, ensure_ascii=False) + "\n")
    calls = list(read_jsonl(WORK / "calls.jsonl"))
    cold_end = meas["runs"]["pilot-cold"]["call_log_lines"][1]
    with (COST / "pilot_calls.jsonl").open("w", encoding="utf-8") as f, \
         (COST / "usage.csv").open("w", encoding="utf-8", newline="") as u:
        w = csv.writer(u)
        w.writerow(["run_id", "stage", "model", "call_id", "uncached_input_tokens", "cached_input_tokens",
                    "output_tokens", "outcome", "seconds", "usage_reported"])
        for i, c in enumerate(calls):
            run_id = "pilot-cold" if i < cold_end else "pilot-warm"
            f.write(json.dumps({"run_id": run_id, **c}, ensure_ascii=False) + "\n")
            w.writerow([run_id, c["role"], c["model"], c["request_id"], c["input_tokens"], 0, c["output_tokens"],
                        c["outcome"], c.get("seconds") or 0, c.get("usage_reported", True)])
    meas["unique_texts"] = meas["prepare"]["distinct_nonempty_texts"]
    meas["measured_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    write_json(COST / "measurements.json", meas)
    build_report()


def build_report(rates_path=COST / "rates.csv", assumptions_path=COST / "assumptions.json"):
    meas = json.loads((COST / "measurements.json").read_text(encoding="utf-8"))
    a = json.loads(Path(assumptions_path).read_text(encoding="utf-8"))
    rates = load_rates(rates_path)
    with (COST / "usage.csv").open(encoding="utf-8", newline="") as f:
        usage = list(csv.DictReader(f))
    cold = [u for u in usage if u["run_id"] == "pilot-cold"]
    warm = [u for u in usage if u["run_id"] == "pilot-warm"]
    c_cost, w_cost = cost_by_stage(cold, rates), cost_by_stage(warm, rates) if warm else {"api_total": "0", "stages": {}}
    rc, rw = meas["runs"]["pilot-cold"], meas["runs"]["pilot-warm"]
    n_rows = meas["prepare"]["rows"]
    completed = rc["enrich"]["completed_new"] + rc["enrich"]["cache_copies"]
    total_cold = Decimal(c_cost["api_total"])

    def stage_tokens(stage):
        rows = [u for u in cold if u["stage"] == stage]
        ok = [u for u in rows if u["outcome"] == "succeeded"]
        tin = sum(int(u["uncached_input_tokens"]) for u in rows)
        return len(rows), len(ok), tin

    enr_calls, enr_ok, enr_tin = stage_tokens("enrich")
    per_enrich_call_tokens = Decimal(enr_tin) / Decimal(max(enr_ok, 1))
    # Projection unit is one distinct text: billed enrich tokens per labelled original.
    per_text_tokens = Decimal(enr_tin) / Decimal(max(rc["enrich"]["completed_new"] + rc["enrich"]["quarantined"], 1))
    in_rate = rates[(meas["model"], "uncached_input")]["price"] / Decimal(1_000_000)
    lat = rc["stage_seconds"]["enrich"] / max(rc["enrich"]["requests"], 1)

    L = ["# 100-review cost and runtime report", "",
         f"Generated offline from `measurements.json`, `usage.csv` and `rates.csv`. Pilot measured {meas['measured_at']}.", "",
         "## Measured pilot (real calls)", "",
         f"- Input: `{meas['input_csv']}`, SHA-256 `{meas['input_sha256']}`; {n_rows} rows, "
         f"{meas['unique_texts']} unique nonempty texts.",
         f"- Provider/model: {meas['provider']} `{meas['model']}` (no thinking/effort setting exists for Jev); "
         f"{meas['reviews_per_request']} review per request; {meas['workers']} worker; prompt versions in `pipeline/prompts.py`.",
         f"- Cold run: {rc['enrich']['completed_new']} enriched + {rc['enrich']['cache_copies']} cache copies completed, "
         f"{rc['enrich']['quarantined']} quarantined; {rc['enrich']['requests']} enrich requests, {rc['enrich']['attempts']} attempts, "
         f"{rc['enrich']['failed_attempts']} failed attempts; verify sample {meas['verify_sample']}.",
         f"- Warm run: {rw['enrich']['requests']} new enrich requests (cache hits: {rw['enrich']['skipped_done']} "
         f"originals reused); verify {rw['verify_new_calls']}, group {rw['group_new_calls']}, memo {rw['memo_new_calls']} new calls.",
         "", "| Run | Wall-clock s | Enrich s | Verify s | Group s | Rank s | Memo s | API cost (USD) |",
         "|---|---|---|---|---|---|---|---|"]
    for rid, r, cst in (("cold", rc, c_cost), ("warm", rw, w_cost)):
        st = r["stage_seconds"]
        L.append(f"| {rid} | {r['wall_seconds']} | {st.get('enrich')} | {st.get('verify')} | {st.get('group')} | "
                 f"{st.get('rank')} | {st.get('memo')} | {cst['api_total']} |")
    L += ["", "### Cold-run cost by stage", "", "| Stage | Model | Calls | Failed | Input tokens | Rate (USD/M) | Cost (USD) |",
          "|---|---|---|---|---|---|---|"]
    for st, info in c_cost["stages"].items():
        it = info["items"]["uncached_input"]
        L.append(f"| {st} | {info['model']} | {info['calls']} | {info['failed_calls']} | {it['units'] if it else 0} | "
                 f"{it['price_per_million'] if it else 'n/a'} | {it['cost'] if it else 'unknown'} |")
    per1000 = money(total_cold / Decimal(n_rows) * 1000) if n_rows else 0
    per_rec = money(total_cold / Decimal(max(completed, 1)))
    L += ["", f"- Cold API total: **${c_cost['api_total']}**; per 1,000 input rows ${per1000}; per completed record ${per_rec}.",
          f"- Enrichment throughput (1 worker): {1 / lat if lat else 0:.2f} requests/s; {per_text_tokens:.1f} billed input "
          f"tokens per distinct text; mean {per_enrich_call_tokens:.1f} "
          "billed input tokens per enrich request (" + str(meas["reviews_per_request"]) + " reviews per request).",
          "- Output tokens are billed at $0 by Jev. Local compute (a laptop running Python) is not priced: **unknown, not zero**.",
          "- Rates: " + ", ".join("{} {} ${}/M as of {} ({})".format(k[0], k[1], v["price"], v["as_of"], v["source_url"])
                                  for k, v in rates.items()) + ".",
          "", "## Full-run projection (estimates, not measurements)", ""]
    budget = Decimal(str(a["budget_usd"]))
    L += [f"Budget (editable in `assumptions.json`): **${budget}** total API spend. Max workers {a['max_workers']}; "
          f"fallback fraction {a['fallback_fraction']} (no stronger-model fallback is used); output-token cap: not applicable "
          "(Jev returns fixed-size structured answers, output billed at $0).", "",
          "| Scenario | Distinct texts | Retry rate | Verify | Enrich cost | Other stages | Total | Hours at workers | Over budget? |",
          "|---|---|---|---|---|---|---|---|---|"]
    other_cold = sum(Decimal(info["items"]["uncached_input"]["cost"]) for st, info in c_cost["stages"].items()
                     if st != "enrich" and info["items"].get("uncached_input"))
    vcalls, _, vtin = stage_tokens("verify")
    per_verify = Decimal(vtin) / Decimal(max(vcalls, 1))
    for name, sc in a["scenarios"].items():
        req = Decimal(sc["enrich_requests"]) * (1 + Decimal(str(sc["retry_rate"])))
        enrich_cost = money(req * per_text_tokens * in_rate)
        verify_cost = Decimal(sc["verify_sample"]) * per_verify * in_rate
        other = money(verify_cost + other_cold * Decimal(str(sc.get("downstream_multiplier", 1))))
        total = money(enrich_cost + other)
        lat_text = rc["stage_seconds"]["enrich"] / max(rc["enrich"]["completed_new"] + rc["enrich"]["quarantined"], 1)
        hours = float(req) * lat_text / (a["max_workers"] * sc["worker_efficiency"]) / 3600
        L.append(f"| {name} | {int(req):,} | {sc['retry_rate']} | {sc['verify_sample']} | ${enrich_cost} | ${other} | "
                 f"**${total}** | {hours:.1f} h at {a['max_workers']} | {'**YES: over budget**' if total > budget else 'no'} |")
    L += ["", "Projection method: measured billed tokens per enrich request x projected requests x rate; verify scaled "
          "by sample size; group and memo are fixed overhead counted once (one call per issue, one memo call). "
          "Time assumes enrich latency stays at the pilot value and workers overlap with the stated efficiency; the "
          "provider's rate limits may cap this. No-reuse comparison uses 660,609 requests instead of 484,189.",
          "", "## Controls", "",
          "- Spend: one ledger (`runs/spend_ledger.json`) shared by every run, worker and stage; worst-case cost is reserved "
          "before each dispatch and work stops when spent + reserved + next reservation would pass the cap.",
          "- Retries: HTTP 429/5xx/529 and network errors retried up to 4 times with exponential backoff, jitter and Retry-After; "
          "invalid output retried once, then quarantined with the reason.",
          "- Recovery: results are appended and fsynced in batches; a rerun loads completed IDs and sends only pending work. "
          "Ctrl-C stops dispatch, drains in-flight calls and saves a checkpoint.",
          "", "## Replay", "", "Offline (no key, no calls): `python3 -m cost.pilot report`. Edit `rates.csv` or "
          "`assumptions.json` and rerun to see the effect. Paid pilot: `python3 -m cost.pilot run --csv data/cost_100.csv`.", ""]
    (COST / "report.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("run", help="PAID: real cold and warm pilot")
    r.add_argument("--csv", required=True)
    r.add_argument("--verify-sample", type=int, default=20)
    rep = sub.add_parser("report", help="offline: rebuild report.md from saved files")
    rep.add_argument("--rates", default=str(COST / "rates.csv"))
    rep.add_argument("--assumptions", default=str(COST / "assumptions.json"))
    args = p.parse_args()
    if args.cmd == "run":
        run_pilot(Path(args.csv), args.verify_sample)
    else:
        build_report(Path(getattr(args, "rates", COST / "rates.csv")),
                     Path(getattr(args, "assumptions", COST / "assumptions.json")))


if __name__ == "__main__":
    main()
