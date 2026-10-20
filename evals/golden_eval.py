"""Golden-set evaluation (rules predeclared in docs/EVALUATION_RULES.md). Offline, no model calls.

    python3 evals/golden_eval.py --golden evals/golden_50_labeled.csv --results runs/full/results.jsonl

The model never saw these labels: golden reviews are labelled as ordinary rows of the full run, and
their human labels are read here only, after the run.

Outputs (evals/):
    golden_cases.csv      one row per review: expected vs predicted for every field, pass/fail
    golden_results.json   agreement, severity MAE, sentiment MAE and tolerance share, quote and entity
                          checks, needs_review 2x2, per-topic counts, topic confusion table
    golden_report.md      readable summary with concrete disagreements
A review with no completed prediction counts as wrong on every field (not dropped).
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
TOL = 0.5


def yes(v):
    return str(v).strip().lower() in ("yes", "true", "1", "y")


def load_results(path):
    latest = {}
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                latest[r["review_id"]] = r
    return latest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default="evals/golden_50_labeled.csv")
    ap.add_argument("--results", default="runs/full/results.jsonl")
    ap.add_argument("--out", default="evals")
    a = ap.parse_args()
    out = Path(a.out)
    gold = list(csv.DictReader(open(a.golden, encoding="utf-8", newline="")))
    pred = load_results(a.results)

    cases, agree = [], Counter()
    sev_err, sent_err, sent_within = [], [], 0
    quote_pass = 0
    ent_pred_total = ent_unsupported = ent_missed = ent_gold_total = 0
    nr = Counter()
    wrong_flagged = wrong_total = 0
    confusion = defaultdict(Counter)
    missing = 0
    for g in gold:
        rid, text = g["review_id"], g["review_text"]
        p = pred.get(rid)
        ok = p is not None and p.get("status") == "completed"
        if not ok:
            missing += 1
        gt = {"topic": g["topic"], "intent": g["intent"], "severity": int(g["severity"]),
              "sentiment": float(g["sentiment"]), "needs_review": yes(g["needs_review"]),
              "entities": json.loads(g["entities"] or "[]")}
        row = {"review_id": rid, "review_text": text.replace("\n", " ")[:300], "ambiguous": g.get("ambiguous", ""),
               "status": p.get("status") if p else "missing"}
        for f in ("topic", "intent", "severity", "sentiment", "needs_review"):
            row[f"expected_{f}"] = gt[f]
            row[f"predicted_{f}"] = p.get(f) if ok else ""
        for f in ("topic", "intent", "severity"):
            hit = ok and p[f] == gt[f]
            agree[f] += hit
            row[f"{f}_pass"] = hit
        confusion[gt["topic"]][p["topic"] if ok else "MISSING"] += 1
        if ok:
            sev_err.append(abs(p["severity"] - gt["severity"]))
            d = abs(p["sentiment"] - gt["sentiment"])
            sent_err.append(d)
            sent_within += d <= TOL + 1e-9
            row["sentiment_within_tol"] = d <= TOL + 1e-9
            qp = bool(p["evidence_quote"]) and p["evidence_quote"] in text
            quote_pass += qp
            row["quote_exact_substring"] = qp
            row["predicted_quote"] = p["evidence_quote"][:200]
            row["quote_supports_label"] = ""          # human check, filled by hand
            pe = list(p.get("entities") or [])
            unsup = [e for e in pe if e.lower() not in text.lower()]
            ge_low = [e.lower() for e in gt["entities"]]
            pe_low = [e.lower() for e in pe]
            missed = [e for e in gt["entities"] if not any(e.lower() in x or x in e.lower() for x in pe_low)]
            ent_pred_total += len(pe)
            ent_unsupported += len(unsup)
            ent_gold_total += len(ge_low)
            ent_missed += len(missed)
            row["predicted_entities"] = json.dumps(pe, ensure_ascii=False)
            row["expected_entities"] = json.dumps(gt["entities"], ensure_ascii=False)
            row["unsupported_entities"] = json.dumps(unsup, ensure_ascii=False)
            row["missed_entities"] = json.dumps(missed, ensure_ascii=False)
            nr[(gt["needs_review"], bool(p["needs_review"]))] += 1
            if p["topic"] != gt["topic"] or p["intent"] != gt["intent"]:
                wrong_total += 1
                wrong_flagged += bool(p["needs_review"])
        else:
            sev_err.append(4)          # worst case for a missing prediction
            row["sentiment_within_tol"] = False
            row["quote_exact_substring"] = False
            wrong_total += 1
        cases.append(row)

    n = len(gold)
    tp, fp, fn, tn = nr[(True, True)], nr[(False, True)], nr[(True, False)], nr[(False, False)]
    res = {
        "n": n, "missing_or_quarantined_predictions": missing,
        "ambiguous_cases": sum(yes(g.get("ambiguous")) for g in gold),
        "agreement": {f: round(agree[f] / n, 4) for f in ("topic", "intent", "severity")},
        "agreement_counts": {f: agree[f] for f in ("topic", "intent", "severity")},
        "severity_mae": round(sum(sev_err) / n, 4),
        "sentiment_mae": round(sum(sent_err) / len(sent_err), 4) if sent_err else None,
        "sentiment_within_tolerance": {"tolerance": TOL, "share": round(sent_within / n, 4), "count": sent_within},
        "evidence_quote_exact_substring": {"share": round(quote_pass / n, 4), "count": quote_pass,
                                           "supports_label": "human check: see quote_supports_label in golden_cases.csv"},
        "entities": {"predicted": ent_pred_total, "unsupported_additions": ent_unsupported,
                     "unsupported_rate": round(ent_unsupported / ent_pred_total, 4) if ent_pred_total else 0.0,
                     "human_entities": ent_gold_total, "missed_by_model": ent_missed},
        "needs_review": {"both_yes": tp, "model_yes_human_no": fp, "model_no_human_yes": fn, "both_no": tn,
                         "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                         "recall": round(tp / (tp + fn), 4) if tp + fn else None,
                         "topic_or_intent_errors_flagged": f"{wrong_flagged}/{wrong_total}"},
        "per_topic_expected": dict(Counter(g["topic"] for g in gold)),
        "per_topic_predicted": dict(Counter(pred[g["review_id"]]["topic"] for g in gold
                                            if g["review_id"] in pred and pred[g["review_id"]].get("status") == "completed")),
        "topic_confusion": {t: dict(confusion[t]) for t in TOPICS if t in confusion},
        "note": "50 cases are a small diagnostic sample, not a population accuracy estimate.",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "golden_results.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    fields = list(dict.fromkeys(k for c in cases for k in c))
    with (out / "golden_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(cases)

    L = ["# Golden-set evaluation (50 hand-labelled reviews)", "",
         "Rules were declared before this evaluation ran (docs/EVALUATION_RULES.md). Golden labels were never model inputs.", "",
         f"- Predictions found: {n - missing}/{n} (missing or quarantined count as wrong on every field)",
         f"- Ambiguous cases (marked by the labeller): {res['ambiguous_cases']}",
         f"- Topic agreement: {agree['topic']}/{n} ({res['agreement']['topic']:.0%})",
         f"- Intent agreement: {agree['intent']}/{n} ({res['agreement']['intent']:.0%})",
         f"- Severity exact agreement: {agree['severity']}/{n} ({res['agreement']['severity']:.0%}); MAE {res['severity_mae']}",
         f"- Sentiment MAE {res['sentiment_mae']}; within ±{TOL}: {sent_within}/{n}",
         f"- Evidence quote exact substring (code): {quote_pass}/{n}. Whether each quote supports the label is a human check (column quote_supports_label).",
         f"- Entities: {ent_pred_total} predicted, {ent_unsupported} unsupported additions; {ent_missed} of {ent_gold_total} human entities missed",
         f"- needs_review: both yes {tp}, model yes/human no {fp}, model no/human yes {fn}, both no {tn}; "
         f"precision {res['needs_review']['precision']}, recall {res['needs_review']['recall']}; "
         f"topic/intent errors flagged for review: {wrong_flagged}/{wrong_total}", "",
         "## Topic confusion (rows = human label, columns = model)", "",
         "| human \\ model | " + " | ".join(TOPICS) + " |", "|---" * (len(TOPICS) + 1) + "|"]
    for t in TOPICS:
        if t in confusion:
            L.append(f"| {t} | " + " | ".join(str(confusion[t].get(c, "")) for c in TOPICS) + " |")
    L += ["", "## Disagreements", "", "| review_id | text | field | human | model | ambiguous |", "|---|---|---|---|---|---|"]
    for c in cases:
        for f in ("topic", "intent", "severity"):
            if not c.get(f"{f}_pass"):
                L.append(f"| {c['review_id'][:8]} | {c['review_text'][:70].replace('|', '/')} | {f} | "
                         f"{c[f'expected_{f}']} | {c.get(f'predicted_{f}', '')} | {c['ambiguous']} |")
    (out / "golden_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()
