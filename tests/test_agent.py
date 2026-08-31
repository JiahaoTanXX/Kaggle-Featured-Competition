from __future__ import annotations

from contextlib import redirect_stdout
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kaggriculture_agent import AgentConfig, Policy
from src.kaggriculture_agent.planner import (
    Task,
    assign_actions,
    get_planner_diagnostics_summary,
    reset_planner_diagnostics,
)
from src.kaggriculture_agent.safety import sanitize
from src.kaggriculture_agent.state import Snapshot
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


class PlannerDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        reset_planner_diagnostics(0)

    @staticmethod
    def snapshot(
        *,
        step: int,
        farmer: list[int],
        hands: list[list[int]],
        seeds: dict[str, int] | None = None,
    ) -> Snapshot:
        obs = minimal_obs()
        obs["step"] = step
        obs["hour"] = step
        obs["farms"][0]["farmer"] = farmer
        obs["farms"][0]["hands"] = hands
        obs["private"]["seeds"] = seeds or {}
        return Snapshot.from_obs(obs)

    def test_instrumentation_preserves_greedy_actions_and_records_counts(self):
        tasks = [
            Task((0, 1), ["WATER"], 80, "daily_water"),
            Task((2, 2), ["DIG"], 55, "clear_weed"),
            Task((4, 4), ["PLANT", "WHEAT"], 40, "plant_wheat"),
        ]
        actions, reasons = assign_actions(
            self.snapshot(step=0, farmer=[0, 0], hands=[[2, 2]]), tasks
        )

        self.assertEqual(actions, [["SOUTH"], ["DIG"]])
        self.assertEqual(reasons, ["move_to_daily_water", "clear_weed"])
        summary = get_planner_diagnostics_summary(0)
        self.assertEqual(summary["total_movement_distance"], 1)
        self.assertEqual(summary["total_productive_actions"], 1)
        self.assertEqual(summary["total_pass_actions"], 0)
        self.assertEqual(summary["worker_stats"]["0"]["move_count"], 1)
        self.assertEqual(summary["worker_stats"]["1"]["action_count"], 1)
        self.assertEqual(summary["remaining_tasks_by_step"][0]["remaining_after_assignment"], 1)
        self.assertEqual(summary["remaining_tasks_by_step"][0]["unexecuted_count"], 2)
        self.assertEqual(
            summary["task_distribution_by_reason"]["daily_water"]["average_priority"],
            80.0,
        )
        self.assertEqual(
            summary["task_distribution_by_reason"]["clear_weed"]["executed"], 1
        )

    def test_seed_guard_pass_and_idle_are_diagnostic_only(self):
        task = Task((4, 4), ["PLANT", "WHEAT"], 40, "plant_wheat")
        actions, reasons = assign_actions(
            self.snapshot(step=2, farmer=[4, 4], hands=[]), [task]
        )

        self.assertEqual(actions, [["PASS"]])
        self.assertEqual(reasons, ["seed_guard"])
        summary = get_planner_diagnostics_summary(0)
        self.assertEqual(summary["seed_guard_passes"], 1)
        self.assertEqual(summary["total_pass_actions"], 1)
        self.assertEqual(summary["worker_stats"]["0"]["pass_count"], 1)
        self.assertEqual(summary["daily_idle_workers"]["0"]["idle_worker_turns"], 1)

    def test_standard_episode_final_observation_emits_summary(self):
        obs = minimal_obs()
        obs["step"] = 718
        obs["day"] = 29
        obs["hour"] = 22
        output = io.StringIO()

        with redirect_stdout(output):
            actions, reasons = assign_actions(Snapshot.from_obs(obs), [])

        self.assertEqual(actions, [["PASS"]])
        self.assertEqual(reasons, ["idle"])
        self.assertTrue(output.getvalue().startswith("KAGGRICULTURE_PLANNER_SUMMARY "))


if __name__ == "__main__":
    unittest.main()
