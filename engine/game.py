from __future__ import annotations
import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from .models import (
    PlayerId, UnitType, UNIT_STATS, Fleet, Node, Lane,
    TrainOrder, MoveOrder, Order, GameConfig
)
from .map import create_default_map, MapGraph
from .combat import resolve_combat
from .fog import BotObservation, generate_player_observation

@dataclass
class CombatEvent:
    node_id: int
    defenders_before: Dict[str, int]
    attackers_before: Dict[str, int]
    defenders_after: Dict[str, int]
    attackers_after: Dict[str, int]
    defender_bonus_applied: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "defenders_before": self.defenders_before,
            "attackers_before": self.attackers_before,
            "defenders_after": self.defenders_after,
            "attackers_after": self.attackers_after,
            "defender_bonus_applied": self.defender_bonus_applied
        }

@dataclass
class GameSnapshot:
    turn: int
    scores: Dict[str, int]
    credits: Dict[str, int]
    income: Dict[str, int]
    upkeep: Dict[str, int]
    relic_active: bool
    relic_node_id: int
    nodes: Dict[int, Dict[str, Any]]
    fleets: List[Dict[str, Any]]
    combat_events: List[Dict[str, Any]]
    capture_events: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "scores": self.scores,
            "credits": self.credits,
            "income": self.income,
            "upkeep": self.upkeep,
            "relic_active": self.relic_active,
            "relic_node_id": self.relic_node_id,
            "nodes": self.nodes,
            "fleets": self.fleets,
            "combat_events": self.combat_events,
            "capture_events": self.capture_events
        }

class NodeWarGame:
    def __init__(self, config: Optional[GameConfig] = None):
        self.config = config or GameConfig()
        self.nodes, self.lanes = create_default_map()
        self.graph = MapGraph(self.nodes, self.lanes)

        self.current_turn: int = 1
        self.player_credits: Dict[PlayerId, int] = {
            PlayerId.PLAYER_1: self.config.initial_credits,
            PlayerId.PLAYER_2: self.config.initial_credits
        }
        self.scores: Dict[PlayerId, int] = {
            PlayerId.PLAYER_1: 0,
            PlayerId.PLAYER_2: 0
        }
        self.relic_turns_held: Dict[PlayerId, int] = {
            PlayerId.PLAYER_1: 0,
            PlayerId.PLAYER_2: 0
        }

        self.fleets: List[Fleet] = []
        self._next_fleet_id: int = 1

        self.history: List[GameSnapshot] = []
        self.game_over: bool = False
        self.winner: Optional[PlayerId] = None
        self.win_reason: str = ""

        # Initial turn 1 snapshot
        self._record_snapshot(combat_events=[], capture_events=[])

    @property
    def relic_active(self) -> bool:
        return self.current_turn >= self.config.relic_spawn_turn

    def get_player_observation(self, player_id: PlayerId) -> BotObservation:
        return generate_player_observation(
            player_id=player_id,
            turn=self.current_turn,
            max_turns=self.config.max_turns,
            player_credits=self.player_credits[player_id],
            scores=self.scores,
            relic_active=self.relic_active,
            relic_node_id=self.config.relic_node_id,
            nodes=self.nodes,
            lanes=self.lanes,
            fleets=self.fleets
        )

    def step(self, p1_orders: List[Order], p2_orders: List[Order]) -> bool:
        """
        Advances the simulation by 1 turn.
        Returns True if game continues, False if game is over.
        """
        if self.game_over:
            return False

        combat_events: List[CombatEvent] = []
        capture_events: List[Dict[str, Any]] = []

        # 1. Economy: Production
        income_map = {PlayerId.PLAYER_1: 0, PlayerId.PLAYER_2: 0}
        for node in self.nodes.values():
            if node.owner in [PlayerId.PLAYER_1, PlayerId.PLAYER_2]:
                income_map[node.owner] += node.production
                self.player_credits[node.owner] += node.production

        # 2. Economy: Upkeep
        for pid in [PlayerId.PLAYER_1, PlayerId.PLAYER_2]:
            total_units = self._count_player_units(pid)
            if total_units > self.config.free_upkeep_cap:
                upkeep = (total_units - self.config.free_upkeep_cap) * self.config.upkeep_cost_per_unit
                self.player_credits[pid] = max(0, self.player_credits[pid] - upkeep)

        # 3. Process Orders: Training & Fleet Launches
        self._process_player_orders(PlayerId.PLAYER_1, p1_orders)
        self._process_player_orders(PlayerId.PLAYER_2, p2_orders)

        # 4. Fleet Movement
        arriving_fleets: List[Fleet] = []
        in_transit_fleets: List[Fleet] = []
        for fleet in self.fleets:
            fleet.turns_remaining -= 1
            if fleet.turns_remaining <= 0:
                arriving_fleets.append(fleet)
            else:
                in_transit_fleets.append(fleet)
        self.fleets = in_transit_fleets

        # 5. Integrate arriving fleets into destination nodes
        # Group arriving units by destination and player
        arrivals: Dict[int, Dict[PlayerId, Dict[UnitType, int]]] = {nid: {PlayerId.PLAYER_1: {}, PlayerId.PLAYER_2: {}} for nid in self.nodes}
        for fleet in arriving_fleets:
            dest = fleet.dest_node
            owner = fleet.owner
            for ut, count in fleet.units.items():
                arrivals[dest][owner][ut] = arrivals[dest][owner].get(ut, 0) + count

        # 6. Combat Resolution at each node
        for nid, node in self.nodes.items():
            # Gather all forces at the node
            # Stationed units belong to node.resident_player (if any)
            forces: Dict[PlayerId, Dict[UnitType, int]] = {
                PlayerId.PLAYER_1: dict(arrivals[nid][PlayerId.PLAYER_1]),
                PlayerId.PLAYER_2: dict(arrivals[nid][PlayerId.PLAYER_2])
            }
            if node.resident_player in forces:
                for ut, count in node.units.items():
                    forces[node.resident_player][ut] = forces[node.resident_player].get(ut, 0) + count

            p1_count = sum(forces[PlayerId.PLAYER_1].values())
            p2_count = sum(forces[PlayerId.PLAYER_2].values())

            if p1_count > 0 and p2_count > 0:
                # Combat erupts!
                p1_before = {ut.value: c for ut, c in forces[PlayerId.PLAYER_1].items()}
                p2_before = {ut.value: c for ut, c in forces[PlayerId.PLAYER_2].items()}
                
                # Check defender bonus
                if node.owner == PlayerId.PLAYER_1:
                    surv_def, surv_att = resolve_combat(
                        defenders=forces[PlayerId.PLAYER_1],
                        attackers=forces[PlayerId.PLAYER_2],
                        defender_bonus=node.defense_bonus
                    )
                    forces[PlayerId.PLAYER_1] = surv_def
                    forces[PlayerId.PLAYER_2] = surv_att
                    bonus_applied = True
                elif node.owner == PlayerId.PLAYER_2:
                    surv_def, surv_att = resolve_combat(
                        defenders=forces[PlayerId.PLAYER_2],
                        attackers=forces[PlayerId.PLAYER_1],
                        defender_bonus=node.defense_bonus
                    )
                    forces[PlayerId.PLAYER_2] = surv_def
                    forces[PlayerId.PLAYER_1] = surv_att
                    bonus_applied = True
                else:
                    # Neutral node battle: neither gets defender bonus
                    surv_p1, surv_p2 = resolve_combat(
                        defenders=forces[PlayerId.PLAYER_1],
                        attackers=forces[PlayerId.PLAYER_2],
                        defender_bonus=0.0
                    )
                    forces[PlayerId.PLAYER_1] = surv_p1
                    forces[PlayerId.PLAYER_2] = surv_p2
                    bonus_applied = False

                p1_after = {ut.value: c for ut, c in forces[PlayerId.PLAYER_1].items()}
                p2_after = {ut.value: c for ut, c in forces[PlayerId.PLAYER_2].items()}

                combat_events.append(CombatEvent(
                    node_id=nid,
                    defenders_before=p1_before if node.owner == PlayerId.PLAYER_1 else p2_before,
                    attackers_before=p2_before if node.owner == PlayerId.PLAYER_1 else p1_before,
                    defenders_after=p1_after if node.owner == PlayerId.PLAYER_1 else p2_after,
                    attackers_after=p2_after if node.owner == PlayerId.PLAYER_1 else p1_after,
                    defender_bonus_applied=bonus_applied
                ))

            # Apply surviving forces to the node
            rem_p1 = sum(forces[PlayerId.PLAYER_1].values())
            rem_p2 = sum(forces[PlayerId.PLAYER_2].values())

            if rem_p1 > 0 and rem_p2 == 0:
                node.units = forces[PlayerId.PLAYER_1]
                node.resident_player = PlayerId.PLAYER_1
                occupier = PlayerId.PLAYER_1
            elif rem_p2 > 0 and rem_p1 == 0:
                node.units = forces[PlayerId.PLAYER_2]
                node.resident_player = PlayerId.PLAYER_2
                occupier = PlayerId.PLAYER_2
            else:
                # Both wiped or empty
                node.units = {ut: 0 for ut in UnitType}
                node.resident_player = PlayerId.NONE
                occupier = PlayerId.NONE

            # 7. Node Capture Dynamics (2-Turn Flip)
            if occupier != PlayerId.NONE:
                if occupier != node.owner:
                    # An invader occupies the node!
                    if node.capturing_player == occupier:
                        node.capture_progress += 1
                        if node.capture_progress >= self.config.capture_turns_needed:
                            old_owner = node.owner
                            node.owner = occupier
                            node.capture_progress = 0
                            node.capturing_player = PlayerId.NONE
                            capture_events.append({
                                "node_id": nid,
                                "type": "flipped",
                                "new_owner": int(occupier),
                                "old_owner": int(old_owner)
                            })
                    else:
                        node.capturing_player = occupier
                        node.capture_progress = 1
                        capture_events.append({
                            "node_id": nid,
                            "type": "contested",
                            "capturing_player": int(occupier),
                            "progress": 1
                        })
                else:
                    # Legitimate owner is present: any hostile capture attempt is thwarted
                    if node.capturing_player != PlayerId.NONE:
                        capture_events.append({
                            "node_id": nid,
                            "type": "relieved",
                            "owner": int(node.owner)
                        })
                        node.capturing_player = PlayerId.NONE
                        node.capture_progress = 0
            else:
                # Nobody present
                pass

        # 8. Scoring & Relic Spawning
        pts_mult = self.config.relic_point_multiplier if self.relic_active else 1
        for node in self.nodes.values():
            if node.owner in [PlayerId.PLAYER_1, PlayerId.PLAYER_2]:
                self.scores[node.owner] += 1 * pts_mult

        if self.relic_active:
            relic_node = self.nodes[self.config.relic_node_id]
            if relic_node.owner in [PlayerId.PLAYER_1, PlayerId.PLAYER_2]:
                self.scores[relic_node.owner] += self.config.relic_points_per_turn
                self.relic_turns_held[relic_node.owner] += 1

        # 9. Game Over Evaluation
        self.current_turn += 1
        self._record_snapshot(
            combat_events=[e.to_dict() for e in combat_events],
            capture_events=capture_events
        )

        p1_nodes = sum(1 for n in self.nodes.values() if n.owner == PlayerId.PLAYER_1)
        p2_nodes = sum(1 for n in self.nodes.values() if n.owner == PlayerId.PLAYER_2)
        p1_units = self._count_player_units(PlayerId.PLAYER_1)
        p2_units = self._count_player_units(PlayerId.PLAYER_2)

        if p1_nodes == 0 and p1_units == 0:
            self.game_over = True
            self.winner = PlayerId.PLAYER_2
            self.win_reason = "Player 1 completely eliminated"
            return False

        if p2_nodes == 0 and p2_units == 0:
            self.game_over = True
            self.winner = PlayerId.PLAYER_1
            self.win_reason = "Player 2 completely eliminated"
            return False

        if self.current_turn > self.config.max_turns:
            self.game_over = True
            self._resolve_tiebreak()
            return False

        return True

    def _process_player_orders(self, pid: PlayerId, orders: List[Order]) -> None:
        """Validates and executes player train and move orders."""
        if not orders:
            return

        for order in orders:
            if isinstance(order, TrainOrder):
                node = self.nodes.get(order.node_id)
                if not node or node.owner != pid:
                    continue
                if node.capturing_player != PlayerId.NONE:
                    # Node is contested/being captured; recruitment is suspended
                    continue
                if order.count <= 0:
                    continue
                cost = UNIT_STATS[order.unit_type].cost * order.count
                if self.player_credits[pid] >= cost:
                    self.player_credits[pid] -= cost
                    node.units[order.unit_type] = node.units.get(order.unit_type, 0) + order.count

            elif isinstance(order, MoveOrder):
                u, v = order.origin_node, order.dest_node
                lane = self.graph.get_lane(u, v)
                if not lane:
                    continue
                node = self.nodes.get(u)
                if not node or node.owner != pid:
                    continue
                
                # Verify and deduct units
                valid_move = True
                units_to_move: Dict[UnitType, int] = {}
                for ut, count in order.units.items():
                    if count <= 0:
                        continue
                    available = node.units.get(ut, 0)
                    if count > available:
                        valid_move = False
                        break
                    units_to_move[ut] = count

                if valid_move and sum(units_to_move.values()) > 0:
                    for ut, count in units_to_move.items():
                        node.units[ut] -= count

                    self.fleets.append(Fleet(
                        id=self._next_fleet_id,
                        owner=pid,
                        origin_node=u,
                        dest_node=v,
                        turns_remaining=lane.travel_turns,
                        total_turns=lane.travel_turns,
                        units=units_to_move
                    ))
                    self._next_fleet_id += 1

    def _count_player_units(self, pid: PlayerId) -> int:
        total = 0
        for node in self.nodes.values():
            if node.resident_player == pid:
                total += node.total_units
        for fleet in self.fleets:
            if fleet.owner == pid:
                total += fleet.total_count
        return total

    def _get_player_army_value(self, pid: PlayerId) -> int:
        total = 0
        for node in self.nodes.values():
            if node.resident_player == pid:
                for ut, count in node.units.items():
                    total += count * UNIT_STATS[ut].cost
        for fleet in self.fleets:
            if fleet.owner == pid:
                for ut, count in fleet.units.items():
                    total += count * UNIT_STATS[ut].cost
        return total

    def _resolve_tiebreak(self) -> None:
        """Computes strict tiebreak score to ensure no draws."""
        # Score = points * 100000 + relic_turns * 1000 + army_value * 10 + credits
        p1_val = (
            self.scores[PlayerId.PLAYER_1] * 100000 +
            self.relic_turns_held[PlayerId.PLAYER_1] * 1000 +
            self._get_player_army_value(PlayerId.PLAYER_1) * 10 +
            self.player_credits[PlayerId.PLAYER_1]
        )
        p2_val = (
            self.scores[PlayerId.PLAYER_2] * 100000 +
            self.relic_turns_held[PlayerId.PLAYER_2] * 1000 +
            self._get_player_army_value(PlayerId.PLAYER_2) * 10 +
            self.player_credits[PlayerId.PLAYER_2]
        )

        if p1_val > p2_val:
            self.winner = PlayerId.PLAYER_1
            self.win_reason = f"Points Tiebreak: P1 ({p1_val}) > P2 ({p2_val})"
        elif p2_val > p1_val:
            self.winner = PlayerId.PLAYER_2
            self.win_reason = f"Points Tiebreak: P2 ({p2_val}) > P1 ({p1_val})"
        else:
            # Deterministic fallback: Home base ownership
            p1_home = self.nodes[0].owner == PlayerId.PLAYER_1
            p2_home = self.nodes[14].owner == PlayerId.PLAYER_2
            if p1_home and not p2_home:
                self.winner = PlayerId.PLAYER_1
                self.win_reason = "Home Base Tiebreak: P1 survived"
            else:
                self.winner = PlayerId.PLAYER_2
                self.win_reason = "Home Base Tiebreak: P2 survived"

    def _record_snapshot(self, combat_events: List[Dict[str, Any]], capture_events: List[Dict[str, Any]]) -> None:
        # Calculate income & upkeep for logging
        income = {
            "p1": sum(n.production for n in self.nodes.values() if n.owner == PlayerId.PLAYER_1),
            "p2": sum(n.production for n in self.nodes.values() if n.owner == PlayerId.PLAYER_2)
        }
        u1 = max(0, (self._count_player_units(PlayerId.PLAYER_1) - self.config.free_upkeep_cap) * self.config.upkeep_cost_per_unit)
        u2 = max(0, (self._count_player_units(PlayerId.PLAYER_2) - self.config.free_upkeep_cap) * self.config.upkeep_cost_per_unit)

        snapshot = GameSnapshot(
            turn=self.current_turn,
            scores={"p1": self.scores[PlayerId.PLAYER_1], "p2": self.scores[PlayerId.PLAYER_2]},
            credits={"p1": self.player_credits[PlayerId.PLAYER_1], "p2": self.player_credits[PlayerId.PLAYER_2]},
            income=income,
            upkeep={"p1": u1, "p2": u2},
            relic_active=self.relic_active,
            relic_node_id=self.config.relic_node_id,
            nodes={nid: n.to_dict() for nid, n in self.nodes.items()},
            fleets=[f.to_dict() for f in self.fleets],
            combat_events=combat_events,
            capture_events=capture_events
        )
        self.history.append(snapshot)
