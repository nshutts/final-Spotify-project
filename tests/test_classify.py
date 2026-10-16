"""Offline tests for stage 2. No network, no API key, no spending.

Run:  python3 -m unittest discover -s tests -v
"""

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline import classify
from pipeline.classify import LABEL_CONFIG, SpendGuard, parse_answers, run
from pipeline.jev_client import JevError
from pipeline.prepare import prepare

ROOT = Path(__file__).resolve().parent.parent


def good_payload(topic="downloads", intent="complaint", severity="4", sentiment="-0.5"):
    return {
        "model": "jev-test",
        "answers": {
            "topic": {"type": "choice", "choice": topic, "probabilities": {}, "confidence": 0.9},
            "intent": {"type": "choice", "choice": intent, "probabilities": {}, "confidence": 0.9},
            "severity": {"type": "choice", "choice": severity, "probabilities": {}, "confidence": 0.9},
            "sentiment": {"type": "choice", "choice": sentiment, "probabilities": {}, "confidence": 0.9},
        },
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


class FakeClient:
    """Returns scripted payloads in order; records how many calls were made."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def choose(self, state, questions):
        self.calls += 1
        item = self.script.pop(0) if self.script else good_payload()
        if isinstance(item, Exception):
            e = JevError("boom", status=500, retryable=True)
            e.attempts = [{"attempt": 1, "outcome": "failed", "status": 500}]
            raise e
        attempts = [{"attempt": 1, "outcome": "succeeded", "status": 200}]
        return item, attempts


def make_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp"])
        for rid, text in rows:
            w.writerow([rid, text, "1", "0", "1.0", "2023-01-01 00:00:00"])


class ParseTests(unittest.TestCase):
    def test_valid_answer_maps_to_schema(self):
        out = parse_answers(good_payload(), "Downloaded songs stop playing when I go offline.")
        self.assertEqual(out["topic"], "downloads")
        self.assertEqual(out["intent"], "complaint")
        self.assertEqual(out["severity"], 4)
        self.assertEqual(out["sentiment"], -0.5)
        self.assertEqual(out["evidence_quote"], "Downloaded songs stop playing when I go offline.")
        self.assertFalse(out["needs_review"])

    def test_rejects_topic_outside_allowed_list(self):
        with self.assertRaises(ValueError):
            parse_answers(good_payload(topic="pricing"), "text")

    def test_rejects_severity_outside_range(self):
        with self.assertRaises(ValueError):
            parse_answers(good_payload(severity="9"), "text")

    def test_rejects_missing_answer(self):
        payload = good_payload()
        del payload["answers"]["intent"]
        with self.assertRaises(ValueError):
            parse_answers(payload, "text")

    def test_long_text_is_flagged_for_review(self):
        text = "Bad. " * 80
        out = parse_answers(good_payload(), text)
        self.assertTrue(out["needs_review"])
        self.assertIn(out["evidence_quote"], text)


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
        client = FakeClient([])
        summary = run(self.work, self.csv, client, self.guard(), log=lambda *_: None)
        recs = {r["review_id"]: r for r in self.results()}
        self.assertEqual(summary["completed_new"], 3)     # r1, r2, r5
        self.assertEqual(summary["reused_cache"], 1)      # r3 reuses r1
        self.assertEqual(client.calls, 3)                 # no paid call for r3
        self.assertEqual(recs["r3"]["cache_source_id"], "r1")
        self.assertEqual(recs["r3"]["label_config"], LABEL_CONFIG)
        # Each review keeps its own source hash, even when its text is reused.
        self.assertNotEqual(recs["r3"]["source_sha256"], recs["r1"]["source_sha256"])

    def test_invalid_output_is_retried_once_then_succeeds(self):
        client = FakeClient([{"answers": {}}, good_payload()])
        summary = run(self.work, self.csv, client, self.guard(), log=lambda *_: None)
        self.assertEqual(summary["quarantined"], 0)
        self.assertEqual(client.calls, 4)  # r1 took 2 calls, then r2 and r5

    def test_invalid_twice_is_quarantined_with_reason(self):
        client = FakeClient([{"answers": {}}, {"answers": {}}])
        summary = run(self.work, self.csv, client, self.guard(), log=lambda *_: None)
        self.assertEqual(summary["quarantined"], 1)
        bad = [r for r in self.results() if r["status"] == "quarantined"]
        self.assertTrue(bad and bad[0]["reason"].startswith("invalid_output"))

    def test_api_error_is_quarantined_and_logged(self):
        client = FakeClient([])
        client.choose = lambda s, q: (_ for _ in ()).throw(_api_error())
        summary = run(self.work, self.csv, client, self.guard(), log=lambda *_: None)
        # Every distinct text fails: r1, r2, r3 (no completed original to reuse) and r5.
        self.assertEqual(summary["quarantined"], 4)
        calls = [json.loads(l) for l in (self.work / "calls.jsonl").read_text().splitlines()]
        self.assertTrue(all(c["outcome"] == "failed" for c in calls))

    def test_resume_after_interruption_makes_no_new_calls_for_done_ids(self):
        client = FakeClient([])
        run(self.work, self.csv, client, self.guard(), limit=1, log=lambda *_: None)
        first_calls = client.calls
        self.assertEqual(first_calls, 1)
        client2 = FakeClient([])
        summary = run(self.work, self.csv, client2, self.guard(), log=lambda *_: None)
        self.assertEqual(client2.calls, 2)            # only the two not yet done
        self.assertGreaterEqual(summary["skipped_done"], 1)
        done = [r["review_id"] for r in self.results() if r["status"] == "completed"]
        self.assertEqual(len(done), len(set(done)))   # no duplicate completed rows

    def test_budget_stops_before_a_call_that_would_pass_cap(self):
        tiny = SpendGuard(0.0001, self.rates)
        client = FakeClient([])
        summary = run(self.work, self.csv, client, tiny, log=lambda *_: None)
        self.assertTrue(summary["stopped_by_budget"])
        self.assertEqual(client.calls, 0)

    def test_unverified_rates_are_reported(self):
        self.rates.write_text(json.dumps({"input_usd_per_million_tokens": 1.0,
                                          "output_usd_per_million_tokens": 5.0, "verified": False}))
        summary = run(self.work, self.csv, FakeClient([]), SpendGuard(10, self.rates), log=lambda *_: None)
        self.assertFalse(summary["rates_verified"])


def _api_error():
    e = JevError("down", status=503, retryable=True)
    e.attempts = [{"attempt": 1, "outcome": "failed", "status": 503}]
    return e


if __name__ == "__main__":
    unittest.main()
