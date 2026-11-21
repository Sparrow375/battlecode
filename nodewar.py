"""
Node War - Official Competitor SDK, Simulator & Validation Toolkit
==================================================================
This self-contained module provides everything competitor teams and AI agents
need to build, validate, and locally simulate Node War bots:
  1. Protocol Dataclasses (UnitType, Order, TrainOrder, MoveOrder, VisibleNode, VisibleFleet, BotObservation)
  2. BotBase Abstract Base Class with built-in pathfinding, distance lookups, and order factories
  3. Lanchester Combat Resolution & Damage Simulator Helpers
  4. Complete Local Game Simulator (NodeWarSimulator / simulate_match)
  5. Built-in Baseline Opponents (RusherBot, TurtleBot, BalancedBot, StarterBot)
  6. Dry-run Bot Validator (validate_bot)
  7. CLI for validation and local match simulation

Usage:
------
    # Validate a bot script:
    python nodewar.py validate my_bot.py
    python nodewar.py my_bot.py

    # Simulate a local match against a baseline bot:
    python nodewar.py simulate my_bot.py rusher
    python nodewar.py simulate my_bot.py turtle --turns 120 --seed 42

    # Run a Best-of-3 series with alternating seats:
    python nodewar.py bo3 my_bot.py balanced

    # Import types and BotBase in your bot:
    from nodewar import BotBase, BotObservation, Order, TrainOrder, MoveOrder, UnitType
"""

from __future__ import annotations
import sys
import os
import types
import inspect
import importlib.util
import time
import math
import random
import heapq
import argparse
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Type

# =====================================================================
# 1. Protocol Types & Dataclasses
# =====================================================================

try:
    from engine.models import (
        UnitType,
        UnitStats,
        UNIT_STATS,
        Order,
        TrainOrder,
        MoveOrder,
    )
    from engine.fog import VisibleNode, VisibleFleet, BotObservation
except ImportError:
    class UnitType(str, Enum):
        RAIDER = "raider"
        GUARD = "guard"
        SIEGE = "siege"
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
        UnitType.GUARD: UnitStats(cost=12, max_hp=30, attack=14, counters=UnitType.RAIDER, weak_to=UnitType.SIEGE),
        UnitType.SIEGE: UnitStats(cost=18, max_hp=35, attack=22, counters=UnitType.GUARD, weak_to=UnitType.RAIDER),
        UnitType.SCOUT: UnitStats(cost=6, max_hp=10, attack=0, counters=None, weak_to=None),
    }

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
        production: int             # Gold per turn (+4, +7, +10, or +15)
        defense_bonus: float        # 0.50 (Home Citadels) or 0.25 (Outposts)
        capture_progress: int       # 0, 1, or 2
        capturing_player: int       # 0: None, 1: Player 1, 2: Player 2
        units: Optional[Dict[str, int]] = None  # None if fog masked; dict of counts if visible
        is_scouted: bool = False

        def to_dict(self) -> Dict[str, Any]:
            return {
                "id": self.id,
                "name": self.name,
                "x": self.x,
                "y": self.y,
                "owner": self.owner,
                "production": self.production,
                "defense_bonus": self.defense_bonus,
                "capture_progress": self.capture_progress,
                "capturing_player": self.capturing_player,
                "units": self.units,
                "is_scouted": self.is_scouted
            }

    @dataclass
    class VisibleFleet:
        id: int
        owner: int                  # 1: Player 1, 2: Player 2
        origin_node: int
        dest_node: int
        turns_remaining: int
        total_turns: int
        total_count: int            # Always visible radar silhouette
        is_revealed: bool = False   # True if composition unmasked by scout
        units: Optional[Dict[str, int]] = None  # None if obscured

        def to_dict(self) -> Dict[str, Any]:
            return {
                "id": self.id,
                "owner": self.owner,
                "origin_node": self.origin_node,
                "dest_node": self.dest_node,
                "turns_remaining": self.turns_remaining,
                "total_turns": self.total_turns,
                "total_count": self.total_count,
                "is_revealed": self.is_revealed,
                "units": self.units
            }

    @dataclass
    class BotObservation:
        current_turn: int
        max_turns: int
        my_player_id: int
        my_credits: int             # Treasury Gold at observation time
        my_score: int               # Accumulated Victory Points
        opponent_score: int
        relic_active: bool
        relic_charging: bool        # 5-turn warning alert before activation
        relic_node_id: int          # Node 7
        nodes: Dict[int, VisibleNode]
        lanes: List[Dict[str, Any]]
        my_fleets: List[VisibleFleet] = field(default_factory=list)
        enemy_fleets: List[VisibleFleet] = field(default_factory=list)

        def to_dict(self) -> Dict[str, Any]:
            return {
                "current_turn": self.current_turn,
                "max_turns": self.max_turns,
                "my_player_id": self.my_player_id,
                "my_credits": self.my_credits,
                "my_score": self.my_score,
                "opponent_score": self.opponent_score,
                "relic_active": self.relic_active,
                "relic_charging": self.relic_charging,
                "relic_node_id": self.relic_node_id,
                "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
                "lanes": self.lanes,
                "my_fleets": [f.to_dict() for f in self.my_fleets],
                "enemy_fleets": [f.to_dict() for f in self.enemy_fleets],
            }

# =====================================================================
# 2. BotBase Abstract Class
# =====================================================================

class BotBase(ABC):
    """
    Abstract base class for all Node War competitor bots.
    Provides cached graph traversal, shortest path calculation, and order builders.
    """
    def __init__(self, player_id: int):
        self.player_id: int = player_id
        self.opponent_id: int = 2 if player_id == 1 else 1
        self._graph_cache: Optional[Dict[Tuple[int, int], int]] = None
        self._adj_cache: Optional[Dict[int, List[Tuple[int, int]]]] = None

    @abstractmethod
    def act(self, obs: BotObservation) -> List[Order]:
        """
        Receives turn observation and returns a list of TrainOrder and MoveOrder objects.
        Must complete within 50 ms wall-clock time.
        """
        pass

    def get_my_nodes(self, obs: BotObservation) -> List[VisibleNode]:
        """Returns all nodes currently owned by this player."""
        return [node for node in obs.nodes.values() if node.owner == self.player_id]

    def get_enemy_nodes(self, obs: BotObservation) -> List[VisibleNode]:
        """Returns all nodes currently owned by the opponent."""
        return [node for node in obs.nodes.values() if node.owner == self.opponent_id]

    def get_neutral_nodes(self, obs: BotObservation) -> List[VisibleNode]:
        """Returns all unowned neutral nodes."""
        return [node for node in obs.nodes.values() if node.owner == 0]

    def get_neighbors(self, obs: BotObservation, node_id: int) -> List[int]:
        """Returns a list of node IDs directly connected to node_id by a lane."""
        self._ensure_graph(obs)
        return [other for other, _ in self._adj_cache.get(node_id, [])]

    def get_distance(self, obs: BotObservation, u: int, v: int) -> int:
        """Returns the shortest path travel time (turns) between nodes u and v."""
        self._ensure_graph(obs)
        return self._graph_cache.get((u, v), 999999)

    def get_path(self, obs: BotObservation, u: int, v: int) -> List[int]:
        """
        Returns the shortest path sequence of node IDs from u to v.
        Example: [0, 1, 5, 7]. Returns [u] if u == v, or [] if no path exists.
        """
        self._ensure_graph(obs)
        if u == v:
            return [u]
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
        """Creates a TrainOrder for recruiting units at an owned, uncontested node."""
        ut = UnitType(unit_type) if isinstance(unit_type, str) else unit_type
        return TrainOrder(node_id=node_id, unit_type=ut, count=count)

    def move(self, origin_node: int, dest_node: int, units: Dict[UnitType | str, int]) -> MoveOrder:
        """Creates a MoveOrder to dispatch mobilized units along a directly connected lane."""
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
# 3. Combat Simulation Helpers (Faithful Lanchester Resolution)
# =====================================================================

def calculate_damage(
    attacker_units: Dict[UnitType, int],
    defender_units: Dict[UnitType, int],
    has_friendly_scout: bool = False,
    has_enemy_scout: bool = False
) -> float:
    """
    Calculates total outgoing damage from attacker_units targeted against defender_units.
    Uses proportional weighting based on defender army composition:
      eff_mult = (2.0 * counter_targets + 1.0 * neutral_targets + 0.5 * weak_targets) / total_defenders
    Applies +15% targeting bonus if friendly scout is present/adjacent, or -15% blind penalty
    if fighting blindly against a scouted enemy army.
    """
    total_defender_count = sum(defender_units.values())
    if total_defender_count == 0:
        return 0.0

    total_damage = 0.0
    for u_type, count in attacker_units.items():
        if count <= 0:
            continue
        stats = UNIT_STATS[u_type]
        base_power = count * stats.attack

        counters = stats.counters
        weak_to = stats.weak_to

        counter_targets = defender_units.get(counters, 0) if counters else 0
        weak_targets = defender_units.get(weak_to, 0) if weak_to else 0
        neutral_targets = total_defender_count - counter_targets - weak_targets

        eff_mult = (2.0 * counter_targets + 1.0 * neutral_targets + 0.5 * weak_targets) / total_defender_count
        total_damage += base_power * eff_mult

    if has_friendly_scout:
        total_damage *= 1.15
    elif has_enemy_scout:
        total_damage *= 0.85

    return total_damage

def apply_damage_to_army(
    army: Dict[UnitType, int],
    damage: float,
    damage_reduction: float = 0.0
) -> Dict[UnitType, int]:
    """
    Applies incoming damage to an army, distributing casualties proportionally by HP.
    damage_reduction: e.g. 0.25 (25% reduction for outposts) or 0.50 (50% reduction for core).
    """
    effective_damage = damage * (1.0 - damage_reduction)
    if effective_damage <= 0 or sum(army.values()) == 0:
        return dict(army)

    total_hp = sum(count * UNIT_STATS[ut].max_hp for ut, count in army.items())
    if effective_damage >= total_hp:
        return {ut: 0 for ut in army}

    remaining_army = dict(army)
    damage_share_ratio = effective_damage / total_hp

    carried_damage = 0.0
    for ut in [UnitType.RAIDER, UnitType.SIEGE, UnitType.GUARD, UnitType.SCOUT]:
        count = remaining_army.get(ut, 0)
        if count <= 0:
            continue
        hp_per_unit = UNIT_STATS[ut].max_hp
        type_damage = (count * hp_per_unit) * damage_share_ratio + carried_damage
        lost_units = int(type_damage // hp_per_unit)
        rem = type_damage % hp_per_unit

        if rem >= (hp_per_unit * 0.5) and lost_units < count:
            lost_units += 1
            carried_damage = 0.0
        else:
            carried_damage = rem

        lost_units = min(count, lost_units)
        remaining_army[ut] = count - lost_units

    return remaining_army

def resolve_combat(
    defenders: Dict[UnitType, int],
    attackers: Dict[UnitType, int],
    defender_bonus: float = 0.25,
    max_rounds: int = 10,
    has_defender_scout: bool = False,
    has_attacker_scout: bool = False
) -> Tuple[Dict[UnitType, int], Dict[UnitType, int]]:
    """
    Simulates combat resolution between defenders and attackers for up to max_rounds (10).
    Returns (surviving_defenders, surviving_attackers).
    If defenders survive after max_rounds, remaining attackers are eliminated.
    """
    cur_defenders = dict(defenders)
    cur_attackers = dict(attackers)

    def_scout = has_defender_scout or (cur_defenders.get(UnitType.SCOUT, 0) > 0)
    att_scout = has_attacker_scout or (cur_attackers.get(UnitType.SCOUT, 0) > 0)

    for _ in range(max_rounds):
        def_combat_count = cur_defenders.get(UnitType.RAIDER, 0) + cur_defenders.get(UnitType.SIEGE, 0) + cur_defenders.get(UnitType.GUARD, 0)
        att_combat_count = cur_attackers.get(UnitType.RAIDER, 0) + cur_attackers.get(UnitType.SIEGE, 0) + cur_attackers.get(UnitType.GUARD, 0)

        if def_combat_count == 0 or att_combat_count == 0:
            break

        def_damage = calculate_damage(cur_defenders, cur_attackers, has_friendly_scout=def_scout, has_enemy_scout=att_scout)
        att_damage = calculate_damage(cur_attackers, cur_defenders, has_friendly_scout=att_scout, has_enemy_scout=def_scout)

        new_defenders = apply_damage_to_army(cur_defenders, att_damage, damage_reduction=defender_bonus)
        new_attackers = apply_damage_to_army(cur_attackers, def_damage, damage_reduction=0.0)

        if new_defenders == cur_defenders and new_attackers == cur_attackers:
            if def_damage >= att_damage:
                for ut in [UnitType.RAIDER, UnitType.SIEGE, UnitType.GUARD]:
                    if new_attackers.get(ut, 0) > 0:
                        new_attackers[ut] -= 1
                        break
            else:
                for ut in [UnitType.RAIDER, UnitType.SIEGE, UnitType.GUARD]:
                    if new_defenders.get(ut, 0) > 0:
                        new_defenders[ut] -= 1
                        break

        cur_defenders = new_defenders
        cur_attackers = new_attackers

    def_combat = cur_defenders.get(UnitType.RAIDER, 0) + cur_defenders.get(UnitType.SIEGE, 0) + cur_defenders.get(UnitType.GUARD, 0)
    att_combat = cur_attackers.get(UnitType.RAIDER, 0) + cur_attackers.get(UnitType.SIEGE, 0) + cur_attackers.get(UnitType.GUARD, 0)

    if def_combat == 0 and att_combat > 0:
        cur_defenders[UnitType.SCOUT] = 0
    elif att_combat == 0 and def_combat > 0:
        cur_attackers[UnitType.SCOUT] = 0

    return cur_defenders, cur_attackers

def resolve_meeting_engagement(
    side_a: Dict[UnitType, int],
    side_b: Dict[UnitType, int],
    has_a_scout: bool = False,
    has_b_scout: bool = False
) -> Tuple[Dict[UnitType, int], Dict[UnitType, int]]:
    """Simulates a neutral meeting engagement with 0% defender bonus."""
    return resolve_combat(side_a, side_b, defender_bonus=0.0, has_defender_scout=has_a_scout, has_attacker_scout=has_b_scout)

# =====================================================================
# 4. Map Graph & Complete Topology
# =====================================================================

MAP_NODES: Dict[int, Tuple[str, float, float, int, int, float, Dict[str, int]]] = {
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

MAP_LANES: List[Tuple[int, int, int]] = [
    # P1 local web (11 lanes)
    (0, 1, 2), (0, 2, 2), (0, 3, 3),
    (1, 3, 2), (2, 3, 2),
    (1, 4, 2), (1, 5, 2), (2, 6, 2),
    (4, 5, 2), (3, 5, 2), (3, 6, 2),

    # Center bridge lanes (6 lanes)
    (5, 7, 2), (6, 7, 2), (3, 7, 3),
    (5, 9, 2), (6, 8, 2), (4, 10, 3),

    # P2 local web (11 lanes)
    (14, 13, 2), (14, 12, 2), (14, 11, 3),
    (13, 11, 2), (12, 11, 2),
    (13, 10, 2), (13, 9, 2), (12, 8, 2),
    (10, 9, 2), (11, 9, 2), (11, 8, 2),

    # P2 to Center (3 lanes)
    (9, 7, 2), (8, 7, 2), (11, 7, 3),
]

# =====================================================================
# 5. Synthetic Module Registration (Full Backward Compatibility)
# =====================================================================

def _register_synthetic_modules():
    # If the real engine package is already loaded, do not overwrite it!
    if "engine.models" in sys.modules and getattr(sys.modules["engine.models"], "__file__", None):
        return

    modules_to_create = ["engine", "engine.models", "engine.fog", "engine.combat", "bots", "bots.base", "nodewar"]
    for mod_name in modules_to_create:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    em = sys.modules["engine.models"]
    if not hasattr(em, "UnitType"):
        em.UnitType = UnitType
        em.Order = Order
        em.TrainOrder = TrainOrder
        em.MoveOrder = MoveOrder
        em.UNIT_STATS = UNIT_STATS
        em.UnitStats = UnitStats

    ef = sys.modules["engine.fog"]
    if not hasattr(ef, "BotObservation"):
        ef.BotObservation = BotObservation
        ef.VisibleNode = VisibleNode
        ef.VisibleFleet = VisibleFleet

    ec = sys.modules["engine.combat"]
    if not hasattr(ec, "calculate_damage"):
        ec.calculate_damage = calculate_damage
        ec.apply_damage_to_army = apply_damage_to_army
        ec.resolve_combat = resolve_combat
        ec.resolve_meeting_engagement = resolve_meeting_engagement

    bb = sys.modules["bots.base"]
    if not hasattr(bb, "BotBase"):
        bb.BotBase = BotBase

    nw = sys.modules["nodewar"]
    nw.BotBase = BotBase
    nw.UnitType = UnitType
    nw.Order = Order
    nw.TrainOrder = TrainOrder
    nw.MoveOrder = MoveOrder
    nw.VisibleNode = VisibleNode
    nw.VisibleFleet = VisibleFleet
    nw.BotObservation = BotObservation
    nw.UNIT_STATS = UNIT_STATS
    nw.calculate_damage = calculate_damage
    nw.resolve_combat = resolve_combat

_register_synthetic_modules()

# =====================================================================
# 6. Built-in Baseline Opponent Bots
# =====================================================================

class StarterBot(BotBase):
    """Reference starter bot template using balanced Raider exploration and Guard Relic defense."""
    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        credits = obs.my_credits
        home_id = 0 if self.player_id == 1 else 14
        home_node = next((n for n in my_nodes if n.id == home_id), my_nodes[0])

        if credits >= 20 and home_node.capturing_player == 0:
            orders.append(self.train(home_node.id, UnitType.RAIDER, 1))
            credits -= 10

        neutral_nodes = self.get_neutral_nodes(obs)
        if neutral_nodes and home_node.units:
            closest_neutral = min(neutral_nodes, key=lambda n: self.get_distance(obs, home_node.id, n.id))
            stationed_raiders = home_node.units.get("raider", 0)
            if stationed_raiders >= 3:
                path = self.get_path(obs, home_node.id, closest_neutral.id)
                if len(path) >= 2:
                    orders.append(self.move(home_node.id, path[1], {UnitType.RAIDER: 2}))

        if obs.relic_charging or obs.relic_active:
            relic_id = obs.relic_node_id
            for node in my_nodes:
                guards = node.units.get("guard", 0) if node.units else 0
                if guards >= 3:
                    path = self.get_path(obs, node.id, relic_id)
                    if len(path) >= 2:
                        orders.append(self.move(node.id, path[1], {UnitType.GUARD: 2}))

        return orders

CompetitorBot = StarterBot

class RusherBot(BotBase):
    """Pure Raider swarm blitzkrieg bot prioritizing speed and early pressure."""
    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        home_id = 0 if self.player_id == 1 else 14
        home_node = next((n for n in my_nodes if n.id == home_id), my_nodes[0])
        credits = obs.my_credits

        num_raiders = credits // 10
        if num_raiders > 0 and home_node.capturing_player == 0:
            orders.append(self.train(home_node.id, UnitType.RAIDER, num_raiders))

        target_id = obs.relic_node_id if (obs.relic_active or obs.relic_charging) else (14 if self.player_id == 1 else 0)

        for node in my_nodes:
            raiders = node.units.get("raider", 0) if node.units else 0
            if raiders > 0:
                path = self.get_path(obs, node.id, target_id)
                if len(path) >= 2:
                    orders.append(self.move(node.id, path[1], {UnitType.RAIDER: raiders}))

        return orders

class TurtleBot(BotBase):
    """Defensive fortification bot recruiting Guards and anchoring Relic Sanctuary."""
    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        home_id = 0 if self.player_id == 1 else 14
        home_node = next((n for n in my_nodes if n.id == home_id), my_nodes[0])
        credits = obs.my_credits

        num_guards = credits // 12
        if num_guards > 0 and home_node.capturing_player == 0:
            orders.append(self.train(home_node.id, UnitType.GUARD, num_guards))

        choke_target = 3 if self.player_id == 1 else 11
        if obs.relic_charging or obs.relic_active:
            choke_target = obs.relic_node_id

        for node in my_nodes:
            if node.id == choke_target:
                continue
            guards = node.units.get("guard", 0) if node.units else 0
            if guards >= 3:
                path = self.get_path(obs, node.id, choke_target)
                if len(path) >= 2:
                    orders.append(self.move(node.id, path[1], {UnitType.GUARD: guards - 1}))

        return orders

class BalancedBot(BotBase):
    """Tactical Recon & Siege artillery bot deploying Scouts for vision and Siege for firepower."""
    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        home_id = 0 if self.player_id == 1 else 14
        home_node = next((n for n in my_nodes if n.id == home_id), my_nodes[0])
        credits = obs.my_credits

        has_scouts = any(f.units and f.units.get("scout", 0) > 0 for f in obs.my_fleets)
        for n in my_nodes:
            if n.units and n.units.get("scout", 0) > 0:
                has_scouts = True

        if not has_scouts and credits >= 6 and home_node.capturing_player == 0:
            orders.append(self.train(home_node.id, UnitType.SCOUT, 1))
            credits -= 6

        if credits >= 18 and home_node.capturing_player == 0:
            orders.append(self.train(home_node.id, UnitType.SIEGE, 1))
            credits -= 18

        for node in my_nodes:
            scouts = node.units.get("scout", 0) if node.units else 0
            if scouts > 0:
                forward_target = obs.relic_node_id
                path = self.get_path(obs, node.id, forward_target)
                if len(path) >= 2:
                    orders.append(self.move(node.id, path[1], {UnitType.SCOUT: 1}))

            siege = node.units.get("siege", 0) if node.units else 0
            if siege >= 2:
                target = obs.relic_node_id if (obs.relic_active or obs.relic_charging) else (3 if self.player_id == 1 else 11)
                path = self.get_path(obs, node.id, target)
                if len(path) >= 2:
                    orders.append(self.move(node.id, path[1], {UnitType.SIEGE: siege}))

        return orders

BUILTIN_BOTS: Dict[str, Type[BotBase]] = {
    "starter": StarterBot,
    "competitor": CompetitorBot,
    "rusher": RusherBot,
    "turtle": TurtleBot,
    "balanced": BalancedBot,
}

# =====================================================================
# 7. Local Match Simulator Engine
# =====================================================================

@dataclass
class InternalNode:
    id: int
    name: str
    x: float
    y: float
    owner: int
    production: int
    defense_bonus: float
    capture_progress: int = 0
    capturing_player: int = 0
    units: Dict[UnitType, int] = field(default_factory=dict)
    resident_player: int = 0

@dataclass
class InternalFleet:
    id: int
    owner: int
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

class LocalSimulator:
    """
    100% self-contained local simulator for Node War matches.
    Matches all official tournament engine mechanics deterministically.
    """
    def __init__(self, max_turns: int = 120, seed: Optional[int] = None, relic_spawn_turn: Optional[int] = None):
        self.max_turns = max_turns
        self.seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        self.rng = random.Random(self.seed)

        if relic_spawn_turn is not None:
            self.relic_spawn_turn = relic_spawn_turn
        else:
            self.relic_spawn_turn = self.rng.randint(80, 100)

        self.current_turn = 1
        self.game_over = False
        self.winner = 0
        self.win_reason = ""
        self.relic_active = False
        self.relic_charging = False
        self.relic_node_id = 7
        self.relic_turns_held = {1: 0, 2: 0}
        self.scores = {1: 0, 2: 0}
        self.player_credits = {1: 30, 2: 30}
        self.fleets: List[InternalFleet] = []
        self._next_fleet_id = 1
        self.history: List[Dict[str, Any]] = []

        # Initialize nodes
        self.nodes: Dict[int, InternalNode] = {}
        for nid, (name, x, y, owner, prod, def_b, units) in MAP_NODES.items():
            garrison = {ut: units.get(ut.value, 0) for ut in UnitType}
            self.nodes[nid] = InternalNode(
                id=nid,
                name=name,
                x=x,
                y=y,
                owner=owner,
                production=prod,
                defense_bonus=def_b,
                units=garrison,
                resident_player=owner
            )

        # Precompute graph
        self.lanes = MAP_LANES
        self.adj: Dict[int, List[Tuple[int, int]]] = {nid: [] for nid in self.nodes}
        self.lane_lookup: Dict[Tuple[int, int], int] = {}
        for u, v, t in self.lanes:
            self.adj[u].append((v, t))
            self.adj[v].append((u, t))
            self.lane_lookup[(u, v)] = t
            self.lane_lookup[(v, u)] = t

    def get_player_observation(self, pid: int) -> BotObservation:
        opp_id = 2 if pid == 1 else 1
        is_charging = (self.relic_spawn_turn - 5 <= self.current_turn < self.relic_spawn_turn)
        is_active = (self.current_turn >= self.relic_spawn_turn)

        scouted_nodes = set()
        for nid, node in self.nodes.items():
            if node.owner == pid:
                scouted_nodes.add(nid)
            elif node.units.get(UnitType.SCOUT, 0) > 0 and node.resident_player == pid:
                scouted_nodes.add(nid)

        scouted_lanes = set()
        for fleet in self.fleets:
            if fleet.owner == pid and fleet.has_scout:
                scouted_lanes.add((fleet.origin_node, fleet.dest_node))
                scouted_lanes.add((fleet.dest_node, fleet.origin_node))

        for nid in scouted_nodes:
            if self.nodes[nid].units.get(UnitType.SCOUT, 0) > 0:
                for other, _ in self.adj[nid]:
                    scouted_lanes.add((nid, other))
                    scouted_lanes.add((other, nid))

        visible_nodes: Dict[int, VisibleNode] = {}
        for nid, node in self.nodes.items():
            is_scouted = (node.owner == pid) or (nid in scouted_nodes)
            adjacent_visibility = any(other in scouted_nodes for other, _ in self.adj[nid])
            units_dict = {ut.value: count for ut, count in node.units.items()} if (is_scouted or adjacent_visibility) else None

            visible_nodes[nid] = VisibleNode(
                id=node.id,
                name=node.name,
                x=node.x,
                y=node.y,
                owner=node.owner,
                production=node.production,
                defense_bonus=node.defense_bonus,
                capture_progress=node.capture_progress,
                capturing_player=node.capturing_player,
                units=units_dict,
                is_scouted=is_scouted
            )

        my_fleets: List[VisibleFleet] = []
        enemy_fleets: List[VisibleFleet] = []
        for fleet in self.fleets:
            if fleet.owner == pid:
                my_fleets.append(VisibleFleet(
                    id=fleet.id,
                    owner=fleet.owner,
                    origin_node=fleet.origin_node,
                    dest_node=fleet.dest_node,
                    turns_remaining=fleet.turns_remaining,
                    total_turns=fleet.total_turns,
                    total_count=fleet.total_count,
                    is_revealed=True,
                    units={ut.value: count for ut, count in fleet.units.items()}
                ))
            else:
                lane_key = (fleet.origin_node, fleet.dest_node)
                is_revealed = (lane_key in scouted_lanes) or (fleet.dest_node in scouted_nodes and self.nodes[fleet.dest_node].units.get(UnitType.SCOUT, 0) > 0)
                enemy_fleets.append(VisibleFleet(
                    id=fleet.id,
                    owner=fleet.owner,
                    origin_node=fleet.origin_node,
                    dest_node=fleet.dest_node,
                    turns_remaining=fleet.turns_remaining,
                    total_turns=fleet.total_turns,
                    total_count=fleet.total_count,
                    is_revealed=is_revealed,
                    units={ut.value: count for ut, count in fleet.units.items()} if is_revealed else None
                ))

        lanes_data = [{"node_a": u, "node_b": v, "travel_turns": t} for u, v, t in self.lanes]

        return BotObservation(
            current_turn=self.current_turn,
            max_turns=self.max_turns,
            my_player_id=pid,
            my_credits=self.player_credits[pid],
            my_score=self.scores[pid],
            opponent_score=self.scores[opp_id],
            relic_active=is_active,
            relic_charging=is_charging,
            relic_node_id=self.relic_node_id,
            nodes=visible_nodes,
            lanes=lanes_data,
            my_fleets=my_fleets,
            enemy_fleets=enemy_fleets
        )

    def _calculate_upkeep(self, pid: int) -> int:
        owned_nodes = sum(1 for n in self.nodes.values() if n.owner == pid)
        free_capacity = 10 + (4 * owned_nodes)
        domestic_units = sum(sum(n.units.values()) for n in self.nodes.values() if n.owner == pid and n.resident_player == pid)
        foreign_units = sum(sum(n.units.values()) for n in self.nodes.values() if n.resident_player == pid and n.owner != pid)
        transit_units = sum(f.total_count for f in self.fleets if f.owner == pid)
        total_units = domestic_units + foreign_units + transit_units

        if total_units <= free_capacity:
            return 0
        excess = total_units - free_capacity
        domestic_shield = min(domestic_units, free_capacity)
        remaining_shield = free_capacity - domestic_shield
        excess_domestic = domestic_units - domestic_shield
        total_foreign = foreign_units + transit_units
        excess_foreign = max(0, total_foreign - remaining_shield)
        return (excess_domestic * 1) + (excess_foreign * 2)

    def step(self, p1_orders: List[Order], p2_orders: List[Order]) -> bool:
        if self.game_over:
            return False

        self.relic_active = (self.current_turn >= self.relic_spawn_turn)
        self.relic_charging = (self.relic_spawn_turn - 5 <= self.current_turn < self.relic_spawn_turn)

        # 1. Economy: Production
        for node in self.nodes.values():
            if node.owner in [1, 2]:
                self.player_credits[node.owner] += node.production

        # 2. Economy: Upkeep & Bankruptcy
        for pid in [1, 2]:
            upkeep = self._calculate_upkeep(pid)
            if self.player_credits[pid] >= upkeep:
                self.player_credits[pid] -= upkeep
            else:
                self.player_credits[pid] = 0

        # 3. Recruitment (Simultaneous)
        p1_newly_trained = self._process_train_orders(1, p1_orders)
        p2_newly_trained = self._process_train_orders(2, p2_orders)

        # 4. Movement (Simultaneous, mobilization check)
        self._process_move_orders(1, p1_orders, p1_newly_trained)
        self._process_move_orders(2, p2_orders, p2_newly_trained)

        # 5. Lane Travel
        arriving_fleets: List[InternalFleet] = []
        in_transit_fleets: List[InternalFleet] = []
        for fleet in self.fleets:
            fleet.turns_remaining -= 1
            if fleet.turns_remaining <= 0:
                arriving_fleets.append(fleet)
            else:
                in_transit_fleets.append(fleet)
        self.fleets = in_transit_fleets

        # 6. Group arrivals
        arrivals: Dict[int, Dict[int, Dict[UnitType, int]]] = {nid: {1: {}, 2: {}} for nid in self.nodes}
        for fleet in arriving_fleets:
            dest = fleet.dest_node
            for ut, count in fleet.units.items():
                arrivals[dest][fleet.owner][ut] = arrivals[dest][fleet.owner].get(ut, 0) + count

        # 7. Combat Resolution
        for nid, node in self.nodes.items():
            arr_p1 = dict(arrivals[nid][1])
            arr_p2 = dict(arrivals[nid][2])
            p1_scout = (arr_p1.get(UnitType.SCOUT, 0) > 0) or (node.units.get(UnitType.SCOUT, 0) > 0 and node.resident_player == 1)
            p2_scout = (arr_p2.get(UnitType.SCOUT, 0) > 0) or (node.units.get(UnitType.SCOUT, 0) > 0 and node.resident_player == 2)

            if node.owner == 1:
                p1_forces = dict(arr_p1)
                if node.resident_player == 1:
                    for ut, count in node.units.items():
                        p1_forces[ut] = p1_forces.get(ut, 0) + count
                p2_forces = dict(arr_p2)

                if sum(p1_forces.values()) > 0 and sum(p2_forces.values()) > 0:
                    surv_def, surv_att = resolve_combat(p1_forces, p2_forces, defender_bonus=node.defense_bonus, has_defender_scout=p1_scout, has_attacker_scout=p2_scout)
                    p1_forces, p2_forces = surv_def, surv_att

                if sum(p1_forces.values()) > 0:
                    node.units = p1_forces
                    node.resident_player = 1
                    occupier = 1
                elif sum(p2_forces.values()) > 0:
                    node.units = p2_forces
                    node.resident_player = 2
                    occupier = 2
                else:
                    node.units = {ut: 0 for ut in UnitType}
                    node.resident_player = 0
                    occupier = 0

            elif node.owner == 2:
                p2_forces = dict(arr_p2)
                if node.resident_player == 2:
                    for ut, count in node.units.items():
                        p2_forces[ut] = p2_forces.get(ut, 0) + count
                p1_forces = dict(arr_p1)

                if sum(p1_forces.values()) > 0 and sum(p2_forces.values()) > 0:
                    surv_def, surv_att = resolve_combat(p2_forces, p1_forces, defender_bonus=node.defense_bonus, has_defender_scout=p2_scout, has_attacker_scout=p1_scout)
                    p2_forces, p1_forces = surv_def, surv_att

                if sum(p2_forces.values()) > 0:
                    node.units = p2_forces
                    node.resident_player = 2
                    occupier = 2
                elif sum(p1_forces.values()) > 0:
                    node.units = p1_forces
                    node.resident_player = 1
                    occupier = 1
                else:
                    node.units = {ut: 0 for ut in UnitType}
                    node.resident_player = 0
                    occupier = 0

            else:
                # Neutral node
                st_p1 = dict(arr_p1)
                st_p2 = dict(arr_p2)
                neut = dict(node.units) if node.resident_player == 0 else {ut: 0 for ut in UnitType}

                if node.resident_player == 1:
                    for ut, count in node.units.items():
                        st_p1[ut] = st_p1.get(ut, 0) + count
                elif node.resident_player == 2:
                    for ut, count in node.units.items():
                        st_p2[ut] = st_p2.get(ut, 0) + count

                if sum(st_p1.values()) > 0 and sum(st_p2.values()) > 0:
                    surv_a, surv_b = resolve_meeting_engagement(st_p1, st_p2, has_a_scout=p1_scout, has_b_scout=p2_scout)
                    st_p1, st_p2 = surv_a, surv_b

                if sum(neut.values()) > 0:
                    if sum(st_p1.values()) > 0:
                        surv_neut, surv_p1 = resolve_combat(neut, st_p1, defender_bonus=node.defense_bonus, has_defender_scout=False, has_attacker_scout=p1_scout)
                        neut, st_p1 = surv_neut, surv_p1
                    elif sum(st_p2.values()) > 0:
                        surv_neut, surv_p2 = resolve_combat(neut, st_p2, defender_bonus=node.defense_bonus, has_defender_scout=False, has_attacker_scout=p2_scout)
                        neut, st_p2 = surv_neut, surv_p2

                if sum(st_p1.values()) > 0:
                    node.units = st_p1
                    node.resident_player = 1
                    occupier = 1
                elif sum(st_p2.values()) > 0:
                    node.units = st_p2
                    node.resident_player = 2
                    occupier = 2
                elif sum(neut.values()) > 0:
                    node.units = neut
                    node.resident_player = 0
                    occupier = 0
                else:
                    node.units = {ut: 0 for ut in UnitType}
                    node.resident_player = 0
                    occupier = 0

            # 8. Capture Dynamics (Scout contest check on arriving scout)
            if occupier != 0:
                if occupier != node.owner:
                    enemy_pid = 2 if occupier == 1 else 1
                    scout_contested = (arrivals[nid][enemy_pid].get(UnitType.SCOUT, 0) > 0)

                    if not scout_contested:
                        if node.capturing_player == occupier:
                            node.capture_progress += 1
                            if node.capture_progress >= 2:
                                node.owner = occupier
                                node.capture_progress = 0
                                node.capturing_player = 0
                        else:
                            node.capturing_player = occupier
                            node.capture_progress = 1
                else:
                    node.capturing_player = 0
                    node.capture_progress = 0

        # 9. Scoring
        pts_mult = 2 if self.relic_active else 1
        for node in self.nodes.values():
            if node.owner in [1, 2]:
                self.scores[node.owner] += 1 * pts_mult

        if self.relic_active:
            relic_owner = self.nodes[self.relic_node_id].owner
            if relic_owner in [1, 2]:
                self.scores[relic_owner] += 10
                self.relic_turns_held[relic_owner] += 1

        self.current_turn += 1

        # 10. Check Elimination or Max Turns
        p1_alive = any(n.owner == 1 for n in self.nodes.values()) or any(sum(n.units.values()) > 0 for n in self.nodes.values() if n.resident_player == 1) or any(f.owner == 1 for f in self.fleets)
        p2_alive = any(n.owner == 2 for n in self.nodes.values()) or any(sum(n.units.values()) > 0 for n in self.nodes.values() if n.resident_player == 2) or any(f.owner == 2 for f in self.fleets)

        if not p1_alive and not p2_alive:
            self.game_over = True
            self.winner = 0
            self.win_reason = "Mutual Elimination"
            return False
        elif not p1_alive:
            self.game_over = True
            self.winner = 2
            self.win_reason = "Player 1 Eliminated"
            return False
        elif not p2_alive:
            self.game_over = True
            self.winner = 1
            self.win_reason = "Player 2 Eliminated"
            return False

        if self.current_turn > self.max_turns:
            self.game_over = True
            self._resolve_tiebreaker()
            return False

        return True

    def _process_train_orders(self, pid: int, orders: List[Order]) -> Dict[int, Dict[UnitType, int]]:
        newly_trained: Dict[int, Dict[UnitType, int]] = {}
        if not orders:
            return newly_trained
        for order in orders:
            if isinstance(order, TrainOrder):
                node = self.nodes.get(order.node_id)
                if not node or node.owner != pid or node.capturing_player != 0 or order.count <= 0:
                    continue
                cost = UNIT_STATS[order.unit_type].cost * order.count
                if self.player_credits[pid] >= cost:
                    self.player_credits[pid] -= cost
                    node.units[order.unit_type] = node.units.get(order.unit_type, 0) + order.count
                    if order.node_id not in newly_trained:
                        newly_trained[order.node_id] = {}
                    newly_trained[order.node_id][order.unit_type] = newly_trained[order.node_id].get(order.unit_type, 0) + order.count
        return newly_trained

    def _process_move_orders(self, pid: int, orders: List[Order], newly_trained: Dict[int, Dict[UnitType, int]]):
        if not orders:
            return
        for order in orders:
            if isinstance(order, MoveOrder):
                u, v = order.origin_node, order.dest_node
                travel_turns = self.lane_lookup.get((u, v))
                if travel_turns is None:
                    continue
                node = self.nodes.get(u)
                if not node or node.owner != pid:
                    continue

                valid_move = True
                units_to_move: Dict[UnitType, int] = {}
                node_trained = newly_trained.get(u, {})

                for ut, count in order.units.items():
                    if count <= 0:
                        continue
                    available = node.units.get(ut, 0) - node_trained.get(ut, 0)
                    if count > available:
                        valid_move = False
                        break
                    units_to_move[ut] = count

                if valid_move and sum(units_to_move.values()) > 0:
                    for ut, count in units_to_move.items():
                        node.units[ut] -= count

                    self.fleets.append(InternalFleet(
                        id=self._next_fleet_id,
                        owner=pid,
                        origin_node=u,
                        dest_node=v,
                        turns_remaining=travel_turns,
                        total_turns=travel_turns,
                        units=units_to_move
                    ))
                    self._next_fleet_id += 1

    def _resolve_tiebreaker(self):
        vp1, vp2 = self.scores[1], self.scores[2]
        r1, r2 = self.relic_turns_held[1], self.relic_turns_held[2]

        val1 = self.player_credits[1]
        for n in self.nodes.values():
            if n.resident_player == 1:
                val1 += sum(c * UNIT_STATS[ut].cost for ut, c in n.units.items())
        for f in self.fleets:
            if f.owner == 1:
                val1 += sum(c * UNIT_STATS[ut].cost for ut, c in f.units.items())

        val2 = self.player_credits[2]
        for n in self.nodes.values():
            if n.resident_player == 2:
                val2 += sum(c * UNIT_STATS[ut].cost for ut, c in n.units.items())
        for f in self.fleets:
            if f.owner == 2:
                val2 += sum(c * UNIT_STATS[ut].cost for ut, c in f.units.items())

        score1 = (vp1 * 100000) + (r1 * 1000) + val1
        score2 = (vp2 * 100000) + (r2 * 1000) + val2

        if score1 > score2:
            self.winner = 1
            self.win_reason = f"Tiebreaker (P1: {score1:,} pts vs P2: {score2:,} pts)"
        elif score2 > score1:
            self.winner = 2
            self.win_reason = f"Tiebreaker (P2: {score2:,} pts vs P1: {score1:,} pts)"
        else:
            self.winner = 1
            self.win_reason = "Tiebreaker Exact Match"

# =====================================================================
# 8. Dynamic Bot Loader & Validator
# =====================================================================

def load_bot_class(target: str | Type[BotBase]) -> Tuple[Type[BotBase], str]:
    """Loads a BotBase class from a registry name, file path, or class object."""
    if isinstance(target, type) and issubclass(target, BotBase):
        return target, target.__name__

    if isinstance(target, str):
        key = target.lower().strip()
        if key in BUILTIN_BOTS:
            return BUILTIN_BOTS[key], BUILTIN_BOTS[key].__name__

        abs_path = os.path.abspath(target)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Bot script not found at {target}")
        if os.path.getsize(abs_path) == 0:
            raise ValueError(f"The bot script '{os.path.basename(target)}' is empty.")

        mod_name = f"custom_bot_{os.path.splitext(os.path.basename(abs_path))[0]}_{int(time.time()*1000)}"
        spec = importlib.util.spec_from_file_location(mod_name, abs_path)
        if not spec or not spec.loader:
            raise ValueError(f"Could not load module from {target}")
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

    raise ValueError(f"Could not find a valid BotBase subclass in '{target}'.")

def validate_bot(file_path: str) -> bool:
    """Validates a bot file locally for protocol conformance, signatures, and P1/P2 compatibility."""
    print("=" * 65)
    print("   NODE WAR - COMPETITOR BOT DRY-RUN VALIDATOR")
    print("=" * 65)
    print(f"Target Script: {file_path}")

    if not os.path.exists(file_path):
        print(f"❌ ERROR: File does not exist: {file_path}")
        return False
    if os.path.getsize(file_path) == 0:
        print(f"❌ ERROR: File is empty (0 bytes): {file_path}")
        return False
    print("  ✓ File located and non-empty")

    try:
        bot_cls, cls_name = load_bot_class(file_path)
        print(f"  ✓ Found Bot class: '{cls_name}'")
    except Exception as e:
        print(f"❌ ERROR during class inspection: {e}")
        return False

    sim = LocalSimulator(max_turns=120)

    # Test P1
    try:
        bot_p1 = bot_cls(player_id=1)
        print("  ✓ Player 1 instance initialized successfully")
    except Exception as e:
        print(f"❌ ERROR during Player 1 __init__: {e}")
        return False

    obs_p1 = sim.get_player_observation(1)
    t0 = time.perf_counter()
    try:
        orders_p1 = bot_p1.act(obs_p1)
        dt = (time.perf_counter() - t0) * 1000.0
        print(f"  ✓ act(obs) executed on Turn 1 (P1) in {dt:.2f} ms -> {len(orders_p1) if orders_p1 else 0} orders")
        if dt > 50.0:
            print(f"  ⚠️ WARNING: Turn 1 execution took {dt:.2f} ms (> 50 ms limit)")
    except Exception as e:
        print(f"❌ ERROR during Player 1 act(): {e}")
        return False

    # Test P2
    try:
        bot_p2 = bot_cls(player_id=2)
        print("  ✓ Player 2 instance initialized successfully")
    except Exception as e:
        print(f"❌ ERROR during Player 2 __init__: {e}")
        return False

    obs_p2 = sim.get_player_observation(2)
    try:
        orders_p2 = bot_p2.act(obs_p2)
        print(f"  ✓ act(obs) executed for Player 2 -> {len(orders_p2) if orders_p2 else 0} orders")
    except Exception as e:
        print(f"❌ ERROR during Player 2 act(): {e}")
        return False

    # Test Relic Warning Flag
    sim.current_turn = 85
    sim.relic_spawn_turn = 88
    obs_relic = sim.get_player_observation(1)
    try:
        orders_relic = bot_p1.act(obs_relic)
        print(f"  ✓ act(obs) executed with relic_charging=True -> {len(orders_relic) if orders_relic else 0} orders")
    except Exception as e:
        print(f"❌ ERROR during act() with relic_charging: {e}")
        return False

    # Validate orders
    all_order_sets = [("P1 Turn 1", orders_p1), ("P2 Turn 1", orders_p2), ("Relic Warning", orders_relic)]
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
                    print(f"❌ ERROR: MoveOrder.units must be a dict in Order #{idx} ({label})")
                    return False
                for ut, cnt in order.units.items():
                    if cnt <= 0:
                        print(f"⚠️ WARNING: MoveOrder has non-positive count {cnt} for unit {ut} in Order #{idx} ({label})")
            else:
                print(f"❌ ERROR: Unknown order type '{type(order)}' in Order #{idx} ({label})")
                return False

    print("  ✓ All returned orders conform strictly to the Node War protocol")
    print("=" * 65)
    print("🎉 VALIDATION PASSED! Your bot is ready for tournament competition.")
    print("=" * 65)
    return True

# =====================================================================
# 9. Simulation Runner Functions
# =====================================================================

def simulate_match(
    bot_a: str | Type[BotBase],
    bot_b: str | Type[BotBase],
    max_turns: int = 120,
    seed: Optional[int] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """Simulates a complete 1v1 match between two bots and prints summary."""
    cls_a, name_a = load_bot_class(bot_a)
    cls_b, name_b = load_bot_class(bot_b)

    sim = LocalSimulator(max_turns=max_turns, seed=seed)
    p1_bot = cls_a(player_id=1)
    p2_bot = cls_b(player_id=2)

    if verbose:
        print(f"\n🎮 Starting Match: {name_a} (Player 1) vs {name_b} (Player 2)")
        print(f"   Seed: {sim.seed} | Max Turns: {max_turns} | Relic Turn: {sim.relic_spawn_turn}")

    start_time = time.perf_counter()
    p1_timeouts = 0
    p2_timeouts = 0

    while not sim.game_over:
        obs1 = sim.get_player_observation(1)
        obs2 = sim.get_player_observation(2)

        t_p1 = time.perf_counter()
        try:
            orders1 = p1_bot.act(obs1) or []
            if (time.perf_counter() - t_p1) * 1000.0 > 50.0:
                p1_timeouts += 1
        except Exception as e:
            orders1 = []

        t_p2 = time.perf_counter()
        try:
            orders2 = p2_bot.act(obs2) or []
            if (time.perf_counter() - t_p2) * 1000.0 > 50.0:
                p2_timeouts += 1
        except Exception as e:
            orders2 = []

        sim.step(orders1, orders2)

    elapsed = time.perf_counter() - start_time
    winner_name = name_a if sim.winner == 1 else (name_b if sim.winner == 2 else "Draw")

    if verbose:
        print(f"🏁 Match Ended at Turn {sim.current_turn - 1}")
        print(f"   Winner: {winner_name} (Player {sim.winner})")
        print(f"   Reason: {sim.win_reason}")
        print(f"   Final Scores: {name_a}: {sim.scores[1]} pts | {name_b}: {sim.scores[2]} pts")
        print(f"   Relic Control: {name_a}: {sim.relic_turns_held[1]} turns | {name_b}: {sim.relic_turns_held[2]} turns")
        print(f"   Simulation Wall-Time: {elapsed*1000.0:.1f} ms")
        if p1_timeouts > 0 or p2_timeouts > 0:
            print(f"   Timeouts (>50ms): {name_a}: {p1_timeouts} turns | {name_b}: {p2_timeouts} turns")

    return {
        "winner": sim.winner,
        "winner_name": winner_name,
        "win_reason": sim.win_reason,
        "total_turns": sim.current_turn - 1,
        "p1_score": sim.scores[1],
        "p2_score": sim.scores[2],
        "seed": sim.seed,
        "relic_turn": sim.relic_spawn_turn
    }

def simulate_bo3(bot_a: str | Type[BotBase], bot_b: str | Type[BotBase], max_turns: int = 120):
    """Runs a Best-of-3 series with alternating seats."""
    cls_a, name_a = load_bot_class(bot_a)
    cls_b, name_b = load_bot_class(bot_b)

    print("=" * 65)
    print(f"   NODE WAR - BEST-OF-3 LOCAL SERIES: {name_a} vs {name_b}")
    print("=" * 65)

    wins_a, wins_b = 0, 0

    print("\n--- Game 1: Seat A (P1) vs Seat B (P2) ---")
    g1 = simulate_match(cls_a, cls_b, max_turns=max_turns, verbose=True)
    if g1["winner"] == 1:
        wins_a += 1
    elif g1["winner"] == 2:
        wins_b += 1

    print("\n--- Game 2: Seat B (P1) vs Seat A (P2) [SEAT SWAP] ---")
    g2 = simulate_match(cls_b, cls_a, max_turns=max_turns, verbose=True)
    if g2["winner"] == 1:
        wins_b += 1
    elif g2["winner"] == 2:
        wins_a += 1

    if wins_a == 1 and wins_b == 1:
        print("\n--- Game 3: Decider Match ---")
        g3 = simulate_match(cls_a, cls_b, max_turns=max_turns, verbose=True)
        if g3["winner"] == 1:
            wins_a += 1
        elif g3["winner"] == 2:
            wins_b += 1

    series_winner = name_a if wins_a > wins_b else name_b
    print("\n" + "=" * 65)
    print(f"🏆 SERIES WINNER: {series_winner} ({wins_a} - {wins_b})")
    print("=" * 65)

# =====================================================================
# 10. CLI Entry Points
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Node War - Competitor SDK, Simulator & Validation Toolkit")
    subparsers = parser.add_subparsers(dest="command")

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Dry-run validate a competitor bot script")
    val_parser.add_argument("bot_path", type=str, help="Path to competitor bot Python script")

    # Simulate command
    sim_parser = subparsers.add_parser("simulate", help="Simulate a 1v1 match locally against a baseline bot")
    sim_parser.add_argument("bot_a", type=str, help="First bot script or baseline name (rusher, turtle, balanced, starter)")
    sim_parser.add_argument("bot_b", type=str, nargs="?", default="rusher", help="Second bot script or baseline name (default: rusher)")
    sim_parser.add_argument("--turns", type=int, default=120, help="Maximum turns (default: 120)")
    sim_parser.add_argument("--seed", type=int, default=None, help="Random seed for deterministic replay")

    # Best-of-3 command
    bo3_parser = subparsers.add_parser("bo3", help="Simulate a Best-of-3 series with seat swapping")
    bo3_parser.add_argument("bot_a", type=str, help="First bot script or baseline name")
    bo3_parser.add_argument("bot_b", type=str, nargs="?", default="turtle", help="Second bot script or baseline name (default: turtle)")
    bo3_parser.add_argument("--turns", type=int, default=120, help="Maximum turns (default: 120)")

    # Legacy fallback: python nodewar.py my_bot.py
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-") and sys.argv[1] not in ["validate", "simulate", "bo3"]:
        target = sys.argv[1]
        success = validate_bot(target)
        sys.exit(0 if success else 1)

    args = parser.parse_args()

    if args.command == "validate":
        success = validate_bot(args.bot_path)
        sys.exit(0 if success else 1)
    elif args.command == "simulate":
        simulate_match(args.bot_a, args.bot_b, max_turns=args.turns, seed=args.seed)
    elif args.command == "bo3":
        simulate_bo3(args.bot_a, args.bot_b, max_turns=args.turns)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
