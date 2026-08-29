"""End-to-end modular policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .market import choose_crop_mix, market_orders
from .planner import assign_actions, build_tasks
from .safety import fallback, sanitize
from .state import Snapshot, get
from .value_model import LinearValueModel


@dataclass(frozen=True)
class AgentConfig:
    target_tiles: int = 20
    hire_target: int = 6
    enable_market: bool = True
    opponent_aware: bool = True
    enable_task_scheduler: bool = True
    enable_value_model: bool = False


class Policy:
    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.last_reasons: list[str] = []
        # Conservative bootstrap weights. Replace with exported replay-trained
        # weights only after held-out paired-seed evaluation.
        self.value_model = LinearValueModel([0.20, 0.12, 0.10, -0.12, -0.10])

    def act(self, obs: Any) -> dict[str, list[Any]]:
        hand_count = 0
        try:
            snapshot = Snapshot.from_obs(obs)
            hand_count = len(get(snapshot.me, "hands", []) or [])
            crop_plan = choose_crop_mix(
                snapshot,
                self.config.target_tiles,
                opponent_aware=self.config.opponent_aware,
                value_model=self.value_model if self.config.enable_value_model else None,
            )
            tasks = build_tasks(snapshot, crop_plan)
            if self.config.enable_task_scheduler:
                unit_actions, reasons = assign_actions(snapshot, tasks)
            else:
                unit_actions, reasons = [["PASS"] for _ in snapshot.positions], ["disabled"]
            self.last_reasons = reasons
            action = {
                "farmer": unit_actions[0] if unit_actions else ["PASS"],
                "hands": unit_actions[1:],
                "market": market_orders(
                    snapshot,
                    crop_plan,
                    self.config.hire_target,
                    enable_market=self.config.enable_market,
                ),
            }
            return sanitize(action, hand_count)
        except Exception:
            return fallback(hand_count)
