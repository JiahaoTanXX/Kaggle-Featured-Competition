# Greedy scheduler diagnostics

This experiment adds read-only instrumentation around the existing greedy priority
scheduler. The reference Kaggle baseline score before instrumentation is **354.2**.
No crop, market, priority, task-generation, assignment, or action-selection rule is
changed by this experiment.

## Run

```bash
python scripts/run_match.py \
  --seed 20260829 \
  --steps 720 \
  --output replays/diagnostic-seed-20260829.json
```

The runner writes the normal replay and replay summary, plus
`replays/diagnostic-seed-20260829.planner.json`. During a standard 720-step
episode the agent also emits one JSON line prefixed with
`KAGGRICULTURE_PLANNER_SUMMARY` after its final policy observation.

## Metric definitions

- A task **appearance** is one `Task` emitted by `build_tasks()` in one policy step.
  A persistent task therefore contributes once on every step where it remains in
  the task pool.
- A task is **selected** when the scheduler removes it from `remaining` and assigns
  it to a worker.
- A task is **executed** when the assigned worker is already on the target tile and
  the scheduler emits the task action. This measures scheduler dispatch, not
  environment-confirmed state change.
- `assigned_manhattan_distance` is the distance from the worker to the target at
  assignment time. `movement_steps` and worker `movement_distance` count actual
  one-tile movement actions.
- A **productive action** is any emitted worker action that is neither movement nor
  `PASS`.
- `worker_utilization = (movement actions + productive actions) / worker turns`.
- `task_completion_ratio = executed task dispatches / task appearances`.
- `average_movement_per_productive_action = actual movement steps / productive
  actions`.
- Worker IDs are stable action-list slots: `0` is the farmer and `1..N` are daily
  hand slots. Hand identities are not persisted by the environment across days.
- `remaining_after_assignment` counts tasks left in the queue after all workers
  receive at most one target. `unexecuted_count` counts all input tasks that did not
  produce their task action during that step, including tasks assigned for travel.
- Daily idle workers count emitted `PASS` actions, including `seed_guard` passes.

## Fixed-seed regression check

With seed `20260829` against `starter`, the instrumented policy completed 720 steps
with reward `11408`, opponent reward `3262`, and margin `8146`. These match the
pre-instrumentation fixed-seed baseline and are a regression check only; they are
not an online leaderboard result.

The corresponding scheduler summary was:

| Metric | Value |
|---|---:|
| movement distance | 3283 |
| productive actions | 919 |
| PASS actions | 651 |
| worker utilization | 86.59% |
| task completion ratio | 9.08% |
| movement / productive action | 3.57 |
| seed-guard PASS | 2 |

The low task completion ratio is based on repeated per-step task appearances, so it
should be interpreted as scheduler pressure rather than the fraction of unique
farm jobs eventually completed.
