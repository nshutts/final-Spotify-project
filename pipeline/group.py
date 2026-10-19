"""Stage 4 - Group (code membership; role: group names each issue).

Membership (code, deterministic): every completed complaint or cancellation record belongs to exactly
one issue, the issue of its topic: ISS-<TOPIC>. Praise, requests and unclear records are excluded.
Membership is saved to group/membership.csv so ranking never needs a model.

Naming (Jev, role group): for each issue, a bounded evidence pack of at most 25 member quotes (highest
severity first, then review_id) is sent with a choice over candidate problem names
(prompts.GROUP_CANDIDATES). The chosen name and its probability are saved in group/issues.json with the
review IDs that were sent. Naming is cached by a hash of its inputs, so an unchanged rerun makes no calls.
"""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from pipeline.common import JsonlWriter, read_jsonl, write_json
from pipeline.jev_client import JevError
from pipeline.prompts import GROUP_CANDIDATES, GROUP_VERSION, TOPICS

COUNTED = ("complaint", "cancellation")
PACK_SIZE = 25


def issue_id(topic):
    return f"ISS-{topic.upper()}"


def final_records(work):
    latest = {}
    for rec in read_jsonl(Path(work) / "results.jsonl"):
        latest[rec["review_id"]] = rec
    return latest


def membership(latest):
    members = defaultdict(list)
    for rid, r in latest.items():
        if r.get("status") == "completed" and r.get("intent") in COUNTED:
            members[issue_id(r["topic"])].append(rid)
    return {iid: sorted(ids) for iid, ids in members.items()}


def write_membership(work, members):
    path = Path(work) / "group" / "membership.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["issue_id", "review_id"])
        for iid in sorted(members):
            for rid in members[iid]:
                w.writerow([iid, rid])
    return path


def evidence_pack(latest, ids):
    """Bounded pack: unique quotes, highest severity first, then review_id."""
    seen, pack = set(), []
    for rid in sorted(ids, key=lambda r: (-latest[r]["severity"], r)):
        q = latest[rid]["evidence_quote"]
        if q in seen:
            continue
        seen.add(q)
        pack.append({"review_id": rid, "severity": latest[rid]["severity"], "quote": q[:300]})
        if len(pack) >= PACK_SIZE:
            break
    return pack


def run(work_dir, client, ledger, rate, log=print):
    work = Path(work_dir)
    latest = final_records(work)
    members = membership(latest)
    write_membership(work, members)
    issues_path = work / "group" / "issues.json"
    cached = json.loads(issues_path.read_text(encoding="utf-8")) if issues_path.exists() else {}
    calls = JsonlWriter(work / "calls.jsonl")
    issues, new_calls = {}, 0
    for topic in TOPICS:
        iid = issue_id(topic)
        if iid not in members:
            continue
        pack = evidence_pack(latest, members[iid])
        state = {"issue": iid, "examples": [{"id": p["review_id"], "text": p["quote"]} for p in pack]}
        crit = {name: None for name in GROUP_CANDIDATES[topic]}
        questions = {"name": {"type": "choice",
                              "instructions": "Which name best describes the most common problem in these complaints?",
                              "criteria": crit}}
        key = hashlib.sha256(json.dumps([state, questions, GROUP_VERSION, client.model], sort_keys=True,
                                        ensure_ascii=False).encode()).hexdigest()
        if cached.get(iid, {}).get("input_hash") == key:
            issues[iid] = cached[iid]
            continue
        entry = {"issue_id": iid, "topic": topic, "input_hash": key, "prompt_version": GROUP_VERSION,
                 "evidence_review_ids": [p["review_id"] for p in pack], "name": f"{topic} (unnamed)",
                 "name_probability": None, "member_count": len(members[iid])}
        est = (len(json.dumps(state)) + len(str(questions))) / 2 * rate
        tokens = 0
        if ledger.try_reserve(est):
            try:
                payload, attempts = client.ask(state, questions)
                usage = payload.get("usage") or {}
                tokens = int(usage.get("input_tokens") or 0)
                ans = (payload.get("answers") or {}).get("name") or {}
                ok = ans.get("choice") in crit
                for a in attempts[:-1]:
                    calls.write(_call(a, entry, client.model, 0, 0, "failed"))
                calls.write(_call(attempts[-1], entry, payload.get("model") or client.model, tokens,
                                  int(usage.get("output_tokens") or 0), "succeeded" if ok else "failed"))
                if ok:
                    entry["name"] = ans["choice"]
                    entry["name_probability"] = (ans.get("probabilities") or {}).get(ans["choice"])
                    entry["model"] = payload.get("model") or client.model
                new_calls += 1
            except JevError as e:
                for a in e.attempts:
                    calls.write(_call(a, entry, client.model, 0, 0, "failed"))
            finally:
                ledger.settle(est, tokens * rate)
        issues[iid] = entry
    calls.close()
    ledger.save()
    write_json(issues_path, issues)
    log(f"group: {sum(len(v) for v in members.values()):,} complaint/cancellation reviews in "
        f"{len(members)} issues; {new_calls} naming calls")
    return {"issues": len(members), "memberships": sum(len(v) for v in members.values()), "new_calls": new_calls}


def _call(a, entry, model, tin, tout, outcome):
    return {"request_id": a["request_id"], "role": "group", "review_ids": entry["evidence_review_ids"],
            "model": model, "phase": "group", "outcome": outcome,
            "label_config": f"{model}|{GROUP_VERSION}", "input_tokens": tin, "output_tokens": tout,
            "issue_id": entry["issue_id"], "attempt": a.get("attempt"), "http_status": a.get("status"),
            "seconds": a.get("seconds")}
