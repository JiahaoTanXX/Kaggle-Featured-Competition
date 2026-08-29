from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kaggriculture_agent import AgentConfig, Policy
from src.kaggriculture_agent.safety import sanitize
from src.kaggriculture_agent.value_model import LinearValueModel


def minimal_obs() -> dict:
    tiles = [[None for _ in range(5)] + ["LOCKED" for _ in range(5)] for _ in range(5)]
    tiles += [["LOCKED" for _ in range(10)] for _ in range(5)]
    farm = {
        "money": 3000,
        "farmer": [4, 4],
        "hands": [],
        "tiles": tiles,
        "unlocked_quadrants": ["NW"],
        "hires_today": 0,
    }
    return {
        "player": 0,
        "step": 0,
        "day": 0,
        "hour": 0,
        "farms": [farm, dict(farm)],
        "private": {"seeds": {}, "shed": {}, "inventories": [[]]},
        "market": {"prices": {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250}},
        "town": {"unlocked_shops": []},
    }


class AgentUnitTests(unittest.TestCase):
    def test_action_shape_and_limits(self):
        result = Policy().act(minimal_obs())
        self.assertEqual(set(result), {"farmer", "hands", "market"})
        self.assertLessEqual(len(result["market"]), 10)
        self.assertEqual(len(result["hands"]), 0)

    def test_ablation_scheduler_off_is_safe(self):
        result = Policy(AgentConfig(enable_task_scheduler=False)).act(minimal_obs())
        self.assertEqual(result["farmer"], ["PASS"])

    def test_sanitizer_rejects_unknown_operations(self):
        result = sanitize({"farmer": ["EXPLODE"], "hands": [], "market": [["STEAL"]]}, 0)
        self.assertEqual(result, {"farmer": ["PASS"], "hands": [], "market": []})

    def test_value_model_round_trip(self):
        rows = [([0, 0, 0, 0, 0], 1.0), ([1, 0, 0, 0, 0], 3.0)]
        model = LinearValueModel.zeros().fit(rows, epochs=300)
        self.assertGreater(model.predict([1, 0, 0, 0, 0]), model.predict([0, 0, 0, 0, 0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.json"
            model.save(path)
            loaded = LinearValueModel.load(path)
        self.assertAlmostEqual(model.predict([1, 0, 0, 0, 0]), loaded.predict([1, 0, 0, 0, 0]))


if __name__ == "__main__":
    unittest.main()
