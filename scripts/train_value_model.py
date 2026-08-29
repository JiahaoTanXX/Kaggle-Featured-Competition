#!/usr/bin/env python3
"""Fit the lightweight crop-value model from prepared JSONL rows.

Each row must contain the five named features and a numeric ``target``. Keep
training and evaluation seeds disjoint; this script deliberately does not infer
labels from leaderboard scores.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.kaggriculture_agent.value_model import FEATURES, LinearValueModel  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path, help="JSONL rows with named features and target")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "value_model.json")
    parser.add_argument("--epochs", type=int, default=500)
    args = parser.parse_args()

    rows = []
    for line_number, line in enumerate(args.dataset.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        try:
            features = [float(row[name]) for name in FEATURES]
            target = float(row["target"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit(f"invalid row {line_number}: {exc}") from exc
        rows.append((features, target))
    model = LinearValueModel.zeros().fit(rows, epochs=args.epochs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    model.save(args.output)
    print(json.dumps({"rows": len(rows), "output": str(args.output), "weights": model.weights, "bias": model.bias}))


if __name__ == "__main__":
    main()
