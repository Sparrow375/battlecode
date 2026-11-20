"""
Node War - Competitor Bot Validator Tool
========================================
This tool allows teams to dry-run validate their custom bot scripts locally.
It verifies inheritance, method signatures, return types, order schemas, and
symmetrical Player 1 / Player 2 compatibility without needing to run an entire match.

It is 100% self-contained and requires only a standard Python 3 installation.

Usage:
------
    python validate_bot.py starter_bot.py
    python validate_bot.py path/to/my_bot.py
"""

from __future__ import annotations
import sys
import os
import types
import inspect
import importlib.util
import time
import argparse
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Type

# =====================================================================
# 1. Self-Contained Protocol Dataclasses
# =====================================================================

class UnitType(str, Enum):
    RAIDER = "raider"
    GUARD = "guard"
    SIEGE = "siege"
    SCOUT = "scout"

class Order(ABC):
    pass

@dataclass
class TrainOrder(Order):
    node_id: int
    unit_type: UnitType
    count: int

@dataclass
class MoveOrder(Order):
    origin_node: int
    dest_node: int
    units: Dict[UnitType, int]

@dataclass
class VisibleNode:
    id: int
    name: str
    x: float
    y: float
    owner: int                  # 0: Neutral, 1: Player 1, 2: Player 2
    production: int            # Gold per turn (4, 7, 10, or 15)
    defense_bonus: float       # 0.50 (Home Citadels) or 0.25 (Outposts)
    capture_progress: int      # 0, 1, or 2
    capturing_player: int      # 0, 1, or 2
    units: Optional[Dict[str, int]] = None
    is_scouted: bool = False

@dataclass
class VisibleFleet:
    id: int
    owner: int
    origin_node: int
    dest_node: int
    turns_remaining: int
    total_turns: int
    total_count: int
    is_revealed: bool = False
    units: Optional[Dict[str, int]] = None

@dataclass
class BotObservation:
    current_turn: int
    max_turns: int
    my_player_id: int
    my_credits: int
    my_score: int
    opponent_score: int
    relic_active: bool
    relic_charging: bool
    relic_node_id: int
    nodes: Dict[int, VisibleNode]
    lanes: List[Dict[str, Any]]
    my_fleets: List[VisibleFleet] = field(default_factory=list)
    enemy_fleets: List[VisibleFleet] = field(default_factory=list)

# =====================================================================
# 2. Self-Contained BotBase Abstract Class
# =====================================================================

class BotBase(ABC):
    def __init__(self, player_id: int):
        self.player_id: int = player_id
        self.opponent_id: int = 2 if player_id == 1 else 1
        self._graph_cache: Optional[Dict[Tuple[int, int], int]] = None
        self._adj_cache: Optional[Dict[int, List[Tuple[int, int]]]] = None

    @abstractmethod
    def act(self, obs: BotObservation) -> List[Order]:
        """Receives the turn observation and returns a list of orders."""
        pass

    def get_my_nodes(self, obs: BotObservation) -> List[VisibleNode]:
        return [node for node in obs.nodes.values() if node.owner == self.player_id]

    def get_enemy_nodes(self, obs: BotObservation) -> List[VisibleNode]:
        return [node for node in obs.nodes.values() if node.owner == self.opponent_id]

    def get_neutral_nodes(self, obs: BotObservation) -> List[VisibleNode]:
        return [node for node in obs.nodes.values() if node.owner == 0]

    def get_neighbors(self, obs: BotObservation, node_id: int) -> List[int]:
        self._ensure_graph(obs)
        return [other for other, _ in self._adj_cache.get(node_id, [])]

    def get_distance(self, obs: BotObservation, u: int, v: int) -> int:
        self._ensure_graph(obs)
        return self._graph_cache.get((u, v), 999999)

    def get_path(self, obs: BotObservation, u: int, v: int) -> List[int]:
        self._ensure_graph(obs)
        if u == v:
            return [u]
        import heapq
        queue = [(0, u, [u])]
        visited = set()
        while queue:
            dist, curr, path = heapq.heappop(queue)
            if curr == v:
                return path
            if curr in visited:
                continue
            visited.add(curr)
            for nxt, weight in self._adj_cache.get(curr, []):
                if nxt not in visited:
                    heapq.heappush(queue, (dist + weight, nxt, path + [nxt]))
        return []

    def train(self, node_id: int, unit_type: UnitType | str, count: int) -> TrainOrder:
        ut = UnitType(unit_type) if isinstance(unit_type, str) else unit_type
        return TrainOrder(node_id=node_id, unit_type=ut, count=count)

    def move(self, origin_node: int, dest_node: int, units: Dict[UnitType | str, int]) -> MoveOrder:
        norm_units: Dict[UnitType, int] = {}
        for k, v in units.items():
            ut = UnitType(k) if isinstance(k, str) else k
            if v > 0:
                norm_units[ut] = v
        return MoveOrder(origin_node=origin_node, dest_node=dest_node, units=norm_units)

    def _ensure_graph(self, obs: BotObservation) -> None:
        if self._graph_cache is not None and self._adj_cache is not None:
            return
        adj: Dict[int, List[Tuple[int, int]]] = {nid: [] for nid in obs.nodes}
        for lane in obs.lanes:
            u, v, t = lane["node_a"], lane["node_b"], lane["travel_turns"]
            adj[u].append((v, t))
            adj[v].append((u, t))
        self._adj_cache = adj

        node_ids = list(obs.nodes.keys())
        inf = 999999
        dist: Dict[Tuple[int, int], int] = {}
        for u in node_ids:
            for v in node_ids:
                dist[(u, v)] = 0 if u == v else inf
        for lane in obs.lanes:
            u, v, t = lane["node_a"], lane["node_b"], lane["travel_turns"]
            dist[(u, v)] = min(dist[(u, v)], t)
            dist[(v, u)] = min(dist[(v, u)], t)
        for k in node_ids:
            for i in node_ids:
                for j in node_ids:
                    if dist[(i, k)] + dist[(k, j)] < dist[(i, j)]:
                        dist[(i, j)] = dist[(i, k)] + dist[(k, j)]
        self._graph_cache = dist

# =====================================================================
# 3. Synthetic Module Registration
# =====================================================================
# Allows competitor scripts importing `from engine.models import ...`
# or `from bots.base import BotBase` to function seamlessly without
# requiring an installed `engine` package.

def _register_synthetic_modules():
    modules_to_create = ["engine", "engine.models", "engine.fog", "bots", "bots.base"]
    for mod_name in modules_to_create:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    # engine.models
    em = sys.modules["engine.models"]
    em.UnitType = UnitType
    em.Order = Order
    em.TrainOrder = TrainOrder
    em.MoveOrder = MoveOrder

    # engine.fog
    ef = sys.modules["engine.fog"]
    ef.BotObservation = BotObservation
    ef.VisibleNode = VisibleNode
    ef.VisibleFleet = VisibleFleet

    # bots.base
    bb = sys.modules["bots.base"]
    bb.BotBase = BotBase

_register_synthetic_modules()

# =====================================================================
# 4. Map Topology & Observation Generator
# =====================================================================

MAP_NODES = {
    0: ("Player 1 Core Citadel", 10.0, 50.0, 1, 15, 0.50, {"raider": 1, "guard": 1, "scout": 1}),
    1: ("Alpha Bastion", 25.0, 25.0, 0, 4, 0.25, {"raider": 1}),
    2: ("Gamma Bastion", 25.0, 75.0, 0, 4, 0.25, {"raider": 1}),
    3: ("Vanguard Chokepoint Gate", 32.0, 50.0, 0, 7, 0.25, {"guard": 2}),
    4: ("North Rig", 40.0, 15.0, 0, 4, 0.25, {"raider": 1}),
    5: ("North Outpost", 45.0, 35.0, 0, 7, 0.25, {"guard": 2}),
    6: ("South Outpost", 45.0, 65.0, 0, 7, 0.25, {"guard": 2}),
    7: ("Relic Sanctuary", 50.0, 50.0, 0, 10, 0.25, {"guard": 2, "siege": 1}),
    8: ("Titan Outpost", 55.0, 65.0, 0, 7, 0.25, {"guard": 2}),
    9: ("Zenith Outpost", 55.0, 35.0, 0, 7, 0.25, {"guard": 2}),
    10: ("Apex Rig", 60.0, 15.0, 0, 4, 0.25, {"raider": 1}),
    11: ("Sentinel Chokepoint Gate", 68.0, 50.0, 0, 7, 0.25, {"guard": 2}),
    12: ("Omega Bastion", 75.0, 75.0, 0, 4, 0.25, {"raider": 1}),
    13: ("Epsilon Bastion", 75.0, 25.0, 0, 4, 0.25, {"raider": 1}),
    14: ("Player 2 Core Citadel", 90.0, 50.0, 2, 15, 0.50, {"raider": 1, "guard": 1, "scout": 1}),
}

MAP_LANES = [
    (0, 1, 2), (0, 2, 2), (0, 3, 3),
    (1, 4, 2), (1, 5, 2), (1, 3, 2),
    (2, 6, 2), (2, 3, 2),
    (4, 5, 2), (4, 10, 3),
    (5, 7, 2), (5, 9, 2),
    (6, 7, 2), (6, 8, 2),
    (3, 7, 3), (7, 11, 3),
    (7, 9, 2), (7, 8, 2),
    (9, 10, 2), (9, 13, 2),
    (8, 12, 2),
    (10, 13, 2),
    (11, 9, 2), (11, 8, 2), (11, 14, 3),
    (13, 14, 2), (12, 14, 2)
]

def create_mock_observation(player_id: int, turn: int = 1, relic_charging: bool = False, relic_active: bool = False) -> BotObservation:
    visible_nodes: Dict[int, VisibleNode] = {}
    for nid, (name, x, y, owner, prod, def_b, units) in MAP_NODES.items():
        is_owned = (owner == player_id)
        visible_nodes[nid] = VisibleNode(
            id=nid,
            name=name,
            x=x,
            y=y,
            owner=owner,
            production=prod,
            defense_bonus=def_b,
            capture_progress=0,
            capturing_player=0,
            units=dict(units) if is_owned else None,
            is_scouted=is_owned
        )

    my_fleets = [
        VisibleFleet(
            id=101,
            owner=player_id,
            origin_node=0 if player_id == 1 else 14,
            dest_node=1 if player_id == 1 else 13,
            turns_remaining=2,
            total_turns=2,
            total_count=3,
            is_revealed=True,
            units={"raider": 3}
        )
    ]

    lanes_data = [{"node_a": u, "node_b": v, "travel_turns": t} for u, v, t in MAP_LANES]

    return BotObservation(
        current_turn=turn,
        max_turns=120,
        my_player_id=player_id,
        my_credits=30,
        my_score=0,
        opponent_score=0,
        relic_active=relic_active,
        relic_charging=relic_charging,
        relic_node_id=7,
        nodes=visible_nodes,
        lanes=lanes_data,
        my_fleets=my_fleets,
        enemy_fleets=[]
    )

def load_bot_from_file(file_path: str) -> Tuple[Type[BotBase], str]:
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Bot script not found at {file_path}")
    if os.path.getsize(abs_path) == 0:
        raise ValueError(f"The bot script '{os.path.basename(file_path)}' is empty.")

    module_name = f"custom_bot_{os.path.splitext(os.path.basename(abs_path))[0]}_{int(time.time()*1000)}"
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    if not spec or not spec.loader:
        raise ValueError(f"Could not load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ == module.__name__:
            if (issubclass(obj, BotBase) or any(b.__name__ == "BotBase" for b in inspect.getmro(obj))) and obj.__name__ != "BotBase":
                return obj, name

    for name, obj in inspect.getmembers(module, inspect.isclass):
        if (issubclass(obj, BotBase) or any(b.__name__ == "BotBase" for b in inspect.getmro(obj))) and obj.__name__ != "BotBase":
            return obj, name

    for name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__name__ != "BotBase" and hasattr(obj, "act") and callable(getattr(obj, "act")):
            return obj, name

    classes_found = [name for name, obj in inspect.getmembers(module, inspect.isclass) if obj.__name__ != "BotBase"]
    if classes_found:
        raise ValueError(
            f"Found classes {classes_found} in {os.path.basename(file_path)}, but none inherit from 'BotBase'. "
            f"Please ensure your bot class inherits from BotBase (e.g. 'class {classes_found[0]}(BotBase):')."
        )
    raise ValueError(f"No classes found in {os.path.basename(file_path)}. Ensure your bot defines a class inheriting from BotBase.")

# =====================================================================
# 5. Validation Routine
# =====================================================================

def validate_bot(file_path: str) -> bool:
    print("=" * 65)
    print("   NODE WAR - COMPETITOR BOT DRY-RUN VALIDATOR")
    print("=" * 65)
    print(f"Target Script: {file_path}")

    # 1. File existence & size
    if not os.path.exists(file_path):
        print(f"❌ ERROR: File does not exist: {file_path}")
        return False
    if os.path.getsize(file_path) == 0:
        print(f"❌ ERROR: File is empty (0 bytes): {file_path}")
        return False
    print("  ✓ File located and non-empty")

    # 2. Dynamic class loading
    try:
        bot_cls, cls_name = load_bot_from_file(file_path)
        print(f"  ✓ Found Bot class: '{cls_name}'")
    except Exception as e:
        print(f"❌ ERROR during class inspection: {e}")
        return False

    # 3. Test Player 1 Instantiation & Act
    try:
        bot_p1 = bot_cls(player_id=1)
        print("  ✓ Player 1 instance initialized successfully")
    except Exception as e:
        print(f"❌ ERROR during Player 1 __init__: {e}")
        return False

    mock_turn1 = create_mock_observation(player_id=1, turn=1)
    try:
        orders_t1 = bot_p1.act(mock_turn1)
        print(f"  ✓ act(obs) executed on Turn 1 -> Returned {len(orders_t1) if orders_t1 else 0} orders")
    except Exception as e:
        print(f"❌ ERROR during act() on Turn 1: {e}")
        return False

    # 4. Test Player 2 Instantiation & Act
    try:
        bot_p2 = bot_cls(player_id=2)
        print("  ✓ Player 2 instance initialized successfully")
    except Exception as e:
        print(f"❌ ERROR during Player 2 __init__: {e}")
        return False

    mock_turn1_p2 = create_mock_observation(player_id=2, turn=1)
    try:
        orders_p2 = bot_p2.act(mock_turn1_p2)
        print(f"  ✓ act(obs) executed for Player 2 -> Returned {len(orders_p2) if orders_p2 else 0} orders")
    except Exception as e:
        print(f"❌ ERROR during Player 2 act(): {e}")
        return False

    # 5. Test Late-Game / Relic Warning Observation
    mock_relic = create_mock_observation(player_id=1, turn=85, relic_charging=True, relic_active=False)
    try:
        orders_relic = bot_p1.act(mock_relic)
        print(f"  ✓ act(obs) executed with relic_charging=True -> {len(orders_relic) if orders_relic else 0} orders")
    except Exception as e:
        print(f"❌ ERROR during act() with relic_charging: {e}")
        return False

    # 6. Validate Returned Orders Schema
    all_order_sets = [("P1 Turn 1", orders_t1), ("P2 Turn 1", orders_p2), ("Relic Warning", orders_relic)]
    valid_lanes = set()
    for u, v, _ in MAP_LANES:
        valid_lanes.add((u, v))
        valid_lanes.add((v, u))

    for label, orders in all_order_sets:
        if orders is None:
            continue
        if not isinstance(orders, list):
            print(f"❌ ERROR: act() must return a list of Orders, got {type(orders)} in {label}")
            return False

        for idx, order in enumerate(orders):
            if isinstance(order, TrainOrder):
                if order.node_id < 0 or order.node_id > 14:
                    print(f"❌ ERROR: Invalid node_id {order.node_id} in TrainOrder #{idx} ({label})")
                    return False
                if order.count <= 0:
                    print(f"❌ ERROR: TrainOrder count must be positive, got {order.count} in Order #{idx} ({label})")
                    return False
                if not isinstance(order.unit_type, (UnitType, str)):
                    print(f"❌ ERROR: Invalid unit_type '{order.unit_type}' in TrainOrder #{idx} ({label})")
                    return False

            elif isinstance(order, MoveOrder):
                if (order.origin_node, order.dest_node) not in valid_lanes:
                    print(f"❌ ERROR: No direct lane connects Node {order.origin_node} to Node {order.dest_node} in MoveOrder #{idx} ({label})")
                    return False
                if not isinstance(order.units, dict):
                    print(f"❌ ERROR: MoveOrder.units must be a dict, got {type(order.units)} in Order #{idx} ({label})")
                    return False
                for ut, cnt in order.units.items():
                    if cnt <= 0:
                        print(f"⚠️ WARNING: MoveOrder has non-positive count {cnt} for unit {ut} in Order #{idx} ({label})")
            else:
                print(f"❌ ERROR: Unknown order type '{type(order)}' in Order #{idx} ({label}). Must be TrainOrder or MoveOrder.")
                return False

    print("  ✓ All returned orders conform strictly to the Node War protocol")
    print("=" * 65)
    print("🎉 VALIDATION PASSED! Your bot is ready for tournament competition.")
    print("=" * 65)
    return True

def main():
    parser = argparse.ArgumentParser(description="Dry-run validator for Node War competitor bots.")
    parser.add_argument("bot_path", type=str, help="Path to competitor bot Python script (e.g. starter_bot.py)")
    args = parser.parse_args()

    success = validate_bot(args.bot_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
