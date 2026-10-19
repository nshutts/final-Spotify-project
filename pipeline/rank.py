"""Stage 5 - Rank (code only, no model calls). Rerunnable from saved outputs at any time.

Inputs:  results.jsonl (final record per review) and group/membership.csv.
Baseline (GRADING_CONTRACT.md):
    complaint_count = member count;  severity_sum = sum of member severities
    mean_severity   = severity_sum / complaint_count, six decimals, ROUND_HALF_UP
    priority_score  = severity_sum   (exactly count x mean, no rounding loss)
    order: priority_score descending, then issue_id ascending; ranks start at 1
Only issues with at least one member are ranked.
Output: rank/ranking.csv
"""

import csv
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pipeline.common import read_jsonl

COUNTED = ("complaint", "cancellation")
COLUMNS = ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]


def mean_string(total, count):
    value = (Decimal(total) / Decimal(count)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return f"{value:.6f}"


def compute(latest, membership_rows):
    sev = defaultdict(list)
    seen = set()
    for iid, rid in membership_rows:
        if (iid, rid) in seen:
            raise ValueError(f"duplicate membership {(iid, rid)}")
        seen.add((iid, rid))
        rec = latest.get(rid)
        if not rec or rec.get("status") != "completed" or rec.get("intent") not in COUNTED:
            raise ValueError(f"membership {rid} is not a completed complaint/cancellation")
        sev[iid].append(int(rec["severity"]))
    rows = [{"issue_id": iid, "complaint_count": len(v), "severity_sum": sum(v),
             "mean_severity": mean_string(sum(v), len(v)), "priority_score": sum(v)} for iid, v in sev.items()]
    rows.sort(key=lambda r: (-r["priority_score"], r["issue_id"]))
    for n, r in enumerate(rows, 1):
        r["rank"] = n
    return rows


def read_membership(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return [(r["issue_id"], r["review_id"]) for r in csv.DictReader(f)]


def run(work_dir, log=print):
    work = Path(work_dir)
    latest = {}
    for rec in read_jsonl(work / "results.jsonl"):
        latest[rec["review_id"]] = rec
    rows = compute(latest, read_membership(work / "group" / "membership.csv"))
    out = work / "rank" / "ranking.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in COLUMNS})
    for r in rows[:3]:
        log(f"rank {r['rank']}: {r['issue_id']} count={r['complaint_count']:,} mean={r['mean_severity']} "
            f"score={r['priority_score']:,}")
    return rows
