"""Offline tests for stages 4-5 (grouping and ranking). No network.

Run:  python3 -m unittest discover -s tests -v
"""

import unittest
from decimal import Decimal

from pipeline.rank import build, mean_string, ranking_rows


def rec(rid, topic, intent, severity, status="completed"):
    return {"review_id": rid, "topic": topic, "intent": intent, "severity": severity, "status": status}


class RankTests(unittest.TestCase):
    def test_only_completed_complaints_and_cancellations_count(self):
        records = [
            rec("a", "playback", "complaint", 4),
            rec("b", "playback", "cancellation", 2),
            rec("c", "playback", "praise", 1),                        # excluded: praise
            rec("d", "playback", "request", 1),                       # excluded: request
            rec("e", "access", "complaint", 5, status="quarantined"),  # excluded: not completed
        ]
        membership, issues = build(records)
        self.assertEqual(membership, [("playback", "a"), ("playback", "b")])
        self.assertEqual(issues["playback"]["complaint_count"], 2)
        self.assertEqual(issues["playback"]["severity_sum"], 6)
        self.assertEqual(issues["access"]["complaint_count"], 0)

    def test_priority_is_exact_severity_sum_and_mean_is_rounded(self):
        records = [rec("a", "billing", "complaint", 5), rec("b", "billing", "complaint", 3),
                   rec("c", "billing", "complaint", 3)]
        _, issues = build(records)
        v = issues["billing"]
        self.assertEqual(v["severity_sum"], 11)
        self.assertEqual(v["priority_score"], 11)            # exact integer, not the rounded mean
        self.assertEqual(v["mean_severity"], "3.666667")     # 11 / 3, half-up at six places
        product = Decimal(v["complaint_count"]) * Decimal(v["mean_severity"])
        self.assertLessEqual(abs(product - Decimal(v["severity_sum"])), Decimal("0.000003"))

    def test_half_up_rounding(self):
        self.assertEqual(mean_string(1, 8), "0.125000")
        self.assertEqual(mean_string(2, 3), "0.666667")
        self.assertEqual(mean_string(5, 2), "2.500000")

    def test_ranking_sorts_by_score_then_issue_id(self):
        records = [
            rec("a", "support", "complaint", 3),    # score 3
            rec("b", "access", "complaint", 3),     # score 3, ties with support: access first
            rec("c", "playback", "complaint", 5),   # score 5: rank 1
        ]
        _, issues = build(records)
        order = [r["issue_id"] for r in ranking_rows(issues) if r["priority_score"] > 0]
        self.assertEqual(order, ["playback", "access", "support"])
        self.assertEqual([r["rank"] for r in ranking_rows(issues)][:3], [1, 2, 3])

    def test_ranking_is_deterministic_regardless_of_input_order(self):
        records = [rec(str(i), "catalog" if i % 2 else "usability", "complaint", (i % 5) + 1) for i in range(40)]
        _, issues_a = build(records)
        _, issues_b = build(list(reversed(records)))
        self.assertEqual(ranking_rows(issues_a), ranking_rows(issues_b))

    def test_unknown_topic_is_rejected(self):
        with self.assertRaises(ValueError):
            build([rec("a", "pricing", "complaint", 2)])

    def test_each_review_counted_once_per_issue(self):
        with self.assertRaises(ValueError):
            build([rec("a", "playback", "complaint", 2), rec("a", "playback", "complaint", 2)])


if __name__ == "__main__":
    unittest.main()
