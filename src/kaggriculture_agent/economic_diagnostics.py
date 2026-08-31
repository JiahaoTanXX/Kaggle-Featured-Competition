"""Offline economic and phase diagnostics for Kaggriculture replays."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from .state import CROP_STATS


PHASES = ("early", "mid", "late")
MOVE_ACTIONS = {"NORTH", "SOUTH", "EAST", "WEST"}
LAND_PRICES = (1000, 2000, 4000)


def _phase(step: int, episode_steps: int) -> str:
    fraction = step / max(1, episode_steps)
    if fraction < 0.25:
        return "early"
    if fraction < 0.75:
        return "mid"
    return "late"


def _player_state(frame: list[dict[str, Any]], player: int) -> tuple[dict[str, Any], dict[str, Any]]:
    state = frame[player]
    obs = state.get("observation") or {}
    farms = obs.get("farms") or []
    farm = farms[player] if player < len(farms) else {}
    return state, farm


def _tile_metrics(farm: dict[str, Any]) -> dict[str, Any]:
    crop_counts: Counter[str] = Counter()
    unlocked = empty = occupied = weeds = harvestable_plants = harvestable_units = 0
    for row in farm.get("tiles") or []:
        for tile in row:
            if tile == "LOCKED":
                continue
            unlocked += 1
            if tile is None:
                empty += 1
                continue
            occupied += 1
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "WEED":
                weeds += 1
            elif tile.get("kind") == "PLANT":
                crop_counts[str(tile.get("crop"))] += 1
                units = int(tile.get("yield_units", 0))
                if units > 0:
                    harvestable_plants += 1
                    harvestable_units += units
    return {
        "unlocked_tiles": unlocked,
        "empty_unlocked_tiles": empty,
        "occupied_tiles": occupied,
        "weed_tiles": weeds,
        "crop_counts": dict(crop_counts),
        "land_utilization": occupied / unlocked if unlocked else 0.0,
        "crop_land_utilization": sum(crop_counts.values()) / unlocked if unlocked else 0.0,
        "harvestable_plants": harvestable_plants,
        "unharvested_yield_units": harvestable_units,
    }


def _inventory_totals(private: dict[str, Any]) -> dict[str, int]:
    totals: Counter[str] = Counter(
        {str(k): int(v) for k, v in (private.get("shed") or {}).items()}
    )
    for inventory in private.get("inventories") or []:
        totals.update({str(k): int(v) for k, v in (inventory or {}).items()})
    return dict(totals)


def _fib(index: int) -> int:
    a, b = 1, 1
    for _ in range(index):
        a, b = b, a + b
    return a


def _unit_actions(action: dict[str, Any]) -> list[list[Any]]:
    return [action.get("farmer") or ["PASS"], *((action.get("hands") or []))]


def _effective_harvests(
    previous_obs: dict[str, Any], action: dict[str, Any], player: int
) -> Counter[str]:
    farms = previous_obs.get("farms") or []
    if player >= len(farms):
        return Counter()
    farm = farms[player]
    positions = [farm.get("farmer") or [0, 0], *(farm.get("hands") or [])]
    tiles = farm.get("tiles") or []
    result: Counter[str] = Counter()
    for pos, unit_action in zip(positions, _unit_actions(action)):
        if not unit_action or unit_action[0] != "HARVEST":
            continue
        x, y = int(pos[0]), int(pos[1])
        tile = tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) else None
        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
            units = int(tile.get("yield_units", 0))
            if units > 0:
                result[str(tile.get("crop"))] += units
    return result


def _phase_worker_stats(planner: dict[str, Any], episode_steps: int) -> dict[str, Any]:
    phase_stats = {
        phase: {"worker_turns": 0, "movement_distance": 0, "productive_actions": 0, "pass": 0}
        for phase in PHASES
    }
    for step in planner.get("remaining_tasks_by_step") or []:
        bucket = phase_stats[_phase(int(step.get("step", 0)), episode_steps)]
        bucket["worker_turns"] += int(step.get("worker_count", 0))
        bucket["movement_distance"] += int(step.get("movement_distance", 0))
        bucket["productive_actions"] += int(step.get("productive_actions", 0))
        bucket["pass"] += int(step.get("pass_actions", 0))
    for bucket in phase_stats.values():
        active = bucket["movement_distance"] + bucket["productive_actions"]
        bucket["worker_utilization"] = (
            active / bucket["worker_turns"] if bucket["worker_turns"] else 0.0
        )
        bucket["movement_per_productive_action"] = (
            bucket["movement_distance"] / bucket["productive_actions"]
            if bucket["productive_actions"]
            else 0.0
        )
    return phase_stats


def _phase_tasks(planner: dict[str, Any], episode_steps: int) -> dict[str, Any]:
    totals: dict[str, dict[str, Counter[str]]] = {
        phase: defaultdict(Counter) for phase in PHASES
    }
    for step in planner.get("remaining_tasks_by_step") or []:
        phase = _phase(int(step.get("step", 0)), episode_steps)
        for reason, values in (step.get("task_distribution_by_reason") or {}).items():
            totals[phase][reason].update(
                {
                    "generated": int(values.get("appearances", 0)),
                    "assigned": int(values.get("selected", 0)),
                    "executed": int(values.get("executed", 0)),
                    "priority_total": int(values.get("priority_total", 0)),
                    "travel_distance_total": int(values.get("assigned_manhattan_distance", 0)),
                }
            )
    result: dict[str, Any] = {}
    for phase in PHASES:
        result[phase] = {}
        for reason, values in sorted(totals[phase].items()):
            generated = values["generated"]
            assigned = values["assigned"]
            result[phase][reason] = {
                "generated": generated,
                "assigned": assigned,
                "executed": values["executed"],
                "average_priority": values["priority_total"] / generated if generated else 0.0,
                "average_travel_distance": (
                    values["travel_distance_total"] / assigned if assigned else 0.0
                ),
            }
    return result


def analyze_economy(
    replay: dict[str, Any], planner: dict[str, Any], focal_player: int = 0
) -> dict[str, Any]:
    """Build a JSON-safe economic ledger without changing or rerunning policy logic."""
    frames = replay.get("steps") or []
    episode_steps = len(frames)
    cash_timeline: list[dict[str, Any]] = []
    asset_timeline: list[dict[str, Any]] = []
    phase_cash: dict[str, list[float]] = {phase: [] for phase in PHASES}
    phase_actions: dict[str, Counter[str]] = {phase: Counter() for phase in PHASES}
    phase_spend: dict[str, Counter[str]] = {phase: Counter() for phase in PHASES}
    phase_harvest: dict[str, Counter[str]] = {phase: Counter() for phase in PHASES}
    phase_crop_samples: dict[str, dict[str, list[int]]] = {
        phase: defaultdict(list) for phase in PHASES
    }
    expenditure: Counter[str] = Counter()
    expenditure.update(
        {
            "land": 0,
            "hiring": 0,
            **{f"seed_{crop.lower()}": 0 for crop in CROP_STATS},
        }
    )
    harvest_yield: Counter[str] = Counter()
    estimated_revenue: Counter[str] = Counter()
    expansion_events: list[dict[str, Any]] = []
    hiring_events: list[dict[str, Any]] = []
    next_land_affordable_steps = 0
    next_land_opportunity_steps = 0

    for index, frame in enumerate(frames):
        state, farm = _player_state(frame, focal_player)
        obs = state.get("observation") or {}
        private = obs.get("private") or {}
        phase = _phase(index, episode_steps)
        cash = float(farm.get("money", 0.0))
        tiles = _tile_metrics(farm)
        seeds = {str(k): int(v) for k, v in (private.get("seeds") or {}).items()}
        inventory = _inventory_totals(private)
        hands = len(farm.get("hands") or [])
        unlocked_quadrants = list(farm.get("unlocked_quadrants") or [])

        phase_cash[phase].append(cash)
        cash_timeline.append(
            {
                "step": index,
                "day": int(obs.get("day", 0)),
                "hour": int(obs.get("hour", 0)),
                "phase": phase,
                "cash": cash,
            }
        )
        asset_timeline.append(
            {
                "step": index,
                "phase": phase,
                "unlocked_tiles": tiles["unlocked_tiles"],
                "unlocked_quadrants": len(unlocked_quadrants),
                "workers": 1 + hands,
                "hands": hands,
                "seeds": seeds,
                "inventory": inventory,
                **{key: value for key, value in tiles.items() if key != "crop_counts"},
                "crop_counts": tiles["crop_counts"],
            }
        )
        for crop in CROP_STATS:
            phase_crop_samples[phase][crop].append(int(tiles["crop_counts"].get(crop, 0)))

        extra_quadrants = max(0, len(unlocked_quadrants) - 1)
        if extra_quadrants < len(LAND_PRICES):
            next_land_opportunity_steps += 1
            if cash >= LAND_PRICES[extra_quadrants]:
                next_land_affordable_steps += 1

        if index == 0:
            continue
        previous_state, previous_farm = _player_state(frames[index - 1], focal_player)
        previous_obs = previous_state.get("observation") or {}
        previous_private = previous_obs.get("private") or {}
        action = state.get("action") or {}

        for unit_action in _unit_actions(action):
            op = str(unit_action[0]) if unit_action else "PASS"
            phase_actions[phase][op] += 1

        harvested = _effective_harvests(previous_obs, action, focal_player)
        harvest_yield.update(harvested)
        phase_harvest[phase].update(harvested)

        previous_quadrants = list(previous_farm.get("unlocked_quadrants") or [])
        gained = len(unlocked_quadrants) - len(previous_quadrants)
        for offset in range(max(0, gained)):
            price_index = max(0, len(previous_quadrants) - 1 + offset)
            cost = LAND_PRICES[price_index]
            expenditure["land"] += cost
            phase_spend[phase]["land"] += cost
            expansion_events.append(
                {"step": index, "day": int(obs.get("day", 0)), "cost": cost}
            )

        previous_day = int(previous_obs.get("day", 0))
        current_day = int(obs.get("day", 0))
        previous_hands = len(previous_farm.get("hands") or [])
        gained_hands = hands - previous_hands if current_day == previous_day else hands
        previous_hires = int(previous_farm.get("hires_today", 0)) if current_day == previous_day else 0
        if gained_hands > 0:
            cost = sum(_fib(previous_hires + n) for n in range(gained_hands))
            expenditure["hiring"] += cost
            phase_spend[phase]["hiring"] += cost
            hiring_events.append(
                {
                    "step": index,
                    "day": current_day,
                    "hands_hired": gained_hands,
                    "cost": cost,
                }
            )

        previous_seeds = previous_private.get("seeds") or {}
        for crop, stats in CROP_STATS.items():
            plant_actions = sum(
                1
                for unit_action in _unit_actions(action)
                if unit_action and unit_action[0] == "PLANT" and len(unit_action) > 1 and unit_action[1] == crop
            )
            purchased = max(
                0,
                int(seeds.get(crop, 0)) - int(previous_seeds.get(crop, 0)) + plant_actions,
            )
            cost = purchased * int(stats["seed"])
            expenditure[f"seed_{crop.lower()}"] += cost
            phase_spend[phase][f"seed_{crop.lower()}"] += cost

        previous_shed = {str(k): int(v) for k, v in (previous_private.get("shed") or {}).items()}
        for order in action.get("market") or []:
            if not order or order[0] != "SELL" or len(order) < 3:
                continue
            item = str(order[1])
            quantity = min(max(0, int(order[2])), max(0, previous_shed.get(item, 0)))
            price = float((previous_obs.get("market") or {}).get("prices", {}).get(item, 0))
            estimated_revenue[item] += quantity * price
            previous_shed[item] = max(0, previous_shed.get(item, 0) - quantity)

    cash_values = [point["cash"] for point in cash_timeline]
    start_cash = cash_values[0] if cash_values else 0.0
    final_cash = cash_values[-1] if cash_values else 0.0
    total_expenditure = float(sum(expenditure.values()))
    total_income = final_cash - start_cash + total_expenditure
    worker_by_phase = _phase_worker_stats(planner, episode_steps)
    tasks_by_phase = _phase_tasks(planner, episode_steps)
    overall_actions: Counter[str] = Counter()
    for counts in phase_actions.values():
        overall_actions.update(counts)

    phase_summary: dict[str, Any] = {}
    for phase in PHASES:
        values = phase_cash[phase]
        action_counts = phase_actions[phase]
        spent = sum(phase_spend[phase].values())
        phase_summary[phase] = {
            "step_range": {
                "start": next((p["step"] for p in cash_timeline if p["phase"] == phase), None),
                "end": next((p["step"] for p in reversed(cash_timeline) if p["phase"] == phase), None),
            },
            "cash": {
                "start": values[0] if values else 0.0,
                "end": values[-1] if values else 0.0,
                "min": min(values) if values else 0.0,
                "max": max(values) if values else 0.0,
                "average": mean(values) if values else 0.0,
                "net_change": values[-1] - values[0] if values else 0.0,
            },
            "cash_spent_by_category": dict(phase_spend[phase]),
            "total_expenditure": spent,
            "total_income": values[-1] - values[0] + spent if values else 0.0,
            "farming_actions": {
                "plant": action_counts["PLANT"],
                "harvest": action_counts["HARVEST"],
                "water": action_counts["WATER"],
                "weed_clear": action_counts["DIG"],
            },
            "harvested_yield_by_crop": dict(phase_harvest[phase]),
            "average_crop_counts": {
                crop: mean(samples) if samples else 0.0
                for crop, samples in phase_crop_samples[phase].items()
            },
            "worker_efficiency": worker_by_phase[phase],
            "task_distribution": tasks_by_phase[phase],
        }

    final_50_assets = asset_timeline[-50:]
    final_50_planner = [
        step
        for step in (planner.get("remaining_tasks_by_step") or [])
        if int(step.get("step", 0)) >= max(0, episode_steps - 50)
    ]
    high_value: Counter[str] = Counter()
    for step in final_50_planner:
        for reason, values in (step.get("task_distribution_by_reason") or {}).items():
            generated = int(values.get("appearances", 0))
            average_priority = int(values.get("priority_total", 0)) / generated if generated else 0
            if average_priority >= 70:
                high_value[reason] += max(0, generated - int(values.get("executed", 0)))

    final_asset = asset_timeline[-1] if asset_timeline else {}
    final_seed_map = final_asset.get("seeds", {})
    final_50 = {
        "unused_cash": {
            "final": final_cash,
            "average": mean(item["cash"] for item in cash_timeline[-50:]) if cash_timeline else 0.0,
        },
        "empty_land": {
            "final_tiles": int(final_asset.get("empty_unlocked_tiles", 0)),
            "average_tiles": (
                mean(item["empty_unlocked_tiles"] for item in final_50_assets)
                if final_50_assets
                else 0.0
            ),
        },
        "unharvested_crops": {
            "final_harvestable_plants": int(final_asset.get("harvestable_plants", 0)),
            "final_yield_units": int(final_asset.get("unharvested_yield_units", 0)),
            "average_harvestable_plants": (
                mean(item["harvestable_plants"] for item in final_50_assets)
                if final_50_assets
                else 0.0
            ),
        },
        "unused_seeds": {
            "final_by_crop": final_seed_map,
            "final_total": sum(int(value) for value in final_seed_map.values()),
            "average_total": (
                mean(sum(int(value) for value in item["seeds"].values()) for item in final_50_assets)
                if final_50_assets
                else 0.0
            ),
        },
        "idle_workers": {
            "pass_actions": sum(int(step.get("pass_actions", 0)) for step in final_50_planner),
            "average_per_step": (
                mean(int(step.get("pass_actions", 0)) for step in final_50_planner)
                if final_50_planner
                else 0.0
            ),
        },
        "unfinished_high_value_task_appearances": dict(high_value),
    }

    daily_assets = []
    for day in sorted({point["day"] for point in cash_timeline}):
        indices = [i for i, point in enumerate(cash_timeline) if point["day"] == day]
        index = indices[-1]
        daily_assets.append({**cash_timeline[index], **asset_timeline[index]})

    return {
        "schema_version": "2.0",
        "experiment": "EXP-002 Economic & Phase Diagnostics",
        "player": focal_player,
        "episode_steps": episode_steps,
        "phase_definition": {"early": "0%-25%", "mid": "25%-75%", "late": "75%-100%"},
        "economy": {
            "cash_over_time": cash_timeline,
            "final_cash": final_cash,
            "total_income": total_income,
            "total_expenditure": total_expenditure,
            "min_cash": min(cash_values) if cash_values else 0.0,
            "max_cash": max(cash_values) if cash_values else 0.0,
            "average_cash": mean(cash_values) if cash_values else 0.0,
            "idle_cash_ratio": (
                next_land_affordable_steps / next_land_opportunity_steps
                if next_land_opportunity_steps
                else 0.0
            ),
            "idle_cash_definition": (
                "fraction of observed steps where the next locked quadrant was affordable but not yet owned"
            ),
            "cash_spent_by_category": dict(expenditure),
        },
        "assets": {
            "over_time": asset_timeline,
            "daily_closing": daily_assets,
            "expansion_timing": expansion_events,
            "hiring_timing": hiring_events,
        },
        "farming": {
            "crop_counts_over_time": [
                {"step": item["step"], "crop_counts": item["crop_counts"]}
                for item in asset_timeline
            ],
            "plant_count": overall_actions["PLANT"],
            "harvest_count": overall_actions["HARVEST"],
            "water_count": overall_actions["WATER"],
            "weed_clear_count": overall_actions["DIG"],
            "harvested_yield_by_crop": dict(harvest_yield),
            "estimated_revenue_by_crop": dict(estimated_revenue),
            "estimated_revenue_note": (
                "sold quantity multiplied by the displayed pre-action price; dynamic intra-order pricing can differ"
            ),
            "empty_unlocked_tiles_over_time": [
                {"step": item["step"], "empty_unlocked_tiles": item["empty_unlocked_tiles"]}
                for item in asset_timeline
            ],
            "land_utilization_over_time": [
                {"step": item["step"], "land_utilization": item["land_utilization"]}
                for item in asset_timeline
            ],
        },
        "worker_efficiency": {
            "overall": {
                "worker_utilization": float(planner.get("worker_utilization", 0.0)),
                "movement_distance": int(planner.get("total_movement_distance", 0)),
                "productive_actions": int(planner.get("total_productive_actions", 0)),
                "pass": int(planner.get("total_pass_actions", 0)),
                "movement_per_productive_action": float(
                    planner.get("average_movement_per_productive_action", 0.0)
                ),
            },
            "by_phase": worker_by_phase,
        },
        "task_distribution": {
            "overall": {
                reason: {
                    "generated": int(values.get("appearances", 0)),
                    "assigned": int(values.get("selected", 0)),
                    "executed": int(values.get("executed", 0)),
                    "average_priority": float(values.get("average_priority", 0.0)),
                    "average_travel_distance": (
                        float(values.get("assigned_manhattan_distance", 0))
                        / int(values.get("selected", 0))
                        if int(values.get("selected", 0))
                        else 0.0
                    ),
                }
                for reason, values in (planner.get("task_distribution_by_reason") or {}).items()
            },
            "by_phase": tasks_by_phase,
        },
        "phases": phase_summary,
        "end_game_last_50_steps": final_50,
        "score_semantics": {
            "local_match_score": (
                "final bank coins in one 720-turn episode; higher final coins determine win/loss"
            ),
            "kaggle_leaderboard_score": (
                "skill rating updated from wins, losses, ties, and opponent rating; final ranking uses Bradley-Terry"
            ),
            "coin_margin_affects_rating_change": False,
            "exact_live_rating_formula": "unknown",
            "same_meaning": False,
            "source": "https://www.kaggle.com/competitions/kaggriculture/overview#evaluation",
        },
    }
