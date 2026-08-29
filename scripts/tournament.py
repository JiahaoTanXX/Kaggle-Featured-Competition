#!/usr/bin/env python3
"""Evaluate an agent against three official baselines on both seats."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kaggle_environments import make  # noqa: E402


def play(agent: str, opponent: str, seed: int, seat: int, steps: int) -> dict[str, object]:
    lineup = [agent, opponent] if seat == 0 else [opponent, agent]
    env = make("kaggriculture", configuration={"episodeSteps": steps, "seed": seed}, debug=False)
    env.run(lineup)
    final = env.steps[-1]
    reward = float(final[seat].reward or 0)
    other = float(final[1 - seat].reward or 0)
    return {
        "opponent": opponent,
        "seed": seed,
        "seat": seat,
        "reward": reward,
        "opponent_reward": other,
        "margin": reward - other,
        "won": reward > other,
        "status": final[seat].status,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="main.py")
    parser.add_argument("--opponents", nargs="+", default=["pass", "random", "starter"])
    parser.add_argument("--seeds", type=int, default=3, help="Number of consecutive seeds")
    parser.add_argument("--seed-start", type=int, default=20260829)
    parser.add_argument("--steps", type=int, default=720)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "generated" / "tournament.csv")
    args = parser.parse_args()

    agent = str((ROOT / args.agent).resolve()) if args.agent.endswith(".py") else args.agent
    rows = [
        play(agent, opponent, seed, seat, args.steps)
        for opponent in args.opponents
        for seed in range(args.seed_start, args.seed_start + args.seeds)
        for seat in (0, 1)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    margins = [float(row["margin"]) for row in rows]
    summary = {
        "games": len(rows),
        "wins": sum(bool(row["won"]) for row in rows),
        "win_rate": sum(bool(row["won"]) for row in rows) / len(rows),
        "mean_margin": statistics.mean(margins),
        "margin_stdev": statistics.stdev(margins) if len(margins) > 1 else 0.0,
        "all_completed": all(row["status"] == "DONE" for row in rows),
        "by_opponent": {},
    }
    for opponent in args.opponents:
        subset = [row for row in rows if row["opponent"] == opponent]
        summary["by_opponent"][opponent] = {
            "games": len(subset),
            "win_rate": sum(bool(row["won"]) for row in subset) / len(subset),
            "mean_margin": statistics.mean(float(row["margin"]) for row in subset),
        }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
