"""Market, resource, and opponent-aware crop planning."""

from __future__ import annotations

from collections import Counter

from .state import CROP_STATS, PRODUCTS, Snapshot, get
from .value_model import LinearValueModel


SHOP_DEMAND = {
    "BAKERY": {"WHEAT": 1, "EGG": 1},
    "PIZZA_SHOP": {"WHEAT": 1, "TOMATO": 1, "MILK": 1},
    "BRUNCH_SPOT": {"WHEAT": 1, "EGG": 1, "STRAWBERRY": 1},
    "YARN_STORE": {"WOOL": 2},
    "ICE_CREAM_SHOP": {"WHEAT": 1, "STRAWBERRY": 1, "MILK": 1},
    "PET_CAFE": {"CARROT": 2},
    "SMOOTHIE_SHOP": {"STRAWBERRY": 1, "MILK": 1},
    "FARMERS_MARKET": {"WHEAT": 1, "CARROT": 1, "TOMATO": 1, "STRAWBERRY": 1},
}


def demand_scores(snapshot: Snapshot) -> Counter[str]:
    demand: Counter[str] = Counter({crop: 1 for crop in CROP_STATS})
    for shop in list(get(snapshot.town, "unlocked_shops", []) or []):
        normalized = str(shop).upper().replace(" ", "_")
        demand.update(SHOP_DEMAND.get(normalized, {}))
    return demand


def choose_crop_mix(
    snapshot: Snapshot,
    target_tiles: int,
    opponent_aware: bool = True,
    value_model: LinearValueModel | None = None,
) -> list[str]:
    """Rank crops by price, time remaining, demand, and opponent saturation."""
    remaining_days = max(0, 30 - snapshot.day)
    demand = demand_scores(snapshot)
    mine = snapshot.crop_counts()
    theirs = snapshot.crop_counts(snapshot.opponent)
    scored: list[tuple[float, str]] = []

    for crop, stats in CROP_STATS.items():
        if remaining_days <= int(stats["first"]) + 1:
            continue
        price = snapshot.prices.get(crop, int(stats["base"]))
        cycle = max(2, int(stats["first"]))
        score = price / float(stats["seed"]) / cycle
        score *= 1.0 + 0.18 * min(demand[crop], 5)
        if crop == "WHEAT":
            score *= 1.35  # liquidity and future animal feed option
        if stats["ongoing"] and remaining_days < int(stats["peak"]) + 2:
            score *= 0.35
        if opponent_aware:
            score *= 1.0 / (1.0 + 0.025 * theirs[crop])
        score *= 1.0 / (1.0 + 0.02 * mine[crop])
        if value_model is not None:
            features = [
                price / float(stats["base"]),
                min(demand[crop], 5) / 5.0,
                remaining_days / 30.0,
                mine[crop] / 25.0,
                theirs[crop] / 25.0,
            ]
            score *= max(0.5, 1.0 + value_model.predict(features))
        scored.append((score, crop))

    scored.sort(reverse=True)
    if not scored:
        return []
    # Diversify between the top two products to reduce market glut risk.
    top = [crop for _, crop in scored[:2]]
    return [top[i % len(top)] for i in range(target_tiles)]


def market_orders(
    snapshot: Snapshot,
    crop_plan: list[str],
    hire_target: int,
    enable_market: bool = True,
) -> list[list[object]]:
    if not enable_market:
        return []

    orders: list[list[object]] = []
    # Liquidate storage first so later purchases cannot consume sale capital.
    for product in PRODUCTS:
        amount = snapshot.shed.get(product, 0)
        if amount > 0:
            orders.append(["SELL", product, amount])

    needed = Counter(crop_plan)
    needed.subtract(snapshot.crop_counts())
    for crop in CROP_STATS:
        deficit = max(0, needed[crop] - snapshot.seeds.get(crop, 0))
        if deficit:
            affordable = int(snapshot.money // int(CROP_STATS[crop]["seed"]))
            quantity = min(deficit, affordable, 12)
            if quantity > 0:
                orders.append(["BUY_SEED", crop, quantity])

    current_hands = len(get(snapshot.me, "hands", []) or [])
    if snapshot.hour == 0 and current_hands < hire_target and snapshot.money > 100:
        for _ in range(hire_target - current_hands):
            orders.append(["HIRE"])

    return orders[:10]
