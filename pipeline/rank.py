"""Stages 4 and 5 - Group and Rank (code only, no model calls).

Baseline grouping: one issue per topic. Only completed complaint or cancellation
records count. Each such review belongs to exactly one issue (its topic), so the
membership has no duplicate (issue_id, review_id) pairs.

Baseline ranking (GRADING_CONTRACT.md):
    complaint_count = number of member reviews
    severity_sum    = sum of member severities
    mean_severity   = severity_sum / complaint_count, six decimals, ROUND_HALF_UP
    priority_score  = severity_sum (exactly count x mean)
    sort: descending priority_score, then ascending issue_id; ranks start at 1

Outputs: membership.csv, ranking.csv, claims.csv (one row per issue metric).
"""

import csv
import json
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pipeline.classify import TOPICS

COUNTED_INTENTS = ("complaint", "cancellation")
METRICS = ("complaint_count", "severity_sum", "mean_severity", "priority_score")


def mean_string(total, count):
    value = (Decimal(total) / Decimal(count)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return f"{value:.6f}"


def build(records):
    """records: iterable of dicts. Returns (membership, issues). Raises on contract violations."""
    members = defaultdict(list)   # issue_id -> [(review_id, severity)]
    seen_pairs = set()
    for rec in records:
        if rec.get("status") != "completed" or rec.get("intent") not in COUNTED_INTENTS:
            continue
        issue_id = rec["topic"]
        if issue_id not in TOPICS:
            raise ValueError(f"unknown topic on {rec['review_id']}: {issue_id}")
        pair = (issue_id, rec["review_id"])
        if pair in seen_pairs:
            raise ValueError(f"duplicate membership {pair}")
        seen_pairs.add(pair)
        members[issue_id].append((rec["review_id"], int(rec["severity"])))

    membership = [(i, rid) for i in sorted(members) for rid, _ in sorted(members[i])]
    issues = {}
    for issue_id in TOPICS:
        rows = members.get(issue_id, [])
        count = len(rows)
        total = sum(sev for _, sev in rows)
        issues[issue_id] = {
            "complaint_count": count,
            "severity_sum": total,
            "mean_severity": mean_string(total, count) if count else "0.000000",
            "priority_score": total,
        }
    return membership, issues


def ranking_rows(issues):
    ordered = sorted(issues.items(), key=lambda kv: (-kv[1]["priority_score"], kv[0]))
    return [{"rank": n, "issue_id": iid, **vals} for n, (iid, vals) in enumerate(ordered, 1)]


def claims_rows(issues):
    rows = []
    for iid in TOPICS:
        for metric in METRICS:
            rows.append({"claim_id": f"C-{iid}-{metric}", "issue_id": iid, "metric": metric,
                         "value": str(issues[iid][metric])})
    return rows


def write_outputs(records_path, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = [json.loads(l) for l in Path(records_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    membership, issues = build(records)
    with (out / "membership.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["issue_id", "review_id"])
        w.writerows(membership)
    rank = ranking_rows(issues)
    with (out / "ranking.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rank", "issue_id", "complaint_count", "severity_sum",
                                          "mean_severity", "priority_score"])
        w.writeheader()
        for r in rank:
            w.writerow({k: r[k] for k in w.fieldnames})
    with (out / "claims.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["claim_id", "issue_id", "metric", "value"])
        w.writeheader()
        w.writerows(claims_rows(issues))
    return {"memberships": len(membership), "issues": len(issues), "ranking": rank}
