"""Stage 1 - Prepare (code only, no model calls).

Reads every row of the input CSV, keeps the original review_id, computes the
source row hash used by the grading contract, quarantines empty review texts,
and writes the pending-work queue. Exact-duplicate texts are grouped so each
distinct text is classified once (cache provenance is recorded later).

Outputs (in the work directory):
    pending.jsonl       one line per nonempty review still needing classification
    quarantine.jsonl    one line per empty review, reason empty_review_text
    dedupe.jsonl        one line per distinct nonempty text: first review_id and all IDs
    ingestion.json      counts for the run; compare with the checker's profile
"""

import csv
import hashlib
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

FIELDS = ("review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def row_sha(row):
    """SHA-256 of the six original fields, exactly as the grading contract defines it."""
    return hashlib.sha256(canonical([row[k] for k in FIELDS]).encode("utf-8")).hexdigest()


def text_key(text):
    """Exact-text key for deduplication. No trimming or normalization: only identical text matches."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_rows(path):
    # Same parsing rules as the checker: UTF-8 with optional BOM, multiline quoted fields kept intact.
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Missing or duplicate CSV headers")
        missing = [k for k in FIELDS if k not in reader.fieldnames]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Malformed CSV row")
            yield row


def prepare(csv_path, work_dir):
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    seen_ids = set()
    texts = OrderedDict()  # text_key -> {"first_review_id", "review_ids"}

    with (work / "pending.jsonl").open("w", encoding="utf-8") as pending, \
         (work / "quarantine.jsonl").open("w", encoding="utf-8") as quarantine:
        for row in iter_rows(csv_path):
            counts["rows"] += 1
            rid = row["review_id"]
            if rid in seen_ids:
                raise ValueError(f"Duplicate review_id in source: {rid}")
            seen_ids.add(rid)
            sha = row_sha(row)
            text = row["review_text"]
            if text.strip() == "":
                counts["empty_review_text"] += 1
                quarantine.write(canonical({
                    "review_id": rid, "source_sha256": sha, "status": "quarantined",
                    "reason": "empty_review_text", "attempts": 0,
                }) + "\n")
                continue
            counts["nonempty"] += 1
            key = text_key(text)
            if key not in texts:
                texts[key] = {"first_review_id": rid, "review_ids": []}
            else:
                counts["exact_duplicate_rows"] += 1
            texts[key]["review_ids"].append(rid)
            pending.write(canonical({
                "review_id": rid, "source_sha256": sha, "text_key": key,
                "is_first_of_text": texts[key]["first_review_id"] == rid,
            }) + "\n")

    with (work / "dedupe.jsonl").open("w", encoding="utf-8") as f:
        for key, info in texts.items():
            f.write(canonical({"text_key": key, **info}) + "\n")

    report = {
        "rows": counts["rows"],
        "nonempty_rows": counts["nonempty"],
        "empty_review_text": counts["empty_review_text"],
        "distinct_nonempty_texts": len(texts),
        "exact_duplicate_rows": counts["exact_duplicate_rows"],
    }
    (work / "ingestion.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python3 pipeline/prepare.py INPUT.csv WORK_DIR")
    print(json.dumps(prepare(sys.argv[1], sys.argv[2]), indent=2))
