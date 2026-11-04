from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

class PlayerId(int, Enum):
    NONE = 0
    PLAYER_1 = 1
    PLAYER_2 = 2

    @property
    def opponent(self) -> PlayerId:
        if self == PlayerId.PLAYER_1:
            return PlayerId.PLAYER_2
        if self == PlayerId.PLAYER_2:
            return PlayerId.PLAYER_1
        return PlayerId.NONE

class UnitType(str, Enum):
    RAIDER = "raider"
    SIEGE = "siege"
    GUARD = "guard"
    SCOUT = "scout"

@dataclass(frozen=True)
class UnitStats:
    cost: int
    max_hp: int
    attack: int
    counters: Optional[UnitType]
    weak_to: Optional[UnitType]

UNIT_STATS: Dict[UnitType, UnitStats] = {
    UnitType.RAIDER: UnitStats(cost=10, max_hp=20, attack=12, counters=UnitType.SIEGE, weak_to=UnitType.GUARD),
    UnitType.SIEGE: UnitStats(cost=18, max_hp=35, attack=22, counters=UnitType.GUARD, weak_to=UnitType.RAIDER),
    UnitType.GUARD: UnitStats(cost=12, max_hp=30, attack=14, counters=UnitType.RAIDER, weak_to=UnitType.SIEGE),
    UnitType.SCOUT: UnitStats(cost=6, max_hp=10, attack=0, counters=None, weak_to=None),
}

@dataclass
class Fleet:
    id: int
    owner: PlayerId
    origin_node: int
    dest_node: int
    turns_remaining: int
    total_turns: int
    units: Dict[UnitType, int]

    @property
    def total_count(self) -> int:
        return sum(self.units.values())

    @property
    def has_scout(self) -> bool:
        return self.units.get(UnitType.SCOUT, 0) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "owner": int(self.owner),
            "origin_node": self.origin_node,
            "dest_node": self.dest_node,
            "turns_remaining": self.turns_remaining,
            "total_turns": self.total_turns,
            "units": {k.value: v for k, v in self.units.items()},
            "total_count": self.total_count,
        }

@dataclass
class Node:
    id: int
    name: str
    x: float
    y: float
    owner: PlayerId
    production: int
    units: Dict[UnitType, int] = field(default_factory=lambda: {
        UnitType.RAIDER: 0,
        UnitType.SIEGE: 0,
        UnitType.GUARD: 0,
        UnitType.SCOUT: 0
    })
    defense_bonus: float = 0.25
    capture_progress: int = 0
    capturing_player: PlayerId = PlayerId.NONE
    resident_player: PlayerId = PlayerId.NONE

    @property
    def total_units(self) -> int:
        return sum(self.units.values())

    @property
    def has_scout(self) -> bool:
        return self.units.get(UnitType.SCOUT, 0) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "owner": int(self.owner),
            "production": self.production,
            "units": {k.value: v for k, v in self.units.items()},
            "defense_bonus": self.defense_bonus,
            "capture_progress": self.capture_progress,
            "capturing_player": int(self.capturing_player),
            "resident_player": int(self.resident_player),
            "total_units": self.total_units,
        }

@dataclass(frozen=True)
class Lane:
    node_a: int
    node_b: int
    travel_turns: int

    def connects(self, u: int, v: int) -> bool:
        return (self.node_a == u and self.node_b == v) or (self.node_a == v and self.node_b == u)

    def get_other(self, u: int) -> Optional[int]:
        if self.node_a == u:
            return self.node_b
        if self.node_b == u:
            return self.node_a
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_a": self.node_a,
            "node_b": self.node_b,
            "travel_turns": self.travel_turns
        }

@dataclass
class TrainOrder:
    node_id: int
    unit_type: UnitType
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "train",
            "node_id": self.node_id,
            "unit_type": self.unit_type.value,
            "count": self.count
        }

@dataclass
class MoveOrder:
    origin_node: int
    dest_node: int
    units: Dict[UnitType, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "move",
            "origin_node": self.origin_node,
            "dest_node": self.dest_node,
            "units": {k.value: v for k, v in self.units.items()}
        }

Order = TrainOrder | MoveOrder

@dataclass
class GameConfig:
    max_turns: int = 120
    relic_spawn_turn: int = 95
    relic_node_id: int = 7
    relic_points_per_turn: int = 15
    relic_point_multiplier: int = 2
    free_upkeep_cap: int = 30
    upkeep_cost_per_unit: int = 1
    capture_turns_needed: int = 2
    defender_bonus: float = 0.25
    initial_credits: int = 30
    base_production: int = 15
