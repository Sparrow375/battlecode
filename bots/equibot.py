from __future__ import annotations
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict

from engine.models import UnitType, Order, TrainOrder, MoveOrder
from engine.fog import BotObservation
from bots.base import BotBase


class NemesisNodeBot(BotBase):
    """
    Purpose-built counter-AI engineered to dismantle ApexNodeBot.

    Anti-Apex Exploits:
    1. Early Guard Ambush (Turns 1-14): Exploits Apex's hardcoded pure-Raider opening.
    2. Tempo Over-Cap (38 units): Breaks Apex's rigid 30-unit cap in mid-game to win map control.
    3. RPS Bait-and-Switch: Baits Apex's 6-turn memory into over-producing Guards, then crushes with Siege.
    4. Multi-Node Pincer Strikes: Converges forces from multiple nodes simultaneously (bypassing Apex's 1-donor limit).
    5. Early Node 7 Lockout: Fortifies Node 7 at T-35 (5 turns before Apex's T-30 endgame trigger).
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

        # Fog-of-war tracking + Bait state tracking
        self.enemy_sightings: Dict[int, Dict[str, int]] = {}
        self.sighting_turn: Dict[int, int] = {}
        self.baited_guard_phase: bool = False

    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        self._scan_board(obs)
        all_nodes = self._get_all_nodes(obs)
        total_units = self._total_army_size(obs, my_nodes)
        enemy_comp = self._visible_enemy_totals(obs)

        total_turns = getattr(obs, "max_turns", getattr(obs, "total_turns", 100))
        turns_left = max(0, total_turns - obs.current_turn)
        relic_active = getattr(obs, "relic_active", False)
        relic_id = getattr(obs, "relic_node_id", self.relic_id)

        # Trigger Relic lockdown 5 turns BEFORE ApexNodeBot wakes up (T-35 vs Apex's T-30)
        early_relic_lock = relic_active or (turns_left <= 35)

        frontline_ids = self._get_frontline_ids(obs, my_nodes, all_nodes)
        reserved: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        # 1. Execute Multi-Node Pincers, Early Guard Ambushes, and Relic Lockdown
        orders.extend(
            self._execute_tactics(
                obs=obs,
                my_nodes=my_nodes,
                all_nodes=all_nodes,
                frontline_ids=frontline_ids,
                early_relic_lock=early_relic_lock,
                relic_active=relic_active,
                relic_id=relic_id,
                reserved=reserved,
            )
        )

        # 2. Execute Anti-Meta Production (Guard Rush -> RPS Bait-and-Switch -> Siege Hammer)
        orders.extend(
            self._execute_production(
                obs=obs,
                my_nodes=my_nodes,
                frontline_ids=frontline_ids,
                total_units=total_units,
                enemy_comp=enemy_comp,
                early_relic_lock=early_relic_lock,
                relic_active=relic_active,
            )
        )

        return orders

    # -------------------------------------------------------------------------
    # BOARD AWARENESS & INTEL
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

    def _scan_board(self, obs: BotObservation) -> None:
        for node in self._get_all_nodes(obs):
            owner = getattr(node, "owner", None)
            if owner not in (None, 0, self.player_id) and getattr(node, "units", None):
                self.enemy_sightings[node.id] = dict(node.units)
                self.sighting_turn[node.id] = obs.current_turn
            elif owner == self.player_id:
                self.enemy_sightings.pop(node.id, None)

        fleets = getattr(obs, "enemy_fleets", getattr(obs, "visible_fleets", []))
        for fleet in fleets:
            dest = getattr(fleet, "target_node_id", getattr(fleet, "to_node", None))
            units = getattr(fleet, "units", {})
            if dest is not None and units:
                merged = dict(self.enemy_sightings.get(dest, {}))
                for u_type, cnt in units.items():
                    key = u_type.value if hasattr(u_type, "value") else str(u_type).lower()
                    merged[key] = max(merged.get(key, 0), cnt)
                self.enemy_sightings[dest] = merged
                self.sighting_turn[dest] = obs.current_turn

    def _total_army_size(self, obs: BotObservation, my_nodes: List) -> int:
        total = sum(sum(n.units.values()) for n in my_nodes if n.units)
        for fleet in getattr(obs, "my_fleets", []):
            if getattr(fleet, "units", None):
                total += sum(fleet.units.values())
        return total

    def _visible_enemy_totals(self, obs: BotObservation) -> Dict[str, int]:
        totals = {"raider": 0, "guard": 0, "siege": 0, "scout": 0}
        for nid, units in self.enemy_sightings.items():
            if obs.current_turn - self.sighting_turn.get(nid, 0) <= 5:
                for k, v in units.items():
                    if k.lower() in totals:
                        totals[k.lower()] += v
        return totals

    def _get_neighbors(self, obs: BotObservation, node_id: int, all_nodes: List) -> List[int]:
        if hasattr(obs, "adjacency") and node_id in obs.adjacency:
            return list(obs.adjacency[node_id])
        return [
            o.id for o in all_nodes
            if o.id != node_id and self.get_distance(obs, node_id, o.id) == 1
        ]

    def _get_frontline_ids(self, obs: BotObservation, my_nodes: List, all_nodes: List) -> Set[int]:
        my_ids = {n.id for n in my_nodes}
        return {
            n.id for n in my_nodes
            if any(nbr not in my_ids for nbr in self._get_neighbors(obs, n.id, all_nodes))
        }

    # -------------------------------------------------------------------------
    # TACTICAL EXECUTION (PINCERS, BAIT-AND-SWITCH, RELIC LOCKDOWN)
    # -------------------------------------------------------------------------

    def _execute_tactics(
        self,
        obs: BotObservation,
        my_nodes: List,
        all_nodes: List,
        frontline_ids: Set[int],
        early_relic_lock: bool,
        relic_active: bool,
        relic_id: int,
        reserved: Dict[int, Dict[str, int]],
    ) -> List[Order]:
        orders: List[Order] = []
        my_map = {n.id: n for n in my_nodes}

        # Score targets with anti-Apex priorities
        targets: List[Tuple[float, int]] = []
        for node in all_nodes:
            score = self._score_target(obs, node, early_relic_lock, relic_active, relic_id)
            if score > 0:
                targets.append((score, node.id))
        targets.sort(key=lambda x: x[0], reverse=True)

        for _, target_id in targets:
            target_node = next((n for n in all_nodes if n.id == target_id), None)
            if not target_node:
                continue

            is_owned = target_id in my_map
            enemy_units = self.enemy_sightings.get(target_id, {})
            enemy_power = self._raw_defensive_power(enemy_units, owned_by_defender=not is_owned)

            # Gather ALL donors within 2 hops to execute a synchronized multi-node pincer
            nearby_donors = [
                n for n in my_nodes
                if n.id != target_id and self.get_distance(obs, n.id, target_id) <= (3 if early_relic_lock else 2)
            ]
            nearby_donors.sort(key=lambda n: self.get_distance(obs, n.id, target_id))

            committed_power = 0.0
            existing_friendly = dict(my_map[target_id].units) if is_owned and my_map[target_id].units else {}
            committed_power += self._raw_offensive_power(existing_friendly, enemy_units)

            required_power = max(18.0, enemy_power * 1.40)
            if target_id == relic_id and early_relic_lock:
                required_power = max(40.0, enemy_power * 1.65)

            for donor in nearby_donors:
                if committed_power >= required_power and target_id != relic_id:
                    break

                avail = self._free_units(donor, reserved[donor.id], donor.id in frontline_ids)
                if sum(avail.values()) == 0:
                    continue

                # Select optimal counter-units from this donor
                payload = self._build_counter_payload(
                    avail=avail,
                    enemy_units=enemy_units,
                    is_neutral=(getattr(target_node, "owner", None) in (None, 0)),
                    is_relic=(target_id == relic_id and early_relic_lock),
                    turn=obs.current_turn,
                )
                if not payload:
                    continue

                path = self.get_path(obs, donor.id, target_id)
                if len(path) >= 2:
                    orders.append(self.move(donor.id, path[1], payload))
                    str_payload = {k.value: v for k, v in payload.items()}
                    committed_power += self._raw_offensive_power(str_payload, enemy_units)
                    for u_enum, cnt in payload.items():
                        reserved[donor.id][u_enum.value] += cnt

        # Forward-funnel all remaining backline units toward Node 7 / active front
        anchor = relic_id if early_relic_lock else self.enemy_home_id
        for node in my_nodes:
            if node.id in frontline_ids or (node.id == relic_id and early_relic_lock):
                continue
            avail = self._free_units(node, reserved[node.id], is_frontline=False)
            if sum(avail.values()) == 0:
                continue

            if frontline_ids:
                best_front = min(
                    frontline_ids,
                    key=lambda fid: self.get_distance(obs, node.id, fid)
                    + 0.6 * self.get_distance(obs, fid, anchor),
                )
                path = self.get_path(obs, node.id, best_front)
                if len(path) >= 2:
                    move_dict = {self.STR_TO_TYPE[k]: v for k, v in avail.items() if v > 0}
                    if move_dict:
                        orders.append(self.move(node.id, path[1], move_dict))

        return orders

    def _score_target(
        self,
        obs: BotObservation,
        node,
        early_relic_lock: bool,
        relic_active: bool,
        relic_id: int,
    ) -> float:
        owner = getattr(node, "owner", None)
        prod = getattr(node, "production", getattr(node, "credits_per_turn", 5))
        dist_home = self.get_distance(obs, self.home_id, node.id)
        dist_relic = self.get_distance(obs, relic_id, node.id)

        # Priority 1: Seize & Fortify Node 7 at T-35 (before Apex wakes up at T-30)
        if node.id == relic_id:
            if relic_active:
                return 1200.0 if owner != self.player_id else 500.0
            if early_relic_lock:
                return 850.0 if owner != self.player_id else 350.0
            # Even mid-game, Node 7 is the central choke point
            if obs.current_turn >= 15:
                return 190.0

        # Priority 2: Defend threatened owned nodes
        if owner == self.player_id:
            if node.id in self.enemy_sightings and (obs.current_turn - self.sighting_turn.get(node.id, 99)) <= 2:
                return 420.0 + prod * 12.0
            return 0.0

        # Priority 3: Neutral nodes along the central spine (closest to Node 7)
        if owner in (None, 0):
            return max(15.0, 160.0 + (prod * 16.0) - (dist_home * 10.0) - (dist_relic * 8.0))

        # Priority 4: Aggressively snipe Apex's outer economy nodes while it sits at <=30 units
        enemy_cnt = sum(self.enemy_sightings.get(node.id, {}).values())
        score = 130.0 + (prod * 15.0) - (dist_home * 7.0) - (enemy_cnt * 8.0)
        if relic_active:
            score *= 1.6
        return max(10.0, score)

    def _free_units(self, node, reserved: Dict[str, int], is_frontline: bool) -> Dict[str, int]:
        free_map = {"raider": 0, "guard": 0, "siege": 0, "scout": 0}
        if not node.units:
            return free_map
        for k, cnt in node.units.items():
            key = k.lower()
            rem = cnt - reserved.get(key, 0)
            # Keep 1 Scout on frontlines to spot Apex's incoming single-detachment stacks
            if key == "scout" and is_frontline:
                rem = max(0, rem - 1)
            free_map[key] = max(0, rem)
        return free_map

    def _build_counter_payload(
        self,
        avail: Dict[str, int],
        enemy_units: Dict[str, int],
        is_neutral: bool,
        is_relic: bool,
        turn: int,
    ) -> Dict[UnitType, int]:
        payload: Dict[UnitType, int] = {}

        # Early Game (Turns 1-14): Send Guards + Raiders to crush Apex's pure-Raider openers
        if turn <= 14 and is_neutral and sum(enemy_units.values()) == 0:
            if avail["guard"] >= 1 and avail["raider"] >= 1:
                payload[UnitType.GUARD] = 1
                payload[UnitType.RAIDER] = min(avail["raider"], 2)
                return payload
            if avail["raider"] >= 2:
                payload[UnitType.RAIDER] = 2
                return payload

        # Relic Endgame: Flood with mixed Guard + Siege (un-counterable by single RPS type)
        if is_relic:
            for k in ("guard", "siege", "raider", "scout"):
                if avail[k] > 0:
                    payload[self.STR_TO_TYPE[k]] = avail[k]
            return payload

        # Counter-RPS selection against known enemy garrison
        e_guards = enemy_units.get("guard", 0)
        e_raiders = enemy_units.get("raider", 0)
        e_siege = enemy_units.get("siege", 0)

        order = ["siege", "guard", "raider"]
        if e_guards >= max(e_raiders, e_siege) and e_guards > 0:
            order = ["siege", "raider", "guard"]
        elif e_raiders > max(e_guards, e_siege):
            order = ["guard", "siege", "raider"]
        elif e_siege > max(e_guards, e_raiders):
            order = ["raider", "guard", "siege"]

        for k in order:
            if avail[k] > 0:
                payload[self.STR_TO_TYPE[k]] = avail[k]

        if sum(payload.values()) >= 2 and avail["scout"] > 0:
            payload[UnitType.SCOUT] = 1

        return payload

    def _raw_offensive_power(self, attackers: Dict[str, int], defenders: Dict[str, int]) -> float:
        power = 0.0
        total_def = max(1, sum(defenders.values()))
        for k, cnt in attackers.items():
            if cnt <= 0:
                continue
            cost = self.UNIT_COSTS.get(self.STR_TO_TYPE.get(k, UnitType.RAIDER), 10)
            weak = self.COUNTERS.get(k)
            mult = 1.0 + (defenders.get(weak, 0) / total_def) if weak and defenders else 1.0
            power += cnt * cost * mult
        return power

    def _raw_defensive_power(self, defenders: Dict[str, int], owned_by_defender: bool) -> float:
        power = 0.0
        for k, cnt in defenders.items():
            cost = self.UNIT_COSTS.get(self.STR_TO_TYPE.get(k, UnitType.RAIDER), 10)
            power += cnt * cost
        return power * (1.25 if owned_by_defender else 1.0)

    # -------------------------------------------------------------------------
    # ANTI-APEX PRODUCTION & BAIT-AND-SWITCH ECONOMY
    # -------------------------------------------------------------------------

    def _execute_production(
        self,
        obs: BotObservation,
        my_nodes: List,
        frontline_ids: Set[int],
        total_units: int,
        enemy_comp: Dict[str, int],
        early_relic_lock: bool,
        relic_active: bool,
    ) -> List[Order]:
        orders: List[Order] = []
        credits = obs.my_credits

        # Exploit Apex's 30-unit cap: run 38 units mid-game (small 8 cr/turn tax for +27% army size)
        # and 75 units in endgame
        army_cap = 75 if early_relic_lock else 38
        if total_units >= army_cap:
            return orders

        anchor = self.relic_id if early_relic_lock else self.enemy_home_id
        spawns = sorted(
            my_nodes,
            key=lambda n: (
                0 if n.id in frontline_ids else 1,
                self.get_distance(obs, n.id, anchor),
            ),
        )

        # Ensure frontline lane vision
        for f_id in frontline_ids:
            if credits < 6 or total_units >= army_cap:
                break
            f_node = next((n for n in my_nodes if n.id == f_id), None)
            if f_node and (f_node.units or {}).get("scout", 0) == 0:
                orders.append(self.train(f_node.id, UnitType.SCOUT, 1))
                credits -= 6
                total_units += 1

        while credits >= 10 and total_units < army_cap:
            unit_type = self._pick_anti_apex_unit(
                obs=obs,
                credits=credits,
                enemy_comp=enemy_comp,
                early_relic_lock=early_relic_lock,
                relic_active=relic_active,
            )
            cost = self.UNIT_COSTS[unit_type]
            if credits < cost:
                break

            orders.append(self.train(spawns[0].id, unit_type, 1))
            credits -= cost
            total_units += 1

        return orders

    def _pick_anti_apex_unit(
        self,
        obs: BotObservation,
        credits: int,
        enemy_comp: Dict[str, int],
        early_relic_lock: bool,
        relic_active: bool,
    ) -> UnitType:
        turn = obs.current_turn

        # Phase 1 (Turns 1-14): Apex is hardcoded to build pure Raiders.
        # Build Guards (2.0x vs Raiders) + fast Raiders to intercept & wipe its expansion squads.
        if turn <= 14:
            if credits >= 12 and turn % 2 == 1:
                return UnitType.GUARD
            return UnitType.RAIDER

        # Phase 2 (Turns 15-24): RPS Bait-and-Switch!
        # Flash Raiders early so Apex's 6-turn memory locks onto Guards, then pivot hard into Siege.
        if 15 <= turn <= 18:
            return UnitType.RAIDER
        if 19 <= turn <= 26 and credits >= 18:
            return UnitType.SIEGE

        # Phase 3 (Endgame / Relic Lock): Apex defaults to Guards + Siege.
        # Counter with a 2:1 Siege-to-Guard ratio (Siege melts Apex's Guards; our Guards block Apex's Raiders).
        if early_relic_lock or relic_active:
            if credits >= 18 and (turn % 3 != 0):
                return UnitType.SIEGE
            if credits >= 12:
                return UnitType.GUARD

        # Reactive hard-counter fallback
        e_guards = enemy_comp.get("guard", 0)
        e_raiders = enemy_comp.get("raider", 0)
        e_siege = enemy_comp.get("siege", 0)

        if e_guards >= max(e_raiders, e_siege) and e_guards > 0 and credits >= 18:
            return UnitType.SIEGE
        if e_raiders > max(e_guards, e_siege) and credits >= 12:
            return UnitType.GUARD
        if e_siege > max(e_guards, e_raiders):
            return UnitType.RAIDER

        return UnitType.SIEGE if credits >= 18 else UnitType.GUARD