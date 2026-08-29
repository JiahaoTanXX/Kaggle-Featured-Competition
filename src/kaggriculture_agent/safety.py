"""Output validation and fail-closed action sanitization."""

from __future__ import annotations

from typing import Any


UNIT_OPS = {
    "NORTH", "SOUTH", "EAST", "WEST", "PASS", "PICKUP", "PLACE", "DROP",
    "PLANT", "WATER", "HARVEST", "FERTILIZE", "BUILD_COOP", "BUILD_PASTURE",
    "FEED", "COLLECT_FERTILIZER", "CARE", "DIG",
}
MARKET_OPS = {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"}


def _unit_action(value: Any) -> list[Any]:
    if not isinstance(value, (list, tuple)) or not value:
        return ["PASS"]
    action = list(value)
    return action if str(action[0]) in UNIT_OPS else ["PASS"]


def sanitize(action: Any, hand_count: int) -> dict[str, list[Any]]:
    if not isinstance(action, dict):
        action = {}
    hands = list(action.get("hands", []) or [])
    safe_hands = [_unit_action(hands[i]) if i < len(hands) else ["PASS"] for i in range(hand_count)]
    market = []
    for order in list(action.get("market", []) or [])[:10]:
        if isinstance(order, (list, tuple)) and order and str(order[0]) in MARKET_OPS:
            market.append(list(order))
    return {
        "farmer": _unit_action(action.get("farmer", ["PASS"])),
        "hands": safe_hands,
        "market": market,
    }


def fallback(hand_count: int = 0) -> dict[str, list[Any]]:
    return {"farmer": ["PASS"], "hands": [["PASS"] for _ in range(hand_count)], "market": []}
