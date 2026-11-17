from __future__ import annotations
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import math

from engine.models import UnitType, Order, TrainOrder, MoveOrder
from engine.fog import BotObservation
from bots.base import BotBase


class ApexNodeBot(BotBase):
    """
    Competitive AI for Node War.
    Features:
    - Dynamic RPS Counter-Composition based on visible enemy forces
    - 30-Unit Upkeep Cap management (breaks cap only for Relic Endgame / lethal pushes)
    - Scout-driven Fog of War lane vision
    - Combat-power evaluated battle groups (accounting for +25% defender bonus)
    - Multi-phase macro (Expansion -> Consolidation -> Relic Endgame)
    """

    UNIT_COSTS = {
        UnitType.SCOUT: 6,
        UnitType.RAIDER: 10,
        UnitType.GUARD: 12,
        UnitType.SIEGE: 18,
    }

    STR_TO_TYPE = {
        "scout": UnitType.SCOUT,
        "raider": UnitType.RAIDER,
        "guard": UnitType.GUARD,
        "siege": UnitType.SIEGE,
    }

    # RPS Counter Matrix: Key beats Value (2.0x multiplier)
    COUNTERS = {
        "raider": "siege",
        "siege": "guard",
        "guard": "raider",
    }

    def __init__(self, player_id: int):
        super().__init__(player_id)
        self.home_id = 0 if self.player_id == 1 else 14
        self.enemy_home_id = 14 if self.player_id == 1 else 0
        self.relic_id = 7

        # Persistent memory across turns (handles Fog of War persistence)
        self.last_seen_enemy: Dict[int, Dict[str, int]] = {}
        self.last_seen_turn: Dict[int, int] = {}
        self.node_ownership_memory: Dict[int, Optional[int]] = {}
        self.capturing_targets: Set[int] = set()

    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        # 1. Update Fog-of-War memory and analyze global board state
        self._update_memory(obs)
        all_nodes = self._get_all_nodes_safe(obs)
        my_node_ids = {n.id for n in my_nodes}
        total_units = self._count_total_units(obs, my_nodes)
        enemy_comp = self._analyze_enemy_composition(obs, all_nodes)

        # Determine game phase
        relic_active = getattr(obs, "relic_active", False)
        relic_id = getattr(obs, "relic_node_id", self.relic_id)
        # Estimate if endgame is imminent (within 5 turns of activation if total_turns is known)
        total_turns = getattr(obs, "max_turns", getattr(obs, "total_turns", 100))
        turns_left = max(0, total_turns - obs.current_turn)
        endgame_prep = relic_active or (turns_left <= 30)

        # 2. Identify Frontline, Contested, and Safe nodes
        frontline_ids, contested_ids = self._classify_nodes(obs, my_nodes, all_nodes)

        # 3. Assign Unit Movements (Combat, Expansion, Reinforcement, Relic)
        reserved_units: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        move_orders = self._plan_movements(
            obs=obs,
            my_nodes=my_nodes,
            all_nodes=all_nodes,
            frontline_ids=frontline_ids,
            contested_ids=contested_ids,
            endgame_prep=endgame_prep,
            relic_active=relic_active,
            relic_id=relic_id,
            reserved_units=reserved_units,
        )
        orders.extend(move_orders)

        # 4. Production & Economy Management (Respecting the 30-unit upkeep cliff)
        train_orders = self._plan_production(
            obs=obs,
            my_nodes=my_nodes,
            all_nodes=all_nodes,
            frontline_ids=frontline_ids,
            total_units=total_units,
            enemy_comp=enemy_comp,
            endgame_prep=endgame_prep,
            relic_active=relic_active,
        )
        orders.extend(train_orders)

        return orders

    # -------------------------------------------------------------------------
    # INTELLIGENCE & MEMORY
    # -------------------------------------------------------------------------

    def _get_all_nodes_safe(self, obs: BotObservation) -> List:
        if hasattr(obs, "nodes") and isinstance(obs.nodes, dict):
            return list(obs.nodes.values())
        if hasattr(obs, "nodes") and isinstance(obs.nodes, list):
            return obs.nodes
        # Fallback using base helpers
        nodes = list(self.get_my_nodes(obs)) + list(self.get_neutral_nodes(obs))
        if hasattr(self, "get_enemy_nodes"):
            nodes.extend(self.get_enemy_nodes(obs))
        return nodes

    def _update_memory(self, obs: BotObservation) -> None:
        all_nodes = self._get_all_nodes_safe(obs)
        for node in all_nodes:
            owner = getattr(node, "owner", None)
            if owner is not None:
                self.node_ownership_memory[node.id] = owner

            # If visible and owned by enemy, cache their garrison
            if owner not in (None, 0, self.player_id) and getattr(node, "units", None):
                self.last_seen_enemy[node.id] = dict(node.units)
                self.last_seen_turn[node.id] = obs.current_turn
            elif owner == self.player_id:
                self.last_seen_enemy.pop(node.id, None)

        # Also inspect visible enemy fleets in transit if exposed by observation
        fleets = getattr(obs, "enemy_fleets", getattr(obs, "visible_fleets", []))
        for fleet in fleets:
            dest = getattr(fleet, "target_node_id", getattr(fleet, "to_node", None))
            units = getattr(fleet, "units", {})
            if dest is not None and units:
                existing = self.last_seen_enemy.get(dest, {})
                merged = dict(existing)
                for u_type, cnt in units.items():
                    key = u_type.value if hasattr(u_type, "value") else str(u_type).lower()
                    merged[key] = max(merged.get(key, 0), cnt)
                self.last_seen_enemy[dest] = merged
                self.last_seen_turn[dest] = obs.current_turn

    def _count_total_units(self, obs: BotObservation, my_nodes: List) -> int:
        total = 0
        for node in my_nodes:
            if node.units:
                total += sum(node.units.values())
        # Include friendly fleets in transit
        my_fleets = getattr(obs, "my_fleets", [])
        for fleet in my_fleets:
            if getattr(fleet, "units", None):
                total += sum(fleet.units.values())
        return total

    def _analyze_enemy_composition(self, obs: BotObservation, all_nodes: List) -> Dict[str, int]:
        counts = {"raider": 0, "guard": 0, "siege": 0, "scout": 0}
        for node_id, units in self.last_seen_enemy.items():
            # Decay stale intel older than 6 turns
            age = obs.current_turn - self.last_seen_turn.get(node_id, 0)
            if age > 6:
                continue
            for u_str, cnt in units.items():
                key = u_str.lower()
                if key in counts:
                    counts[key] += cnt
        return counts

    def _get_neighbors(self, obs: BotObservation, node_id: int, all_nodes: List) -> List[int]:
        if hasattr(obs, "adjacency") and node_id in obs.adjacency:
            return list(obs.adjacency[node_id])
        neighbors = []
        for other in all_nodes:
            if other.id != node_id and self.get_distance(obs, node_id, other.id) == 1:
                neighbors.append(other.id)
        return neighbors

    def _classify_nodes(
        self, obs: BotObservation, my_nodes: List, all_nodes: List
    ) -> Tuple[Set[int], Set[int]]:
        frontline_ids: Set[int] = set()
        contested_ids: Set[int] = set()
        my_ids = {n.id for n in my_nodes}

        for node in my_nodes:
            neighbors = self._get_neighbors(obs, node.id, all_nodes)
            if any(nbr not in my_ids for nbr in neighbors):
                frontline_ids.add(node.id)
            # Check if an enemy is actively contesting/capturing this node
            if node.id in self.last_seen_enemy and (obs.current_turn - self.last_seen_turn.get(node.id, 999)) <= 1:
                contested_ids.add(node.id)

        return frontline_ids, contested_ids

    # -------------------------------------------------------------------------
    # COMBAT EVALUATION
    # -------------------------------------------------------------------------

    def _estimate_combat_score(
        self,
        attackers: Dict[str, int],
        defenders: Dict[str, int],
        defender_owns_node: bool = True,
    ) -> float:
        """
        Calculates relative combat strength (> 1.0 means attacker wins decisively).
        Accounts for:
        - Unit credit values as base combat power proxy
        - 2.0x Rock-Paper-Scissors multipliers
        - +25% defender bonus on owned nodes
        """
        atk_power = 0.0
        for u_type, count in attackers.items():
            if count <= 0:
                continue
            base = self.UNIT_COSTS.get(self.STR_TO_TYPE.get(u_type, UnitType.RAIDER), 10)
            target_weakness = self.COUNTERS.get(u_type)
            multiplier = 1.0
            if target_weakness and defenders.get(target_weakness, 0) > 0:
                # Scale bonus by proportion of enemy army weak to this unit
                total_def = max(1, sum(defenders.values()))
                weak_ratio = defenders[target_weakness] / total_def
                multiplier = 1.0 + (1.0 * weak_ratio)  # Up to 2.0x
            atk_power += count * base * multiplier

        def_power = 0.0
        for u_type, count in defenders.items():
            if count <= 0:
                continue
            base = self.UNIT_COSTS.get(self.STR_TO_TYPE.get(u_type, UnitType.RAIDER), 10)
            target_weakness = self.COUNTERS.get(u_type)
            multiplier = 1.0
            if target_weakness and attackers.get(target_weakness, 0) > 0:
                total_atk = max(1, sum(attackers.values()))
                weak_ratio = attackers[target_weakness] / total_atk
                multiplier = 1.0 + (1.0 * weak_ratio)
            def_power += count * base * multiplier

        if defender_owns_node:
            def_power *= 1.25

        if def_power == 0:
            return 99.0 if atk_power > 0 else 0.0
        return atk_power / def_power

    # -------------------------------------------------------------------------
    # MOVEMENT & TACTICAL DISPATCH
    # -------------------------------------------------------------------------

    def _plan_movements(
        self,
        obs: BotObservation,
        my_nodes: List,
        all_nodes: List,
        frontline_ids: Set[int],
        contested_ids: Set[int],
        endgame_prep: bool,
        relic_active: bool,
        relic_id: int,
        reserved_units: Dict[int, Dict[str, int]],
    ) -> List[Order]:
        orders: List[Order] = []
        my_node_map = {n.id: n for n in my_nodes}
        all_node_map = {n.id: n for n in all_nodes}

        # Score every node on the map as a potential movement target
        candidate_targets: List[Tuple[float, int]] = []
        for node in all_nodes:
            score = self._evaluate_target_priority(
                obs, node, endgame_prep, relic_active, relic_id
            )
            if score > 0:
                candidate_targets.append((score, node.id))

        # Highest priority targets claim forces first
        candidate_targets.sort(key=lambda x: x[0], reverse=True)

        for priority, target_id in candidate_targets:
            target_node = all_node_map.get(target_id)
            if not target_node:
                continue

            is_owned = target_id in my_node_map
            enemy_garrison = self.last_seen_enemy.get(target_id, {})

            # Determine required force to take/hold this node
            # Must survive 2 turns of occupation if capturing!
            min_combat_ratio = 1.35 if not is_owned else 1.15
            if target_id == relic_id and endgame_prep:
                min_combat_ratio = 1.60

            # Find closest available friendly nodes with spare troops
            donors = sorted(
                my_nodes,
                key=lambda n: self.get_distance(obs, n.id, target_id),
            )

            for donor in donors:
                if donor.id == target_id:
                    continue
                dist = self.get_distance(obs, donor.id, target_id)
                if dist > 6 and not endgame_prep:
                    continue

                avail = self._get_available_units(
                    donor, reserved_units[donor.id], donor.id in frontline_ids
                )
                if sum(avail.values()) == 0:
                    continue

                # Check if donor + existing defenders at target meet combat threshold
                existing_at_target = dict(my_node_map[target_id].units) if is_owned and my_node_map[target_id].units else {}
                combined = {
                    k: avail.get(k, 0) + existing_at_target.get(k, 0)
                    for k in ("raider", "guard", "siege", "scout")
                }

                # Never send tiny trickles into defended enemy territory
                if not is_owned and sum(enemy_garrison.values()) > 0:
                    ratio = self._estimate_combat_score(combined, enemy_garrison, defender_owns_node=True)
                    if ratio < min_combat_ratio:
                        continue

                # Calculate exact detachment to send
                detachment = self._select_detachment(
                    avail=avail,
                    enemy_garrison=enemy_garrison,
                    is_neutral=(getattr(target_node, "owner", None) in (None, 0)),
                    is_relic=(target_id == relic_id and endgame_prep),
                )

                if not detachment:
                    continue

                path = self.get_path(obs, donor.id, target_id)
                if len(path) >= 2:
                    next_hop = path[1]
                    orders.append(self.move(donor.id, next_hop, detachment))
                    for u_enum, cnt in detachment.items():
                        reserved_units[donor.id][u_enum.value] += cnt
                    break  # One coordinated strike group per target per turn

        # Secondary pass: Forward-deploy idle backline troops to the nearest frontline
        for node in my_nodes:
            if node.id in frontline_ids or (node.id == relic_id and endgame_prep):
                continue
            avail = self._get_available_units(node, reserved_units[node.id], is_frontline=False)
            if sum(avail.values()) == 0:
                continue

            # Pick frontline node closest to Relic (if endgame) or Enemy Home
            anchor_id = relic_id if endgame_prep else self.enemy_home_id
            if frontline_ids:
                best_front = min(
                    frontline_ids,
                    key=lambda fid: self.get_distance(obs, node.id, fid)
                    + 0.7 * self.get_distance(obs, fid, anchor_id),
                )
                path = self.get_path(obs, node.id, best_front)
                if len(path) >= 2:
                    payload = {
                        self.STR_TO_TYPE[k]: v for k, v in avail.items() if v > 0
                    }
                    if payload:
                        orders.append(self.move(node.id, path[1], payload))

        return orders

    def _evaluate_target_priority(
        self,
        obs: BotObservation,
        node,
        endgame_prep: bool,
        relic_active: bool,
        relic_id: int,
    ) -> float:
        owner = getattr(node, "owner", None)
        production = getattr(node, "production", getattr(node, "credits_per_turn", 5))
        dist_from_home = self.get_distance(obs, self.home_id, node.id)

        # 1. Relic Sanctuary (Node 7) overrides everything in the final 25 turns
        if node.id == relic_id:
            if relic_active:
                return 1000.0 if owner != self.player_id else 400.0
            if endgame_prep:
                return 600.0

        # 2. Defend owned nodes under active threat
        if owner == self.player_id:
            if node.id in self.last_seen_enemy:
                age = obs.current_turn - self.last_seen_turn.get(node.id, 99)
                if age <= 2:
                    return 350.0 + (production * 10)
            return 0.0  # No need to attack our own peaceful nodes

        # 3. Neutral nodes: high ROI early-to-mid game
        if owner in (None, 0):
            # Penalize far neutral nodes early on
            base = 120.0 + (production * 15.0) - (dist_from_home * 12.0)
            # Early game rush bonus
            if obs.current_turn < 20:
                base += 80.0
            return max(10.0, base)

        # 4. Enemy-owned nodes: target weak/undefended nodes or high-production hubs
        enemy_units = self.last_seen_enemy.get(node.id, {})
        enemy_strength = sum(enemy_units.values())
        score = 90.0 + (production * 14.0) - (dist_from_home * 8.0) - (enemy_strength * 10.0)
        if relic_active:
            # Doubled node scores make enemy nodes much more valuable in endgame
            score *= 1.5
        return max(5.0, score)

    def _get_available_units(
        self, node, reserved: Dict[str, int], is_frontline: bool
    ) -> Dict[str, int]:
        avail = {"raider": 0, "guard": 0, "siege": 0, "scout": 0}
        if not node.units:
            return avail

        for u_str, count in node.units.items():
            key = u_str.lower()
            free = count - reserved.get(key, 0)
            # Keep 1 Scout stationed on frontline nodes for lane vision
            if key == "scout" and is_frontline:
                free = max(0, free - 1)
            # Keep a minimum garrison on frontline nodes unless counter-attacking
            if is_frontline and key == "guard":
                free = max(0, free - 1)
            avail[key] = max(0, free)
        return avail

    def _select_detachment(
        self,
        avail: Dict[str, int],
        enemy_garrison: Dict[str, int],
        is_neutral: bool,
        is_relic: bool,
    ) -> Dict[UnitType, int]:
        detachment: Dict[UnitType, int] = {}

        # Neutral capture: fast Raiders + 1 Scout for vision
        if is_neutral and sum(enemy_garrison.values()) == 0:
            if avail["raider"] >= 2:
                detachment[UnitType.RAIDER] = min(avail["raider"], 3)
            elif avail["guard"] >= 2:
                detachment[UnitType.GUARD] = 2
            if detachment and avail["scout"] >= 1:
                detachment[UnitType.SCOUT] = 1
            return detachment

        # Relic push: send everything available
        if is_relic:
            for k in ("guard", "siege", "raider", "scout"):
                if avail[k] > 0:
                    detachment[self.STR_TO_TYPE[k]] = avail[k]
            return detachment

        # Combat push: prioritize units that counter the enemy garrison
        prioritized_types = ["raider", "guard", "siege"]
        if enemy_garrison.get("guard", 0) > enemy_garrison.get("raider", 0):
            prioritized_types = ["siege", "guard", "raider"]
        elif enemy_garrison.get("raider", 0) > enemy_garrison.get("siege", 0):
            prioritized_types = ["guard", "raider", "siege"]
        elif enemy_garrison.get("siege", 0) > 0:
            prioritized_types = ["raider", "siege", "guard"]

        total_sent = 0
        for k in prioritized_types:
            if avail[k] > 0:
                detachment[self.STR_TO_TYPE[k]] = avail[k]
                total_sent += avail[k]

        if total_sent >= 2 and avail["scout"] > 0:
            detachment[UnitType.SCOUT] = 1

        return detachment

    # -------------------------------------------------------------------------
    # ECONOMY & ADAPTIVE RPS PRODUCTION
    # -------------------------------------------------------------------------

    def _plan_production(
        self,
        obs: BotObservation,
        my_nodes: List,
        all_nodes: List,
        frontline_ids: Set[int],
        total_units: int,
        enemy_comp: Dict[str, int],
        endgame_prep: bool,
        relic_active: bool,
    ) -> List[Order]:
        orders: List[Order] = []
        credits = obs.my_credits

        # Hard Upkeep Cap: Stay <= 30 units before endgame to avoid 1 credit/unit/turn drain
        unit_cap = 65 if endgame_prep else 30
        if total_units >= unit_cap:
            return orders

        # Choose spawn nodes closest to the active front or Relic
        target_anchor = self.relic_id if endgame_prep else self.enemy_home_id
        spawn_candidates = sorted(
            my_nodes,
            key=lambda n: (
                0 if n.id in frontline_ids else 1,
                self.get_distance(obs, n.id, target_anchor),
            ),
        )

        # Ensure frontline nodes each have at least 1 Scout for lane vision
        for f_id in frontline_ids:
            if credits < self.UNIT_COSTS[UnitType.SCOUT] or total_units >= unit_cap:
                break
            f_node = next((n for n in my_nodes if n.id == f_id), None)
            if f_node:
                scouts_here = (f_node.units or {}).get("scout", 0)
                if scouts_here == 0:
                    orders.append(self.train(f_node.id, UnitType.SCOUT, 1))
                    credits -= self.UNIT_COSTS[UnitType.SCOUT]
                    total_units += 1

        # Determine optimal unit to train based on Game Phase + RPS Counter Matrix
        while credits >= 10 and total_units < unit_cap:
            chosen_type = self._choose_next_unit_type(
                obs=obs,
                credits=credits,
                enemy_comp=enemy_comp,
                endgame_prep=endgame_prep,
                relic_active=relic_active,
            )
            cost = self.UNIT_COSTS[chosen_type]
            if credits < cost:
                break

            # Pick best spawn node (prefer frontline nodes near the action)
            spawn_node = spawn_candidates[0]
            orders.append(self.train(spawn_node.id, chosen_type, 1))
            credits -= cost
            total_units += 1

        return orders

    def _choose_next_unit_type(
        self,
        obs: BotObservation,
        credits: int,
        enemy_comp: Dict[str, int],
        endgame_prep: bool,
        relic_active: bool,
    ) -> UnitType:
        # Phase 1: Early Expansion (Turns 1-14) -> Raiders for rapid neutral node capture
        if obs.current_turn < 14 and sum(enemy_comp.values()) < 3:
            return UnitType.RAIDER

        # Phase 2: Counter visible enemy composition
        e_raiders = enemy_comp.get("raider", 0)
        e_guards = enemy_comp.get("guard", 0)
        e_siege = enemy_comp.get("siege", 0)

        # If enemy is Guard-heavy (common on Node 7 defense), build Siege
        if e_guards >= max(e_raiders, e_siege) and e_guards > 0 and credits >= 18:
            return UnitType.SIEGE

        # If enemy is Raider-heavy, build Guards
        if e_raiders > max(e_guards, e_siege) and credits >= 12:
            return UnitType.GUARD

        # If enemy is Siege-heavy, build Raiders
        if e_siege > max(e_raiders, e_guards):
            return UnitType.RAIDER

        # Phase 3: Endgame Relic default mix (Guards to hold Node 7 + Siege to crack enemy Guards)
        if endgame_prep or relic_active:
            if credits >= 18 and obs.current_turn % 2 == 0:
                return UnitType.SIEGE
            if credits >= 12:
                return UnitType.GUARD

        # Balanced default
        return UnitType.GUARD if credits >= 12 else UnitType.RAIDER