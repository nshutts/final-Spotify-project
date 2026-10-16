"""Stage 2 - Classify (Jev; code validates and maps every answer).

One Jev request per distinct review text. Several questions share the call:
- topic      Choice over the 8 contract topics (includes other)
- intent     Choice over complaint, request, praise, unclear
- cancel     Noul: one yes/no proposition, explicit cancellation intent (probability 0-1)
- severity   Choice over five defined labels 1-5
- sentiment  Score over five defined ordered levels; sentiment = score / 2 - 1

Intent precedence (contract): cancellation (from Noul) > complaint > request > praise > unclear.
The Noul probability is a signal, not a guarantee: values between CANCEL_LOW and
CANCEL_HIGH are routed to needs_review. Thresholds are set on development examples
and recorded in the label config.

Evidence: a short review's complete original text is its quote; longer reviews use
their first sentence and are flagged needs_review. Entities: explicit feature terms
matched in code from ENTITY_TERMS.

Rules: one retry on an invalid or refused answer, then quarantine with reason;
exact-text reuse copies only from a direct completed original; resume skips work
already completed under the same label_config; the spend guard stops before a call
that would pass the cap; every HTTP attempt is logged.
"""

import json
import os
import re
from pathlib import Path

from pipeline.jev_client import JevError
from pipeline.prepare import canonical, iter_rows

SCHEMA_TAG = "choice+noul+score+schema-v2"
CANCEL_LOW, CANCEL_HIGH = 0.3, 0.7   # Noul thresholds; tune on development examples only

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
    "complaint": "A negative experience, including mixed praise and criticism. Use only if not cancellation.",
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
# Ordered from lowest (index 0) to highest (index 4). sentiment = score / 2 - 1.
SENTIMENT_LEVELS = [
    "Very negative: strong dislike or anger about the app or its service.",
    "Negative: clear dissatisfaction without strong anger.",
    "Neutral or mixed: no clear overall feeling, or positive and negative balance out.",
    "Positive: clear satisfaction without strong enthusiasm.",
    "Very positive: strong enthusiasm or praise.",
]
CANCEL_PROPOSITION = ("The reviewer explicitly says they are leaving Spotify, uninstalling it, cancelling "
                      "their subscription, or threatening to do so.")

# Explicit feature terms matched in code (word boundaries, case-insensitive). Entities = matched terms.
ENTITY_TERMS = ["download", "offline", "playlist", "podcast", "lyrics", "shuffle", "search", "login",
                "password", "premium", "subscription", "ads", "crash", "playback", "queue", "radio",
                "library", "support", "refund", "price", "album", "artist", "song"]

MAX_RETRIES_INVALID = 1
LONG_TEXT_CHARS = 280
REFUSED_STATES = {"refused", "incomplete", "content_filter"}


def build_questions():
    return {
        "topic": {"type": "choice", "instructions": "Which topic is the main subject of this review?",
                  "criteria": TOPICS},
        "intent": {"type": "choice",
                   "instructions": "What is the reviewer's intent? Use complaint for any negative experience.",
                   "criteria": INTENTS},
        "cancel": {"type": "noul", "instructions": CANCEL_PROPOSITION,
                   "criteria": {"true": "The reviewer is leaving, cancelling, uninstalling, or threatening to.",
                                "false": "The reviewer is not expressing intent to leave."}},
        "severity": {"type": "choice",
                     "instructions": "How severe is the most serious specific problem? Use the highest supported level.",
                     "criteria": SEVERITY},
        "sentiment": {"type": "score", "instructions": "How positive or negative is the overall sentiment of the review text?",
                      "criteria": SENTIMENT_LEVELS},
    }


def evidence_for(text):
    """Complete text for short reviews; first sentence (exact substring) for long ones."""
    if len(text) <= LONG_TEXT_CHARS:
        return text
    match = re.search(r"[.!?](\s|$)", text)
    return text[: match.end()].rstrip() if match else text[:LONG_TEXT_CHARS]


def entities_for(text):
    found = []
    lowered = text.lower()
    for term in ENTITY_TERMS:
        if re.search(r"\b" + re.escape(term) + r"(s|es|ed|ing)?\b", lowered) and term not in found:
            found.append(term)
    return found


def parse_answers(payload, text):
    """Map a Jev response to contract fields. Raises ValueError on any invalid or refused answer."""
    if payload.get("refusal") or payload.get("status") in REFUSED_STATES:
        raise ValueError("refused_or_incomplete response")
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("missing answers")

    def get(name, kind):
        ans = answers.get(name)
        if not isinstance(ans, dict) or ans.get("type") != kind:
            raise ValueError(f"missing or wrong-type {name} answer")
        return ans

    topic = get("topic", "choice")["choice"]
    if topic not in TOPICS:
        raise ValueError(f"topic not allowed: {topic!r}")
    intent = get("intent", "choice")["choice"]
    if intent not in INTENTS:
        raise ValueError(f"intent not allowed: {intent!r}")
    severity = get("severity", "choice")["choice"]
    if severity not in SEVERITY:
        raise ValueError(f"severity not allowed: {severity!r}")
    p_cancel = get("cancel", "noul")["noul"]
    if not isinstance(p_cancel, (int, float)) or not 0 <= p_cancel <= 1:
        raise ValueError("noul probability out of range")
    score = get("sentiment", "score")["score"]
    if not isinstance(score, (int, float)) or not 0 <= score <= 4:
        raise ValueError("score out of range 0-4")

    quote = evidence_for(text)
    if quote not in text:
        raise ValueError("evidence is not an exact substring")

    if p_cancel >= CANCEL_HIGH:
        final_intent, review = "cancellation", False
    else:
        final_intent = intent
        review = CANCEL_LOW < p_cancel < CANCEL_HIGH
    return {
        "topic": topic,
        "intent": final_intent,
        "sentiment": round(score / 2 - 1, 6),
        "severity": int(severity),
        "entities": entities_for(text),
        "evidence_quote": quote,
        "needs_review": review or len(text) > LONG_TEXT_CHARS,
        "cancel_probability": p_cancel,
        "model_version": payload.get("model"),
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
        self.reserve_in = 1200   # generous upper bound on prompt tokens per call
        self.reserve_out = 300   # output cap requested per call

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


def load_completed(results_path, label_config):
    done, by_text = set(), {}
    if Path(results_path).exists():
        for line in Path(results_path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") == "completed" and rec.get("label_config") == label_config:
                done.add(rec["review_id"])
                by_text.setdefault(rec["text_key"], rec)
    return done, by_text


def run(work_dir, source_csv, client, guard, limit=None, log=print):
    """Classify pending reviews. Safe to re-run: it resumes. Returns a summary dict."""
    from pipeline.prepare import text_key  # noqa: F401  (kept for callers that verify keys)

    work = Path(work_dir)
    results_path, calls_path = work / "results.jsonl", work / "calls.jsonl"
    questions = build_questions()

    # The label config pins the model version the provider reports. It is learned from the
    # first successful response, then fixed for the rest of the run and for resumes.
    label_config = None
    if results_path.exists():
        for line in results_path.read_text(encoding="utf-8").splitlines():
            if line.strip() and json.loads(line).get("status") == "completed":
                label_config = json.loads(line)["label_config"]
                break
    done, by_text = load_completed(results_path, label_config) if label_config else (set(), {})

    pending = [json.loads(line) for line in (work / "pending.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    texts = {row["review_id"]: row["review_text"] for row in iter_rows(source_csv)}

    summary = {"completed_new": 0, "reused_cache": 0, "skipped_done": 0, "quarantined": 0,
               "stopped_by_budget": False}
    processed = 0
    for item in pending:
        rid, key = item["review_id"], item["text_key"]
        if rid in done:
            summary["skipped_done"] += 1
            continue
        if key in by_text and by_text[key]["review_id"] != rid:
            src = by_text[key]
            rec = {k: src[k] for k in ("topic", "intent", "sentiment", "severity", "entities",
                                       "evidence_quote", "needs_review", "label_config",
                                       "cancel_probability", "model_version")}
            rec.update({"review_id": rid, "source_sha256": item["source_sha256"], "status": "completed",
                        "cache_source_id": src["review_id"], "text_key": key})
            append_line(results_path, rec)
            done.add(rid)
            summary["reused_cache"] += 1
            continue
        if limit is not None and processed >= limit:
            break
        if not guard.can_call():
            summary["stopped_by_budget"] = True
            log(f"stopped before {rid}: next call would pass the ${guard.cap:.2f} cap")
            break
        processed += 1
        text = texts[rid]

        record, last_reason = None, None
        for attempt_no in range(MAX_RETRIES_INVALID + 1):
            try:
                payload, attempts = client.choose(text, questions)
            except JevError as e:
                for a in getattr(e, "attempts", []):
                    append_line(calls_path, {"review_ids": [rid], "role": "classify", "model": "jev-latest",
                                             "phase": "initial", **a})
                last_reason = f"api_error: {e}"
                break
            usage = payload.get("usage") or {}
            guard.record(usage)
            for a in attempts:
                append_line(calls_path, {"review_ids": [rid], "role": "classify",
                                         "model": payload.get("model", "jev-latest"), "phase": "initial",
                                         "input_tokens": usage.get("input_tokens"),
                                         "output_tokens": usage.get("output_tokens"), **a})
            try:
                record = parse_answers(payload, text)
                break
            except ValueError as e:
                last_reason = f"invalid_output: {e}"
                log(f"{rid}: {last_reason} (attempt {attempt_no + 1})")

        if record is None:
            append_line(results_path, {"review_id": rid, "source_sha256": item["source_sha256"],
                                       "status": "quarantined", "reason": last_reason,
                                       "text_key": key, "attempts": MAX_RETRIES_INVALID + 1})
            summary["quarantined"] += 1
            continue

        if label_config is None:
            label_config = f"{record['model_version']}|{SCHEMA_TAG}"
            done, by_text = set(), {}
        rec = {"review_id": rid, "source_sha256": item["source_sha256"], "status": "completed",
               "label_config": label_config, "text_key": key, **record}
        append_line(results_path, rec)
        done.add(rid)
        by_text.setdefault(key, rec)
        summary["completed_new"] += 1

    summary["label_config"] = label_config
    summary["spent_usd_estimate"] = round(guard.spent, 6)
    summary["rates_verified"] = guard.rates_verified
    return summary
