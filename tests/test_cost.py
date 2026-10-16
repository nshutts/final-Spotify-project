"""Offline tests for the cost calculator. Synthetic fixtures only; no calls, no keys.

Run:  python3 -m unittest discover -s tests -v
"""

import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from cost.calculator import cost_by_stage, load_rates, load_usage, project, replay

FIX = Path(__file__).parent / "fixtures"


class CostTests(unittest.TestCase):
    def setUp(self):
        self.usage = load_usage(FIX / "synthetic_usage.csv")
        self.rates = load_rates(FIX / "synthetic_rates.csv")

    def test_item_cost_is_units_times_price_per_unit(self):
        out = cost_by_stage(self.usage, self.rates)
        classify = out["stages"]["classify"]["items"]
        # 1,000,000 uncached input tokens x $1.00 per million = $1.00
        self.assertEqual(classify["uncached_input"]["cost"], "1.000000")
        # 500,000 output tokens x $5.00 per million = $2.50
        self.assertEqual(classify["output"]["cost"], "2.500000")
        self.assertEqual(classify["cached_input"]["cost"], "0.000000")

    def test_api_total_is_sum_of_items_across_stages(self):
        out = cost_by_stage(self.usage, self.rates)
        # classify: 1.00 + 0.00 + 2.50 = 3.50 ; verify: 200k x $2 = 0.40, 100k x $0.20 = 0.02, 100k x $10 = 1.00
        self.assertEqual(out["api_total"], "4.920000")

    def test_failed_calls_are_counted_but_not_double_billed(self):
        out = cost_by_stage(self.usage, self.rates)
        self.assertEqual(out["stages"]["classify"]["calls"], 2)
        self.assertEqual(out["stages"]["classify"]["failed_calls"], 1)

    def test_doubling_all_rates_doubles_api_total_and_keeps_time(self):
        out = cost_by_stage(self.usage, self.rates)
        doubled = {k: {**v, "price": v["price"] * 2} for k, v in self.rates.items()}
        out2 = cost_by_stage(self.usage, doubled)
        self.assertEqual(Decimal(out2["api_total"]), Decimal(out["api_total"]) * 2)
        self.assertEqual(out2["stages"]["classify"]["seconds_summed"], out["stages"]["classify"]["seconds_summed"])

    def test_missing_rate_is_reported_not_zeroed(self):
        rates = {k: v for k, v in self.rates.items() if k[0] != "haiku-test-model"}
        out = cost_by_stage(self.usage, rates)
        self.assertIn("verify:uncached_input", out["unknown_rates"])
        self.assertIsNone(out["stages"]["verify"]["items"]["uncached_input"])

    def test_unverified_rates_are_marked_in_output(self):
        out = cost_by_stage(self.usage, self.rates)
        self.assertFalse(out["stages"]["classify"]["items"]["output"]["verified"])

    def test_replay_has_no_network_and_reports_local_note(self):
        out = replay(FIX / "synthetic_usage.csv", FIX / "synthetic_rates.csv")
        self.assertIn("Local compute is not included", out["note"])

    def test_projection_scales_measured_usage_and_adds_overhead_once(self):
        out = project(FIX / "synthetic_usage.csv", FIX / "synthetic_rates.csv", FIX / "synthetic_assumptions.json")
        base = out["scenarios"]["base"]
        # Measured classify cost is 3.50 over 2 calls (one failed), so 1.75 per call.
        # 1.75 x 484,189 full-run calls = 847,330.75.
        self.assertEqual(base["per_stage"]["classify"], "847330.750000")
        self.assertEqual(Decimal(base["api_total"]), Decimal(base["per_stage"]["classify"]) +
                         Decimal(base["per_stage"]["verify"]) + Decimal("0.5"))

    def test_projection_flags_over_budget_scenarios(self):
        assumptions = json.loads((FIX / "synthetic_assumptions.json").read_text())
        assumptions["budget_usd"] = 1
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(assumptions, f)
        out = project(FIX / "synthetic_usage.csv", FIX / "synthetic_rates.csv", f.name)
        self.assertTrue(out["scenarios"]["base"]["over_budget"])

    def test_changing_projected_volume_does_not_change_measured_results(self):
        a = json.loads((FIX / "synthetic_assumptions.json").read_text())
        before = cost_by_stage(self.usage, self.rates)
        a["scenarios"]["base"]["full_run_units"]["classify"] = 1
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(a, f)
        project(FIX / "synthetic_usage.csv", FIX / "synthetic_rates.csv", f.name)
        self.assertEqual(cost_by_stage(self.usage, self.rates), before)


if __name__ == "__main__":
    unittest.main()
