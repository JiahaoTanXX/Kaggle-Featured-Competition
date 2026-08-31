"""Greedy collision-free task scheduler with read-only episode diagnostics."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import json
from typing import Any

from .state import CROP_STATS, Snapshot, get, manhattan, step_toward


@dataclass(frozen=True)
class Task:
    pos: tuple[int, int]
    action: list[Any]
    priority: int
    reason: str


MOVE_ACTIONS = {"NORTH", "SOUTH", "EAST", "WEST"}


@dataclass
class ReasonDiagnostics:
    appearances: int = 0
    selected: int = 0
    executed: int = 0
    priority_total: int = 0
    assigned_manhattan_distance: int = 0
    movement_steps: int = 0


@dataclass
class WorkerDiagnostics:
    move_count: int = 0
    action_count: int = 0
    pass_count: int = 0
    movement_distance: int = 0


@dataclass
class PlannerDiagnostics:
    player: int
    task_stats: dict[str, ReasonDiagnostics] = field(default_factory=dict)
    worker_stats: dict[int, WorkerDiagnostics] = field(default_factory=dict)
    remaining_tasks_by_step: list[dict[str, int]] = field(default_factory=list)
    daily_idle: dict[int, dict[str, Any]] = field(default_factory=dict)
    seed_guard_passes: int = 0
    total_task_appearances: int = 0
    total_selected_tasks: int = 0
    total_executed_tasks: int = 0
    emitted: bool = False

    def reason(self, reason: str) -> ReasonDiagnostics:
        if reason not in self.task_stats:
            self.task_stats[reason] = ReasonDiagnostics()
        return self.task_stats[reason]

    def worker(self, worker_id: int) -> WorkerDiagnostics:
        if worker_id not in self.worker_stats:
            self.worker_stats[worker_id] = WorkerDiagnostics()
        return self.worker_stats[worker_id]

    def record_task_pool(self, tasks: list[Task]) -> dict[str, ReasonDiagnostics]:
        step_stats: dict[str, ReasonDiagnostics] = {}
        for task in tasks:
            stats = self.reason(task.reason)
            stats.appearances += 1
            stats.priority_total += task.priority
            self.total_task_appearances += 1
            current = step_stats.setdefault(task.reason, ReasonDiagnostics())
            current.appearances += 1
            current.priority_total += task.priority
        return step_stats

    def record_assignment(
        self,
        task: Task,
        distance: int,
        moved: bool,
        step_stats: dict[str, ReasonDiagnostics] | None = None,
    ) -> None:
        stats = self.reason(task.reason)
        stats.selected += 1
        stats.assigned_manhattan_distance += distance
        if moved:
            stats.movement_steps += 1
        self.total_selected_tasks += 1
        if step_stats is not None:
            current = step_stats.setdefault(task.reason, ReasonDiagnostics())
            current.selected += 1
            current.assigned_manhattan_distance += distance
            if moved:
                current.movement_steps += 1

    def record_execution(
        self, task: Task, step_stats: dict[str, ReasonDiagnostics] | None = None
    ) -> None:
        self.reason(task.reason).executed += 1
        self.total_executed_tasks += 1
        if step_stats is not None:
            step_stats.setdefault(task.reason, ReasonDiagnostics()).executed += 1

    def record_worker_action(self, worker_id: int, action: list[Any]) -> None:
        stats = self.worker(worker_id)
        op = str(action[0]) if action else "PASS"
        if op in MOVE_ACTIONS:
            stats.move_count += 1
            stats.movement_distance += 1
        elif op == "PASS":
            stats.pass_count += 1
        else:
            stats.action_count += 1

    def record_step(
        self,
        snapshot: Snapshot,
        task_count: int,
        assigned_count: int,
        executed_count: int,
        remaining_count: int,
        idle_workers: int,
        actions: list[list[Any]],
        task_stats: dict[str, ReasonDiagnostics],
    ) -> None:
        ops = [str(action[0]) if action else "PASS" for action in actions]
        self.remaining_tasks_by_step.append(
            {
                "step": snapshot.step,
                "day": snapshot.day,
                "hour": snapshot.hour,
                "task_count": task_count,
                "assigned_count": assigned_count,
                "executed_count": executed_count,
                "remaining_after_assignment": remaining_count,
                "unexecuted_count": max(0, task_count - executed_count),
                "worker_count": len(actions),
                "movement_distance": sum(op in MOVE_ACTIONS for op in ops),
                "productive_actions": sum(op not in MOVE_ACTIONS and op != "PASS" for op in ops),
                "pass_actions": sum(op == "PASS" for op in ops),
                "idle_workers": idle_workers,
                "task_distribution_by_reason": {
                    reason: asdict(stats) for reason, stats in sorted(task_stats.items())
                },
            }
        )
        day_stats = self.daily_idle.setdefault(
            snapshot.day,
            {"steps": 0, "idle_worker_turns": 0, "idle_workers_by_step": []},
        )
        day_stats["steps"] += 1
        day_stats["idle_worker_turns"] += idle_workers
        day_stats["idle_workers_by_step"].append(idle_workers)

    def summary(self) -> dict[str, Any]:
        total_movement = sum(stats.movement_distance for stats in self.worker_stats.values())
        total_productive = sum(stats.action_count for stats in self.worker_stats.values())
        total_pass = sum(stats.pass_count for stats in self.worker_stats.values())
        worker_turns = total_movement + total_productive + total_pass
        task_distribution = {}
        for reason, stats in sorted(self.task_stats.items()):
            task_distribution[reason] = {
                "appearances": stats.appearances,
                "selected": stats.selected,
                "executed": stats.executed,
                "average_priority": (
                    stats.priority_total / stats.appearances if stats.appearances else 0.0
                ),
                "assigned_manhattan_distance": stats.assigned_manhattan_distance,
                "movement_steps": stats.movement_steps,
                "completion_ratio": stats.executed / stats.appearances if stats.appearances else 0.0,
            }
        daily_idle = {}
        for day, stats in sorted(self.daily_idle.items()):
            daily_idle[str(day)] = {
                **stats,
                "average_idle_workers_per_step": (
                    stats["idle_worker_turns"] / stats["steps"] if stats["steps"] else 0.0
                ),
                "max_idle_workers_in_step": max(stats["idle_workers_by_step"], default=0),
            }
        return {
            "schema_version": "1.0",
            "player": self.player,
            "total_movement_distance": total_movement,
            "total_productive_actions": total_productive,
            "total_pass_actions": total_pass,
            "worker_utilization": (
                (total_movement + total_productive) / worker_turns if worker_turns else 0.0
            ),
            "productive_utilization": total_productive / worker_turns if worker_turns else 0.0,
            "task_completion_ratio": (
                self.total_executed_tasks / self.total_task_appearances
                if self.total_task_appearances
                else 0.0
            ),
            "assignment_execution_ratio": (
                self.total_executed_tasks / self.total_selected_tasks
                if self.total_selected_tasks
                else 0.0
            ),
            "average_movement_per_productive_action": (
                total_movement / total_productive if total_productive else 0.0
            ),
            "total_task_appearances": self.total_task_appearances,
            "total_selected_tasks": self.total_selected_tasks,
            "total_executed_tasks": self.total_executed_tasks,
            "seed_guard_passes": self.seed_guard_passes,
            "worker_stats": {
                str(worker_id): asdict(stats)
                for worker_id, stats in sorted(self.worker_stats.items())
            },
            "daily_idle_workers": daily_idle,
            "remaining_tasks_by_step": self.remaining_tasks_by_step,
            "task_distribution_by_reason": task_distribution,
        }


_DIAGNOSTICS_BY_PLAYER: dict[int, PlannerDiagnostics] = {}


def reset_planner_diagnostics(player: int = 0) -> None:
    """Reset one player's episode-level diagnostic collector."""
    _DIAGNOSTICS_BY_PLAYER[player] = PlannerDiagnostics(player=player)


def get_planner_diagnostics_summary(player: int = 0) -> dict[str, Any]:
    """Return a JSON-safe snapshot without mutating scheduler state."""
    diagnostics = _DIAGNOSTICS_BY_PLAYER.get(player)
    return diagnostics.summary() if diagnostics else PlannerDiagnostics(player=player).summary()


def finalize_planner_diagnostics(player: int = 0, emit: bool = True) -> dict[str, Any]:
    """Return and optionally emit the episode summary exactly once."""
    diagnostics = _DIAGNOSTICS_BY_PLAYER.get(player)
    summary = get_planner_diagnostics_summary(player)
    if emit and diagnostics is not None and not diagnostics.emitted:
        emitted_summary = {
            key: value
            for key, value in summary.items()
            if key not in {"remaining_tasks_by_step", "daily_idle_workers"}
        }
        print("KAGGRICULTURE_PLANNER_SUMMARY " + json.dumps(emitted_summary, sort_keys=True))
        diagnostics.emitted = True
    return summary


def _diagnostics_for(snapshot: Snapshot) -> PlannerDiagnostics | None:
    """Best-effort diagnostics; failures must never affect policy actions."""
    try:
        if snapshot.step == 0 or snapshot.player not in _DIAGNOSTICS_BY_PLAYER:
            reset_planner_diagnostics(snapshot.player)
        return _DIAGNOSTICS_BY_PLAYER[snapshot.player]
    except Exception:
        return None


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
    diagnostics = _diagnostics_for(snapshot)
    step_task_stats: dict[str, ReasonDiagnostics] = {}
    assigned_count = 0
    executed_count = 0
    idle_workers = 0
    if diagnostics is not None:
        try:
            step_task_stats = diagnostics.record_task_pool(tasks)
        except Exception:
            diagnostics = None

    # Urgent tasks are assigned first, then distance breaks ties.
    for worker_id, pos in enumerate(snapshot.positions):
        if not remaining:
            actions.append(["PASS"])
            reasons.append("idle")
            idle_workers += 1
            if diagnostics is not None:
                try:
                    diagnostics.record_worker_action(worker_id, actions[-1])
                except Exception:
                    pass
            continue
        best = min(
            remaining,
            key=lambda task: (-task.priority, manhattan(pos, task.pos), task.pos[1], task.pos[0]),
        )
        remaining.remove(best)
        assigned_count += 1
        distance = manhattan(pos, best.pos)
        if diagnostics is not None:
            try:
                diagnostics.record_assignment(
                    best, distance, pos != best.pos, step_stats=step_task_stats
                )
            except Exception:
                pass
        if pos != best.pos:
            actions.append(step_toward(pos, best.pos))
            reasons.append(f"move_to_{best.reason}")
            if diagnostics is not None:
                try:
                    diagnostics.record_worker_action(worker_id, actions[-1])
                except Exception:
                    pass
            continue

        if best.action[0] == "PLANT":
            crop = str(best.action[1])
            if plant_budget[crop] <= 0:
                actions.append(["PASS"])
                reasons.append("seed_guard")
                idle_workers += 1
                if diagnostics is not None:
                    try:
                        diagnostics.seed_guard_passes += 1
                        diagnostics.record_worker_action(worker_id, actions[-1])
                    except Exception:
                        pass
                continue
            plant_budget[crop] -= 1
        actions.append(best.action)
        reasons.append(best.reason)
        executed_count += 1
        if diagnostics is not None:
            try:
                diagnostics.record_execution(best, step_stats=step_task_stats)
                diagnostics.record_worker_action(worker_id, actions[-1])
            except Exception:
                pass

    if diagnostics is not None:
        try:
            diagnostics.record_step(
                snapshot,
                task_count=len(tasks),
                assigned_count=assigned_count,
                executed_count=executed_count,
                remaining_count=len(remaining),
                idle_workers=idle_workers,
                actions=actions,
                task_stats=step_task_stats,
            )
            # A 720-step Kaggle episode's final policy observation is step 718
            # (day 29, hour 22); the environment owns the terminal transition.
            if snapshot.day == 29 and snapshot.hour >= 22:
                finalize_planner_diagnostics(snapshot.player, emit=True)
        except Exception:
            pass

    return actions, reasons
