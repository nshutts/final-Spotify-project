"""Compare two pilot label sets on the same reviews (development data only, never the golden set).

    python3 tools/compare_pilots.py cost/pilot_v3/pilot_records.jsonl cost/pilot_records.jsonl
"""
import json
import sys
from collections import Counter

a = {r["review_id"]: r for r in map(json.loads, open(sys.argv[1], encoding="utf-8")) if r["status"] == "completed"}
b = {r["review_id"]: r for r in map(json.loads, open(sys.argv[2], encoding="utf-8")) if r["status"] == "completed"}
ids = sorted(set(a) & set(b))
print(f"{len(ids)} reviews in both")
for f in ("topic", "intent", "severity"):
    same = sum(a[i][f] == b[i][f] for i in ids)
    print(f"{f}: {same}/{len(ids)} agree ({same / len(ids):.0%})")
mae = sum(abs(a[i]["sentiment"] - b[i]["sentiment"]) for i in ids) / len(ids)
print(f"sentiment mean absolute difference: {mae:.3f}")
print("topic changes:", Counter((a[i]["topic"], b[i]["topic"]) for i in ids if a[i]["topic"] != b[i]["topic"]).most_common(8))
print("intent changes:", Counter((a[i]["intent"], b[i]["intent"]) for i in ids if a[i]["intent"] != b[i]["intent"]).most_common(8))
