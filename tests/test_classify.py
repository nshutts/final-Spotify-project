"""Offline tests for stage 2. No network, no API key, no spending.

Run:  python3 -m unittest discover -s tests -v
"""

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.classify import SpendGuard, entities_for, evidence_for, parse_answers, run
from pipeline.jev_client import JevError
from pipeline.prepare import prepare


def good_payload(topic="downloads", intent="complaint", severity="4", score=1.0, noul=0.05,
                 model="jev-1.13.0"):
    return {
        "model": model,
        "answers": {
            "topic": {"type": "choice", "choice": topic, "probabilities": {}, "confidence": 0.9},
            "intent": {"type": "choice", "choice": intent, "probabilities": {}, "confidence": 0.9},
            "cancel": {"type": "noul", "noul": noul},
            "severity": {"type": "choice", "choice": severity, "probabilities": {}, "confidence": 0.9},
            "sentiment": {"type": "score", "score": score, "confidence": 0.8,
                          "probabilities": {}, "legend": {}},
        },
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


class FakeClient:
    """Returns scripted payloads in order (default: a good answer); counts calls."""

    def __init__(self, script=()):
        self.script = list(script)
        self.calls = 0

    def choose(self, state, questions):
        self.calls += 1
        item = self.script.pop(0) if self.script else good_payload()
        if isinstance(item, Exception):
            raise item
        return item, [{"attempt": 1, "outcome": "succeeded", "status": 200}]


def api_error():
    e = JevError("down", status=503, retryable=True)
    e.attempts = [{"attempt": 1, "outcome": "failed", "status": 503}]
    return e


def make_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp"])
        for rid, text in rows:
            w.writerow([rid, text, "1", "0", "1.0", "2023-01-01 00:00:00"])


class ParseTests(unittest.TestCase):
    TEXT = "Downloaded songs stop playing when I go offline."

    def test_valid_answer_maps_to_schema(self):
        out = parse_answers(good_payload(score=3.0), self.TEXT)
        self.assertEqual(out["topic"], "downloads")
        self.assertEqual(out["intent"], "complaint")
        self.assertEqual(out["severity"], 4)
        self.assertEqual(out["sentiment"], 0.5)          # score 3.0 -> 3.0 / 2 - 1
        self.assertEqual(out["evidence_quote"], self.TEXT)  # short review: full text is the quote
        self.assertEqual(out["entities"], ["download", "offline", "song"])
        self.assertFalse(out["needs_review"])

    def test_sentiment_mapping_covers_all_five_levels(self):
        expected = {0.0: -1.0, 1.0: -0.5, 2.0: 0.0, 3.0: 0.5, 4.0: 1.0}
        for score, sentiment in expected.items():
            self.assertEqual(parse_answers(good_payload(score=score), self.TEXT)["sentiment"], sentiment)

    def test_noul_above_high_threshold_is_cancellation_and_takes_precedence(self):
        out = parse_answers(good_payload(intent="complaint", noul=0.9), self.TEXT)
        self.assertEqual(out["intent"], "cancellation")
        self.assertFalse(out["needs_review"])

    def test_noul_in_uncertain_band_routes_to_review(self):
        out = parse_answers(good_payload(intent="complaint", noul=0.5), self.TEXT)
        self.assertEqual(out["intent"], "complaint")
        self.assertTrue(out["needs_review"])

    def test_rejects_topic_outside_allowed_list(self):
        with self.assertRaises(ValueError):
            parse_answers(good_payload(topic="pricing"), self.TEXT)

    def test_rejects_severity_outside_range(self):
        with self.assertRaises(ValueError):
            parse_answers(good_payload(severity="9"), self.TEXT)

    def test_rejects_score_outside_range(self):
        with self.assertRaises(ValueError):
            parse_answers(good_payload(score=5.0), self.TEXT)

    def test_rejects_noul_outside_probability_range(self):
        with self.assertRaises(ValueError):
            parse_answers(good_payload(noul=1.4), self.TEXT)

    def test_rejects_missing_or_wrong_type_answer(self):
        payload = good_payload()
        payload["answers"]["cancel"] = {"type": "choice", "choice": "yes"}
        with self.assertRaises(ValueError):
            parse_answers(payload, self.TEXT)

    def test_refused_or_incomplete_response_is_rejected(self):
        payload = good_payload()
        payload["status"] = "refused"
        with self.assertRaises(ValueError):
            parse_answers(payload, self.TEXT)

    def test_long_text_uses_first_sentence_and_is_flagged(self):
        text = "Bad. " * 80
        out = parse_answers(good_payload(), text)
        self.assertTrue(out["needs_review"])
        self.assertIn(out["evidence_quote"], text)
        self.assertEqual(out["evidence_quote"], "Bad.")

    def test_entities_are_explicit_terms_only(self):
        self.assertEqual(entities_for("Love the new podcast feature"), ["podcast"])
        self.assertEqual(entities_for("Nothing specific here"), [])


class RunTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.csv = self.dir / "in.csv"
        make_csv(self.csv, [
            ("r1", "Downloaded songs stop playing when I go offline."),
            ("r2", "Love the app."),
            ("r3", "Downloaded songs stop playing when I go offline."),  # exact duplicate of r1
            ("r4", ""),                                                   # empty -> quarantined in stage 1
            ("r5", "Login keeps failing for me."),
        ])
        self.work = self.dir / "work"
        prepare(self.csv, self.work)
        self.rates = self.dir / "rates.json"
        self.rates.write_text(json.dumps({"input_usd_per_million_tokens": 1.0,
                                          "output_usd_per_million_tokens": 5.0, "verified": True}))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def results(self):
        return [json.loads(l) for l in (self.work / "results.jsonl").read_text().splitlines() if l.strip()]

    def guard(self, cap=10.0):
        return SpendGuard(cap, self.rates)

    def test_completes_each_distinct_text_once_and_reuses_duplicates(self):
        client = FakeClient()
        summary = run(self.work, self.csv, client, self.guard(), log=lambda *_: None)
        recs = {r["review_id"]: r for r in self.results()}
        self.assertEqual(summary["completed_new"], 3)     # r1, r2, r5
        self.assertEqual(summary["reused_cache"], 1)      # r3 reuses r1
        self.assertEqual(client.calls, 3)                 # no paid call for r3
        self.assertEqual(recs["r3"]["cache_source_id"], "r1")
        self.assertNotEqual(recs["r3"]["source_sha256"], recs["r1"]["source_sha256"])
        self.assertEqual(recs["r1"]["label_config"], "jev-1.13.0|choice+noul+score+schema-v2")

    def test_invalid_output_is_retried_once_then_succeeds(self):
        client = FakeClient([{"answers": {}}, good_payload()])
        summary = run(self.work, self.csv, client, self.guard(), log=lambda *_: None)
        self.assertEqual(summary["quarantined"], 0)
        self.assertEqual(client.calls, 4)  # r1 took 2 calls; r2 and r5 one each

    def test_invalid_twice_is_quarantined_with_reason(self):
        client = FakeClient([{"answers": {}}, {"answers": {}}])
        summary = run(self.work, self.csv, client, self.guard(), log=lambda *_: None)
        self.assertEqual(summary["quarantined"], 1)
        bad = [r for r in self.results() if r["status"] == "quarantined"]
        self.assertTrue(bad[0]["reason"].startswith("invalid_output"))

    def test_api_error_is_quarantined_and_logged(self):
        client = FakeClient()
        client.choose = lambda s, q: (_ for _ in ()).throw(api_error())
        summary = run(self.work, self.csv, client, self.guard(), log=lambda *_: None)
        # r1, r2 and r5 fail; r3 has no completed original to reuse, so it fails too.
        self.assertEqual(summary["quarantined"], 4)
        calls = [json.loads(l) for l in (self.work / "calls.jsonl").read_text().splitlines()]
        self.assertTrue(all(c["outcome"] == "failed" for c in calls))

    def test_resume_after_interruption_makes_no_new_calls_for_done_ids(self):
        run(self.work, self.csv, FakeClient(), self.guard(), limit=1, log=lambda *_: None)
        client2 = FakeClient()
        summary = run(self.work, self.csv, client2, self.guard(), log=lambda *_: None)
        self.assertEqual(client2.calls, 2)            # only r2 and r5 are new
        self.assertGreaterEqual(summary["skipped_done"], 1)
        done = [r["review_id"] for r in self.results() if r["status"] == "completed"]
        self.assertEqual(len(done), len(set(done)))   # no duplicate completed rows

    def test_budget_stops_before_a_call_that_would_pass_cap(self):
        client = FakeClient()
        summary = run(self.work, self.csv, client, SpendGuard(0.0001, self.rates), log=lambda *_: None)
        self.assertTrue(summary["stopped_by_budget"])
        self.assertEqual(client.calls, 0)

    def test_unverified_rates_are_reported(self):
        self.rates.write_text(json.dumps({"input_usd_per_million_tokens": 1.0,
                                          "output_usd_per_million_tokens": 5.0, "verified": False}))
        summary = run(self.work, self.csv, FakeClient(), SpendGuard(10, self.rates), log=lambda *_: None)
        self.assertFalse(summary["rates_verified"])


if __name__ == "__main__":
    unittest.main()
