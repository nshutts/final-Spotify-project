"""Ranking arithmetic and tie-break rules (GRADING_CONTRACT.md)."""
import unittest

from pipeline.rank import compute, mean_string


class RankTests(unittest.TestCase):
    def test_mean_half_up_six_decimals(self):
        self.assertEqual(mean_string(2, 3), "0.666667")
        self.assertEqual(mean_string(1, 8), "0.125000")

    def test_order_and_tie_break(self):
        latest = {f"r{i}": {"status": "completed", "intent": "complaint", "severity": s}
                  for i, s in enumerate([4, 2, 3, 3, 2])}
        rows = compute(latest, [("ISS-B", "r0"), ("ISS-B", "r1"), ("ISS-A", "r2"), ("ISS-A", "r3"), ("ISS-C", "r4")])
        self.assertEqual([r["issue_id"] for r in rows], ["ISS-A", "ISS-B", "ISS-C"])
        self.assertEqual(rows[0]["priority_score"], 6)
        self.assertEqual(rows[0]["rank"], 1)

    def test_rejects_non_complaint_member(self):
        latest = {"r0": {"status": "completed", "intent": "praise", "severity": 1}}
        with self.assertRaises(ValueError):
            compute(latest, [("ISS-A", "r0")])


if __name__ == "__main__":
    unittest.main()
