#!/usr/bin/env python3
"""Convert a raw Kaggle replay into the stable analyst schema."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kaggriculture_agent.replay import summarize_replay  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("replay", type=Path)
    parser.add_argument("--player", type=int, choices=[0, 1], default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = summarize_replay(json.loads(args.replay.read_text(encoding="utf-8")), args.player)
    output = args.output or args.replay.with_suffix(".summary.json")
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
