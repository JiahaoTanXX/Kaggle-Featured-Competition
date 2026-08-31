from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kaggriculture_agent.economic_diagnostics import analyze_economy


class EconomicDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.replay = json.loads(
            (ROOT / "replays" / "full_starter_seed20260829.json").read_text(encoding="utf-8")
        )
        cls.result = analyze_economy(cls.replay, {}, 0)

    def test_cash_ledger_reconciles_fixed_seed_episode(self):
        economy = self.result["economy"]
        self.assertEqual(economy["final_cash"], 11408.0)
        self.assertEqual(economy["total_expenditure"], 3500.0)
        self.assertEqual(economy["total_income"], 11908.0)
        self.assertEqual(economy["cash_spent_by_category"]["land"], 0)
        self.assertAlmostEqual(
            economy["cash_over_time"][0]["cash"]
            + economy["total_income"]
            - economy["total_expenditure"],
            economy["final_cash"],
        )

    def test_harvest_and_score_semantics(self):
        self.assertEqual(
            self.result["farming"]["harvested_yield_by_crop"],
            {"CARROT": 176, "WHEAT": 211},
        )
        self.assertFalse(self.result["score_semantics"]["same_meaning"])
        self.assertEqual(
            self.result["score_semantics"]["exact_live_rating_formula"], "unknown"
        )


if __name__ == "__main__":
    unittest.main()
