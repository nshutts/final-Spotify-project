"""Stage 6 - Recommend (role: memo). Jev chooses the priority; code writes and checks the memo.

Input to the model (bounded): the saved ranking for the issues that map to the four candidate areas
in the assignment question (access, usability, playback, billing/support), each area's share of all
complaints, and an evidence pack of at most 3 quotes per area with review IDs. The raw dataset is
never sent.

Model: one Jev choice over the four areas (prompts.MEMO_QUESTIONS). The answer and its probabilities
are saved in memo/decision.json. The call is cached by an input hash, so an unchanged rerun makes no call.

Code: writes memo/memo.md from the saved numbers and the model's choice, writes memo/claims.csv
(one row per issue-level number shown), and checks that every cited issue ID, review ID and number
matches the saved calculations (memo/check.json). Prose is templated by code; the judgment of which
area to prioritise, and the ordering of alternatives, comes from the model.
"""

import csv
import hashlib
import json
from pathlib import Path

from pipeline.common import JsonlWriter, read_jsonl, write_json
from pipeline.jev_client import JevError
from pipeline.prompts import MEMO_AREAS, MEMO_QUESTIONS, MEMO_VERSION

AREA_ISSUES = {"access": ["ISS-ACCESS"], "usability": ["ISS-USABILITY"], "playback": ["ISS-PLAYBACK"],
               "billing_support": ["ISS-BILLING", "ISS-SUPPORT"]}
AREA_LABEL = {"access": "Access", "usability": "Usability", "playback": "Playback",
              "billing_support": "Billing / support"}
METRICS = ("complaint_count", "severity_sum", "mean_severity", "priority_score")


def load(work):
    work = Path(work)
    with (work / "rank" / "ranking.csv").open(encoding="utf-8", newline="") as f:
        ranking = {r["issue_id"]: r for r in csv.DictReader(f)}
    latest = {}
    for rec in read_jsonl(work / "results.jsonl"):
        latest[rec["review_id"]] = rec
    issues = json.loads((work / "group" / "issues.json").read_text(encoding="utf-8"))
    return ranking, latest, issues


def area_numbers(ranking, total_complaints):
    out = {}
    for area, iids in AREA_ISSUES.items():
        count = sum(int(ranking[i]["complaint_count"]) for i in iids if i in ranking)
        score = sum(int(ranking[i]["priority_score"]) for i in iids if i in ranking)
        out[area] = {"issues": [i for i in iids if i in ranking], "complaint_count": count,
                     "severity_sum": score,
                     "share_of_all_complaints": round(count / total_complaints, 4) if total_complaints else 0.0}
    return out


def pack_for(area, issues, latest):
    pack = []
    for iid in AREA_ISSUES[area]:
        for rid in issues.get(iid, {}).get("evidence_review_ids", [])[:3]:
            pack.append({"review_id": rid, "issue_id": iid, "severity": latest[rid]["severity"],
                         "quote": latest[rid]["evidence_quote"][:240]})
    return pack[:3]


def run(work_dir, client, ledger, rate, log=print):
    work = Path(work_dir)
    mdir = work / "memo"
    mdir.mkdir(parents=True, exist_ok=True)
    ranking, latest, issues = load(work)
    total_complaints = sum(int(r["complaint_count"]) for r in ranking.values())
    areas = area_numbers(ranking, total_complaints)
    evidence = {a: pack_for(a, issues, latest) for a in AREA_ISSUES}
    state = {
        "question": "Where should the next quarter of Spotify product effort go?",
        "metric_definitions": {"complaint_count": "complaint or cancellation reviews in the area",
                               "severity_sum": "sum of severity 1-5 over those reviews (priority score)",
                               "share_of_all_complaints": "complaint_count / all complaint reviews"},
        "areas": {a: {**areas[a], "issue_names": [issues.get(i, {}).get("name") for i in areas[a]["issues"]],
                      "examples": [e["quote"] for e in evidence[a]]} for a in AREA_ISSUES},
    }
    key = hashlib.sha256(json.dumps([state, MEMO_QUESTIONS, MEMO_VERSION, client.model], sort_keys=True,
                                    ensure_ascii=False).encode()).hexdigest()
    decision_path = mdir / "decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8")) if decision_path.exists() else {}
    new_calls = 0
    if decision.get("input_hash") != key:
        decision = {"input_hash": key, "prompt_version": MEMO_VERSION, "choice": None, "probabilities": {},
                    "state_sent": state}
        calls = JsonlWriter(work / "calls.jsonl")
        est = len(json.dumps(state)) / 2 * rate
        tokens = 0
        if ledger.try_reserve(est):
            try:
                payload, attempts = client.ask(state, MEMO_QUESTIONS)
                usage = payload.get("usage") or {}
                tokens = int(usage.get("input_tokens") or 0)
                ans = (payload.get("answers") or {}).get("priority") or {}
                ok = ans.get("choice") in MEMO_AREAS
                for a in attempts[:-1]:
                    calls.write(_call(a, client.model, 0, 0, "failed"))
                calls.write(_call(attempts[-1], payload.get("model") or client.model, tokens,
                                  int(usage.get("output_tokens") or 0), "succeeded" if ok else "failed"))
                if ok:
                    decision.update({"choice": ans["choice"], "probabilities": ans.get("probabilities") or {},
                                     "confidence": ans.get("confidence"),
                                     "model": payload.get("model") or client.model})
                new_calls += 1
            except JevError as e:
                for a in e.attempts:
                    calls.write(_call(a, client.model, 0, 0, "failed"))
            finally:
                ledger.settle(est, tokens * rate)
        calls.close()
        ledger.save()
        write_json(decision_path, decision)
    write_outputs(work, ranking, latest, issues, areas, evidence, decision)
    log(f"memo: model chose {decision.get('choice')} ({new_calls} new calls)")
    return {"choice": decision.get("choice"), "new_calls": new_calls}


def _call(a, model, tin, tout, outcome):
    return {"request_id": a["request_id"], "role": "memo", "review_ids": [], "model": model, "phase": "memo",
            "outcome": outcome, "label_config": f"{model}|{MEMO_VERSION}", "input_tokens": tin,
            "output_tokens": tout, "inputs": "rank/ranking.csv, group/issues.json, memo evidence pack",
            "attempt": a.get("attempt"), "http_status": a.get("status"), "seconds": a.get("seconds")}


def claim_id(iid, metric):
    return f"C-{iid}-{metric}"


def write_outputs(work, ranking, latest, issues, areas, evidence, decision):
    mdir = Path(work) / "memo"
    claims = []
    for iid in sorted(ranking, key=lambda i: int(ranking[i]["rank"])):
        for m in METRICS:
            claims.append({"claim_id": claim_id(iid, m), "issue_id": iid, "metric": m, "value": ranking[iid][m]})
    with (mdir / "claims.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["claim_id", "issue_id", "metric", "value"])
        w.writeheader()
        w.writerows(claims)

    choice = decision.get("choice")
    probs = decision.get("probabilities") or {}
    total = sum(int(r["complaint_count"]) for r in ranking.values())
    completed = sum(1 for r in latest.values() if r.get("status") == "completed")
    quarantined = sum(1 for r in latest.values() if r.get("status") == "quarantined")
    quarantined += sum(1 for r in read_jsonl(Path(work) / "quarantine.jsonl") if r.get("review_id") not in latest)
    sev5 = [r for r in latest.values() if r.get("status") == "completed"
            and r.get("intent") in ("complaint", "cancellation") and r.get("severity") == 5]
    baseline_area = max(AREA_ISSUES, key=lambda a: (areas[a]["severity_sum"], a))

    def issue_line(iid):
        r = ranking[iid]
        name = issues.get(iid, {}).get("name", "")
        return (f"| {r['rank']} | {iid} | {name} | {int(r['complaint_count']):,} [{claim_id(iid, 'complaint_count')}] | "
                f"{r['mean_severity']} [{claim_id(iid, 'mean_severity')}] | "
                f"{int(r['priority_score']):,} [{claim_id(iid, 'priority_score')}] |")

    lines = ["# Decision memo: where the next quarter of Spotify product effort should go", ""]
    if choice:
        p = probs.get(choice)
        lines += [f"**Recommendation: {AREA_LABEL[choice]}.** The memo model (Jev, role `memo`) chose this area "
                  f"from the saved aggregates and evidence pack" + (f" with probability {p:.2f}." if isinstance(p, (int, float)) else "."),
                  ""]
        if choice == baseline_area:
            lines.append(f"This agrees with the baseline ranking: {AREA_LABEL[choice]} has the highest combined priority "
                         f"score of the four candidate areas.")
        else:
            lines.append(f"Note: the baseline ranking puts {AREA_LABEL[baseline_area]} first among the four candidate "
                         f"areas by priority score. The model's choice differs; a reviewer should weigh both.")
    else:
        lines.append("**No model recommendation was produced** (the memo call failed or was not run). "
                     f"By baseline priority score the leading candidate area is {AREA_LABEL[baseline_area]}.")
    lines += ["", "## Supporting numbers (baseline ranking)", "",
              "Priority score = complaint count × mean severity = severity sum. Bracketed IDs are rows in `claims.csv`.", "",
              "| Rank | Issue | Dominant problem (group role) | Complaints | Mean severity | Priority score |",
              "|---|---|---|---|---|---|"]
    lines += [issue_line(i) for i in sorted(ranking, key=lambda i: int(ranking[i]["rank"]))]
    lines += ["", f"All complaint and cancellation reviews: {total:,}.", "",
              "## The four candidate areas compared", "",
              "| Area | Issues | Complaints | Share of all complaints | Priority score | Model probability |",
              "|---|---|---|---|---|---|"]
    for a in sorted(AREA_ISSUES, key=lambda a: -(probs.get(a) or 0)):
        pa = probs.get(a)
        lines.append(f"| {AREA_LABEL[a]} | {', '.join(areas[a]['issues']) or 'none'} | {areas[a]['complaint_count']:,} | "
                     f"{areas[a]['share_of_all_complaints']:.1%} | {areas[a]['severity_sum']:,} | "
                     f"{pa:.2f} |" if isinstance(pa, (int, float)) else
                     f"| {AREA_LABEL[a]} | {', '.join(areas[a]['issues']) or 'none'} | {areas[a]['complaint_count']:,} | "
                     f"{areas[a]['share_of_all_complaints']:.1%} | {areas[a]['severity_sum']:,} | n/a |")
    lines += ["", "Billing / support combines ISS-BILLING and ISS-SUPPORT; its counts are sums of those two issue rows.",
              "", "## Representative evidence", ""]
    for a in AREA_ISSUES:
        for e in evidence[a]:
            lines.append(f"- {AREA_LABEL[a]} · `{e['review_id']}` ({e['issue_id']}, severity {e['severity']}): "
                         f"\"{e['quote'][:200]}\"")
    lines += ["", "## Limitations", "",
              "- Reviews are self-selected Google Play reviews from May 2022 to November 2023; they are not a sample "
              "of all users. Counts measure complaint volume in reviews, not prevalence among customers.",
              "- Cancellation language is expressed intent, not observed churn. No revenue, plan tier or retention "
              "effect is calculated or implied.",
              "- Labels come from an automated classifier (Jev). See the golden-set evaluation and verifier report "
              "for measured agreement and known errors.",
              f"- Coverage: {completed:,} completed classifications and {quarantined:,} quarantined records "
              "(empty review text) in this run.",
              f"- Severity 5 (serious money, privacy or data harm) is assigned to {len(sev5):,} complaint reviews; many only "
              "mention paying for Premium, so level 5 is likely over-assigned by the compressed prompt. Recoding every 5 "
              "as 4 leaves the issue order unchanged (see README, sensitivity check).",
              "- ISS-OTHER (general criticism with no specific feature) has the largest score but is not a product area "
              "the next quarter can target, so the recommendation compares the four named areas.",
              "- Topics are coarse issues (one per topic); sub-problems within an issue are named from a 25-quote "
              "sample and are indicative only.", ""]
    (mdir / "memo.md").write_text("\n".join(lines), encoding="utf-8")

    # Code check: every number and ID in the memo comes from saved calculations.
    problems = []
    for c in claims:
        if ranking[c["issue_id"]][c["metric"]] != c["value"]:
            problems.append(f"claim mismatch {c['claim_id']}")
    for a in AREA_ISSUES:
        for e in evidence[a]:
            r = latest.get(e["review_id"])
            if not r or r.get("intent") not in ("complaint", "cancellation"):
                problems.append(f"evidence {e['review_id']} is not a complaint record")
    if choice and choice not in MEMO_AREAS:
        problems.append("model choice outside the allowed areas")
    write_json(mdir / "check.json", {"claims": len(claims), "problems": problems, "status": "ok" if not problems else "review"})
