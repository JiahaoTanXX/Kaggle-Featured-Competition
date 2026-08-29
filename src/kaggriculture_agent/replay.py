"""Replay-to-structured-summary conversion for evaluation and LLM analysis."""

from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from .state import PRODUCTS, get


def summarize_replay(replay: dict[str, Any], focal_player: int = 0) -> dict[str, Any]:
    steps = replay.get("steps", [])
    action_counts: Counter[str] = Counter()
    market_counts: Counter[str] = Counter()
    money_by_day: dict[int, list[float]] = {}
    final_shed: dict[str, int] = {}
    final_crop_counts: Counter[str] = Counter()
    weeds = 0

    for frame in steps:
        if focal_player >= len(frame):
            continue
        state = frame[focal_player]
        action = state.get("action") or {}
        farmer = action.get("farmer") or ["PASS"]
        action_counts[str(farmer[0])] += 1
        for hand_action in action.get("hands", []) or []:
            if hand_action:
                action_counts[str(hand_action[0])] += 1
        for order in action.get("market", []) or []:
            if order:
                market_counts[str(order[0])] += 1

        obs = state.get("observation") or {}
        farms = obs.get("farms", []) or []
        day = int(obs.get("day", 0))
        if focal_player < len(farms):
            money_by_day.setdefault(day, []).append(float(farms[focal_player].get("money", 0)))

    if steps and focal_player < len(steps[-1]):
        last = steps[-1][focal_player]
        obs = last.get("observation") or {}
        farms = obs.get("farms", []) or []
        private = obs.get("private") or {}
        final_shed = {k: int(v) for k, v in (private.get("shed") or {}).items() if int(v) != 0}
        if focal_player < len(farms):
            for row in farms[focal_player].get("tiles", []) or []:
                for tile in row:
                    if not isinstance(tile, dict):
                        continue
                    if tile.get("kind") == "WEED":
                        weeds += 1
                    if tile.get("kind") == "PLANT":
                        final_crop_counts[str(tile.get("crop"))] += 1

    rewards = replay.get("rewards") or []
    if len(rewards) < 2 and steps:
        rewards = [player.get("reward") for player in steps[-1]]
    focal_reward = float(rewards[focal_player] or 0) if focal_player < len(rewards) else 0.0
    opponent_reward = float(rewards[1 - focal_player] or 0) if len(rewards) > 1 else 0.0
    unsold = sum(final_shed.get(product, 0) for product in PRODUCTS)

    failure_tags = []
    if focal_reward < opponent_reward:
        failure_tags.append("lost_match")
    if weeds:
        failure_tags.append("crop_loss_or_unmanaged_weeds")
    if unsold:
        failure_tags.append("unsold_inventory")
    total_actions = sum(action_counts.values())
    if total_actions and action_counts["PASS"] / total_actions > 0.45:
        failure_tags.append("high_idle_ratio")

    return {
        "schema_version": "1.0",
        "player": focal_player,
        "episode_steps": len(steps),
        "reward": focal_reward,
        "opponent_reward": opponent_reward,
        "margin": focal_reward - opponent_reward,
        "won": focal_reward > opponent_reward,
        "action_counts": dict(action_counts),
        "market_order_counts": dict(market_counts),
        "daily_closing_money": {str(day): values[-1] for day, values in sorted(money_by_day.items())},
        "mean_daily_money": mean(values[-1] for values in money_by_day.values()) if money_by_day else 0.0,
        "final_shed": final_shed,
        "final_crop_counts": dict(final_crop_counts),
        "weed_count": weeds,
        "failure_tags": failure_tags,
    }
