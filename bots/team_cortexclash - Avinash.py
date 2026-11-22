from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from nodewar import (
        BotBase,
        BotObservation,
        UnitType,
        Order,
        resolve_combat,
    )
except ImportError:
    try:
        from validate_bot import (
            BotBase,
            BotObservation,
            UnitType,
            Order,
            resolve_combat,
        )
    except ImportError:
        from engine.models import UnitType, Order
        from engine.fog import BotObservation
        from engine.combat import resolve_combat
        from bots.base import BotBase

UNIT_ORDER = (UnitType.RAIDER, UnitType.GUARD, UnitType.SIEGE, UnitType.SCOUT)
COMBAT_TYPES = (UnitType.RAIDER, UnitType.GUARD, UnitType.SIEGE)
UNIT_COST = {
    UnitType.RAIDER: 10,
    UnitType.GUARD: 12,
    UnitType.SIEGE: 18,
    UnitType.SCOUT: 6,
}


def _army_dict(raw: Optional[Dict[str, int]]) -> Dict[UnitType, int]:
    res = {ut: 0 for ut in UNIT_ORDER}
    if not raw:
        return res
    for ut in UNIT_ORDER:
        val = raw.get(ut.value, raw.get(ut, 0))
        res[ut] = max(0, int(val))
    return res


def _combat_count(army: Dict[UnitType, int]) -> int:
    return army[UnitType.RAIDER] + army[UnitType.GUARD] + army[UnitType.SIEGE]


def _total_count(army: Dict[UnitType, int]) -> int:
    return army[UnitType.RAIDER] + army[UnitType.GUARD] + army[UnitType.SIEGE] + army[UnitType.SCOUT]


def _army_value(army: Dict[UnitType, int]) -> int:
    return (
        army[UnitType.RAIDER] * 10
        + army[UnitType.GUARD] * 12
        + army[UnitType.SIEGE] * 18
        + army[UnitType.SCOUT] * 6
    )


def _add_armies(a: Dict[UnitType, int], b: Dict[UnitType, int]) -> Dict[UnitType, int]:
    return {ut: a.get(ut, 0) + b.get(ut, 0) for ut in UNIT_ORDER}


class CompetitorBot(BotBase):
    def __init__(self, player_id: int):
        super().__init__(player_id)
        self.home_id = 0 if self.player_id == 1 else 14
        self.enemy_home_id = 14 if self.player_id == 1 else 0
        self._lane_time: Optional[Dict[Tuple[int, int], int]] = None

        if self.player_id == 1:
            self.bastion_a = 1
            self.bastion_b = 2
            self.gate_id = 3
            self.rig_id = 4
            self.outpost_a = 5
            self.outpost_b = 6
            self.enemy_rig = 10
            self.enemy_outpost_a = 9
            self.enemy_outpost_b = 8
            self.enemy_gate = 11
            self.my_half = {0, 1, 2, 3, 4, 5, 6}
        else:
            self.bastion_a = 13
            self.bastion_b = 12
            self.gate_id = 11
            self.rig_id = 10
            self.outpost_a = 9
            self.outpost_b = 8
            self.enemy_rig = 4
            self.enemy_outpost_a = 5
            self.enemy_outpost_b = 6
            self.enemy_gate = 3
            self.my_half = {14, 13, 12, 11, 10, 9, 8}

        self.opp_seen: Dict[UnitType, float] = {
            UnitType.RAIDER: 1.5,
            UnitType.GUARD: 3.0,
            UnitType.SIEGE: 2.5,
            UnitType.SCOUT: 1.0,
        }
        self.opp_est_bank: float = 30.0
        self.prev_opp_visible_val: int = 28
        self.pending_strike: Optional[Dict[str, Any]] = None
        self.counter_targets: Dict[int, int] = {}
        self.echo_waves: Dict[int, Dict[str, Any]] = {}

    def _get_lane_time(self, obs: BotObservation, u: int, v: int) -> int:
        if self._lane_time is None:
            lt: Dict[Tuple[int, int], int] = {}
            for lane in obs.lanes:
                a, b, t = lane["node_a"], lane["node_b"], lane["travel_turns"]
                lt[(a, b)] = t
                lt[(b, a)] = t
            self._lane_time = lt
        return self._lane_time.get((u, v), 99)

    def _estimate_upkeep(self, obs: BotObservation, extra_dom: int = 0) -> int:
        owned_nodes = sum(1 for n in obs.nodes.values() if n.owner == self.player_id)
        free_cap = 10 + 4 * owned_nodes
        dom = extra_dom
        fgn = 0
        for n in obs.nodes.values():
            if n.units:
                cnt = sum(n.units.values())
                if n.owner == self.player_id:
                    dom += cnt
                elif n.capturing_player == self.player_id:
                    fgn += cnt
        tr = sum(f.total_count for f in obs.my_fleets)
        tot = dom + fgn + tr
        if tot <= free_cap:
            return 0
        dom_shield = min(dom, free_cap)
        rem_shield = free_cap - dom_shield
        return (dom - dom_shield) + 2 * max(0, (fgn + tr) - rem_shield)

    def _update_intel(self, obs: BotObservation) -> None:
        for ut in UNIT_ORDER:
            self.opp_seen[ut] *= 0.86

        vis_val = 0
        opp_inc = 0
        for n in obs.nodes.values():
            if n.owner == self.opponent_id:
                opp_inc += n.production
                if n.units:
                    a = _army_dict(n.units)
                    vis_val += _army_value(a)
                    for ut in UNIT_ORDER:
                        self.opp_seen[ut] += a[ut] * 0.50
            elif n.capturing_player == self.opponent_id and n.units:
                a = _army_dict(n.units)
                vis_val += _army_value(a)
                for ut in UNIT_ORDER:
                    self.opp_seen[ut] += a[ut] * 0.50

        for f in obs.enemy_fleets:
            if f.is_revealed and f.units:
                a = _army_dict(f.units)
                vis_val += _army_value(a)
                for ut in UNIT_ORDER:
                    self.opp_seen[ut] += a[ut] * 0.85
            else:
                vis_val += f.total_count * 13

        delta_army = max(0, vis_val - self.prev_opp_visible_val)
        self.opp_est_bank = max(0.0, min(78.0, self.opp_est_bank + opp_inc - delta_army * 0.95 - 6.0))
        self.prev_opp_visible_val = vis_val

        t = obs.current_turn
        self.counter_targets = {k: exp for k, exp in self.counter_targets.items() if exp >= t}

    def _estimate_unrevealed(self, count: int) -> Dict[UnitType, int]:
        tot = sum(self.opp_seen[ut] for ut in COMBAT_TYPES)
        sc = 1 if count >= 4 else 0
        rem = max(0, count - sc)
        if tot <= 1e-6:
            g = rem // 2
            s = rem // 3
            r = max(0, rem - g - s)
            return {UnitType.RAIDER: r, UnitType.GUARD: g, UnitType.SIEGE: s, UnitType.SCOUT: sc}
        r = int(round(rem * self.opp_seen[UnitType.RAIDER] / tot))
        g = int(round(rem * self.opp_seen[UnitType.GUARD] / tot))
        s = max(0, rem - r - g)
        return {UnitType.RAIDER: r, UnitType.GUARD: g, UnitType.SIEGE: s, UnitType.SCOUT: sc}

    def _best_counter_type(self, enemy_army: Optional[Dict[UnitType, int]] = None) -> UnitType:
        if enemy_army is not None and _combat_count(enemy_army) > 0:
            r = float(enemy_army[UnitType.RAIDER])
            g = float(enemy_army[UnitType.GUARD])
            s = float(enemy_army[UnitType.SIEGE])
        else:
            r = self.opp_seen[UnitType.RAIDER]
            g = self.opp_seen[UnitType.GUARD]
            s = self.opp_seen[UnitType.SIEGE]
        sg = (2.0 * r + 1.0 * g + 0.5 * s) * 1.20
        ss = (2.0 * g + 1.0 * s + 0.5 * r) * 1.08
        sr = (2.0 * s + 1.0 * r + 0.5 * g) * 1.00
        return max(((sg, UnitType.GUARD), (ss, UnitType.SIEGE), (sr, UnitType.RAIDER)), key=lambda x: x[0])[1]

    def _pick_minimax_counter_train(
        self,
        tot_r: int,
        tot_g: int,
        tot_s: int,
        spendable: int,
    ) -> UnitType:
        opp_tot = max(1e-6, self.opp_seen[UnitType.RAIDER] + self.opp_seen[UnitType.GUARD] + self.opp_seen[UnitType.SIEGE])
        opp_r = self.opp_seen[UnitType.RAIDER] / opp_tot
        opp_g = self.opp_seen[UnitType.GUARD] / opp_tot
        opp_s = self.opp_seen[UnitType.SIEGE] / opp_tot

        want_g = 0.55 * 0.48 + 0.45 * min(0.75, opp_r * 1.35 + 0.15)
        want_s = 0.55 * 0.38 + 0.45 * min(0.70, opp_g * 1.35 + 0.10)
        want_r = 0.55 * 0.14 + 0.45 * min(0.70, opp_s * 1.45)

        norm = want_g + want_s + want_r
        want_g /= norm
        want_s /= norm
        want_r /= norm

        cur_tot = max(1, tot_r + tot_g + tot_s)
        deficits = [
            (want_g - tot_g / cur_tot, UnitType.GUARD),
            (want_s - tot_s / cur_tot, UnitType.SIEGE),
            (want_r - tot_r / cur_tot, UnitType.RAIDER),
        ]
        deficits.sort(key=lambda x: x[0], reverse=True)
        for _, ut in deficits:
            if UNIT_COST[ut] <= spendable:
                return ut
        return UnitType.RAIDER

    def _solve_jit_defense(
        self,
        cur_def: Dict[UnitType, int],
        threat: Dict[UnitType, int],
        def_bonus: float,
        max_budget: int,
    ) -> Optional[Dict[UnitType, int]]:
        att_sc = threat[UnitType.SCOUT] > 0
        sd0, sa0 = resolve_combat(
            cur_def, threat, defender_bonus=def_bonus,
            has_defender_scout=(cur_def[UnitType.SCOUT] > 0), has_attacker_scout=att_sc
        )
        if _combat_count(sd0) > 0 and _combat_count(sa0) == 0:
            if cur_def[UnitType.SCOUT] == 0 and max_budget >= 6:
                d_sc = dict(cur_def)
                d_sc[UnitType.SCOUT] = 1
                sd1, sa1 = resolve_combat(d_sc, threat, defender_bonus=def_bonus, has_defender_scout=True, has_attacker_scout=att_sc)
                loss0 = _army_value(cur_def) - _army_value(sd0)
                loss1 = _army_value(d_sc) - _army_value(sd1)
                if _combat_count(sd1) > 0 and _combat_count(sa1) == 0 and (loss1 + 6) < loss0:
                    return {UnitType.SCOUT: 1}
            return {}

        if max_budget < 6:
            return None

        r_t, g_t, s_t = threat[UnitType.RAIDER], threat[UnitType.GUARD], threat[UnitType.SIEGE]
        ranked_types = sorted(
            [
                ((2.0 * r_t + 1.0 * g_t + 0.5 * s_t) * 1.20, UnitType.GUARD),
                ((2.0 * g_t + 1.0 * s_t + 0.5 * r_t) * 1.08, UnitType.SIEGE),
                ((2.0 * s_t + 1.0 * r_t + 0.5 * g_t) * 1.00, UnitType.RAIDER),
            ],
            key=lambda x: x[0],
            reverse=True,
        )
        u1, u2 = ranked_types[0][1], ranked_types[1][1]
        c1, c2 = UNIT_COST[u1], UNIT_COST[u2]

        best_score = 1e18
        best_spawn: Optional[Dict[UnitType, int]] = None
        sc_options = (0, 1) if cur_def[UnitType.SCOUT] == 0 else (0,)
        max_n1 = min(14, max_budget // c1)

        for sc in sc_options:
            if sc * 6 > max_budget:
                continue
            for n1 in range(0, max_n1 + 1):
                cost1 = sc * 6 + n1 * c1
                if cost1 > max_budget:
                    break
                max_n2 = min(4 if n1 > 0 else 10, (max_budget - cost1) // c2)
                for n2 in range(0, max_n2 + 1):
                    if n1 == 0 and n2 == 0 and sc == 0:
                        continue
                    spend = cost1 + n2 * c2
                    trial = dict(cur_def)
                    trial[u1] += n1
                    trial[u2] += n2
                    trial[UnitType.SCOUT] += sc
                    sd, sa = resolve_combat(
                        trial, threat, defender_bonus=def_bonus,
                        has_defender_scout=(trial[UnitType.SCOUT] > 0), has_attacker_scout=att_sc
                    )
                    if _combat_count(sd) > 0 and _combat_count(sa) == 0:
                        loss = _army_value(trial) - _army_value(sd)
                        score = loss * 1.0 + spend * 0.20
                        if score < best_score:
                            best_score = score
                            sp: Dict[UnitType, int] = {}
                            if n1 > 0:
                                sp[u1] = n1
                            if n2 > 0:
                                sp[u2] = n2
                            if sc > 0:
                                sp[UnitType.SCOUT] = sc
                            best_spawn = sp
                        if n2 >= 2:
                            break
        return best_spawn

    def _select_attack_force(
        self,
        avail: Dict[UnitType, int],
        defenders: Dict[UnitType, int],
        effective_def_bonus: float,
        target_is_enemy: bool,
        can_enemy_train: bool,
        est_opp_jit_gold: float,
        is_high_priority: bool = False,
    ) -> Optional[Dict[UnitType, int]]:
        if _combat_count(avail) == 0:
            return None

        if not target_is_enemy:
            dr, dg, ds = defenders[UnitType.RAIDER], defenders[UnitType.GUARD], defenders[UnitType.SIEGE]
            if dr == 1 and dg == 0 and ds == 0:
                if avail[UnitType.GUARD] >= 1:
                    return {UnitType.GUARD: 1}
                if avail[UnitType.SIEGE] >= 1:
                    return {UnitType.SIEGE: 1}
                if avail[UnitType.RAIDER] >= 2:
                    return {UnitType.RAIDER: 2}
            if dr == 0 and dg == 2 and ds == 0:
                if avail[UnitType.SIEGE] >= 1:
                    return {UnitType.SIEGE: 1}
                if avail[UnitType.GUARD] >= 3:
                    return {UnitType.GUARD: 3}
            if dr == 0 and dg == 2 and ds == 1:
                if avail[UnitType.SIEGE] >= 2:
                    return {UnitType.SIEGE: 2}

        send_scout = 1 if (avail[UnitType.SCOUT] >= 1 and (target_is_enemy or _combat_count(defenders) >= 3)) else 0

        max_att = {
            UnitType.RAIDER: avail[UnitType.RAIDER],
            UnitType.GUARD: avail[UnitType.GUARD],
            UnitType.SIEGE: avail[UnitType.SIEGE],
            UnitType.SCOUT: send_scout,
        }

        sim_def = dict(defenders)
        if target_is_enemy and can_enemy_train:
            opp_c = self._best_counter_type(max_att)
            c_cost = UNIT_COST[opp_c]
            est_sp = min(3, max(1, int(est_opp_jit_gold // max(14, c_cost))))
            sim_def[opp_c] = sim_def.get(opp_c, 0) + est_sp
            if sim_def[UnitType.SCOUT] == 0:
                sim_def[UnitType.SCOUT] = 1

        sd, sa = resolve_combat(
            sim_def,
            max_att,
            defender_bonus=effective_def_bonus,
            has_defender_scout=(sim_def[UnitType.SCOUT] > 0),
            has_attacker_scout=(send_scout > 0),
        )
        if _combat_count(sd) > 0 or _combat_count(sa) == 0:
            return None

        if target_is_enemy and can_enemy_train and not is_high_priority:
            my_loss = _army_value(max_att) - _army_value(sa)
            opp_loss = _army_value(sim_def)
            if my_loss > opp_loss + 42:
                return None

        cur = dict(max_att)
        if not target_is_enemy or not can_enemy_train:
            for ut in (UnitType.RAIDER, UnitType.SIEGE, UnitType.GUARD):
                while cur[ut] > 0 and _combat_count(cur) > 1:
                    trial = dict(cur)
                    trial[ut] -= 1
                    tsd, tsa = resolve_combat(
                        sim_def, trial, defender_bonus=effective_def_bonus,
                        has_defender_scout=(sim_def[UnitType.SCOUT] > 0),
                        has_attacker_scout=(trial[UnitType.SCOUT] > 0),
                    )
                    if _combat_count(tsd) == 0 and _combat_count(tsa) > 0:
                        if (_army_value(trial) - _army_value(tsa)) <= (_army_value(cur) - _army_value(sa)):
                            cur = trial
                            sa = tsa
                            continue
                    break

        return {ut: c for ut, c in cur.items() if c > 0}

    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        self._update_intel(obs)
        my_ids: Set[int] = {n.id for n in my_nodes}
        turn = obs.current_turn
        relic_id = obs.relic_node_id
        enemy_nodes = self.get_enemy_nodes(obs)
        enemy_income = sum(n.production for n in enemy_nodes)

        income = sum(n.production for n in my_nodes)
        upkeep = self._estimate_upkeep(obs)
        budget = max(0, obs.my_credits + income - upkeep)
        owned_count = len(my_nodes)
        free_cap = 10 + 4 * owned_count
        total_my_units = sum(sum(n.units.values()) for n in my_nodes if n.units) + sum(
            f.total_count for f in obs.my_fleets
        )

        incoming_enemy_t1: Dict[int, Dict[UnitType, int]] = {nid: _army_dict(None) for nid in obs.nodes}
        incoming_enemy_t2: Dict[int, Dict[UnitType, int]] = {nid: _army_dict(None) for nid in obs.nodes}
        incoming_enemy_t23: Dict[int, Dict[UnitType, int]] = {nid: _army_dict(None) for nid in obs.nodes}
        incoming_enemy_all: Dict[int, Dict[UnitType, int]] = {nid: _army_dict(None) for nid in obs.nodes}
        enemy_origins_t1: Dict[int, List[int]] = {nid: [] for nid in obs.nodes}

        for f in obs.enemy_fleets:
            f_army = _army_dict(f.units) if (f.is_revealed and f.units) else self._estimate_unrevealed(f.total_count)
            incoming_enemy_all[f.dest_node] = _add_armies(incoming_enemy_all[f.dest_node], f_army)
            if f.turns_remaining == 1:
                incoming_enemy_t1[f.dest_node] = _add_armies(incoming_enemy_t1[f.dest_node], f_army)
                enemy_origins_t1[f.dest_node].append(f.origin_node)
            else:
                incoming_enemy_t23[f.dest_node] = _add_armies(incoming_enemy_t23[f.dest_node], f_army)
                if f.turns_remaining == 2:
                    incoming_enemy_t2[f.dest_node] = _add_armies(incoming_enemy_t2[f.dest_node], f_army)

        incoming_my_t1: Dict[int, Dict[UnitType, int]] = {nid: _army_dict(None) for nid in obs.nodes}
        incoming_my_t2: Dict[int, Dict[UnitType, int]] = {nid: _army_dict(None) for nid in obs.nodes}
        combat_enroute: Set[int] = set()
        scout_pin_enroute: Set[int] = set()
        for f in obs.my_fleets:
            if f.units:
                fa = _army_dict(f.units)
                if f.turns_remaining == 1:
                    incoming_my_t1[f.dest_node] = _add_armies(incoming_my_t1[f.dest_node], fa)
                elif f.turns_remaining == 2:
                    incoming_my_t2[f.dest_node] = _add_armies(incoming_my_t2[f.dest_node], fa)
                if _combat_count(fa) > 0:
                    combat_enroute.add(f.dest_node)
                if fa[UnitType.SCOUT] > 0:
                    scout_pin_enroute.add(f.dest_node)
            else:
                combat_enroute.add(f.dest_node)

        avail_move: Dict[int, Dict[UnitType, int]] = {n.id: _army_dict(n.units) for n in my_nodes}
        trained: Dict[int, Dict[UnitType, int]] = {n.id: _army_dict(None) for n in my_nodes}

        frontline_ids: Set[int] = set()
        for n in my_nodes:
            for nb in self.get_neighbors(obs, n.id):
                tn = obs.nodes[nb]
                if tn.owner == self.opponent_id or tn.capturing_player == self.opponent_id or nb == relic_id:
                    frontline_ids.add(n.id)
                    break

        def do_train(nid: int, ut: UnitType, count: int) -> bool:
            nonlocal budget, total_my_units
            if count <= 0:
                return False
            node = obs.nodes[nid]
            if node.owner != self.player_id or node.capturing_player != 0:
                return False
            cost = UNIT_COST[ut] * count
            if cost > budget:
                return False
            orders.append(self.train(nid, ut, count))
            budget -= cost
            total_my_units += count
            trained[nid][ut] += count
            return True

        def do_move(u: int, v: int, units: Dict[UnitType, int]) -> bool:
            clean = {ut: int(c) for ut, c in units.items() if c > 0}
            if not clean:
                return False
            for ut, c in clean.items():
                if c > avail_move[u][ut]:
                    return False
            for ut, c in clean.items():
                avail_move[u][ut] -= c
            orders.append(self.move(u, v, clean))
            if sum(clean.get(ut, 0) for ut in COMBAT_TYPES) > 0:
                combat_enroute.add(v)
            if clean.get(UnitType.SCOUT, 0) > 0:
                scout_pin_enroute.add(v)
            return True

        def schedule_echo(target_id: int, origins: List[int]) -> None:
            if obs.nodes[target_id].owner == self.opponent_id:
                self.echo_waves[target_id] = {
                    "launch_turn": turn + 1,
                    "origins": list(origins),
                }

        lost_or_bailed_nodes: Set[int] = set()
        t1_threatened = [n for n in my_nodes if _combat_count(incoming_enemy_t1[n.id]) > 0]
        t1_threatened.sort(key=lambda x: (x.id == self.home_id, x.id == relic_id, x.production), reverse=True)

        for n in t1_threatened:
            threat = incoming_enemy_t1[n.id]
            cur_def = _add_armies(_add_armies(avail_move[n.id], trained[n.id]), incoming_my_t1[n.id])
            if n.capturing_player != 0:
                lost_or_bailed_nodes.add(n.id)
                continue
            spawn = self._solve_jit_defense(cur_def, threat, n.defense_bonus, budget)
            if spawn is not None:
                for ut, cnt in spawn.items():
                    do_train(n.id, ut, cnt)
                for org in enemy_origins_t1[n.id]:
                    self.counter_targets[org] = turn + 2
            else:
                lost_or_bailed_nodes.add(n.id)

        for n in my_nodes:
            threat2 = incoming_enemy_t2[n.id]
            if _combat_count(threat2) == 0 or n.id in lost_or_bailed_nodes:
                continue
            cur_proj = _add_armies(_add_armies(avail_move[n.id], trained[n.id]), incoming_my_t2[n.id])
            sd, sa = resolve_combat(
                cur_proj, threat2, defender_bonus=n.defense_bonus,
                has_defender_scout=(cur_proj[UnitType.SCOUT] > 0),
                has_attacker_scout=(threat2[UnitType.SCOUT] > 0),
            )
            if _combat_count(sd) == 0 or _combat_count(sa) > 0:
                for nb in self.get_neighbors(obs, n.id):
                    if (
                        nb in my_ids
                        and nb not in lost_or_bailed_nodes
                        and self._get_lane_time(obs, nb, n.id) == 2
                        and _combat_count(incoming_enemy_t1[nb]) == 0
                        and _combat_count(incoming_enemy_t2[nb]) == 0
                    ):
                        av_nb = avail_move[nb]
                        if _combat_count(av_nb) > 0:
                            send = {ut: av_nb[ut] for ut in COMBAT_TYPES if av_nb[ut] > 0}
                            if do_move(nb, n.id, send):
                                cur_proj = _add_armies(cur_proj, send)
                                sd2, sa2 = resolve_combat(
                                    cur_proj, threat2, defender_bonus=n.defense_bonus,
                                    has_defender_scout=(cur_proj[UnitType.SCOUT] > 0),
                                    has_attacker_scout=(threat2[UnitType.SCOUT] > 0),
                                )
                                if _combat_count(sd2) > 0 and _combat_count(sa2) == 0:
                                    break

        if turn == 1 and self.home_id in my_ids and self.home_id not in lost_or_bailed_nodes:
            av0 = avail_move[self.home_id]
            if av0[UnitType.GUARD] >= 1 and obs.nodes[self.bastion_a].owner == 0:
                do_move(self.home_id, self.bastion_a, {UnitType.GUARD: 1})
            if av0[UnitType.RAIDER] >= 1 and av0[UnitType.SCOUT] >= 1 and obs.nodes[self.bastion_b].owner == 0:
                do_move(self.home_id, self.bastion_b, {UnitType.RAIDER: 1, UnitType.SCOUT: 1})
            do_train(self.home_id, UnitType.SIEGE, 2)
            do_train(self.home_id, UnitType.SCOUT, 1)
            return orders

        if turn == 2 and self.home_id in my_ids and self.home_id not in lost_or_bailed_nodes:
            av0 = avail_move[self.home_id]
            if av0[UnitType.SIEGE] >= 1 and obs.nodes[self.gate_id].owner == 0:
                do_move(self.home_id, self.gate_id, {UnitType.SIEGE: 1})
            if av0[UnitType.SIEGE] >= 1:
                do_move(self.home_id, self.bastion_a, {UnitType.SIEGE: 1})
            do_train(self.home_id, UnitType.SIEGE, 1)
            return orders

        if turn == 3 and self.home_id in my_ids and self.home_id not in lost_or_bailed_nodes:
            av0 = avail_move[self.home_id]
            if av0[UnitType.SIEGE] >= 1:
                do_move(self.home_id, self.bastion_b, {UnitType.SIEGE: 1})
            return orders

        if turn == 4 and self.bastion_a in my_ids and self.bastion_a not in lost_or_bailed_nodes:
            ava = avail_move[self.bastion_a]
            if ava[UnitType.GUARD] >= 1 and obs.nodes[self.rig_id].owner == 0:
                do_move(self.bastion_a, self.rig_id, {UnitType.GUARD: 1})
            if ava[UnitType.SIEGE] >= 1 and obs.nodes[self.outpost_a].owner == 0:
                do_move(self.bastion_a, self.outpost_a, {UnitType.SIEGE: 1})
            do_train(self.bastion_a, UnitType.SIEGE, 1)
            if self.bastion_b in my_ids:
                do_train(self.bastion_b, UnitType.GUARD, 1)
            return orders

        max_t23_threat = 0
        max_border_enemy = 0
        for n in my_nodes:
            v23 = _army_value(incoming_enemy_t23[n.id])
            if v23 > max_t23_threat:
                max_t23_threat = v23
            for nb in self.get_neighbors(obs, n.id):
                en = obs.nodes[nb]
                if en.owner == self.opponent_id and en.units:
                    ev = _army_value(_army_dict(en.units))
                    if ev > max_border_enemy:
                        max_border_enemy = ev

        behind_on_map = (len(my_nodes) < len(enemy_nodes)) or (obs.nodes[relic_id].owner == self.opponent_id)
        lock_in_lead = (
            turn >= 95
            and obs.nodes[relic_id].owner == self.player_id
            and obs.my_score >= obs.opponent_score + 60
            and len(my_nodes) >= len(enemy_nodes)
        )

        if turn <= 10 and obs.nodes[relic_id].owner != self.player_id:
            reserve_target = int(max_t23_threat * 0.65)
        elif lock_in_lead:
            reserve_target = max(90, int(max_t23_threat * 0.85), min(110, int(max_border_enemy * 0.65)))
        elif behind_on_map:
            reserve_target = max(int(max_t23_threat * 0.72), min(40, int(max_border_enemy * 0.25)))
        else:
            reserve_target = max(int(max_t23_threat * 0.72), min(64, int(max_border_enemy * 0.40)))
            if max_t23_threat == 0 and max_border_enemy < 24:
                reserve_target = 18

        if turn >= obs.max_turns - 2 and total_my_units >= free_cap:
            reserve_target = 999999

        curtain_nodes = [
            n for n in my_nodes
            if n.capturing_player == 0
            and n.id not in lost_or_bailed_nodes
            and (n.id in frontline_ids or n.id == relic_id or n.id in (self.outpost_a, self.outpost_b, self.gate_id))
        ]
        curtain_nodes.sort(key=lambda x: (x.id == relic_id, x.id in frontline_ids, x.production), reverse=True)
        for n in curtain_nodes:
            sc_cnt = avail_move[n.id][UnitType.SCOUT] + trained[n.id][UnitType.SCOUT]
            want_sc = 2 if (n.id in frontline_ids and _combat_count(avail_move[n.id]) >= 3) else 1
            if sc_cnt < want_sc and budget >= 6:
                do_train(n.id, UnitType.SCOUT, 1)

        spendable = max(0, budget - reserve_target)
        if upkeep >= income and obs.my_credits + income < upkeep * 2:
            spendable = 0
        max_units_cap = free_cap + max(12, income // 3)
        if lock_in_lead:
            max_units_cap = free_cap + 6
        elif obs.relic_charging or obs.relic_active or turn >= 68 or behind_on_map:
            max_units_cap = free_cap + max(22, income // 2)

        uncontested = [n for n in my_nodes if n.capturing_player == 0 and n.id not in lost_or_bailed_nodes]

        if spendable >= 10 and uncontested and total_my_units < max_units_cap:
            def hub_priority(n: Any) -> Tuple[int, int, int]:
                d_rel = self.get_distance(obs, n.id, relic_id)
                d_en = min(
                    (self.get_distance(obs, n.id, en.id) for en in enemy_nodes),
                    default=self.get_distance(obs, n.id, self.enemy_home_id),
                )
                unclaimed_adj = sum(
                    1 for nb in self.get_neighbors(obs, n.id)
                    if obs.nodes[nb].owner == 0 and nb not in combat_enroute
                )
                is_front = 1 if n.id in frontline_ids else 0
                if turn <= 10:
                    return (unclaimed_adj * 4, -d_rel, n.production)
                if obs.relic_charging or obs.relic_active or obs.nodes[relic_id].owner != self.player_id:
                    return (is_front * 2, -d_rel * 3 - d_en, n.production)
                return (is_front * 3, -d_en * 3 - d_rel, n.production)

            uncontested.sort(key=hub_priority, reverse=True)

            hub_count = min(2, len(uncontested))
            loop = 0
            while spendable >= 10 and total_my_units < max_units_cap and loop < 16:
                loop += 1
                hub = uncontested[loop % hub_count]
                tot_r = sum(avail_move[x.id][UnitType.RAIDER] + trained[x.id][UnitType.RAIDER] for x in my_nodes)
                tot_g = sum(avail_move[x.id][UnitType.GUARD] + trained[x.id][UnitType.GUARD] for x in my_nodes)
                tot_s = sum(avail_move[x.id][UnitType.SIEGE] + trained[x.id][UnitType.SIEGE] for x in my_nodes)

                if turn <= 9 and obs.nodes[relic_id].owner == 0 and tot_s < 4 and spendable >= 18:
                    pick = UnitType.SIEGE
                else:
                    pick = self._pick_minimax_counter_train(tot_r, tot_g, tot_s, spendable)

                cost = UNIT_COST[pick]
                if cost <= spendable and do_train(hub.id, pick, 1):
                    spendable -= cost
                elif pick == UnitType.SIEGE and spendable >= 12 and do_train(hub.id, UnitType.GUARD, 1):
                    spendable -= 12
                elif spendable >= 10 and do_train(hub.id, UnitType.RAIDER, 1):
                    spendable -= 10
                else:
                    break

        reserved: Dict[int, Dict[UnitType, int]] = {n.id: _army_dict(None) for n in my_nodes}
        for n in my_nodes:
            if _combat_count(incoming_enemy_t1[n.id]) > 0 and n.id not in lost_or_bailed_nodes:
                reserved[n.id] = dict(avail_move[n.id])
            elif lock_in_lead and (n.id == relic_id or n.id in frontline_ids):
                reserved[n.id] = dict(avail_move[n.id])
            elif n.id == relic_id and (obs.relic_active or obs.relic_charging or turn >= 70):
                reserved[n.id][UnitType.GUARD] = min(avail_move[n.id][UnitType.GUARD], 4)
                reserved[n.id][UnitType.SIEGE] = min(avail_move[n.id][UnitType.SIEGE], 3)

        def get_free(nid: int) -> Dict[UnitType, int]:
            av = avail_move[nid]
            rs = reserved[nid]
            return {ut: max(0, av[ut] - rs[ut]) for ut in UNIT_ORDER}

        for bailed_id in lost_or_bailed_nodes:
            av = avail_move[bailed_id]
            if _total_count(av) == 0:
                continue
            safe_nbs = [
                nb for nb in self.get_neighbors(obs, bailed_id)
                if nb in my_ids and nb not in lost_or_bailed_nodes and _combat_count(incoming_enemy_t1[nb]) == 0
            ]
            if safe_nbs:
                dest = min(safe_nbs, key=lambda x: self.get_distance(obs, x, self.home_id))
                do_move(bailed_id, dest, dict(av))

        done_echoes: List[int] = []
        for tgt_id, info in self.echo_waves.items():
            lt = int(info["launch_turn"])
            if turn > lt:
                done_echoes.append(tgt_id)
                continue
            if turn == lt:
                done_echoes.append(tgt_id)
                if obs.nodes[tgt_id].owner == self.player_id:
                    continue
                echo_orgs = [
                    nb for nb in self.get_neighbors(obs, tgt_id)
                    if nb in my_ids
                    and nb not in lost_or_bailed_nodes
                    and self._get_lane_time(obs, nb, tgt_id) == 2
                    and _combat_count(get_free(nb)) > 0
                ]
                for org in echo_orgs:
                    f_org = get_free(org)
                    send: Dict[UnitType, int] = {}
                    for ut in (UnitType.GUARD, UnitType.RAIDER, UnitType.SIEGE):
                        if f_org[ut] > 0:
                            send[ut] = min(2, f_org[ut])
                            break
                    if send:
                        do_move(org, tgt_id, send)
                        break
        for k in done_echoes:
            self.echo_waves.pop(k, None)

        pin_candidates: List[Tuple[int, int]] = []
        for nid, tn in obs.nodes.items():
            if tn.owner == self.opponent_id:
                continue
            if tn.owner == self.player_id and nid not in lost_or_bailed_nodes:
                continue
            inc_a = incoming_enemy_t1[nid]
            if _combat_count(inc_a) > 0:
                val = _army_value(inc_a)
                if nid == relic_id or tn.production >= 7 or val >= 24 or nid in lost_or_bailed_nodes:
                    pin_candidates.append((val + tn.production * 6 + (70 if nid == relic_id else 0), nid))
            elif tn.capturing_player == self.opponent_id:
                occ_val = _army_value(_army_dict(tn.units)) if tn.units else 30
                if nid == relic_id or tn.production >= 7 or occ_val >= 20:
                    pin_candidates.append((occ_val + tn.production * 6 + (70 if nid == relic_id else 0), nid))

        pin_candidates.sort(reverse=True)
        for _, target_id in pin_candidates:
            if target_id in scout_pin_enroute:
                continue
            adj_2t = [
                nb for nb in self.get_neighbors(obs, target_id)
                if nb in my_ids
                and nb not in lost_or_bailed_nodes
                and self._get_lane_time(obs, nb, target_id) == 2
                and _combat_count(incoming_enemy_t1[nb]) == 0
            ]
            launched_pin = False
            for org in adj_2t:
                if avail_move[org][UnitType.SCOUT] >= 1:
                    do_move(org, target_id, {UnitType.SCOUT: 1})
                    if avail_move[org][UnitType.SCOUT] == 0 and trained[org][UnitType.SCOUT] == 0 and budget >= 6:
                        do_train(org, UnitType.SCOUT, 1)
                    launched_pin = True
                    break
            if not launched_pin and adj_2t and budget >= 6:
                do_train(adj_2t[0], UnitType.SCOUT, 1)

        claimed_combat: Set[int] = set(combat_enroute)
        if self.pending_strike is not None:
            p_target = int(self.pending_strike["target"])
            p_turn = int(self.pending_strike["launch_turn"])
            p_origins: List[int] = list(self.pending_strike["origins_2t"])
            if turn == p_turn:
                scout_sent = False
                launched_any = False
                for org in p_origins:
                    if org in my_ids and _combat_count(incoming_enemy_t1[org]) == 0:
                        f_org = get_free(org)
                        send = {ut: f_org[ut] for ut in COMBAT_TYPES if f_org[ut] > 0}
                        if not scout_sent and avail_move[org][UnitType.SCOUT] >= 1:
                            send[UnitType.SCOUT] = 1
                            scout_sent = True
                            if avail_move[org][UnitType.SCOUT] == 1 and trained[org][UnitType.SCOUT] == 0 and budget >= 6:
                                do_train(org, UnitType.SCOUT, 1)
                        if send:
                            if do_move(org, p_target, send):
                                claimed_combat.add(p_target)
                                launched_any = True
                if launched_any:
                    schedule_echo(p_target, p_origins)
                self.pending_strike = None
            elif turn > p_turn:
                self.pending_strike = None

        relic_node = obs.nodes[relic_id]
        vulture_wait_nodes: Set[int] = set()
        if relic_node.owner == 0 and relic_node.capturing_player == 0:
            if _combat_count(incoming_enemy_t2[relic_id]) > 0 and _combat_count(incoming_enemy_t1[relic_id]) == 0:
                vulture_wait_nodes.add(relic_id)
            elif _combat_count(incoming_enemy_t1[relic_id]) > 0:
                neu_gar = _army_dict(relic_node.units)
                en_arr = incoming_enemy_t1[relic_id]
                _, surv_en = resolve_combat(
                    neu_gar, en_arr, defender_bonus=relic_node.defense_bonus,
                    has_defender_scout=False, has_attacker_scout=(en_arr[UnitType.SCOUT] > 0),
                )
                if _combat_count(surv_en) > 0:
                    adj_2t = [
                        nb for nb in self.get_neighbors(obs, relic_id)
                        if nb in my_ids and self._get_lane_time(obs, nb, relic_id) == 2 and _combat_count(get_free(nb)) > 0
                    ]
                    if adj_2t:
                        comb = _army_dict(None)
                        for org in adj_2t:
                            comb = _add_armies(comb, get_free(org))
                        has_sc = any(avail_move[org][UnitType.SCOUT] >= 1 for org in adj_2t)
                        if has_sc:
                            comb[UnitType.SCOUT] = 1
                        sd, sa = resolve_combat(
                            surv_en, comb, defender_bonus=0.0,
                            has_defender_scout=(surv_en[UnitType.SCOUT] > 0), has_attacker_scout=has_sc,
                        )
                        if _combat_count(sd) == 0 and _combat_count(sa) > 0:
                            sc_done = False
                            for org in adj_2t:
                                f_org = get_free(org)
                                send = {ut: f_org[ut] for ut in COMBAT_TYPES if f_org[ut] > 0}
                                if not sc_done and avail_move[org][UnitType.SCOUT] >= 1:
                                    send[UnitType.SCOUT] = 1
                                    sc_done = True
                                    if avail_move[org][UnitType.SCOUT] == 1 and trained[org][UnitType.SCOUT] == 0 and budget >= 6:
                                        do_train(org, UnitType.SCOUT, 1)
                                do_move(org, relic_id, send)
                            claimed_combat.add(relic_id)

        for nid, tn in obs.nodes.items():
            if tn.owner == 0 and tn.capturing_player == self.opponent_id and tn.units is not None:
                def_army = _add_armies(_army_dict(tn.units), incoming_enemy_t1[nid])
                adj_2t = [
                    nb for nb in self.get_neighbors(obs, nid)
                    if nb in my_ids and _combat_count(get_free(nb)) > 0
                ]
                launched = False
                for nb in sorted(adj_2t, key=lambda x: -_combat_count(get_free(x))):
                    free_sc = dict(get_free(nb))
                    free_sc[UnitType.SCOUT] = avail_move[nb][UnitType.SCOUT]
                    force = self._select_attack_force(
                        avail=free_sc,
                        defenders=def_army,
                        effective_def_bonus=0.0,
                        target_is_enemy=True,
                        can_enemy_train=False,
                        est_opp_jit_gold=0.0,
                        is_high_priority=True,
                    )
                    if force:
                        used_sc = force.get(UnitType.SCOUT, 0) > 0
                        if do_move(nb, nid, force):
                            claimed_combat.add(nid)
                            if used_sc and avail_move[nb][UnitType.SCOUT] == 0 and trained[nb][UnitType.SCOUT] == 0 and budget >= 6:
                                do_train(nb, UnitType.SCOUT, 1)
                            launched = True
                            break
                if not launched and len(adj_2t) >= 2:
                    same_2t = [nb for nb in adj_2t if self._get_lane_time(obs, nb, nid) == 2]
                    if len(same_2t) >= 2:
                        comb = _army_dict(None)
                        for org in same_2t:
                            comb = _add_armies(comb, get_free(org))
                        has_sc = any(avail_move[org][UnitType.SCOUT] >= 1 for org in same_2t)
                        if has_sc:
                            comb[UnitType.SCOUT] = 1
                        sd, sa = resolve_combat(
                            def_army, comb, defender_bonus=0.0,
                            has_defender_scout=(def_army[UnitType.SCOUT] > 0), has_attacker_scout=has_sc,
                        )
                        if _combat_count(sd) == 0 and _combat_count(sa) > 0:
                            sc_done = False
                            for org in same_2t:
                                f_org = get_free(org)
                                send = {ut: f_org[ut] for ut in COMBAT_TYPES if f_org[ut] > 0}
                                if not sc_done and avail_move[org][UnitType.SCOUT] >= 1:
                                    send[UnitType.SCOUT] = 1
                                    sc_done = True
                                    if avail_move[org][UnitType.SCOUT] == 1 and trained[org][UnitType.SCOUT] == 0 and budget >= 6:
                                        do_train(org, UnitType.SCOUT, 1)
                                do_move(org, nid, send)
                            claimed_combat.add(nid)

        if turn >= 10 and not lock_in_lead:
            hydra_options: List[Tuple[int, int, Dict[UnitType, int], float]] = []
            for n in my_nodes:
                free = get_free(n.id)
                if _combat_count(free) < 3:
                    continue
                for nb in self.get_neighbors(obs, n.id):
                    tn = obs.nodes[nb]
                    if tn.owner != self.opponent_id or tn.units is None:
                        continue
                    if self._get_lane_time(obs, n.id, nb) != 2:
                        continue
                    def_army = _add_armies(_army_dict(tn.units), incoming_enemy_all[nb])
                    free_sc = dict(free)
                    free_sc[UnitType.SCOUT] = avail_move[n.id][UnitType.SCOUT]
                    force = self._select_attack_force(
                        avail=free_sc,
                        defenders=def_army,
                        effective_def_bonus=tn.defense_bonus,
                        target_is_enemy=True,
                        can_enemy_train=(tn.capturing_player == 0),
                        est_opp_jit_gold=max(12.0, self.opp_est_bank * 0.42),
                        is_high_priority=True,
                    )
                    if force:
                        pri = tn.production * 3.0 + (45.0 if nb == relic_id else 0.0) + (55.0 if nb == self.enemy_home_id else 0.0)
                        hydra_options.append((n.id, nb, force, pri))

            hydra_options.sort(key=lambda x: x[3], reverse=True)
            chosen_pairs: List[Tuple[int, int, Dict[UnitType, int]]] = []
            used_orgs: Set[int] = set()
            used_tgts: Set[int] = set()
            for org, tgt, frc, _ in hydra_options:
                if org not in used_orgs and tgt not in used_tgts:
                    chosen_pairs.append((org, tgt, frc))
                    used_orgs.add(org)
                    used_tgts.add(tgt)
            if len(chosen_pairs) >= 2:
                for org, tgt, frc in chosen_pairs[:3]:
                    used_sc = frc.get(UnitType.SCOUT, 0) > 0
                    if do_move(org, tgt, frc):
                        claimed_combat.add(tgt)
                        schedule_echo(tgt, [org])
                        if used_sc and avail_move[org][UnitType.SCOUT] == 0 and trained[org][UnitType.SCOUT] == 0 and budget >= 6:
                            do_train(org, UnitType.SCOUT, 1)

        multi_targets = [
            tn for tn in obs.nodes.values()
            if tn.owner != self.player_id
            and tn.id not in vulture_wait_nodes
            and tn.units is not None
            and (not lock_in_lead or tn.owner == 0)
            and (tn.owner == self.opponent_id or tn.capturing_player == self.opponent_id or tn.id == relic_id)
            and (tn.id not in claimed_combat or tn.owner == self.opponent_id)
        ]
        multi_targets.sort(
            key=lambda x: (
                x.id == self.enemy_home_id,
                x.id == relic_id and (obs.relic_active or obs.relic_charging or turn >= 65 or x.owner == 0),
                x.id in (self.enemy_outpost_a, self.enemy_outpost_b),
                x.id == relic_id,
                x.production,
            ),
            reverse=True,
        )

        for tn in multi_targets:
            orgs_2t: List[int] = []
            orgs_3t: List[int] = []
            for nb in self.get_neighbors(obs, tn.id):
                if nb in my_ids and _combat_count(get_free(nb)) > 0:
                    lt = self._get_lane_time(obs, nb, tn.id)
                    if lt == 2:
                        orgs_2t.append(nb)
                    elif lt == 3:
                        orgs_3t.append(nb)

            def_army = _add_armies(_army_dict(tn.units), incoming_enemy_all[tn.id])
            eff_bonus = 0.0 if (tn.owner == 0 and tn.capturing_player == self.opponent_id) else tn.defense_bonus
            sim_def = dict(def_army)
            can_en_train = (tn.owner == self.opponent_id and tn.capturing_player == 0)
            if can_en_train:
                est_sp = min(3, max(1, int(max(enemy_income, self.opp_est_bank) // 22)))
                sim_def[UnitType.GUARD] = sim_def.get(UnitType.GUARD, 0) + est_sp
                if sim_def[UnitType.SCOUT] == 0:
                    sim_def[UnitType.SCOUT] = 1

            if len(orgs_2t) >= 2:
                comb = _army_dict(None)
                for org in orgs_2t:
                    comb = _add_armies(comb, get_free(org))
                has_att_sc = any(avail_move[org][UnitType.SCOUT] >= 1 for org in orgs_2t)
                if has_att_sc and comb[UnitType.SCOUT] == 0:
                    comb[UnitType.SCOUT] = 1
                sd, sa = resolve_combat(
                    sim_def, comb, defender_bonus=eff_bonus,
                    has_defender_scout=(sim_def[UnitType.SCOUT] > 0),
                    has_attacker_scout=has_att_sc,
                )
                if _combat_count(sd) == 0 and _combat_count(sa) > 0:
                    scout_sent = False
                    for org in orgs_2t:
                        f_org = get_free(org)
                        send = {ut: f_org[ut] for ut in COMBAT_TYPES if f_org[ut] > 0}
                        if not scout_sent and avail_move[org][UnitType.SCOUT] >= 1:
                            send[UnitType.SCOUT] = 1
                            scout_sent = True
                            if avail_move[org][UnitType.SCOUT] == 1 and trained[org][UnitType.SCOUT] == 0 and budget >= 6:
                                do_train(org, UnitType.SCOUT, 1)
                        do_move(org, tn.id, send)
                    schedule_echo(tn.id, orgs_2t)
                    claimed_combat.add(tn.id)
                    continue

            if self.pending_strike is None and len(orgs_3t) >= 1 and len(orgs_2t) >= 1:
                comb = _army_dict(None)
                for org in orgs_3t + orgs_2t:
                    comb = _add_armies(comb, get_free(org))
                has_att_sc = any(avail_move[org][UnitType.SCOUT] >= 1 for org in orgs_3t + orgs_2t)
                if has_att_sc and comb[UnitType.SCOUT] == 0:
                    comb[UnitType.SCOUT] = 1
                sd, sa = resolve_combat(
                    sim_def, comb, defender_bonus=eff_bonus,
                    has_defender_scout=(sim_def[UnitType.SCOUT] > 0),
                    has_attacker_scout=has_att_sc,
                )
                if _combat_count(sd) == 0 and _combat_count(sa) > 0:
                    for org in orgs_3t:
                        f_org = get_free(org)
                        send = {ut: f_org[ut] for ut in COMBAT_TYPES if f_org[ut] > 0}
                        do_move(org, tn.id, send)
                    self.pending_strike = {
                        "target": tn.id,
                        "launch_turn": turn + 1,
                        "origins_2t": orgs_2t,
                    }
                    for org in orgs_2t:
                        reserved[org] = dict(avail_move[org])
                    claimed_combat.add(tn.id)
                    continue

        for n in sorted(my_nodes, key=lambda x: -_combat_count(get_free(x.id))):
            free = get_free(n.id)
            if _combat_count(free) == 0:
                continue

            t_scores: List[Tuple[float, int]] = []
            for nb in self.get_neighbors(obs, n.id):
                tn = obs.nodes[nb]
                if tn.owner == self.player_id or nb in vulture_wait_nodes:
                    continue
                if lock_in_lead and tn.owner == self.opponent_id:
                    continue
                if nb in claimed_combat and tn.owner == 0 and tn.capturing_player != self.opponent_id:
                    continue
                val = float(tn.production) * 3.0
                if nb == relic_id:
                    val += 60.0 if (obs.relic_active or obs.relic_charging or turn >= 65 or tn.owner == 0) else 26.0
                if nb in self.counter_targets:
                    val += 34.0
                if tn.capturing_player == self.opponent_id and tn.owner != self.opponent_id:
                    val += 45.0
                elif tn.owner == self.opponent_id:
                    val += 16.0
                    if nb == self.enemy_home_id:
                        val += 55.0
                    elif nb in (self.enemy_outpost_a, self.enemy_outpost_b):
                        en_cnt = _combat_count(_army_dict(tn.units)) if tn.units else 99
                        if en_cnt <= 2:
                            val += 36.0
                    elif nb == self.enemy_rig and n.id == self.rig_id:
                        val += 24.0
                elif nb in self.my_half:
                    val += 18.0
                t_scores.append((val, nb))

            t_scores.sort(reverse=True)
            for _, nb in t_scores:
                free = get_free(n.id)
                if _combat_count(free) == 0:
                    break
                tn = obs.nodes[nb]
                if tn.units is None:
                    continue
                def_army = _add_armies(_army_dict(tn.units), incoming_enemy_all[nb])
                is_enemy = (
                    (tn.owner == self.opponent_id)
                    or (tn.capturing_player == self.opponent_id)
                    or (_combat_count(incoming_enemy_all[nb]) > 0)
                )
                can_en_train = (tn.owner == self.opponent_id and tn.capturing_player == 0)
                eff_bonus = 0.0 if (tn.owner == 0 and tn.capturing_player == self.opponent_id) else tn.defense_bonus

                free_with_sc = dict(free)
                free_with_sc[UnitType.SCOUT] = avail_move[n.id][UnitType.SCOUT]

                force = self._select_attack_force(
                    avail=free_with_sc,
                    defenders=def_army,
                    effective_def_bonus=eff_bonus,
                    target_is_enemy=is_enemy,
                    can_enemy_train=can_en_train,
                    est_opp_jit_gold=max(float(enemy_income) * 0.7, self.opp_est_bank * 0.72),
                    is_high_priority=(nb == relic_id or nb == self.enemy_home_id or behind_on_map),
                )
                if force:
                    used_sc = force.get(UnitType.SCOUT, 0) > 0
                    if do_move(n.id, nb, force):
                        claimed_combat.add(nb)
                        schedule_echo(nb, [n.id])
                        if used_sc and avail_move[n.id][UnitType.SCOUT] == 0 and trained[n.id][UnitType.SCOUT] == 0 and budget >= 6:
                            do_train(n.id, UnitType.SCOUT, 1)

        for n in my_nodes:
            free = get_free(n.id)
            if _combat_count(free) == 0:
                continue
            if n.id == relic_id and (obs.relic_active or obs.relic_charging or turn >= 68):
                if _combat_count(free) < 7:
                    continue

            dest_id: Optional[int] = None

            own_unclaimed = [
                obs.nodes[nid] for nid in self.my_half
                if obs.nodes[nid].owner == 0 and nid not in claimed_combat
            ]
            if own_unclaimed:
                dest_id = min(own_unclaimed, key=lambda x: (self.get_distance(obs, n.id, x.id), -x.production)).id

            if dest_id is None and lock_in_lead:
                rel_cnt = sum(relic_node.units.values()) if relic_node.units else 0
                if n.id != relic_id and rel_cnt < 16:
                    dest_id = relic_id
                elif frontline_ids:
                    weak_front = min(
                        frontline_ids,
                        key=lambda fid: _combat_count(avail_move.get(fid, _army_dict(None))),
                    )
                    if n.id != weak_front:
                        dest_id = weak_front

            if dest_id is None:
                if relic_node.owner != self.player_id and (turn >= 5 or obs.relic_charging or obs.relic_active):
                    dest_id = relic_id
                elif (obs.relic_charging or obs.relic_active) and relic_node.owner == self.player_id and n.id != relic_id:
                    rel_cnt = sum(relic_node.units.values()) if relic_node.units else 0
                    if rel_cnt < 12:
                        dest_id = relic_id

            if dest_id is None:
                other_unclaimed = [
                    x for x in obs.nodes.values()
                    if x.owner == 0 and x.id not in claimed_combat
                ]
                if other_unclaimed:
                    dest_id = min(other_unclaimed, key=lambda x: self.get_distance(obs, n.id, x.id)).id
                elif enemy_nodes:
                    dest_id = min(enemy_nodes, key=lambda x: self.get_distance(obs, n.id, x.id)).id
                else:
                    dest_id = self.enemy_home_id

            if dest_id is not None and dest_id != n.id:
                path = self.get_path(obs, n.id, dest_id)
                if len(path) >= 2:
                    nxt = path[1]
                    if obs.nodes[nxt].owner == self.player_id and nxt not in lost_or_bailed_nodes:
                        send = {ut: free[ut] for ut in COMBAT_TYPES if free[ut] > 0}
                        keep_sc = 1 if (n.id in frontline_ids or n.id == relic_id) else 0
                        if avail_move[n.id][UnitType.SCOUT] > keep_sc:
                            send[UnitType.SCOUT] = 1
                        if send:
                            do_move(n.id, nxt, send)

        return orders


StarterBot = CompetitorBot