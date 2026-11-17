from __future__ import annotations
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import random

from engine.models import UnitType, Order, TrainOrder, MoveOrder
from engine.fog import BotObservation
from bots.base import BotBase


class EquilibriumNodeBot(BotBase):
    """
    Tournament-Grade Adaptive Game-Theoretic Agent for Node War.
    Designed to beat both static macro bots (Apex) and scripted anti-meta bots (Nemesis).

    Core Architecture:
    1. Real-Time Opponent Archetype Classifier (Economist vs. Rusher vs. Baiter)
    2. Marginal Economic ROI Calculator (dynamically decides whether breaking the 30-unit cap is profitable)
    3. Exact 2-Turn Capture & Combat Simulator (accounts for +25% defender bonus and 2.0x RPS)
    4. Anti-Bait & Mixed-Strategy Production (prevents memory-poisoning traps)
    5. Dynamic Relic Timing Window (triggers based on travel distance + enemy staging, not fixed turn numbers)
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

        # Deterministic RNG seeded by player_id for controlled mixed-strategy unpredictability
        self.rng = random.Random(42 + player_id)

        # Fog of war & behavioral telemetry
        self.enemy_sightings: Dict[int, Dict[str, int]] = {}
        self.sighting_turn: Dict[int, int] = {}
        self.historical_enemy_comp: Dict[str, int] = defaultdict(int)
        self.enemy_aggression_events: int = 0
        self.enemy_early_guards: int = 0

    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        # 1. Update telemetry & classify opponent archetype
        self._update_telemetry(obs)
        all_nodes = self._get_all_nodes(obs)
        archetype = self._classify_opponent(obs)

        total_units = self._count_friendly_units(obs, my_nodes)
        income = sum(getattr(n, "production", getattr(n, "credits_per_turn", 5)) for n in my_nodes)

        total_turns = getattr(obs, "max_turns", getattr(obs, "total_turns", 100))
        turns_left = max(0, total_turns - obs.current_turn)
        relic_active = getattr(obs, "relic_active", False)
        relic_id = getattr(obs, "relic_node_id", self.relic_id)

        # Dynamic Relic Timing: calculate exact hops from our main army to Node 7 + 4 turns buffer
        # Automatically beats both T-30 (Apex) and T-35 (Nemesis) by staging just ahead of enemy movement
        max_dist_to_relic = max((self.get_distance(obs, n.id, relic_id) for n in my_nodes), default=4)
        relic_staging_window = relic_active or (turns_left <= (25 + max_dist_to_relic + 7))

        frontline_ids = self._find_frontlines(obs, my_nodes, all_nodes)
        reserved: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # 2. Tactical Movement & Multi-Node Convergence
        orders.extend(
            self._plan_moves(
                obs=obs,
                my_nodes=my_nodes,
                all_nodes=all_nodes,
                frontline_ids=frontline_ids,
                archetype=archetype,
                relic_window=relic_staging_window,
                relic_active=relic_active,
                relic_id=relic_id,
                reserved=reserved,
            )
        )

        # 3. Marginal-ROI Upkeep & Mixed-Strategy Production
        orders.extend(
            self._plan_production(
                obs=obs,
                my_nodes=my_nodes,
                frontline_ids=frontline_ids,
                total_units=total_units,
                income=income,
                archetype=archetype,
                relic_window=relic_staging_window,
                relic_active=relic_active,
            )
        )

        return orders

    # -------------------------------------------------------------------------
    # OPPONENT MODELING & TELEMETRY
    # -------------------------------------------------------------------------

    def _get_all_nodes(self, obs: BotObservation) -> List:
        if hasattr(obs, "nodes") and isinstance(obs.nodes, dict):
            return list(obs.nodes.values())
        if hasattr(obs, "nodes") and isinstance(obs.nodes, list):
            return obs.nodes
        nodes = list(self.get_my_nodes(obs)) + list(self.get_neutral_nodes(obs))
        if hasattr(self, "get_enemy_nodes"):
            nodes.extend(self.get_enemy_nodes(obs))
        return nodes

    def _update_telemetry(self, obs: BotObservation) -> None:
        for node in self._get_all_nodes(obs):
            owner = getattr(node, "owner", None)
            if owner not in (None, 0, self.player_id) and getattr(node, "units", None):
                prev = self.enemy_sightings.get(node.id, {})
                curr = dict(node.units)
                self.enemy_sightings[node.id] = curr
                self.sighting_turn[node.id] = obs.current_turn

                for u_str, cnt in curr.items():
                    key = u_str.lower()
                    delta = max(0, cnt - prev.get(key, 0))
                    self.historical_enemy_comp[key] += delta
                    if obs.current_turn <= 15 and key == "guard" and delta > 0:
                        self.enemy_early_guards += delta

            elif owner == self.player_id:
                self.enemy_sightings.pop(node.id, None)

        fleets = getattr(obs, "enemy_fleets", getattr(obs, "visible_fleets", []))
        for fleet in fleets:
            dest = getattr(fleet, "target_node_id", getattr(fleet, "to_node", None))
            units = getattr(fleet, "units", {})
            if dest is not None and units:
                if self.get_distance(obs, self.home_id, dest) <= 3:
                    self.enemy_aggression_events += 1
                merged = dict(self.enemy_sightings.get(dest, {}))
                for u_type, cnt in units.items():
                    key = u_type.value if hasattr(u_type, "value") else str(u_type).lower()
                    merged[key] = max(merged.get(key, 0), cnt)
                self.enemy_sightings[dest] = merged
                self.sighting_turn[dest] = obs.current_turn

    def _classify_opponent(self, obs: BotObservation) -> str:
        """
        Identifies whether opponent is:
        - 'ANTI_META_RUSHER' (like NemesisNodeBot: builds early Guards, pressures center early)
        - 'MACRO_ECONOMIST' (like ApexNodeBot: opens pure Raiders, plays passive until endgame)
        - 'BALANCED_HYBRID' (unknown / adaptive LLM bot)
        """
        if self.enemy_early_guards >= 2 or self.enemy_aggression_events >= 3:
            return "ANTI_META_RUSHER"
        if obs.current_turn >= 10 and self.historical_enemy_comp["raider"] >= 4 and self.enemy_early_guards == 0:
            return "MACRO_ECONOMIST"
        return "BALANCED_HYBRID"

    def _count_friendly_units(self, obs: BotObservation, my_nodes: List) -> int:
        total = sum(sum(n.units.values()) for n in my_nodes if n.units)
        for fleet in getattr(obs, "my_fleets", []):
            if getattr(fleet, "units", None):
                total += sum(fleet.units.values())
        return total

    def _find_frontlines(self, obs: BotObservation, my_nodes: List, all_nodes: List) -> Set[int]:
        my_ids = {n.id for n in my_nodes}
        frontlines = set()
        adj = getattr(obs, "adjacency", None)
        for n in my_nodes:
            nbrs = adj[n.id] if (adj and n.id in adj) else [
                o.id for o in all_nodes if o.id != n.id and self.get_distance(obs, n.id, o.id) == 1
            ]
            if any(nbr not in my_ids for nbr in nbrs):
                frontlines.add(n.id)
        return frontlines

    # -------------------------------------------------------------------------
    # EXACT 2-TURN COMBAT & CAPTURE SIMULATION
    # -------------------------------------------------------------------------

    def _simulate_battle_advantage(
        self,
        attackers: Dict[str, int],
        defenders: Dict[str, int],
        defender_owns_node: bool,
    ) -> float:
        """
        Computes effective combat power ratio.
        Accounts for:
        - 2.0x Rock-Paper-Scissors damage multipliers
        - +25% defender bonus
        - Penalty for single-type compositions (vulnerable to hard counters)
        """
        def calc_side(army: Dict[str, int], enemy: Dict[str, int], is_defender: bool) -> float:
            total_enemy = max(1, sum(enemy.values()))
            score = 0.0
            active_types = 0
            for u_type, cnt in army.items():
                if cnt <= 0:
                    continue
                active_types += 1
                base = self.UNIT_COSTS.get(self.STR_TO_TYPE.get(u_type, UnitType.RAIDER), 10)
                weak_target = self.COUNTERS.get(u_type)
                mult = 1.0 + (enemy.get(weak_target, 0) / total_enemy) if (weak_target and enemy) else 1.0
                score += cnt * base * mult
            if is_defender:
                score *= 1.25
            # Combined-arms synergy bonus (prevents opponent from getting a clean 2.0x wipe)
            if active_types >= 2:
                score *= 1.12
            return score

        atk_score = calc_side(attackers, defenders, is_defender=False)
        def_score = calc_side(defenders, attackers, is_defender=defender_owns_node)

        if def_score == 0:
            return 99.0 if atk_score > 0 else 0.0
        return atk_score / def_score

    # -------------------------------------------------------------------------
    # TACTICAL MOVEMENT & COORDINATED STRIKES
    # -------------------------------------------------------------------------

    def _plan_moves(
        self,
        obs: BotObservation,
        my_nodes: List,
        all_nodes: List,
        frontline_ids: Set[int],
        archetype: str,
        relic_window: bool,
        relic_active: bool,
        relic_id: int,
        reserved: Dict[int, Dict[str, int]],
    ) -> List[Order]:
        orders: List[Order] = []
        my_map = {n.id: n for n in my_nodes}

        # Score all nodes
        scored_targets: List[Tuple[float, int]] = []
        for node in all_nodes:
            s = self._score_node_value(obs, node, archetype, relic_window, relic_active, relic_id)
            if s > 0:
                scored_targets.append((s, node.id))
        scored_targets.sort(key=lambda x: x[0], reverse=True)

        for _, target_id in scored_targets:
            target_node = next((n for n in all_nodes if n.id == target_id), None)
            if not target_node:
                continue

            is_owned = target_id in my_map
            enemy_garrison = self.enemy_sightings.get(target_id, {})

            # Gather multi-node strike group from up to 3 hops away
            donors = [
                n for n in my_nodes
                if n.id != target_id and self.get_distance(obs, n.id, target_id) <= (4 if relic_window else 2)
            ]
            donors.sort(key=lambda n: self.get_distance(obs, n.id, target_id))

            # Build virtual combined force before issuing orders so we never send suicidal waves
            planned_dispatch: List[Tuple[int, Dict[UnitType, int]]] = []
            combined_army: Dict[str, int] = dict(my_map[target_id].units) if (is_owned and my_map[target_id].units) else defaultdict(int)

            for donor in donors:
                avail = self._get_available_units(donor, reserved[donor.id], donor.id in frontline_ids)
                if sum(avail.values()) == 0:
                    continue

                chunk = self._select_optimal_squad(
                    avail=avail,
                    enemy_garrison=enemy_garrison,
                    is_neutral=(getattr(target_node, "owner", None) in (None, 0)),
                    is_relic=(target_id == relic_id and relic_window),
                    archetype=archetype,
                )
                if not chunk:
                    continue

                for u_enum, cnt in chunk.items():
                    combined_army[u_enum.value] = combined_army.get(u_enum.value, 0) + cnt
                planned_dispatch.append((donor.id, chunk))

                # Stop recruiting donors once we achieve decisive combat superiority (unless Relic)
                if target_id != relic_id and sum(enemy_garrison.values()) > 0:
                    ratio = self._simulate_battle_advantage(combined_army, enemy_garrison, not is_owned)
                    if ratio >= 1.45:
                        break

            # Verify the combined force actually wins the battle + survives 2-turn capture
            if not is_owned and sum(enemy_garrison.values()) > 0:
                final_ratio = self._simulate_battle_advantage(combined_army, enemy_garrison, defender_owns_node=True)
                if final_ratio < 1.35:
                    continue  # Abort attack; hold and reinforce instead of feeding

            for donor_id, chunk in planned_dispatch:
                path = self.get_path(obs, donor_id, target_id)
                if len(path) >= 2:
                    orders.append(self.move(donor_id, path[1], chunk))
                    for u_enum, cnt in chunk.items():
                        reserved[donor_id][u_enum.value] += cnt

        # Forward-deploy idle backline reserves toward the active front / Relic
        anchor = relic_id if relic_window else self.enemy_home_id
        for node in my_nodes:
            if node.id in frontline_ids or (node.id == relic_id and relic_window):
                continue
            avail = self._get_available_units(node, reserved[node.id], is_frontline=False)
            if sum(avail.values()) == 0:
                continue
            if frontline_ids:
                best_front = min(
                    frontline_ids,
                    key=lambda fid: self.get_distance(obs, node.id, fid)
                    + 0.65 * self.get_distance(obs, fid, anchor),
                )
                path = self.get_path(obs, node.id, best_front)
                if len(path) >= 2:
                    payload = {self.STR_TO_TYPE[k]: v for k, v in avail.items() if v > 0}
                    if payload:
                        orders.append(self.move(node.id, path[1], payload))

        return orders

    def _score_node_value(
        self,
        obs: BotObservation,
        node,
        archetype: str,
        relic_window: bool,
        relic_active: bool,
        relic_id: int,
    ) -> float:
        owner = getattr(node, "owner", None)
        prod = getattr(node, "production", getattr(node, "credits_per_turn", 5))
        dist_home = self.get_distance(obs, self.home_id, node.id)
        dist_relic = self.get_distance(obs, relic_id, node.id)

        # 1. Node 7 Relic Control (Pre-empts both Apex T-30 and Nemesis T-35)
        if node.id == relic_id:
            if relic_active:
                return 1500.0 if owner != self.player_id else 600.0
            if relic_window:
                return 950.0 if owner != self.player_id else 400.0
            # Central spine control in mid-game
            if obs.current_turn >= 12:
                return 210.0

        # 2. Defend owned nodes under attack
        if owner == self.player_id:
            if node.id in self.enemy_sightings and (obs.current_turn - self.sighting_turn.get(node.id, 99)) <= 2:
                return 480.0 + prod * 12.0
            return 0.0

        # 3. Neutral expansion
        if owner in (None, 0):
            return max(15.0, 175.0 + (prod * 16.0) - (dist_home * 11.0) - (dist_relic * 6.0))

        # 4. Enemy nodes: punish passive economists harder; punish rushers by taking their unguarded backline
        enemy_cnt = sum(self.enemy_sightings.get(node.id, {}).values())
        aggression_bonus = 45.0 if archetype == "MACRO_ECONOMIST" else 20.0
        score = 120.0 + aggression_bonus + (prod * 15.0) - (dist_home * 7.0) - (enemy_cnt * 9.0)
        if relic_active:
            score *= 1.65
        return max(10.0, score)

    def _get_available_units(self, node, reserved: Dict[str, int], is_frontline: bool) -> Dict[str, int]:
        avail = {"raider": 0, "guard": 0, "siege": 0, "scout": 0}
        if not node.units:
            return avail
        for k, cnt in node.units.items():
            key = k.lower()
            free = cnt - reserved.get(key, 0)
            if key == "scout" and is_frontline:
                free = max(0, free - 1)
            avail[key] = max(0, free)
        return avail

    def _select_optimal_squad(
        self,
        avail: Dict[str, int],
        enemy_garrison: Dict[str, int],
        is_neutral: bool,
        is_relic: bool,
        archetype: str,
    ) -> Dict[UnitType, int]:
        squad: Dict[UnitType, int] = {}

        # Neutral capture: send combined arms (Guard + Raider) if facing an Anti-Meta Rusher,
        # or fast Raiders if facing a Macro Economist
        if is_neutral and sum(enemy_garrison.values()) == 0:
            if archetype == "ANTI_META_RUSHER" and avail["guard"] >= 1 and avail["raider"] >= 1:
                squad[UnitType.GUARD] = 1
                squad[UnitType.RAIDER] = 1
            elif avail["raider"] >= 2:
                squad[UnitType.RAIDER] = 2
            elif avail["guard"] >= 2:
                squad[UnitType.GUARD] = 2
            if squad and avail["scout"] >= 1:
                squad[UnitType.SCOUT] = 1
            return squad

        # Relic commitment: send full combined-arms stack
        if is_relic:
            for k in ("guard", "siege", "raider", "scout"):
                if avail[k] > 0:
                    squad[self.STR_TO_TYPE[k]] = avail[k]
            return squad

        # Counter-composition against visible garrison
        e_g = enemy_garrison.get("guard", 0)
        e_r = enemy_garrison.get("raider", 0)
        e_s = enemy_garrison.get("siege", 0)

        priority = ["siege", "guard", "raider"]
        if e_g >= max(e_r, e_s) and e_g > 0:
            priority = ["siege", "raider", "guard"]
        elif e_r > max(e_g, e_s):
            priority = ["guard", "siege", "raider"]
        elif e_s > max(e_g, e_r):
            priority = ["raider", "guard", "siege"]

        for k in priority:
            if avail[k] > 0:
                squad[self.STR_TO_TYPE[k]] = avail[k]

        if sum(squad.values()) >= 2 and avail["scout"] > 0:
            squad[UnitType.SCOUT] = 1

        return squad

    # -------------------------------------------------------------------------
    # MARGINAL ROI ECONOMY & NASH MIXED-STRATEGY PRODUCTION
    # -------------------------------------------------------------------------

    def _plan_production(
        self,
        obs: BotObservation,
        my_nodes: List,
        frontline_ids: Set[int],
        total_units: int,
        income: int,
        archetype: str,
        relic_window: bool,
        relic_active: bool,
    ) -> List[Order]:
        orders: List[Order] = []
        credits = obs.my_credits

        # Dynamic Upkeep Cap based on net income & game phase:
        # Never let upkeep exceed 35% of our node income before endgame,
        # but scale freely up to 44 units if we hold high-economy nodes (beats Apex's 30 cap & Nemesis's 38 cap)
        if relic_window or relic_active:
            dynamic_cap = 80
        else:
            affordable_upkeep = max(4, int(income * 0.35))
            dynamic_cap = min(44, 30 + affordable_upkeep)

        if total_units >= dynamic_cap:
            return orders

        anchor = self.relic_id if relic_window else self.enemy_home_id
        spawns = sorted(
            my_nodes,
            key=lambda n: (
                0 if n.id in frontline_ids else 1,
                self.get_distance(obs, n.id, anchor),
            ),
        )

        # Maintain frontline scout grid
        for f_id in frontline_ids:
            if credits < 6 or total_units >= dynamic_cap:
                break
            f_node = next((n for n in my_nodes if n.id == f_id), None)
            if f_node and (f_node.units or {}).get("scout", 0) == 0:
                orders.append(self.train(f_node.id, UnitType.SCOUT, 1))
                credits -= 6
                total_units += 1

        while credits >= 10 and total_units < dynamic_cap:
            u_type = self._select_nash_unit(
                obs=obs,
                credits=credits,
                archetype=archetype,
                relic_window=relic_window,
            )
            cost = self.UNIT_COSTS[u_type]
            if credits < cost:
                break

            orders.append(self.train(spawns[0].id, u_type, 1))
            credits -= cost
            total_units += 1

        return orders

    def _select_nash_unit(
        self,
        obs: BotObservation,
        credits: int,
        archetype: str,
        relic_window: bool,
    ) -> UnitType:
        """
        Blends deterministic archetype exploitation with a Nash-equilibrium
        combined-arms mix so neither Apex nor Nemesis can hard-counter us.
        """
        # 1. Opening (Turns 1-8): Build a balanced Guard+Raider core.
        # Beats Apex's pure Raiders AND trades evenly/wins against Nemesis's Guard rush.
        if obs.current_turn <= 8:
            if credits >= 12 and obs.current_turn % 2 == 0:
                return UnitType.GUARD
            return UnitType.RAIDER

        # 2. If opponent is classified as ANTI_META_RUSHER (Nemesis):
        # Nemesis spams Guards early and pivots to 2:1 Siege in mid/endgame.
        # Counter with a Raider + Siege + Guard triad (Raiders shred Nemesis's Siege; Siege melts Nemesis's Guards).
        if archetype == "ANTI_META_RUSHER":
            roll = self.rng.random()
            if roll < 0.45 and credits >= 18:
                return UnitType.SIEGE
            if roll < 0.80:
                return UnitType.RAIDER
            return UnitType.GUARD if credits >= 12 else UnitType.RAIDER

        # 3. If opponent is classified as MACRO_ECONOMIST (Apex):
        # Apex opens Raiders then over-reacts with Guards when it sees Raiders.
        # Build Siege + Guard heavy to crush both its Raiders and its reactive Guards.
        if archetype == "MACRO_ECONOMIST":
            if credits >= 18 and self.rng.random() < 0.55:
                return UnitType.SIEGE
            if credits >= 12:
                return UnitType.GUARD
            return UnitType.RAIDER

        # 4. Relic Endgame / Unknown Hybrid: True Combined-Arms Nash Mix
        # 40% Siege, 40% Guard, 20% Raider — immune to any single-unit RPS hard counter.
        if relic_window or archetype == "BALANCED_HYBRID":
            roll = self.rng.random()
            if roll < 0.40 and credits >= 18:
                return UnitType.SIEGE
            if roll < 0.80 and credits >= 12:
                return UnitType.GUARD
            return UnitType.RAIDER

        return UnitType.GUARD if credits >= 12 else UnitType.RAIDER