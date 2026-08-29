#!/usr/bin/env python3
"""Run one reproducible match and write replay plus structured summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kaggle_environments import make  # noqa: E402
from src.kaggriculture_agent.replay import summarize_replay  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="main.py")
    parser.add_argument("--opponent", default="starter", choices=["pass", "random", "starter"])
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument("--steps", type=int, default=720)
    parser.add_argument("--output", type=Path, default=ROOT / "replays" / "latest.json")
    args = parser.parse_args()

    agent_path = str((ROOT / args.agent).resolve()) if args.agent.endswith(".py") else args.agent
    env = make("kaggriculture", configuration={"episodeSteps": args.steps, "seed": args.seed}, debug=True)
    env.run([agent_path, args.opponent])
    replay = env.toJSON()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(replay), encoding="utf-8")
    summary_path = args.output.with_suffix(".summary.json")
    summary = summarize_replay(replay, 0)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
