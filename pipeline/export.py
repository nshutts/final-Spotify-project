"""Build the standardized grading/ folder (GRADING_CONTRACT.md) from a finished run. No model calls.

grading/run.json, ingestion.json (course helper profile), records.jsonl.gz (exactly one final record
per source ID), membership.csv, ranking.csv, claims.csv, calls.jsonl.gz, checkpoint_before.json,
checkpoint_after.json.

Source IDs that never received a final result in this run are exported as quarantined with reason
"not_classified_in_run" so nothing is silently missing; they count as incomplete classifications.
"""

import gzip
import hashlib
import json
import shutil
import sys
from pathlib import Path

from pipeline.common import canonical, read_jsonl, write_json
from pipeline.fake_jev import SIM_MODEL
from pipeline.prepare import FIELDS, iter_rows, row_sha

ROOT = Path(__file__).resolve().parent.parent
RECORD_KEYS = ("review_id", "source_sha256", "status", "topic", "intent", "sentiment", "severity", "entities",
               "evidence_quote", "needs_review", "label_config", "cache_source_id")
CALL_KEYS = ("request_id", "role", "review_ids", "model", "phase", "outcome", "label_config", "input_tokens",
             "output_tokens", "attempt", "http_status", "seconds", "error", "issue_id", "inputs",
             "usage_reported")


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def profile(csv_path):
    sys.path.insert(0, str(ROOT / "tools"))
    import check_submission  # course-provided helper, standard library only
    return check_submission.profile(Path(csv_path))


def build(work_dir, csv_path, out_dir, before, after, allow_simulated=False, log=print):
    work, out = Path(work_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    latest = {}
    for rec in read_jsonl(work / "results.jsonl"):
        latest[rec["review_id"]] = rec
    for rec in read_jsonl(work / "quarantine.jsonl"):
        latest.setdefault(rec["review_id"], rec)
    if not allow_simulated and any(SIM_MODEL in str(r.get("label_config", "")) for r in latest.values()):
        raise SystemExit("Refusing to export: this run contains SIMULATED records (dry run).")

    rows = 0
    counts = {"completed": 0, "quarantined": 0, "not_classified_in_run": 0}
    with gzip.open(out / "records.jsonl.gz", "wt", encoding="utf-8") as f:
        for row in iter_rows(csv_path):
            rows += 1
            rid = row["review_id"]
            rec = latest.get(rid)
            if rec is None:
                rec = {"review_id": rid, "source_sha256": row_sha(row), "status": "quarantined",
                       "reason": "not_classified_in_run"}
                counts["not_classified_in_run"] += 1
            elif rec["status"] == "completed":
                rec = {k: rec[k] for k in RECORD_KEYS if k in rec}
                counts["completed"] += 1
            else:
                rec = {"review_id": rid, "source_sha256": rec["source_sha256"], "status": "quarantined",
                       "reason": rec.get("reason") or "unresolved"}
                counts["quarantined"] += 1
            f.write(canonical(rec) + "\n")

    write_json(out / "run.json", {"version": "a5-audit-v1", "analysis_count": rows,
                                  "analysis_sha256": file_sha(csv_path),
                                  "classification_input_fields": ["review_text"], "allow_multi_issue": False})
    write_json(out / "ingestion.json", profile(csv_path))
    shutil.copy(work / "group" / "membership.csv", out / "membership.csv")
    shutil.copy(work / "rank" / "ranking.csv", out / "ranking.csv")
    shutil.copy(work / "memo" / "claims.csv", out / "claims.csv")
    with gzip.open(out / "calls.jsonl.gz", "wt", encoding="utf-8") as f:
        n_calls = 0
        for c in read_jsonl(work / "calls.jsonl"):
            f.write(canonical({k: c[k] for k in CALL_KEYS if k in c and c[k] is not None}) + "\n")
            n_calls += 1
    for name, src in (("checkpoint_before.json", before), ("checkpoint_after.json", after)):
        data = json.loads(Path(src).read_text(encoding="utf-8"))
        write_json(out / name, {"completed_ids": data["completed_ids"]})
    log(f"export: {rows:,} records ({counts}), {n_calls:,} call-log lines -> {out}")
    return counts
