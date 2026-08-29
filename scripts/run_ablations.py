#!/usr/bin/env python3
"""Run the four declared policy ablations with paired seeds and both seats."""

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
from src.kaggriculture_agent import AgentConfig, Policy  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--opponent", default="starter", choices=["pass", "random", "starter"])
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--seed-start", type=int, default=20260829)
    parser.add_argument("--steps", type=int, default=720)
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "generated" / "ablations.csv")
    args = parser.parse_args()

    variants = json.loads((ROOT / "configs" / "ablations.json").read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for name, values in variants.items():
        policy = Policy(AgentConfig(**values))

        # kaggle-environments inspects callable signatures. Passing a bound
        # method makes it count ``self`` and incorrectly supply configuration
        # as a second argument, so keep the environment-facing wrapper unary.
        def variant_agent(obs):
            return policy.act(obs)

        for seed in range(args.seed_start, args.seed_start + args.seeds):
            for seat in (0, 1):
                lineup = [variant_agent, args.opponent] if seat == 0 else [args.opponent, variant_agent]
                env = make("kaggriculture", configuration={"episodeSteps": args.steps, "seed": seed}, debug=False)
                env.run(lineup)
                final = env.steps[-1]
                reward = float(final[seat].reward or 0)
                other = float(final[1 - seat].reward or 0)
                rows.append({
                    "variant": name,
                    "seed": seed,
                    "seat": seat,
                    "reward": reward,
                    "opponent_reward": other,
                    "margin": reward - other,
                    "won": reward > other,
                    "status": final[seat].status,
                })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {}
    for name in variants:
        subset = [row for row in rows if row["variant"] == name]
        margins = [float(row["margin"]) for row in subset]
        summary[name] = {
            "games": len(subset),
            "win_rate": sum(bool(row["won"]) for row in subset) / len(subset),
            "mean_margin": statistics.mean(margins),
            "margin_stdev": statistics.stdev(margins) if len(margins) > 1 else 0.0,
            "all_completed": all(row["status"] == "DONE" for row in subset),
        }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
