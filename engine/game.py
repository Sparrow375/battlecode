from __future__ import annotations
import copy
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from .models import (
    PlayerId, UnitType, UNIT_STATS, Fleet, Node, Lane,
    TrainOrder, MoveOrder, Order, GameConfig
)
from .map import create_default_map, MapGraph
from .combat import resolve_combat, resolve_meeting_engagement
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
    relic_charging: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "scores": self.scores,
            "credits": self.credits,
            "income": self.income,
            "upkeep": self.upkeep,
            "relic_active": self.relic_active,
            "relic_charging": self.relic_charging,
            "relic_node_id": self.relic_node_id,
            "nodes": self.nodes,
            "fleets": self.fleets,
            "combat_events": self.combat_events,
            "capture_events": self.capture_events
        }

class NodeWarGame:
    def __init__(self, config: Optional[GameConfig] = None):
        self.config = config or GameConfig()
        if self.config.seed is not None:
            self.rng = random.Random(self.config.seed)
        else:
            self.config.seed = random.randint(0, 2**31 - 1)
            self.rng = random.Random(self.config.seed)

        if self.config.relic_spawn_turn is None:
            self.config.relic_spawn_turn = self.rng.randint(self.config.min_relic_turn, self.config.max_relic_turn)

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

    @property
    def relic_charging(self) -> bool:
        return (self.config.relic_spawn_turn - 5 <= self.current_turn < self.config.relic_spawn_turn)

    def get_player_free_supply_cap(self, pid: PlayerId) -> int:
        """Dynamic supply cap: 10 + (4 * owned_nodes)"""
        owned_nodes_count = sum(1 for n in self.nodes.values() if n.owner == pid)
        return self.config.base_supply_cap + (self.config.supply_cap_per_node * owned_nodes_count)

    def _calculate_player_upkeep(self, pid: PlayerId) -> int:
        """
        Calculates dynamic upkeep.
        Free cap covers domestic (friendly owned) units first (1 cr/turn over cap),
        then foreign/expeditionary units (2 cr/turn over cap).
        """
        free_cap = self.get_player_free_supply_cap(pid)
        home_units = sum(n.total_units for n in self.nodes.values() if n.owner == pid and n.resident_player == pid)
        foreign_units = sum(n.total_units for n in self.nodes.values() if n.owner != pid and n.resident_player == pid)
        foreign_units += sum(f.total_count for f in self.fleets if f.owner == pid)

        total_units = home_units + foreign_units
        if total_units <= free_cap:
            return 0

        if home_units >= free_cap:
            home_over = home_units - free_cap
            foreign_over = foreign_units
        else:
            home_over = 0
            remaining_cap = free_cap - home_units
            foreign_over = max(0, foreign_units - remaining_cap)

        return (home_over * self.config.upkeep_cost_per_unit) + (foreign_over * self.config.foreign_upkeep_cost_per_unit)

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
            fleets=self.fleets,
            relic_charging=self.relic_charging
        )

    def _player_has_scout(self, pid: PlayerId, nid: int, arrivals: Dict[int, Dict[PlayerId, Dict[UnitType, int]]]) -> bool:
        """Checks if player has a scout present or adjacent to node nid."""
        # 1. Scout arriving at this node
        if arrivals.get(nid, {}).get(pid, {}).get(UnitType.SCOUT, 0) > 0:
            return True
        # 2. Scout stationed at this node
        node = self.nodes.get(nid)
        if node and node.resident_player == pid and node.units.get(UnitType.SCOUT, 0) > 0:
            return True
        # 3. Scout at any adjacent neighbor
        for neighbor in self.graph.get_neighbors(nid):
            n_node = self.nodes.get(neighbor)
            if n_node and n_node.resident_player == pid and n_node.units.get(UnitType.SCOUT, 0) > 0:
                return True
        # 4. Scout in fleet traveling on connected lane
        for fleet in self.fleets:
            if fleet.owner == pid and fleet.has_scout:
                if fleet.origin_node == nid or fleet.dest_node == nid:
                    return True
        return False

    def step(self, p1_orders: List[Order], p2_orders: List[Order]) -> bool:
        """
        Advances the simulation by 1 turn using 100% simultaneous phase execution.
        Returns True if game continues, False if game is over.
        """
        if self.game_over:
            return False

        combat_events: List[CombatEvent] = []
        capture_events: List[Dict[str, Any]] = []

        # 1. Economy: Tiered Production
        for node in self.nodes.values():
            if node.owner in [PlayerId.PLAYER_1, PlayerId.PLAYER_2]:
                self.player_credits[node.owner] += node.production

        # 2. Economy: Dynamic Supply Upkeep
        for pid in [PlayerId.PLAYER_1, PlayerId.PLAYER_2]:
            upkeep = self._calculate_player_upkeep(pid)
            if self.player_credits[pid] >= upkeep:
                self.player_credits[pid] -= upkeep
            else:
                deficit = upkeep - self.player_credits[pid]
                self.player_credits[pid] = 0
                self._apply_desertion_attrition(pid, deficit)

        # 3. 100% Simultaneous Phase Execution
        # Phase 3A: Train orders for BOTH players executed simultaneously
        p1_newly_trained = self._process_train_orders(PlayerId.PLAYER_1, p1_orders)
        p2_newly_trained = self._process_train_orders(PlayerId.PLAYER_2, p2_orders)

        # Phase 3B: Move orders for BOTH players executed simultaneously (mobilization rule: cannot move newly trained units same turn)
        self._process_move_orders(PlayerId.PLAYER_1, p1_orders, p1_newly_trained)
        self._process_move_orders(PlayerId.PLAYER_2, p2_orders, p2_newly_trained)

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
        arrivals: Dict[int, Dict[PlayerId, Dict[UnitType, int]]] = {
            nid: {PlayerId.PLAYER_1: {}, PlayerId.PLAYER_2: {}} for nid in self.nodes
        }
        for fleet in arriving_fleets:
            dest = fleet.dest_node
            owner = fleet.owner
            for ut, count in fleet.units.items():
                arrivals[dest][owner][ut] = arrivals[dest][owner].get(ut, 0) + count

        # 6. Combat Resolution at each node
        for nid, node in self.nodes.items():
            arr_p1 = dict(arrivals[nid][PlayerId.PLAYER_1])
            arr_p2 = dict(arrivals[nid][PlayerId.PLAYER_2])

            p1_scout = self._player_has_scout(PlayerId.PLAYER_1, nid, arrivals)
            p2_scout = self._player_has_scout(PlayerId.PLAYER_2, nid, arrivals)

            if node.owner == PlayerId.PLAYER_1:
                # P1 owned node
                p1_forces = dict(arr_p1)
                if node.resident_player == PlayerId.PLAYER_1:
                    for ut, count in node.units.items():
                        p1_forces[ut] = p1_forces.get(ut, 0) + count
                p2_forces = dict(arr_p2)

                if sum(p1_forces.values()) > 0 and sum(p2_forces.values()) > 0:
                    p1_before = {ut.value: c for ut, c in p1_forces.items()}
                    p2_before = {ut.value: c for ut, c in p2_forces.items()}

                    surv_def, surv_att = resolve_combat(
                        defenders=p1_forces,
                        attackers=p2_forces,
                        defender_bonus=node.defense_bonus,
                        has_defender_scout=p1_scout,
                        has_attacker_scout=p2_scout
                    )
                    p1_forces = surv_def
                    p2_forces = surv_att

                    combat_events.append(CombatEvent(
                        node_id=nid,
                        defenders_before=p1_before,
                        attackers_before=p2_before,
                        defenders_after={ut.value: c for ut, c in p1_forces.items()},
                        attackers_after={ut.value: c for ut, c in p2_forces.items()},
                        defender_bonus_applied=True
                    ))

                if sum(p1_forces.values()) > 0:
                    node.units = p1_forces
                    node.resident_player = PlayerId.PLAYER_1
                    occupier = PlayerId.PLAYER_1
                elif sum(p2_forces.values()) > 0:
                    node.units = p2_forces
                    node.resident_player = PlayerId.PLAYER_2
                    occupier = PlayerId.PLAYER_2
                else:
                    node.units = {ut: 0 for ut in UnitType}
                    node.resident_player = PlayerId.NONE
                    occupier = PlayerId.NONE

            elif node.owner == PlayerId.PLAYER_2:
                # P2 owned node
                p2_forces = dict(arr_p2)
                if node.resident_player == PlayerId.PLAYER_2:
                    for ut, count in node.units.items():
                        p2_forces[ut] = p2_forces.get(ut, 0) + count
                p1_forces = dict(arr_p1)

                if sum(p1_forces.values()) > 0 and sum(p2_forces.values()) > 0:
                    p1_before = {ut.value: c for ut, c in p1_forces.items()}
                    p2_before = {ut.value: c for ut, c in p2_forces.items()}

                    surv_def, surv_att = resolve_combat(
                        defenders=p2_forces,
                        attackers=p1_forces,
                        defender_bonus=node.defense_bonus,
                        has_defender_scout=p2_scout,
                        has_attacker_scout=p1_scout
                    )
                    p2_forces = surv_def
                    p1_forces = surv_att

                    combat_events.append(CombatEvent(
                        node_id=nid,
                        defenders_before=p2_before,
                        attackers_before=p1_before,
                        defenders_after={ut.value: c for ut, c in p2_forces.items()},
                        attackers_after={ut.value: c for ut, c in p1_forces.items()},
                        defender_bonus_applied=True
                    ))

                if sum(p2_forces.values()) > 0:
                    node.units = p2_forces
                    node.resident_player = PlayerId.PLAYER_2
                    occupier = PlayerId.PLAYER_2
                elif sum(p1_forces.values()) > 0:
                    node.units = p1_forces
                    node.resident_player = PlayerId.PLAYER_1
                    occupier = PlayerId.PLAYER_1
                else:
                    node.units = {ut: 0 for ut in UnitType}
                    node.resident_player = PlayerId.NONE
                    occupier = PlayerId.NONE

            else:
                # Neutral Node (node.owner == PlayerId.NONE)
                stationed_p1 = dict(arr_p1)
                stationed_p2 = dict(arr_p2)
                neutral_defenders = {ut: 0 for ut in UnitType}

                if node.resident_player == PlayerId.PLAYER_1:
                    for ut, count in node.units.items():
                        stationed_p1[ut] = stationed_p1.get(ut, 0) + count
                elif node.resident_player == PlayerId.PLAYER_2:
                    for ut, count in node.units.items():
                        stationed_p2[ut] = stationed_p2.get(ut, 0) + count
                else:
                    neutral_defenders = dict(node.units)

                # Neutral Meeting Engagement: if both P1 and P2 enter on the same turn
                if sum(stationed_p1.values()) > 0 and sum(stationed_p2.values()) > 0:
                    p1_before = {ut.value: c for ut, c in stationed_p1.items()}
                    p2_before = {ut.value: c for ut, c in stationed_p2.items()}

                    surv_p1, surv_p2 = resolve_meeting_engagement(
                        stationed_p1, stationed_p2,
                        has_a_scout=p1_scout,
                        has_b_scout=p2_scout
                    )
                    stationed_p1 = surv_p1
                    stationed_p2 = surv_p2

                    combat_events.append(CombatEvent(
                        node_id=nid,
                        defenders_before=p1_before,
                        attackers_before=p2_before,
                        defenders_after={ut.value: c for ut, c in stationed_p1.items()},
                        attackers_after={ut.value: c for ut, c in stationed_p2.items()},
                        defender_bonus_applied=False
                    ))

                # If neutral defenders still exist, whoever survived fights neutral garrison
                if sum(neutral_defenders.values()) > 0:
                    if sum(stationed_p1.values()) > 0:
                        neut_before = {ut.value: c for ut, c in neutral_defenders.items()}
                        p1_before = {ut.value: c for ut, c in stationed_p1.items()}

                        surv_neut, surv_p1 = resolve_combat(
                            defenders=neutral_defenders,
                            attackers=stationed_p1,
                            defender_bonus=node.defense_bonus,
                            has_defender_scout=False,
                            has_attacker_scout=p1_scout
                        )
                        neutral_defenders = surv_neut
                        stationed_p1 = surv_p1

                        combat_events.append(CombatEvent(
                            node_id=nid,
                            defenders_before=neut_before,
                            attackers_before=p1_before,
                            defenders_after={ut.value: c for ut, c in neutral_defenders.items()},
                            attackers_after={ut.value: c for ut, c in stationed_p1.items()},
                            defender_bonus_applied=True
                        ))
                    elif sum(stationed_p2.values()) > 0:
                        neut_before = {ut.value: c for ut, c in neutral_defenders.items()}
                        p2_before = {ut.value: c for ut, c in stationed_p2.items()}

                        surv_neut, surv_p2 = resolve_combat(
                            defenders=neutral_defenders,
                            attackers=stationed_p2,
                            defender_bonus=node.defense_bonus,
                            has_defender_scout=False,
                            has_attacker_scout=p2_scout
                        )
                        neutral_defenders = surv_neut
                        stationed_p2 = surv_p2

                        combat_events.append(CombatEvent(
                            node_id=nid,
                            defenders_before=neut_before,
                            attackers_before=p2_before,
                            defenders_after={ut.value: c for ut, c in neutral_defenders.items()},
                            attackers_after={ut.value: c for ut, c in stationed_p2.items()},
                            defender_bonus_applied=True
                        ))

                # Apply surviving forces to the node
                if sum(stationed_p1.values()) > 0:
                    node.units = stationed_p1
                    node.resident_player = PlayerId.PLAYER_1
                    occupier = PlayerId.PLAYER_1
                elif sum(stationed_p2.values()) > 0:
                    node.units = stationed_p2
                    node.resident_player = PlayerId.PLAYER_2
                    occupier = PlayerId.PLAYER_2
                elif sum(neutral_defenders.values()) > 0:
                    node.units = neutral_defenders
                    node.resident_player = PlayerId.NONE
                    occupier = PlayerId.NONE
                else:
                    node.units = {ut: 0 for ut in UnitType}
                    node.resident_player = PlayerId.NONE
                    occupier = PlayerId.NONE

            # 7. Node Capture Dynamics & Scout Contest Lock
            if occupier != PlayerId.NONE:
                if occupier != node.owner:
                    enemy_pid = occupier.opponent
                    # Scout Contest Utility: an enemy scout arriving that turn freezes capture progress for that turn
                    scout_contested = arrivals[nid][enemy_pid].get(UnitType.SCOUT, 0) > 0

                    if scout_contested:
                        capture_events.append({
                            "node_id": nid,
                            "type": "scout_contested",
                            "capturing_player": int(occupier),
                            "progress": node.capture_progress
                        })
                    else:
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
                    # Legitimate owner is present: any hostile capture attempt is relieved
                    if node.capturing_player != PlayerId.NONE:
                        capture_events.append({
                            "node_id": nid,
                            "type": "relieved",
                            "owner": int(node.owner)
                        })
                        node.capturing_player = PlayerId.NONE
                        node.capture_progress = 0

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

    def _process_train_orders(self, pid: PlayerId, orders: List[Order]) -> Dict[int, Dict[UnitType, int]]:
        """Validates and executes player train orders. Returns mapping of node_id -> {unit_type: count} trained."""
        newly_trained: Dict[int, Dict[UnitType, int]] = {}
        if not orders:
            return newly_trained
        for order in orders:
            if isinstance(order, TrainOrder):
                node = self.nodes.get(order.node_id)
                if not node or node.owner != pid:
                    continue
                if node.capturing_player != PlayerId.NONE:
                    # Contested node; recruitment suspended
                    continue
                if order.count <= 0:
                    continue
                cost = UNIT_STATS[order.unit_type].cost * order.count
                if self.player_credits[pid] >= cost:
                    self.player_credits[pid] -= cost
                    node.units[order.unit_type] = node.units.get(order.unit_type, 0) + order.count
                    if order.node_id not in newly_trained:
                        newly_trained[order.node_id] = {}
                    newly_trained[order.node_id][order.unit_type] = newly_trained[order.node_id].get(order.unit_type, 0) + order.count
        return newly_trained

    def _process_move_orders(self, pid: PlayerId, orders: List[Order], newly_trained: Optional[Dict[int, Dict[UnitType, int]]] = None) -> None:
        """Validates and executes player move orders. Enforces mobilization rule: newly trained units cannot march same turn."""
        if not orders:
            return
        if newly_trained is None:
            newly_trained = {}

        for order in orders:
            if isinstance(order, MoveOrder):
                u, v = order.origin_node, order.dest_node
                lane = self.graph.get_lane(u, v)
                if not lane:
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
                    # Total units stationed at node minus units trained this turn (mobilization delay)
                    mobilized_available = node.units.get(ut, 0) - node_trained.get(ut, 0)
                    if count > mobilized_available:
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

    def _apply_desertion_attrition(self, pid: PlayerId, deficit: int) -> int:
        """
        Disbands unpaid units when an empire cannot afford its dynamic supply upkeep.
        Foreign units (expeditionary tax 2 cr) desert first, then domestic units (1 cr).
        Priority: Raider, Scout, Guard, Siege.
        Returns total number of deserting units.
        """
        deserted_count = 0
        rem_deficit = deficit
        priority = [UnitType.RAIDER, UnitType.SCOUT, UnitType.GUARD, UnitType.SIEGE]

        # 1. Foreign units stationed on unowned / foreign nodes (saves 2 upkeep per unit)
        for node in self.nodes.values():
            if rem_deficit <= 0:
                break
            if node.owner != pid and node.resident_player == pid:
                for ut in priority:
                    while node.units.get(ut, 0) > 0 and rem_deficit > 0:
                        node.units[ut] -= 1
                        deserted_count += 1
                        rem_deficit -= self.config.foreign_upkeep_cost_per_unit
                if node.total_units == 0:
                    node.resident_player = PlayerId.NONE

        # 2. Foreign units in transit fleets (saves 2 upkeep per unit)
        if rem_deficit > 0:
            for fleet in list(self.fleets):
                if rem_deficit <= 0:
                    break
                if fleet.owner == pid:
                    for ut in priority:
                        while fleet.units.get(ut, 0) > 0 and rem_deficit > 0:
                            fleet.units[ut] -= 1
                            deserted_count += 1
                            rem_deficit -= self.config.foreign_upkeep_cost_per_unit
                    if fleet.total_count == 0:
                        self.fleets.remove(fleet)

        # 3. Domestic garrison units on friendly owned nodes (saves 1 upkeep per unit)
        if rem_deficit > 0:
            for node in self.nodes.values():
                if rem_deficit <= 0:
                    break
                if node.owner == pid and node.resident_player == pid:
                    for ut in priority:
                        while node.units.get(ut, 0) > 0 and rem_deficit > 0:
                            node.units[ut] -= 1
                            deserted_count += 1
                            rem_deficit -= self.config.upkeep_cost_per_unit

        return deserted_count

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
        """Computes strict tiebreak score to ensure no draws. 1:1 net worth parity eliminates Gold Dump exploit."""
        p1_net_worth = self._get_player_army_value(PlayerId.PLAYER_1) + self.player_credits[PlayerId.PLAYER_1]
        p2_net_worth = self._get_player_army_value(PlayerId.PLAYER_2) + self.player_credits[PlayerId.PLAYER_2]

        p1_val = (
            self.scores[PlayerId.PLAYER_1] * 100000 +
            self.relic_turns_held[PlayerId.PLAYER_1] * 1000 +
            p1_net_worth
        )
        p2_val = (
            self.scores[PlayerId.PLAYER_2] * 100000 +
            self.relic_turns_held[PlayerId.PLAYER_2] * 1000 +
            p2_net_worth
        )

        if p1_val > p2_val:
            self.winner = PlayerId.PLAYER_1
            self.win_reason = f"Points Tiebreak: P1 ({p1_val}) > P2 ({p2_val})"
        elif p2_val > p1_val:
            self.winner = PlayerId.PLAYER_2
            self.win_reason = f"Points Tiebreak: P2 ({p2_val}) > P1 ({p1_val})"
        else:
            p1_home = self.nodes[0].owner == PlayerId.PLAYER_1
            p2_home = self.nodes[14].owner == PlayerId.PLAYER_2
            if p1_home and not p2_home:
                self.winner = PlayerId.PLAYER_1
                self.win_reason = "Home Base Tiebreak: P1 survived"
            else:
                self.winner = PlayerId.PLAYER_2
                self.win_reason = "Home Base Tiebreak: P2 survived"

    def _record_snapshot(self, combat_events: List[Dict[str, Any]], capture_events: List[Dict[str, Any]]) -> None:
        income = {
            "p1": sum(n.production for n in self.nodes.values() if n.owner == PlayerId.PLAYER_1),
            "p2": sum(n.production for n in self.nodes.values() if n.owner == PlayerId.PLAYER_2)
        }
        u1 = self._calculate_player_upkeep(PlayerId.PLAYER_1)
        u2 = self._calculate_player_upkeep(PlayerId.PLAYER_2)

        snapshot = GameSnapshot(
            turn=self.current_turn,
            scores={"p1": self.scores[PlayerId.PLAYER_1], "p2": self.scores[PlayerId.PLAYER_2]},
            credits={"p1": self.player_credits[PlayerId.PLAYER_1], "p2": self.player_credits[PlayerId.PLAYER_2]},
            income=income,
            upkeep={"p1": u1, "p2": u2},
            relic_active=self.relic_active,
            relic_charging=self.relic_charging,
            relic_node_id=self.config.relic_node_id,
            nodes={nid: n.to_dict() for nid, n in self.nodes.items()},
            fleets=[f.to_dict() for f in self.fleets],
            combat_events=combat_events,
            capture_events=capture_events
        )
        self.history.append(snapshot)
