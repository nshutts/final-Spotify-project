"""Build the run manifest, ingestion report, quarantine log, aggregates and reproducibility check
from the saved export. Offline: no key, no model calls.

    python3 tools/build_reports.py --csv data/spotify_reviews_18months.csv

Writes outputs/full/{data_manifest.json, ingestion_report.json, quarantine.jsonl, aggregates.csv}
and evals/reproducibility.json.
"""

import argparse
import csv
import gzip
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import prompts  # noqa: E402
from pipeline.prepare import iter_rows, text_key  # noqa: E402
from pipeline.rank import COLUMNS, compute, mean_string  # noqa: E402

OUT = ROOT / "outputs" / "full"
G = ROOT / "grading"
EXPECTED = {"rows": 660622, "empty_review_text": 13, "missing_app_version": 159701, "duplicate_review_ids": 0,
            "distinct_nonempty_texts": 484189, "file_bytes": 97400616,
            "file_sha256": "1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6"}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def records():
    with gzip.open(G / "records.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "data" / "spotify_reviews_18months.csv"))
    a = ap.parse_args()
    csv_path = Path(a.csv)

    # Ingestion report: full-file profile, checked against the brief's stated facts.
    ids, dup, empty, missing_ver, texts = set(), 0, 0, 0, set()
    ratings, months, ts_missing = Counter(), Counter(), 0
    for row in iter_rows(csv_path):
        rid = row["review_id"]
        dup += rid in ids
        ids.add(rid)
        if not row["review_text"].strip():
            empty += 1
        else:
            texts.add(text_key(row["review_text"]))
        missing_ver += not row["app_version"].strip()
        ratings[row["review_rating"]] += 1
        if row["review_timestamp"]:
            months[row["review_timestamp"][:7]] += 1
        else:
            ts_missing += 1
    observed = {"rows": len(ids) + dup, "empty_review_text": empty, "missing_app_version": missing_ver,
                "duplicate_review_ids": dup, "distinct_nonempty_texts": len(texts),
                "file_bytes": csv_path.stat().st_size, "file_sha256": sha(csv_path)}
    checks = {k: {"expected": EXPECTED[k], "observed": observed[k], "match": EXPECTED[k] == observed[k]}
              for k in EXPECTED}
    ingestion = {
        "source": "spotify_reviews_18months.csv (course extract of BwandoWando, 3.4 Million Spotify Google Store "
                  "Reviews v2, CC0)",
        "checks_against_brief": checks, "all_checks_pass": all(c["match"] for c in checks.values()),
        "reviews_by_rating": dict(sorted(ratings.items())), "reviews_by_month": dict(sorted(months.items())),
        "missing_timestamps": ts_missing,
        "exact_duplicate_rows": observed["rows"] - empty - observed["distinct_nonempty_texts"],
        "quarantine_rule": "empty or whitespace-only review_text -> quarantined, reason empty_review_text; "
                           "missing app_version does not prevent classification",
        "course_profile": json.loads((G / "ingestion.json").read_text(encoding="utf-8")),
        "note": "First (2022-05) and last (2023-11) months are partial.",
    }
    (OUT / "ingestion_report.json").write_text(json.dumps(ingestion, indent=2) + "\n", encoding="utf-8")

    # Quarantine log and status counts from the final export.
    latest = {}
    status = Counter()
    with (OUT / "quarantine.jsonl").open("w", encoding="utf-8") as q:
        for r in records():
            status[r["status"]] += 1
            if r["status"] == "quarantined":
                q.write(json.dumps({"review_id": r["review_id"], "source_sha256": r["source_sha256"],
                                    "status": r["status"], "reason": r["reason"], "attempts": 0}) + "\n")
            else:
                latest[r["review_id"]] = r

    # Aggregates: per issue (baseline) and per candidate area, plus intent and topic totals.
    members = []
    with (G / "membership.csv").open(encoding="utf-8", newline="") as f:
        members = [(r["issue_id"], r["review_id"]) for r in csv.DictReader(f)]
    ranking = compute(latest, members)
    names = json.loads((OUT / "group" / "issues.json").read_text(encoding="utf-8"))
    sev_dist = defaultdict(Counter)
    for iid, rid in members:
        sev_dist[iid][latest[rid]["severity"]] += 1
    total = sum(r["complaint_count"] for r in ranking)
    with (OUT / "aggregates.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["level", "id", "name", "complaint_count", "severity_sum", "mean_severity", "priority_score",
                    "share_of_complaints", "sev1", "sev2", "sev3", "sev4", "sev5"])
        for r in ranking:
            d = sev_dist[r["issue_id"]]
            w.writerow(["issue", r["issue_id"], names.get(r["issue_id"], {}).get("name", ""), r["complaint_count"],
                        r["severity_sum"], r["mean_severity"], r["priority_score"],
                        f"{r['complaint_count'] / total:.6f}", *[d[i] for i in range(1, 6)]])
        by = {r["issue_id"]: r for r in ranking}
        for area, iids in (("access", ["ISS-ACCESS"]), ("usability", ["ISS-USABILITY"]),
                           ("playback", ["ISS-PLAYBACK"]), ("billing_support", ["ISS-BILLING", "ISS-SUPPORT"])):
            c = sum(by[i]["complaint_count"] for i in iids if i in by)
            s = sum(by[i]["severity_sum"] for i in iids if i in by)
            d = Counter()
            for i in iids:
                d.update(sev_dist[i])
            w.writerow(["area", area, "+".join(iids), c, s, mean_string(s, c), s, f"{c / total:.6f}",
                        *[d[i] for i in range(1, 6)]])

    # Reproducibility: ranking regenerated from saved records + membership equals the saved ranking.
    with (G / "ranking.csv").open(encoding="utf-8", newline="") as f:
        saved = [{k: r[k] for k in COLUMNS} for r in csv.DictReader(f)]
    regen = [{k: str(r[k]) for k in COLUMNS} for r in ranking]
    ranking_again = [{k: str(r[k]) for k in COLUMNS} for r in compute(latest, members)]
    repro = {"ranking_regenerated_equals_saved": regen == saved, "two_regenerations_identical": regen == ranking_again,
             "issues": len(regen), "memberships": len(members),
             "method": "pipeline.rank.compute over grading/records.jsonl.gz and grading/membership.csv; no model call",
             "course_checker": json.loads((ROOT / "outputs" / "self-check.json").read_text())["status"]}
    (ROOT / "evals" / "reproducibility.json").write_text(json.dumps(repro, indent=2) + "\n", encoding="utf-8")

    # Run manifest tying source, code, prompts, model, settings and outputs together.
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = None
    summary = json.loads((OUT / "run_summary.json").read_text(encoding="utf-8"))
    out_files = ["grading/run.json", "grading/ingestion.json", "grading/records.jsonl.gz", "grading/membership.csv",
                 "grading/ranking.csv", "grading/claims.csv", "grading/calls.jsonl.gz", "grading/checkpoint_before.json",
                 "grading/checkpoint_after.json", "outputs/full/group/issues.json", "outputs/full/memo/memo.md",
                 "outputs/full/memo/decision.json", "outputs/full/verify/report.json", "outputs/full/aggregates.csv",
                 "outputs/full/quarantine.jsonl"]
    manifest = {
        "run_id": summary["run_id"], "source_file": "spotify_reviews_18months.csv", "source_sha256": observed["file_sha256"],
        "source_bytes": observed["file_bytes"], "code_commit_at_manifest_build": commit,
        "provider": "TypeSafe Jev", "model": "jev-1.13.0", "reasoning_or_effort_setting": "none exists for Jev",
        "label_config": summary["label_config"],
        "prompt_versions": {"enrich": prompts.ENRICH_VERSION, "verify": prompts.VERIFY_VERSION,
                            "group": prompts.GROUP_VERSION, "memo": prompts.MEMO_VERSION, "schema": prompts.SCHEMA_VERSION},
        "settings": {"reviews_per_enrich_request": 20, "workers": 4, "max_http_retries": 4, "max_invalid_output_retries": 1,
                     "verify_sample": 1000, "verify_seed": 20261019, "group_evidence_pack": 25, "memo_evidence_per_area": 3,
                     "spend_cap_usd": 10.0, "downstream_reserve_usd": 0.10, "fallback_model": None},
        "status_counts": dict(status), "exact_text_cache_copies": summary["exact_text_cache_copies"],
        "api_spend_usd_all_runs": summary["api_spend_usd_all_runs_ledger"],
        "outputs_sha256": {p: sha(ROOT / p) for p in out_files},
    }
    (OUT / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ingestion_checks_pass": ingestion["all_checks_pass"], "status": dict(status), **repro}, indent=1))


if __name__ == "__main__":
    main()
