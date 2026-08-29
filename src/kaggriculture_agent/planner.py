"""Greedy collision-free task scheduler for field units."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .state import CROP_STATS, Snapshot, get, manhattan, step_toward


@dataclass(frozen=True)
class Task:
    pos: tuple[int, int]
    action: list[Any]
    priority: int
    reason: str


def _plant_task(snapshot: Snapshot, pos: tuple[int, int], crop: str) -> Task:
    return Task(pos, ["PLANT", crop], 40, f"plant_{crop.lower()}")


def build_tasks(snapshot: Snapshot, crop_plan: list[str]) -> list[Task]:
    tasks: list[Task] = []
    seed_slots = Counter(crop_plan)
    seed_slots.subtract(snapshot.crop_counts())
    seed_slots = Counter({crop: max(0, count) for crop, count in seed_slots.items()})

    for pos, tile in snapshot.iter_unlocked():
        if tile is None:
            crop = next((c for c in crop_plan if seed_slots[c] > 0), None)
            if crop:
                tasks.append(_plant_task(snapshot, pos, crop))
                seed_slots[crop] -= 1
            continue

        if not isinstance(tile, dict):
            continue
        kind = get(tile, "kind")
        if kind == "WEED":
            tasks.append(Task(pos, ["DIG"], 55, "clear_weed"))
            continue
        if kind != "PLANT":
            continue

        crop = str(get(tile, "crop", "WHEAT"))
        stats = CROP_STATS.get(crop, CROP_STATS["WHEAT"])
        age = snapshot.day - int(get(tile, "planted_day", snapshot.day))
        yield_units = int(get(tile, "yield_units", 0))
        unwatered = int(get(tile, "consecutive_unwatered", 0))
        watered = bool(get(tile, "watered_today", False))

        if unwatered >= 1 and not watered:
            tasks.append(Task(pos, ["WATER"], 100, "prevent_crop_loss"))
        elif not watered:
            tasks.append(Task(pos, ["WATER"], 80, "daily_water"))

        ready = yield_units > 0 and (stats["ongoing"] or age >= int(stats["first"]))
        peak = age >= int(stats["peak"])
        if ready and (stats["ongoing"] or peak or snapshot.day >= 28):
            priority = 95 if snapshot.day >= 28 else 70
            tasks.append(Task(pos, ["HARVEST"], priority, "harvest_ready"))

    return sorted(tasks, key=lambda task: (-task.priority, task.pos[1], task.pos[0]))


def assign_actions(snapshot: Snapshot, tasks: list[Task]) -> tuple[list[list[Any]], list[str]]:
    """Assign one unique target to each unit and return actions plus reason labels."""
    remaining = list(tasks)
    actions: list[list[Any]] = []
    reasons: list[str] = []
    plant_budget = Counter(snapshot.seeds)

    # Urgent tasks are assigned first, then distance breaks ties.
    for pos in snapshot.positions:
        if not remaining:
            actions.append(["PASS"])
            reasons.append("idle")
            continue
        best = min(
            remaining,
            key=lambda task: (-task.priority, manhattan(pos, task.pos), task.pos[1], task.pos[0]),
        )
        remaining.remove(best)
        if pos != best.pos:
            actions.append(step_toward(pos, best.pos))
            reasons.append(f"move_to_{best.reason}")
            continue

        if best.action[0] == "PLANT":
            crop = str(best.action[1])
            if plant_budget[crop] <= 0:
                actions.append(["PASS"])
                reasons.append("seed_guard")
                continue
            plant_budget[crop] -= 1
        actions.append(best.action)
        reasons.append(best.reason)

    return actions, reasons
