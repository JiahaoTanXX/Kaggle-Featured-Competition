"""Observation helpers kept dependency-free for Kaggle submission compatibility."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


CROP_STATS = {
    "WHEAT": {"seed": 10, "first": 2, "peak": 4, "base": 25, "ongoing": False},
    "CARROT": {"seed": 20, "first": 2, "peak": 3, "base": 35, "ongoing": False},
    "TOMATO": {"seed": 50, "first": 8, "peak": 11, "base": 60, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "peak": 16, "base": 120, "ongoing": True},
    "MELON": {"seed": 80, "first": 10, "peak": 10, "base": 250, "ongoing": False},
}

PRODUCTS = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)


def get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, Mapping):
        return dict(obj)
    try:
        return dict(obj)
    except (TypeError, ValueError):
        return {}


@dataclass(frozen=True)
class Snapshot:
    player: int
    step: int
    day: int
    hour: int
    me: Any
    opponent: Any
    private: Any
    market: Any
    town: Any
    board_size: int

    @classmethod
    def from_obs(cls, obs: Any) -> "Snapshot":
        player = int(get(obs, "player", 0))
        farms = list(get(obs, "farms", []) or [])
        me = farms[player] if player < len(farms) else {}
        opponent = farms[1 - player] if len(farms) > 1 else {}
        tiles = list(get(me, "tiles", []) or [])
        return cls(
            player=player,
            step=int(get(obs, "step", 0)),
            day=int(get(obs, "day", 0)),
            hour=int(get(obs, "hour", 0)),
            me=me,
            opponent=opponent,
            private=get(obs, "private", {}) or {},
            market=get(obs, "market", {}) or {},
            town=get(obs, "town", {}) or {},
            board_size=len(tiles) or 10,
        )

    @property
    def positions(self) -> list[tuple[int, int]]:
        farmer = tuple(get(self.me, "farmer", [4, 4]))
        hands = [tuple(pos) for pos in (get(self.me, "hands", []) or [])]
        return [farmer, *hands]

    @property
    def tiles(self) -> list[list[Any]]:
        return list(get(self.me, "tiles", []) or [])

    @property
    def seeds(self) -> dict[str, int]:
        return {k: int(v) for k, v in as_dict(get(self.private, "seeds", {})).items()}

    @property
    def shed(self) -> dict[str, int]:
        return {k: int(v) for k, v in as_dict(get(self.private, "shed", {})).items()}

    @property
    def prices(self) -> dict[str, int]:
        return {k: int(v) for k, v in as_dict(get(self.market, "prices", {})).items()}

    @property
    def money(self) -> float:
        return float(get(self.me, "money", 0.0))

    def tile_at(self, pos: tuple[int, int]) -> Any:
        x, y = pos
        if 0 <= y < len(self.tiles) and 0 <= x < len(self.tiles[y]):
            return self.tiles[y][x]
        return "LOCKED"

    def iter_unlocked(self):
        for y, row in enumerate(self.tiles):
            for x, tile in enumerate(row):
                if tile != "LOCKED":
                    yield (x, y), tile

    def crop_counts(self, farm: Any | None = None) -> dict[str, int]:
        farm = self.me if farm is None else farm
        result = {crop: 0 for crop in CROP_STATS}
        for row in list(get(farm, "tiles", []) or []):
            for tile in row:
                if isinstance(tile, Mapping) and get(tile, "kind") == "PLANT":
                    crop = str(get(tile, "crop", ""))
                    if crop in result:
                        result[crop] += 1
        return result


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def step_toward(start: tuple[int, int], target: tuple[int, int]) -> list[str]:
    sx, sy = start
    tx, ty = target
    if sx < tx:
        return ["EAST"]
    if sx > tx:
        return ["WEST"]
    if sy < ty:
        return ["SOUTH"]
    if sy > ty:
        return ["NORTH"]
    return ["PASS"]
