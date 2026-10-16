"""Stage 2 - Classify (Jev Choice; code validates every answer).

For each pending review, one Jev call asks four Choice questions about the
review text: topic, intent, severity and sentiment. Code maps the answers to
the grading-contract schema, checks them, and saves the result before moving on.

Rules implemented here:
- one retry on an invalid answer, then the review is quarantined with a reason
- exact-text reuse: a later review with identical text copies the first
  completed record and records cache_source_id (only direct originals)
- resume: reviews already completed under the same label_config are skipped
- spend guard: stops before a call that would pass the budget cap
- every HTTP attempt is logged to calls.jsonl, including failures
"""

import json
import os
import re
from pathlib import Path

from pipeline.jev_client import JevClient, JevError
from pipeline.prepare import canonical

LABEL_CONFIG = "jev-latest+choice-v1+schema-v1"

TOPICS = {
    "access": "Login, signup, password or account access.",
    "usability": "Navigation, controls, layout, queue or playlist management, ad interruptions.",
    "playback": "Playback failure, crashes, lag, connection failures, audio quality, resource use.",
    "downloads": "Downloading, saved music, offline listening, disappearing downloads.",
    "catalog": "Missing songs or artists, search or discovery, recommendations, lyrics availability.",
    "billing": "Price, charges, subscriptions, paywalls, premium entitlement. Premium-only controls go here.",
    "support": "Contacting support and the support response.",
    "other": "General praise or criticism, unrelated content, or no supported specific topic.",
}
INTENTS = {
    "cancellation": "Explicitly leaving, uninstalling, cancelling, or threatening to do so. Takes precedence.",
    "complaint": "A negative experience, including mixed praise and criticism.",
    "request": "A desired change without a reported failure.",
    "praise": "Positive comment without a reported problem.",
    "unclear": "Bare boycott slogans, meaningless text, or no evaluable content.",
}
SEVERITY = {
    "1": "No reported problem: praise, neutral or unclear content, or a pure feature request.",
    "2": "Dislike, generic criticism, minor annoyance, or cosmetic issue; no functional loss.",
    "3": "A degraded or restricted function; some use or a workaround remains.",
    "4": "A clearly blocked core task, such as being unable to log in or play music.",
    "5": "Explicit serious financial, privacy or data harm. An expensive plan, a crash, or angry language alone is not enough.",
}
SENTIMENT = {
    "-1": "Very negative.",
    "-0.5": "Negative.",
    "0": "Neutral or mixed.",
    "0.5": "Positive.",
    "1": "Very positive.",
}

QUESTIONS = {
    "topic": {"type": "choice", "instructions": "Which topic is the main subject of this review?",
              "criteria": TOPICS},
    "intent": {"type": "choice", "instructions": "What is the reviewer's intent? Cancellation takes precedence over complaint, then request, praise, unclear.",
               "criteria": INTENTS},
    "severity": {"type": "choice", "instructions": "How severe is the most serious specific problem in this review? Use the highest supported level.",
                 "criteria": SEVERITY},
    "sentiment": {"type": "choice", "instructions": "What is the overall sentiment of the review text?",
                  "criteria": SENTIMENT},
}
MAX_RETRIES_INVALID = 1
LONG_TEXT_CHARS = 280


def evidence_for(text):
    """Exact substring of the source: the first sentence, or the start of a long text."""
    match = re.search(r"[.!?](\s|$)", text)
    quote = text[: match.end()].rstrip() if match else text
    if len(quote) > LONG_TEXT_CHARS:
        quote = quote[:LONG_TEXT_CHARS].rstrip()
    return quote


def parse_answers(payload, text):
    """Turn a Jev response into the contract fields. Raises ValueError on any invalid answer."""
    answers = payload.get("answers") or {}
    out = {}
    for name, options in (("topic", TOPICS), ("intent", INTENTS), ("severity", SEVERITY), ("sentiment", SENTIMENT)):
        ans = answers.get(name)
        if not isinstance(ans, dict) or ans.get("type") != "choice":
            raise ValueError(f"missing {name} answer")
        choice = ans.get("choice")
        if choice not in options:
            raise ValueError(f"{name} choice not allowed: {choice!r}")
        out[name] = choice
    quote = evidence_for(text)
    if quote not in text:
        raise ValueError("evidence is not an exact substring")
    needs_review = len(text) > LONG_TEXT_CHARS
    return {
        "topic": out["topic"],
        "intent": out["intent"],
        "sentiment": float(out["sentiment"]),
        "severity": int(out["severity"]),
        "entities": [],
        "evidence_quote": quote,
        "needs_review": needs_review,
    }


class SpendGuard:
    """Refuses a call when spent + reserved would pass the cap. Rates come from rates.json."""

    def __init__(self, cap_usd, rates_path):
        rates = json.loads(Path(rates_path).read_text(encoding="utf-8"))
        self.cap = cap_usd
        self.in_rate = rates["input_usd_per_million_tokens"] / 1_000_000
        self.out_rate = rates["output_usd_per_million_tokens"] / 1_000_000
        self.rates_verified = bool(rates.get("verified", False))
        self.spent = 0.0
        self.reserve_in = 1200       # generous upper bound on prompt tokens per call
        self.reserve_out = 300       # matches the output cap we ask for

    def reserve(self):
        return self.reserve_in * self.in_rate + self.reserve_out * self.out_rate

    def can_call(self):
        return self.spent + self.reserve() <= self.cap

    def record(self, usage):
        self.spent += usage.get("input_tokens", 0) * self.in_rate + usage.get("output_tokens", 0) * self.out_rate


def append_line(path, obj):
    with open(path, "a", encoding="utf-8") as f:
        f.write(canonical(obj) + "\n")
        f.flush()
        os.fsync(f.fileno())


def load_completed(results_path):
    done, by_text = set(), {}
    if Path(results_path).exists():
        for line in Path(results_path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") == "completed" and rec.get("label_config") == LABEL_CONFIG:
                done.add(rec["review_id"])
                by_text.setdefault(rec["text_key"], rec)
    return done, by_text


def run(work_dir, source_csv, client, guard, limit=None, log=print):
    """Classify pending reviews. Returns a summary dict. Safe to re-run: it resumes."""
    from pipeline.prepare import iter_rows, text_key

    work = Path(work_dir)
    results_path, calls_path = work / "results.jsonl", work / "calls.jsonl"
    done, by_text = load_completed(results_path)
    pending = [json.loads(line) for line in (work / "pending.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    texts = {}
    for row in iter_rows(source_csv):
        texts[row["review_id"]] = row["review_text"]

    summary = {"completed_new": 0, "reused_cache": 0, "skipped_done": 0, "quarantined": 0, "stopped_by_budget": False}
    processed = 0
    for item in pending:
        rid = item["review_id"]
        if rid in done:
            summary["skipped_done"] += 1
            continue
        if limit is not None and processed >= limit:
            break
        processed += 1
        text = texts[rid]
        key = item["text_key"]

        if key in by_text and by_text[key]["review_id"] != rid:
            src = by_text[key]
            rec = {k: src[k] for k in ("topic", "intent", "sentiment", "severity", "entities",
                                       "evidence_quote", "needs_review", "label_config")}
            rec.update({"review_id": rid, "source_sha256": item["source_sha256"], "status": "completed",
                        "cache_source_id": src["review_id"], "text_key": key})
            append_line(results_path, rec)
            done.add(rid)
            summary["reused_cache"] += 1
            continue

        if not guard.can_call():
            summary["stopped_by_budget"] = True
            log(f"stopped before {rid}: next call would pass the ${guard.cap:.2f} cap")
            break

        record, last_reason = None, None
        for attempt_no in range(MAX_RETRIES_INVALID + 1):
            try:
                payload, attempts = client.choose(text, QUESTIONS)
            except JevError as e:
                for a in getattr(e, "attempts", []):
                    append_line(calls_path, {"review_ids": [rid], "role": "classify", "model": "jev-latest", **a})
                last_reason = f"api_error: {e}"
                break
            usage = payload.get("usage") or {}
            guard.record(usage)
            for a in attempts:
                append_line(calls_path, {"review_ids": [rid], "role": "classify", "model": payload.get("model", "jev-latest"),
                                         "phase": "initial", "label_config": LABEL_CONFIG,
                                         "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                                         **a})
            try:
                fields = parse_answers(payload, text)
                record = fields
                break
            except ValueError as e:
                last_reason = f"invalid_output: {e}"
                log(f"{rid}: {last_reason} (attempt {attempt_no + 1})")

        if record is None:
            append_line(results_path, {"review_id": rid, "source_sha256": item["source_sha256"], "status": "quarantined",
                                       "reason": last_reason, "text_key": key, "label_config": LABEL_CONFIG})
            summary["quarantined"] += 1
            continue

        rec = {"review_id": rid, "source_sha256": item["source_sha256"], "status": "completed",
               "label_config": LABEL_CONFIG, "text_key": key, **record}
        append_line(results_path, rec)
        done.add(rid)
        by_text.setdefault(key, rec)
        summary["completed_new"] += 1

    summary["spent_usd_estimate"] = round(guard.spent, 6)
    summary["rates_verified"] = guard.rates_verified
    return summary
