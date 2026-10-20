"""Load a finished run's processed data and analysis outputs into Supabase. No model calls.

    python3 db/load.py --work runs/full --csv data/spotify_reviews_18months.csv

Needs SUPABASE_URL and SUPABASE_SERVICE_KEY in .env (service-role key: write access, never sent to the
browser or committed). Apply db/schema.sql first. Safe to rerun: rows are upserted by primary key.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.common import read_jsonl  # noqa: E402
from pipeline.prepare import iter_rows, row_sha  # noqa: E402

BATCH = 5000


class Supabase:
    def __init__(self, url, key):
        self.base = url.rstrip("/") + "/rest/v1/"
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                        "Prefer": "resolution=merge-duplicates,return=minimal"}

    def upsert(self, table, rows):
        keys = list(dict.fromkeys(k for r in rows for k in r))      # PostgREST needs identical keys per batch
        rows = [{k: r.get(k) for k in keys} for r in rows]
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            body = json.dumps(chunk, ensure_ascii=False).encode("utf-8")
            for attempt in range(5):
                try:
                    req = urllib.request.Request(self.base + table, data=body, method="POST", headers=self.headers)
                    with urllib.request.urlopen(req, timeout=120):
                        break
                except urllib.error.HTTPError as e:
                    detail = e.read().decode("utf-8", "replace")[:300]
                    if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                        time.sleep(2 ** attempt)
                        continue
                    sys.exit(f"Supabase {table} HTTP {e.code}: {detail}")
                except (urllib.error.URLError, TimeoutError) as e:
                    if attempt < 4:
                        time.sleep(2 ** attempt)
                        continue
                    sys.exit(f"Supabase network error: {e}")
            if len(rows) > BATCH:
                print(f"  {table}: {min(i + BATCH, len(rows)):,}/{len(rows):,}", end="\r", flush=True)
        print(f"  {table}: {len(rows):,} rows" + " " * 20)


def build(work, csv_path):
    work = Path(work)
    latest = {}
    for r in read_jsonl(work / "results.jsonl"):
        latest[r["review_id"]] = r
    for r in read_jsonl(work / "quarantine.jsonl"):
        latest.setdefault(r["review_id"], r)
    issues = json.loads((work / "group" / "issues.json").read_text(encoding="utf-8"))
    with (work / "rank" / "ranking.csv").open(encoding="utf-8", newline="") as f:
        ranking = list(csv.DictReader(f))
    with (work / "memo" / "claims.csv").open(encoding="utf-8", newline="") as f:
        claims = list(csv.DictReader(f))
    member = {}
    with (work / "group" / "membership.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            member[r["review_id"]] = r["issue_id"]

    reviews, months = [], defaultdict(Counter)
    counts = Counter()
    intents, topics, sev, cache = Counter(), Counter(), Counter(), 0
    for row in iter_rows(csv_path):
        rid = row["review_id"]
        r = latest.get(rid)
        month = row["review_timestamp"][:7]
        months[month]["ALL"] += 1
        base = {"review_id": rid, "review_rating": int(row["review_rating"]) if row["review_rating"].isdigit() else None,
                "review_timestamp": row["review_timestamp"]}
        if r is None:
            counts["not_classified"] += 1
            reviews.append({**base, "source_sha256": row_sha(row), "status": "quarantined",
                            "reason": "not_classified_in_run"})
            continue
        if r["status"] != "completed":
            counts["quarantined"] += 1
            reviews.append({**base, "source_sha256": r["source_sha256"], "status": "quarantined",
                            "reason": r.get("reason")})
            continue
        counts["completed"] += 1
        cache += bool(r.get("cache_source_id"))
        intents[r["intent"]] += 1
        topics[r["topic"]] += 1
        iid = member.get(rid)
        if iid:
            sev[r["severity"]] += 1
            months[month][iid] += 1
            months[month]["COMPLAINTS"] += 1
        reviews.append({**base, "source_sha256": r["source_sha256"], "status": "completed", "topic": r["topic"],
                        "intent": r["intent"], "severity": r["severity"], "sentiment": r["sentiment"],
                        "needs_review": r["needs_review"], "evidence_quote": r["evidence_quote"],
                        "cache_source_id": r.get("cache_source_id"), "issue_id": iid})

    issue_rows = [{"issue_id": r["issue_id"], "rank": int(r["rank"]), "name": issues.get(r["issue_id"], {}).get("name"),
                   "complaint_count": int(r["complaint_count"]), "severity_sum": int(r["severity_sum"]),
                   "mean_severity": r["mean_severity"], "priority_score": int(r["priority_score"])} for r in ranking]
    evidence = []
    for iid, info in issues.items():
        for rid in info.get("evidence_review_ids", []):
            rr = latest[rid]
            evidence.append({"issue_id": iid, "review_id": rid, "severity": rr["severity"],
                             "quote": rr["evidence_quote"][:300]})
    monthly = []
    for m, c in sorted(months.items()):
        for iid, n in c.items():
            if iid != "ALL":
                monthly.append({"month": m, "issue_id": iid, "complaints": n, "reviews": c["ALL"]})

    def jload(p, default=None):
        p = work / p
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    run_log = list(read_jsonl(work / "run_log.jsonl"))
    enrich_ends = [e for e in run_log if e.get("event") == "enrich_end"]
    ledger = jload("../spend_ledger.json", {}) or {}
    golden = None
    gpath = ROOT / "evals" / "golden_results.json"
    if gpath.exists():
        golden = json.loads(gpath.read_text(encoding="utf-8"))
    decision = jload("memo/decision.json", {}) or {}
    decision.pop("state_sent", None)
    overall = {
        "source_rows": len(reviews), "completed": counts["completed"], "quarantined": counts["quarantined"],
        "not_classified": counts["not_classified"], "cache_copies": cache,
        "distinct_texts_labelled": counts["completed"] - cache,
        "complaints": sum(int(r["complaint_count"]) for r in ranking),
        "intents": dict(intents), "topics": dict(topics), "complaint_severity": {str(k): v for k, v in sorted(sev.items())},
        "needs_review": sum(1 for r in reviews if r.get("needs_review")),
        "model": "jev-1.13.0", "label_config": next((e["label_config"] for e in enrich_ends), None),
        "enrich_requests": sum(e["requests"] for e in enrich_ends),
        "enrich_failed_attempts": sum(e["failed_attempts"] for e in enrich_ends),
        "enrich_wall_seconds": round(sum(e["wall_seconds"] for e in enrich_ends), 1),
        "enrich_sessions": [{"phase": e["phase"], "stop_reason": e["stop_reason"], "completed_new": e["completed_new"],
                             "requests": e["requests"], "time": e["time"]} for e in enrich_ends],
        "total_api_spend_usd_all_runs": ledger.get("spent_usd"), "spend_cap_usd": ledger.get("cap_usd"),
        "loaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    metrics = [{"key": "overall", "value": overall},
               {"key": "memo_decision", "value": decision},
               {"key": "memo_markdown", "value": {"text": (work / "memo" / "memo.md").read_text(encoding="utf-8")}},
               {"key": "verify", "value": jload("verify/report.json", {})},
               {"key": "golden", "value": golden or {"status": "not yet run"}}]
    return {"reviews": reviews, "issues": issue_rows, "claims": claims, "evidence": evidence,
            "monthly": monthly, "metrics": metrics}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="runs/full")
    ap.add_argument("--csv", default="data/spotify_reviews_18months.csv")
    ap.add_argument("--skip-reviews", action="store_true", help="reload only the small tables")
    a = ap.parse_args()
    import config  # loads .env
    url, key = os.getenv("SUPABASE_URL", "").strip(), os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env first.")
    data = build(a.work, a.csv)
    db = Supabase(url, key)
    for table in ("metrics", "issues", "claims", "evidence", "monthly"):
        db.upsert(table, data[table])
    if not a.skip_reviews:
        db.upsert("reviews", data["reviews"])
    print("Loaded. Dashboard data is live.")


if __name__ == "__main__":
    main()
