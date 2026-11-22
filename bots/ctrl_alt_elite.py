"""
CTRL ALT ELITE | Champions League 2026 Winner
============================================
Author: Saketh Gottimukkula
Status: Tournament Champion (Champions League 2026)

Predictive-defense AI combining exact forward Lanchester combat simulation,
binary-search force allocation, Bayesian opponent profiling, and dynamic supply management.
"""
from __future__ import annotations
try:
    from nodewar import BotBase, UnitType, resolve_combat
except ImportError:
    from engine.models import UnitType
    from engine.combat import resolve_combat
    from bots.base import BotBase

R, G, S, C = UnitType.RAIDER, UnitType.GUARD, UnitType.SIEGE, UnitType.SCOUT
TYPES = (R, G, S, C)
COST = (10, 12, 18, 6)


def army(data):
    return [int((data or {}).get(u.value, 0)) for u in TYPES]


def mapping(counts):
    return {u: n for u, n in zip(TYPES, counts) if n}


class CompetitorBot(BotBase):
    def __init__(self, player_id):
        super().__init__(player_id)
        self.home = 0 if player_id == 1 else 14
        self.adj = {}
        self.battles = {}
        self.enemy_mix = [1., 2., 1.]
        self.last_seen = {}
        self.arrival_bound = {}
        self.uncertain_residents = set()
        self.possible_contests = set()
        self.active_holds = [0, 0]

    def wins(self, attack, defense, bonus):
        if not any(attack[:3]):
            return False
        if not any(defense[:3]):
            return True
        key = (tuple(attack), tuple(defense), bonus)
        if key not in self.battles:
            d, a = resolve_combat(mapping(defense), mapping(attack), defender_bonus=bonus)
            if len(self.battles) >= 2048:
                self.battles.clear()
            self.battles[key] = not any(d.values()) and any(a.get(u, 0) for u in TYPES[:3])
        return self.battles[key]

    def act(self, obs):
        me, enemy = self.player_id, self.opponent_id
        nodes = obs.nodes
        relic = obs.relic_node_id
        owned = [i for i, n in nodes.items() if n.owner == me]
        if not owned:
            return []
        if not self.adj:
            self.adj = {i: [] for i in nodes}
            for lane in obs.lanes:
                i, j, t = lane['node_a'], lane['node_b'], lane['travel_turns']
                self.adj[i].append((j, t))
                self.adj[j].append((i, t))
        dist = lambda i, j: self.get_distance(obs, i, j)
        turn = obs.current_turn
        left = obs.max_turns - turn + 1
        active = obs.relic_active or obs.relic_charging
        stock = {i: army(nodes[i].units) for i in owned if not nodes[i].capturing_player
                 and i not in self.uncertain_residents}
        # A friendly scout dying in a relief fleet can freeze the enemy's first
        # capture tick. For one observation an enemy army can look friendly.
        landings = {f.dest_node for f in obs.enemy_fleets if f.turns_remaining == 1}
        scout_relief = {f.dest_node for f in obs.my_fleets if f.turns_remaining == 1 and army(f.units)[3]}
        self.uncertain_residents = landings & scout_relief
        income = sum(nodes[i].production for i in owned)
        domestic = sum(sum(army(nodes[i].units)) for i in owned if not nodes[i].capturing_player)
        foreign = sum(f.total_count for f in obs.my_fleets)
        foreign += sum(sum(army(n.units)) if n.units is not None else self.arrival_bound.get(i, 0)
                       for i, n in nodes.items() if n.capturing_player == me)
        # An arriving hostile scout can leave an occupation unflagged. Budget for
        # unconfirmed friendly landings even when the progress indicator is blank.
        for i in self.possible_contests:
            if nodes[i].owner != me and nodes[i].capturing_player != me:
                bound = self.arrival_bound.get(i, 0)
                foreign += min(bound, sum(army(nodes[i].units))) if nodes[i].units is not None else bound
        capacity = 10 + 4 * len(owned)
        upkeep = max(0, domestic - capacity) + 2 * max(0, foreign - max(0, capacity - domestic))
        budget = max(0, obs.my_credits + income - upkeep)
        capacity_left = max(0, capacity + int(income * .36) - domestic - foreign)
        budget = min(budget, 18 * capacity_left)
        incoming = {i: {} for i in nodes}
        threat = {i: 0 for i in nodes}
        revealed = [0, 0, 0]
        for i, n in nodes.items():
            if n.units is not None and n.owner == enemy and n.capturing_player != me:
                garrison = army(n.units)
                self.last_seen[i] = (turn, garrison)
                for k in range(3):
                    revealed[k] += garrison[k]
        for f in obs.enemy_fleets:
            threat[f.dest_node] += f.total_count
            if f.units:
                for k, count in enumerate(army(f.units)[:3]):
                    revealed[k] += count
        if sum(revealed):
            self.enemy_mix = [a * .72 + b * .28 for a, b in zip(self.enemy_mix, revealed)]
        for f in obs.my_fleets:
            eta = f.turns_remaining
            d = incoming[f.dest_node]
            d[eta] = d.get(eta, 0) + f.total_count
        old_bounds = self.arrival_bound
        self.arrival_bound = {}
        for i, arrivals in incoming.items():
            ambiguous = nodes[i].capturing_player == me or i in self.possible_contests
            possible = old_bounds.get(i, 0) if nodes[i].owner != me and ambiguous else 0
            if nodes[i].units is not None:
                possible = min(possible, sum(army(nodes[i].units)))
            # Consecutive scout contests can mask an occupation for several turns.
            self.arrival_bound[i] = possible + arrivals.get(1, 0)
        self.possible_contests = {f.dest_node for f in obs.enemy_fleets if f.turns_remaining == 1
                                  and (f.units is None or army(f.units)[3])}
        frontier = {i: [j for j, _ in self.adj[i] if nodes[j].owner != me] for i in owned}
        # Predict hostile pressure before launch. Only direct enemy neighbors can
        # launch an attack that arrives in <=3 turns. Their garrisons are fully
        # observable across an adjacent lane; unseen troops use a stale, decayed
        # upper bound. A visible fleet is a definite commitment, not a forecast.
        pressure = {i: 0.0 for i in owned}
        vulnerable = {i: False for i in owned}
        if turn >= 9:
            for i in owned:
                if i not in stock:
                    continue
                local = stock[i]
                for j, eta in self.adj[i]:
                    target = nodes[j]
                    if target.owner != enemy or eta > 3:
                        continue
                    if target.units is not None:
                        hostile = army(target.units)
                    else:
                        cached = self.last_seen.get(j)
                        if cached and turn - cached[0] <= 3:
                            hostile = cached[1][:]
                        else:
                            continue
                    # An enemy can commit at most its observed garrison. This
                    # is an upper-bound scenario; no claimed knowledge of orders.
                    fighting = sum(hostile[:3]); defending = sum(local[:3])
                    if fighting < 2:
                        continue
                    wins_if_attacked = self.wins(hostile, local, nodes[i].defense_bonus)
                    if wins_if_attacked:
                        vulnerable[i] = True
                        pressure[i] = max(pressure[i], min(12.0, 1.5 + .95 * fighting - .35 * defending))
                    elif fighting >= defending + 3:
                        pressure[i] = max(pressure[i], min(6., .5 * (fighting - defending)))
                for f in obs.enemy_fleets:
                    if f.dest_node == i and f.turns_remaining <= 3:
                        # Committed fleet is harder evidence than a potential launch.
                        vulnerable[i] = True
                        pressure[i] = max(pressure[i], min(13., 2. + 1.0 * f.total_count))
        sites = [i for i in stock if sum(stock[i])]
        trained = {i: [0, 0, 0, 0] for i in sites}
        goals = {i: 0 for i in owned}
        if obs.relic_active and nodes[relic].owner:
            self.active_holds[nodes[relic].owner - 1] += 1
        territory_margin = len(owned) - sum(n.owner == enemy for n in nodes.values())
        relic_margin = (nodes[relic].owner == me) - (nodes[relic].owner == enemy)
        active_left = left if obs.relic_active else max(0, left - (5 if active else max(1, 90 - turn)))
        lead = obs.my_score - obs.opponent_score
        projected_vp = lead + territory_margin * (left + active_left) + 10 * relic_margin * active_left
        projected_hold = self.active_holds[me - 1] - self.active_holds[enemy - 1] + relic_margin * active_left
        # Net worth is only a marginal tiebreak. The enemy bank is unobservable.
        own_assets = sum(sum(x * c for x, c in zip(a, COST)) for a in stock.values())
        own_assets += sum(sum(x * c for x, c in zip(army(f.units), COST)) for f in obs.my_fleets)
        visible_assets = sum(sum(x * c for x, c in zip(army(n.units), COST))
                             for n in nodes.values() if n.owner == enemy and n.capturing_player != me)
        visible_assets += sum(sum(x * c for x, c in zip(army(f.units), COST))
                              if f.units else 12 * f.total_count for f in obs.enemy_fleets)
        ahead = 100000 * projected_vp + 1000 * projected_hold + obs.my_credits + own_assets - visible_assets > 0
        # V5-inspired: reinforce production fronts facing a large visible enemy army.
        # V4-inspired: divert surplus new recruits away from an owned inactive Relic.
        for i in owned:
            goals[i] = (1.5 * min(16, max((sum(army(nodes[j].units)[:3]) for j in frontier[i] if nodes[j].owner == enemy and not nodes[j].capturing_player), default=0)) + 3 * len(frontier[i]) + 1.5 * sum(nodes[j].owner == enemy for j in frontier[i])
                        + (-12 if i == relic and nodes[relic].owner == me and not obs.relic_active else 4 if i == relic else 0) + min(16, threat[i] * 2) + 1.75 * pressure[i])
        # Buy locally. Multiple production sites can mobilize and attack on the next turn.
        for _ in range(min(capacity_left, 18)):
            if budget < 6 or not sites:
                break
            def recruitment_priority(i):
                present = sum(stock[i]) + sum(trained[i]) + sum(incoming[i].values())
                return goals[i] - .95 * present - .23 * dist(i, relic)
            i = max(sites, key=recruitment_priority)
            local = [x + y for x, y in zip(stock[i], trained[i])]
            if left <= 3 and ahead and not threat[i]:
                break
            if not local[3] and (sum(local[:3]) >= 2 or any(nodes[j].owner == enemy for j in frontier[i])):
                k = 3
            else:
                er, eg, es = self.enemy_mix
                # Guards and Siege take the standard neutral garrisons efficiently.
                neutral_weight = sum(nodes[j].owner == 0 for j in frontier[i])
                weights = [1.0 + 2.1 * es, 2.0 + 2.2 * er + 2 * neutral_weight,
                           1.5 + 1.65 * eg + 4 * neutral_weight]
                k = max(range(3), key=lambda u: weights[u] / (local[u] + 1) if COST[u] <= budget else -1)
            if COST[k] > budget:
                break
            trained[i][k] += 1
            budget -= COST[k]
        orders = [self.train(i, TYPES[k], count) for i in sites for k, count in enumerate(trained[i]) if count]
        movable = {}
        for i in sites:
            pool = stock[i][:]
            hold = 1 if not any(trained[i]) else 0
            nearby = max((sum(army(nodes[j].units)[:3]) for j in frontier[i]
                          if nodes[j].owner == enemy and not nodes[j].capturing_player), default=0)
            # Balanced reserve ratio: V4 held 25%, V5 held 15%.
            hold = max(hold, min(sum(pool), int(nearby * 0.2) - sum(trained[i])))
            if turn >= 9 and vulnerable.get(i, False) and pressure[i] >= 4:
                hold = max(hold, min(sum(pool), int(pressure[i] * 0.4) + 1 - sum(trained[i])))
            if threat[i]:
                hold = max(hold, min(sum(pool), int(threat[i] * 1.15) + 1 - sum(trained[i])))
            if i == relic and active and ahead and frontier[i]:
                hold = max(hold, min(8, 2 + max((sum(army(nodes[j].units)) for j in frontier[i]), default=0) // 3))
            for k in (3, 1, 0, 2):
                keep = min(pool[k], hold)
                hold -= keep
                pool[k] -= keep
            movable[i] = pool

        def send(i, j, eta, pack):
            orders.append(self.move(i, j, mapping(pack)))
            for k in range(4):
                movable[i][k] -= pack[k]
            incoming[j][eta] = incoming[j].get(eta, 0) + sum(pack)

        # Reinforce our first Relic landing when enemy fleets are approaching
        # during the vulnerable capture clock. Use the shorter two-turn lane.
        if 7 in incoming and incoming[7] and nodes[7].owner != me and \
                any(f.dest_node == 7 for f in obs.enemy_fleets):
            for i in ((9, 8) if me == 2 else (5, 6)):
                if i not in movable:
                    continue
                edge = next((tt for j, tt in self.adj[i] if j == 7), 0)
                if edge != 2:
                    continue
                pool = movable[i]
                if sum(pool[:3]) < 3:
                    continue
                send(i, 7, edge, pool[:])
                break
        # Recover disrupted friendly production and land the follow-up to an invasion.
        for i, pool in movable.items():
            for j, eta in self.adj[i]:
                n = nodes[j]
                repair = n.owner == me and (n.capturing_player or not sum(army(n.units)))
                relay = n.owner == enemy and (eta - 1 in incoming[j] or n.capturing_player == me)
                if not (relay or repair) or eta in incoming[j] or eta > left:
                    continue
                if repair and incoming[j]:
                    continue
                choices = [k for k in (0, 1, 2, 3) if pool[k]]
                if choices:
                    pack = [0] * 4
                    k = choices[0]
                    pack[k] = min(pool[k], 1 + min(4, threat[j]))
                    send(i, j, eta, pack)

        options = []
        for i, pool in movable.items():
            for j, eta in self.adj[i]:
                n = nodes[j]
                if n.owner == me or n.capturing_player == me or eta + 1 > left:
                    continue
                exposure = dist(14 - self.home, j) - dist(self.home, j)
                # Keep V5 territorial aggression but retain V4 early-Relic support.
                value = (n.production + .65 * len(self.adj[j]) + (4 if n.owner == enemy else 0)
                         + (-5 if j == relic and not active else 3 if j == relic else 0) + (18 if j == relic and active else 0)
                         + min(2, max(-2, exposure * .2)) - .9 * eta)
                defense = army(n.units)
                if n.units is None:
                    sight = self.last_seen.get(j)
                    defense = sight[1][:] if sight and turn - sight[0] <= 4 else [1, 2, 1, 0]
                if n.owner == enemy and not n.capturing_player and any(defense):
                    defense[max(range(3), key=self.enemy_mix.__getitem__)] += 2
                if threat[j]:
                    # A silhouette guarantees size even if its mix is concealed.
                    strongest = max(range(3), key=self.enemy_mix.__getitem__)
                    defense[strongest] += threat[j]
                options.append((value - .25 * sum(defense), i, j, eta, defense))
        for _, i, j, eta, defense in sorted(options, reverse=True):
            pool = movable[i]
            if incoming[j] or not self.wins(pool, defense, nodes[j].defense_bonus):
                continue
            pack = pool[:]
            # Reduce the force in logarithmic steps. Under hostile recruitment
            # preserve a margin and a unit at origin for a follow-up landing.
            for k in (3, 0, 1, 2):
                lo, hi = 0, pack[k]
                while lo < hi:
                    mid = (lo + hi) // 2
                    pack[k] = mid
                    if self.wins(pack, defense, nodes[j].defense_bonus):
                        hi = mid
                    else:
                        lo = mid + 1
                pack[k] = lo
            if nodes[j].owner == enemy or threat[j] or j == relic:
                for k in range(4):
                    pack[k] = min(pool[k], pack[k] + (1 if k == 3 else 1 + pack[k] // 2))
            send(i, j, eta, pack)

        # Stage idle units along owned corridors towards useful production fronts.
        border = [i for i in owned if frontier[i] or threat[i]]
        for i, pool in movable.items():
            if not any(pool) or not border or left < 3:
                continue
            def staging_value(j):
                return (goals[j] - .7 * (sum(stock.get(j, [])) + sum(incoming[j].values()))
                        - 1.8 * dist(i, j))
            dest = max(border, key=staging_value)
            hops = [(dist(j, dest) + eta, j, eta) for j, eta in self.adj[i]
                    if nodes[j].owner == me and not nodes[j].capturing_player and dist(j, dest) < dist(i, dest)]
            if hops:
                _, j, eta = min(hops)
                send(i, j, eta, pool[:])
        return orders
