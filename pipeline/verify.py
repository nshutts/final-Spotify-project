"""Stage 3 - Verify (role: verify). Independent re-labelling of a declared random sample.

The verifier receives only the original review text and its own differently worded questions
(prompts.VERIFY_QUESTIONS). It never sees the enrich answer. Code then compares the two labels.

Sample: completed *original* records (not cache copies), drawn with a fixed seed. Size is declared
on the command line (default 1,000 for the full run, 20 for the pilot).

Planted-error test: a separate test copy of the enrich predictions has one deliberately wrong topic
written in. The same comparison must flag that record. The copy is marked synthetic and is never used
in business aggregates.

Outputs (in the work folder):
    verify/verifier_predictions.jsonl   one line per sampled review: verifier labels
    verify/disagreements.csv            every field where enrich and verifier differ
    verify/report.json                  agreement rates, counts, planted-error outcome
"""

import csv
import random
from collections import Counter
from pathlib import Path

from pipeline.common import JsonlWriter, read_jsonl, write_json
from pipeline.jev_client import JevError
from pipeline.prepare import iter_rows
from pipeline.prompts import INTENTS, TOPICS, VERIFY_QUESTIONS, VERIFY_VERSION

FIELDS = ("topic", "intent", "severity")
SEED = 20261019


def parse_verifier(payload):
    answers = (payload or {}).get("answers") or {}
    out = {}
    for name, allowed in (("topic", TOPICS), ("intent", INTENTS), ("severity", ("1", "2", "3", "4", "5"))):
        a = answers.get(name)
        if not isinstance(a, dict) or str(a.get("choice")) not in allowed:
            raise ValueError(f"invalid verifier answer: {name}")
        out[name] = int(a["choice"]) if name == "severity" else a["choice"]
    return out


def sample_ids(latest_records, n, seed=SEED):
    originals = sorted(rid for rid, r in latest_records.items()
                       if r.get("status") == "completed" and not r.get("cache_source_id"))
    rng = random.Random(seed)
    return sorted(rng.sample(originals, min(n, len(originals))))


def compare(enriched, verified):
    """Field-by-field comparison. Returns (per-field agreement counts, list of disagreements)."""
    agree, rows = Counter(), []
    for rid, v in verified.items():
        e = enriched[rid]
        for f in FIELDS:
            if e[f] == v[f]:
                agree[f] += 1
            else:
                rows.append({"review_id": rid, "field": f, "enrich": e[f], "verifier": v[f]})
        if all(e[f] == v[f] for f in FIELDS):
            agree["all_three"] += 1
    return agree, rows


def run(work_dir, source_csv, client, ledger, rate, n=1000, log=print):
    work = Path(work_dir)
    vdir = work / "verify"
    vdir.mkdir(parents=True, exist_ok=True)
    latest = {}
    for rec in read_jsonl(work / "results.jsonl"):
        latest[rec["review_id"]] = rec
    ids = sample_ids(latest, n)
    texts = {r["review_id"]: r["review_text"] for r in iter_rows(source_csv) if r["review_id"] in set(ids)}

    preds_path = vdir / "verifier_predictions.jsonl"
    already = {p["review_id"]: p for p in read_jsonl(preds_path) if p.get("prompt_version") == VERIFY_VERSION}
    preds = JsonlWriter(preds_path)
    calls = JsonlWriter(work / "calls.jsonl")
    spent_calls = 0
    for rid in ids:
        if rid in already:
            continue
        est = (len(str(VERIFY_QUESTIONS)) + 4 * len(texts[rid])) / 2 * rate
        if not ledger.try_reserve(est):
            log("verify: spend cap reached; stopping the sample early")
            break
        tokens = 0
        try:
            payload, attempts = client.ask(texts[rid], VERIFY_QUESTIONS)
            usage = payload.get("usage") or {}
            tokens = int(usage.get("input_tokens") or 0)
            for a in attempts[:-1]:
                calls.write(_call(a, rid, client.model, 0, 0, "failed"))
            try:
                v = parse_verifier(payload)
                outcome = "succeeded"
            except ValueError as e:
                v, outcome = None, "failed"
                log(f"verify: {rid}: {e}")
            calls.write(_call(attempts[-1], rid, payload.get("model") or client.model, tokens,
                              int(usage.get("output_tokens") or 0), outcome))
            if v:
                rec = {"review_id": rid, "prompt_version": VERIFY_VERSION,
                       "model": payload.get("model") or client.model, **v}
                preds.write(rec)
                already[rid] = rec
            spent_calls += 1
        except JevError as e:
            for a in e.attempts:
                calls.write(_call(a, rid, client.model, 0, 0, "failed"))
        finally:
            ledger.settle(est, tokens * rate)
    preds.close()
    calls.close()
    ledger.save()
    return report(work, ids, already, log=log, new_calls=spent_calls)


def _call(a, rid, model, tin, tout, outcome):
    return {"request_id": a["request_id"], "role": "verify", "review_ids": [rid], "model": model,
            "phase": "verify", "outcome": outcome, "label_config": f"{model}|{VERIFY_VERSION}",
            "input_tokens": tin, "output_tokens": tout, "attempt": a.get("attempt"),
            "http_status": a.get("status"), "seconds": a.get("seconds")}


def report(work, ids, verified, log=print, new_calls=0):
    work = Path(work)
    latest = {}
    for rec in read_jsonl(work / "results.jsonl"):
        latest[rec["review_id"]] = rec
    verified = {rid: v for rid, v in verified.items() if rid in latest and latest[rid].get("status") == "completed"}
    enriched = {rid: latest[rid] for rid in verified}
    agree, rows = compare(enriched, verified)
    n = len(verified)

    with (work / "verify" / "disagreements.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["review_id", "field", "enrich", "verifier"])
        w.writeheader()
        w.writerows(rows)

    # Planted-error test on a separate synthetic copy: flip one record's topic, re-run the comparison.
    planted = {"status": "not_run"}
    agreeing = [rid for rid in sorted(verified) if enriched[rid]["topic"] == verified[rid]["topic"]]
    if agreeing:
        target = agreeing[0]
        wrong = next(t for t in TOPICS if t != enriched[target]["topic"])
        test_copy = {rid: dict(r) for rid, r in enriched.items()}
        test_copy[target]["topic"] = wrong
        _, test_rows = compare(test_copy, verified)
        caught = any(r["review_id"] == target and r["field"] == "topic" for r in test_rows)
        planted = {"status": "caught" if caught else "missed", "synthetic": True, "review_id": target,
                   "true_enrich_topic": enriched[target]["topic"], "planted_topic": wrong,
                   "note": "Test copy only; the planted label is never written to results or aggregates."}

    rep = {"prompt_version": VERIFY_VERSION, "seed": SEED, "declared_sample_size": len(ids),
           "verified": n, "new_calls_this_run": new_calls,
           "agreement": {f: round(agree[f] / n, 4) if n else None for f in (*FIELDS, "all_three")},
           "agreement_counts": {f: agree[f] for f in (*FIELDS, "all_three")},
           "disagreement_rows": len(rows), "planted_error_test": planted}
    write_json(work / "verify" / "report.json", rep)
    log(f"verify: {n} sampled reviews; agreement topic {rep['agreement']['topic']}, intent "
        f"{rep['agreement']['intent']}, severity {rep['agreement']['severity']}; planted error {planted['status']}")
    return rep
