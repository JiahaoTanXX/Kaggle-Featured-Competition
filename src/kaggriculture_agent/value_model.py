"""Small dependency-free linear model for replay-derived crop utility.

This model is intentionally trained offline. The Kaggle policy can consume the
exported weights, but no LLM or training dependency is needed during a match.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


FEATURES = ("price_ratio", "town_demand", "remaining_days", "own_saturation", "opponent_saturation")


@dataclass
class LinearValueModel:
    weights: list[float]
    bias: float = 0.0

    @classmethod
    def zeros(cls) -> "LinearValueModel":
        return cls([0.0] * len(FEATURES), 0.0)

    def predict(self, features: list[float]) -> float:
        return self.bias + sum(w * x for w, x in zip(self.weights, features))

    def fit(
        self,
        rows: list[tuple[list[float], float]],
        epochs: int = 500,
        learning_rate: float = 0.02,
        l2: float = 0.001,
    ) -> "LinearValueModel":
        if not rows:
            raise ValueError("at least one training row is required")
        for _ in range(epochs):
            grad_w = [0.0] * len(self.weights)
            grad_b = 0.0
            for features, target in rows:
                error = self.predict(features) - target
                grad_b += error
                for i, value in enumerate(features):
                    grad_w[i] += error * value
            scale = 2.0 / len(rows)
            self.bias -= learning_rate * scale * grad_b
            for i in range(len(self.weights)):
                gradient = scale * grad_w[i] + 2.0 * l2 * self.weights[i]
                self.weights[i] -= learning_rate * gradient
        return self

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps({"features": FEATURES, "weights": self.weights, "bias": self.bias}, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "LinearValueModel":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if tuple(data.get("features", ())) != FEATURES:
            raise ValueError("feature schema mismatch")
        return cls([float(x) for x in data["weights"]], float(data.get("bias", 0.0)))
