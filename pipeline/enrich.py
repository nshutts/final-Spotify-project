"""Stage 2 - Enrich (role: enrich). Jev labels each distinct review text; code does the rest.

Model (Jev, one request per distinct text, 4 questions sharing the call):
    topic (choice over the 8 contract topics), intent (choice, 5 intents in precedence order),
    severity (choice over 5 defined levels), sentiment (score over 5 levels; sentiment = score/2 - 1)
Code:
    evidence_quote  complete text if <= 280 characters, else the first sentence (exact substring)
    entities        feature terms found in the text, reported exactly as written there
    needs_review    long text (quote is partial) or low model confidence on topic or intent
    validation      allowed labels, ranges, exact quote membership; one retry on invalid output,
                    then quarantine with the reason and attempt count
    caching         each distinct text is labelled once; other IDs with identical text get a copy
                    with cache_source_id pointing at the direct original (never a chain)
    control         shared spend ledger with reservation before dispatch, bounded workers,
                    graceful stop on Ctrl-C / limit / time cap, resume from saved results
Every HTTP attempt (including failures and retries) is logged to calls.jsonl in the grading format.
"""

import re
import signal
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from pipeline.common import JsonlWriter, log_event, read_jsonl, write_json
from pipeline.jev_client import JevError
from pipeline.prepare import iter_rows
from pipeline.prompts import ENRICH_QUESTIONS, INTENTS, TOPICS, label_config

LONG_TEXT_CHARS = 280
LOW_CONFIDENCE = 0.5      # declared before tuning; top-choice probability below this sets needs_review
MAX_INVALID_RETRIES = 1
SEVERITIES = ("1", "2", "3", "4", "5")
QUESTIONS_CHARS = len(str(ENRICH_QUESTIONS))

# Feature terms (case-insensitive, whole words, simple plural/verb endings). Matched spans are
# reported exactly as they appear in the text, so every entity is supported by the source.
ENTITY_TERMS = ["ad", "ads", "advert", "advertisement", "advertising", "commercial", "download", "offline",
                "playlist", "podcast", "lyrics", "shuffle", "search", "login", "log in", "password",
                "premium", "subscription", "crash", "queue", "radio", "library", "support", "refund",
                "price", "update", "skip", "recommendation", "audiobook", "account", "volume"]
_ENTITY_RE = re.compile(r"\b(" + "|".join(sorted((re.escape(t) for t in ENTITY_TERMS), key=len, reverse=True))
                        + r")(s|es|ed|ing)?\b", re.IGNORECASE)


def evidence_for(text):
    if len(text) <= LONG_TEXT_CHARS:
        return text
    match = re.search(r"[.!?](\s|$)", text)
    quote = text[: match.end()].rstrip() if match else text[:LONG_TEXT_CHARS]
    return quote if quote.strip() else text[:LONG_TEXT_CHARS]


def entities_for(text):
    found, seen = [], set()
    for m in _ENTITY_RE.finditer(text):
        span = m.group(0)
        if span.lower() not in seen:
            seen.add(span.lower())
            found.append(span)
    return found


def parse_answers(payload, text):
    """Map a single-review Jev reply to contract fields. Raises ValueError if invalid or refused."""
    if not isinstance(payload, dict) or payload.get("refusal"):
        raise ValueError("refused or empty response")
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("missing answers")
    return parse_one(answers, text, "")


def parse_one(answers, text, prefix):
    """Validate the four answers for one review (keys prefixed, e.g. 'r3_topic') and map to the schema."""
    def ans(name, kind):
        a = answers.get(prefix + name)
        if not isinstance(a, dict) or a.get("type") != kind:
            raise ValueError(f"missing or wrong-type answer: {name}")
        return a

    topic_a, intent_a, sev_a, sent_a = (ans("topic", "choice"), ans("intent", "choice"),
                                         ans("severity", "choice"), ans("sentiment", "score"))
    topic, intent, severity = topic_a.get("choice"), intent_a.get("choice"), str(sev_a.get("choice"))
    if topic not in TOPICS:
        raise ValueError(f"topic not allowed: {topic!r}")
    if intent not in INTENTS:
        raise ValueError(f"intent not allowed: {intent!r}")
    if severity not in SEVERITIES:
        raise ValueError(f"severity not allowed: {severity!r}")
    score = sent_a.get("score")
    if not isinstance(score, (int, float)) or not 0 <= score <= 4:
        raise ValueError("sentiment score outside 0-4")

    def top_prob(a, choice):
        p = (a.get("probabilities") or {}).get(choice)
        return float(p) if isinstance(p, (int, float)) else None

    p_topic, p_intent = top_prob(topic_a, topic), top_prob(intent_a, intent)
    low_conf = any(p is not None and p < LOW_CONFIDENCE for p in (p_topic, p_intent))
    quote = evidence_for(text)
    if not quote.strip() or quote not in text:
        raise ValueError("evidence quote is not an exact substring")
    return {
        "topic": topic, "intent": intent, "severity": int(severity),
        "sentiment": round(score / 2 - 1, 6),
        "entities": entities_for(text), "evidence_quote": quote,
        "needs_review": bool(low_conf or len(text) > LONG_TEXT_CHARS),
        "p_topic": p_topic, "p_intent": p_intent,
    }


def batch_request(texts_in_order):
    """State and questions for several reviews in one request. Keys r1..rN keep tokens low; each
    question names the review it is about. Returns (state, questions, prefixes)."""
    state, questions, prefixes = {}, {}, []
    for i, text in enumerate(texts_in_order, 1):
        key = f"r{i}"
        state[key] = text
        prefixes.append(key + "_")
        for name, q in ENRICH_QUESTIONS.items():
            qq = dict(q)
            qq["instructions"] = f"Review {key}: {q['instructions']}"
            questions[f"{key}_{name}"] = qq
    return state, questions, prefixes


def reservation_usd(texts_batch, rate):
    """Worst-case cost of one request: generous token estimate (about 2x the pilot measurement)."""
    tokens = 800 + sum(QUESTIONS_CHARS / 2 + 120 + len(t) for t in texts_batch)
    return tokens * rate


class StopFlag:
    """First Ctrl-C: stop dispatching, finish in-flight work and save. Second Ctrl-C: hard stop."""

    def __init__(self):
        self.reason = None
        self._event = threading.Event()

    def set(self, reason):
        if self.reason is None:
            self.reason = reason
        self._event.set()

    def is_set(self):
        return self._event.is_set()

    def install(self, log=print):
        def handler(signum, frame):
            if self.is_set():
                raise KeyboardInterrupt
            log("\nStopping: finishing in-flight requests and saving. Press Ctrl-C again to force.")
            self.set("interrupted")
        try:
            signal.signal(signal.SIGINT, handler)
        except ValueError:      # not in the main thread (tests)
            pass


def load_state(results_path, config):
    """Latest record per review_id. Completed only counts under the same label_config."""
    latest = {}
    for rec in read_jsonl(results_path):
        latest[rec["review_id"]] = rec
    done = {rid for rid, r in latest.items() if r.get("status") == "completed" and r.get("label_config") == config}
    hard_quarantined = {rid for rid, r in latest.items()
                        if r.get("status") == "quarantined" and str(r.get("reason", "")).startswith("invalid_output")
                        and r.get("label_config") == config}
    return latest, done, hard_quarantined


def snapshot(work_dir, name, config=None):
    """Write the completed IDs at this moment (for checkpoint_before / checkpoint_after).

    Counts records completed under `config`, or under the label_config of the latest completed record.
    """
    work = Path(work_dir)
    if config is None:
        for rec in read_jsonl(work / "results.jsonl"):
            if rec.get("status") == "completed":
                config = rec["label_config"]
    _, done, _ = load_state(work / "results.jsonl", config)
    path = work / "checkpoints" / f"{name}.json"
    write_json(path, {"completed_ids": sorted(done), "count": len(done), "label_config": config,
                      "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return path, len(done)


def run(work_dir, source_csv, client, ledger, rate, workers=1, limit=None, max_seconds=None,
        stop=None, log=print, progress_every=30, batch_size=20):
    """Enrich every pending distinct text. Safe to re-run: completed work is never re-sent."""
    work = Path(work_dir)
    config = label_config(client.model)
    results_path, calls_path, runlog = work / "results.jsonl", work / "calls.jsonl", work / "run_log.jsonl"
    latest, done, hard_q = load_state(results_path, config)
    phase = "resume" if done else "initial"
    stop = stop or StopFlag()

    pending = list(read_jsonl(work / "pending.jsonl"))
    by_key, item_by_id = {}, {}
    for item in pending:
        by_key.setdefault(item["text_key"], []).append(item["review_id"])
        item_by_id[item["review_id"]] = item
    texts = {r["review_id"]: r["review_text"] for r in iter_rows(source_csv) if r["review_id"] in item_by_id}

    results = JsonlWriter(results_path)
    calls = JsonlWriter(calls_path, sync_every=200)
    summary = {"phase": phase, "label_config": config, "workers": workers, "batch_size": batch_size, "requests": 0, "attempts": 0,
               "failed_attempts": 0, "completed_new": 0, "cache_copies": 0, "quarantined": 0,
               "invalid_retries": 0, "input_tokens": 0, "output_tokens": 0, "skipped_done": 0,
               "stop_reason": None}

    def write_cache_copies(origin_rec):
        for rid in by_key[origin_rec["text_key"]]:
            if rid == origin_rec["review_id"] or rid in done:
                continue
            copy = {k: origin_rec[k] for k in ("topic", "intent", "sentiment", "severity", "entities",
                                               "evidence_quote", "needs_review", "label_config", "text_key",
                                               "model")}
            copy.update({"review_id": rid, "source_sha256": item_by_id[rid]["source_sha256"],
                         "status": "completed", "cache_source_id": origin_rec["review_id"]})
            results.write(copy)
            done.add(rid)
            summary["cache_copies"] += 1

    # Repair: originals finished before a hard stop but whose duplicates were not yet copied.
    for rid in list(done):
        rec = latest.get(rid)
        if rec and not rec.get("cache_source_id"):
            write_cache_copies(rec)

    # Texts shared by the most reviews go first, so a run stopped by the spend cap covers the most reviews.
    originals = [i["review_id"] for i in pending if i["is_first_of_text"]]
    originals.sort(key=lambda rid: -len(by_key[item_by_id[rid]["text_key"]]))
    units = []
    for rid in originals:
        if rid in done:
            summary["skipped_done"] += 1
        elif rid not in hard_q:
            units.append(rid)

    def single(rid, events):
        """One review alone (used to retry a review whose batch answer was invalid)."""
        text = texts[rid]
        try:
            payload, attempts = client.ask(text, ENRICH_QUESTIONS)
        except JevError as e:
            events.extend({**a, "review_ids": [rid], "input_tokens": 0, "output_tokens": 0} for a in e.attempts)
            return None, f"api_error: {e}", 0
        usage = payload.get("usage") or {}
        tin, tout = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
        events.extend({**a, "review_ids": [rid], "input_tokens": 0, "output_tokens": 0} for a in attempts[:-1])
        last = {**attempts[-1], "review_ids": [rid], "input_tokens": tin, "output_tokens": tout,
                "usage_reported": bool(usage)}
        try:
            rec = parse_answers(payload, text)
            rec["model"] = payload.get("model") or client.model
            events.append(last)
            return rec, None, tin
        except ValueError as e:
            events.append({**last, "outcome": "failed", "error": f"invalid_output: {e}"})
            return None, f"invalid_output: {e}", tin

    def work_batch(rids):
        """Send up to batch_size reviews in one request. Each review is validated on its own; an invalid
        answer is retried once alone, then quarantined. Returns (outcomes, events, billed_tokens)."""
        events, tokens, outcomes = [], 0, {}
        state, questions, prefixes = batch_request([texts[r] for r in rids])
        try:
            payload, attempts = client.ask(state, questions)
        except JevError as e:
            events.extend({**a, "review_ids": list(rids), "input_tokens": 0, "output_tokens": 0} for a in e.attempts)
            return {r: (None, f"api_error: {e}", len(e.attempts)) for r in rids}, events, 0
        usage = payload.get("usage") or {}
        tin, tout = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
        tokens += tin
        events.extend({**a, "review_ids": list(rids), "input_tokens": 0, "output_tokens": 0} for a in attempts[:-1])
        answers = payload.get("answers") if isinstance(payload, dict) else None
        retry = []
        for rid, prefix in zip(rids, prefixes):
            try:
                if not isinstance(answers, dict) or payload.get("refusal"):
                    raise ValueError("refused or missing answers")
                rec = parse_one(answers, texts[rid], prefix)
                rec["model"] = payload.get("model") or client.model
                outcomes[rid] = (rec, None, 1)
            except ValueError as e:
                retry.append((rid, str(e)))
        ok_ids = [r for r in rids if r in outcomes]
        last = {**attempts[-1], "input_tokens": tin, "output_tokens": tout, "usage_reported": bool(usage)}
        if ok_ids:
            events.append({**last, "review_ids": list(rids), "outcome": "succeeded",
                           "invalid_in_batch": [r for r, _ in retry]})
        else:
            events.append({**last, "review_ids": list(rids), "outcome": "failed",
                           "error": "invalid_output for every review in the batch"})
        for rid, why in retry:          # one retry, alone
            rec, reason, t = single(rid, events)
            tokens += t
            outcomes[rid] = (rec, reason, 2) if rec else (None, reason or f"invalid_output: {why}", 2)
        return outcomes, events, tokens

    started = time.time()
    last_progress = started
    log_event(runlog, event="enrich_start", phase=phase, workers=workers, pending_units=len(units),
              already_completed=len(done), cap_usd=ledger.cap, spent_usd=round(ledger.spent, 6))
    log(f"enrich: {len(units)} distinct texts to label, {len(done)} reviews already completed "
        f"(phase={phase}, workers={workers}, cap=${ledger.cap:.2f}, spent so far=${ledger.spent:.4f})")

    batches = [units[i:i + batch_size] for i in range(0, len(units), batch_size)]
    batch_iter = iter(batches)
    inflight = {}
    dispatched = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            while not stop.is_set() and len(inflight) < workers:
                if limit is not None and dispatched >= limit:
                    stop.set("limit_reached")
                    break
                if max_seconds is not None and time.time() - started > max_seconds:
                    stop.set("time_cap_reached")
                    break
                batch = next(batch_iter, None)
                if batch is None:
                    break
                if limit is not None:
                    batch = batch[:max(limit - dispatched, 0)]
                est = reservation_usd([texts[r] for r in batch], rate)
                if not ledger.try_reserve(est):
                    stop.set("spend_cap_reached")
                    log(f"spend cap: next request would pass ${ledger.cap:.2f}; stopping cleanly")
                    break
                inflight[pool.submit(work_batch, batch)] = (batch, est)
                dispatched += len(batch)
            if not inflight:
                break
            finished, _ = wait(list(inflight), return_when=FIRST_COMPLETED, timeout=5)
            for fut in finished:
                batch, est = inflight.pop(fut)
                outcomes, events, tokens = fut.result()
                ledger.settle(est, tokens * rate)
                summary["requests"] += 1
                model_used = next((o[0]["model"] for o in outcomes.values() if o[0]), client.model)
                for ev in events:
                    summary["attempts"] += 1
                    summary["failed_attempts"] += ev["outcome"] == "failed"
                    summary["input_tokens"] += ev["input_tokens"]
                    summary["output_tokens"] += ev["output_tokens"]
                    calls.write({"request_id": ev["request_id"], "role": "enrich", "review_ids": ev["review_ids"],
                                 "model": model_used, "phase": phase, "outcome": ev["outcome"],
                                 "label_config": config, "input_tokens": ev["input_tokens"],
                                 "output_tokens": ev["output_tokens"], "attempt": ev["attempt"],
                                 "http_status": ev.get("status"), "seconds": ev["seconds"],
                                 "error": ev.get("error"), "invalid_in_batch": ev.get("invalid_in_batch") or None,
                                 "usage_reported": ev.get("usage_reported", False)})
                for rid in batch:
                    record, reason, n_attempts = outcomes[rid]
                    item = item_by_id[rid]
                    if n_attempts == 2 and record:
                        summary["invalid_retries"] += 1
                    if record is None:
                        results.write({"review_id": rid, "source_sha256": item["source_sha256"],
                                       "status": "quarantined", "reason": reason, "attempts": n_attempts,
                                       "label_config": config, "text_key": item["text_key"]})
                        summary["quarantined"] += 1
                        continue
                    rec = {"review_id": rid, "source_sha256": item["source_sha256"], "status": "completed",
                           "label_config": config, "text_key": item["text_key"], **record}
                    results.write(rec)
                    done.add(rid)
                    summary["completed_new"] += 1
                    write_cache_copies(rec)
            now = time.time()
            if now - last_progress >= progress_every:
                last_progress = now
                ledger.save()
                rate_s = dispatched / max(now - started, 1e-9)
                left = len(units) - dispatched
                eta_h = left / rate_s / 3600 if rate_s else float("inf")
                msg = (f"  {summary['requests']:,} requests, {len(done):,} reviews done, "
                       f"{rate_s:.1f} texts/s, ${ledger.spent:.4f} spent, ~{eta_h:.1f} h left")
                log(msg)
                log_event(runlog, event="progress", requests=summary["requests"], completed=len(done),
                          texts_per_s=round(rate_s, 3), spent_usd=round(ledger.spent, 6))

    results.close()
    calls.close()
    ledger.save()
    elapsed = time.time() - started
    summary.update({"stop_reason": stop.reason or "finished", "wall_seconds": round(elapsed, 3),
                    "completed_total": len(done), "spent_usd_ledger": round(ledger.spent, 8)})
    log_event(runlog, event="enrich_end", **summary)
    if stop.reason in ("interrupted", "spend_cap_reached", "time_cap_reached", "limit_reached"):
        path, n = snapshot(work, f"stopped_{time.strftime('%Y%m%d_%H%M%S')}", config)
        summary["checkpoint"] = str(path)
        log(f"saved checkpoint with {n:,} completed IDs: {path}")
    return summary
