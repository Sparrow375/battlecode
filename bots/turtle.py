from __future__ import annotations
from typing import List, Dict
from engine.models import UnitType, Order
from engine.fog import BotObservation
from .base import BotBase

class TurtleBot(BotBase):
    """
    Turtle Bot:
    - Rapidly secures the defensive perimeter (Bastions & Chokepoint Gate) with Guards.
    - Heavily leverages the 25% defender bonus and 2.0x Guard vs Raider counter multiplier.
    - Repels early aggressive rushes, starves the attacker of momentum, and expands methodically.
    """
    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        home_id = 0 if self.player_id == 1 else 14
        relic_id = obs.relic_node_id
        guard_cost = 12

        # Chokepoints to claim and fortify
        # P1 perimeter: 1 (Alpha), 2 (Gamma), 3 (Vanguard Gate)
        # P2 perimeter: 13 (Epsilon), 12 (Omega), 11 (Sentinel Gate)
        perimeter = [1, 2, 3] if self.player_id == 1 else [13, 12, 11]

        # 1. Production: Train Guards wherever affordable
        credits = obs.my_credits
        # Train at home or at under-defended perimeter nodes
        train_targets = [n for n in my_nodes if n.id in perimeter] or my_nodes
        for node in train_targets:
            if credits < guard_cost:
                break
            can_buy = credits // guard_cost
            if can_buy > 0:
                orders.append(self.train(node.id, UnitType.GUARD, can_buy))
                credits -= can_buy * guard_cost

        # 2. Movement: Dispatch guards to secure perimeter nodes immediately
        home_node = next((n for n in my_nodes if n.id == home_id), None)
        if home_node and home_node.units:
            home_guards = home_node.units.get("guard", 0)
            # Send squads to unowned or weakly defended perimeter nodes
            for p_id in perimeter:
                p_node = obs.nodes.get(p_id)
                # Check if perimeter node is not yet owned or has fewer than 4 guards
                p_guards = p_node.units.get("guard", 0) if (p_node and p_node.units) else 0
                if p_node and (p_node.owner != self.player_id or p_guards < 4):
                    if home_guards >= 2:
                        path = self.get_path(obs, home_id, p_id)
                        if len(path) >= 2:
                            send_cnt = min(2, home_guards - 1)
                            if send_cnt > 0:
                                orders.append(self.move(home_id, path[1], {UnitType.GUARD: send_cnt}))
                                home_guards -= send_cnt

        # 3. Mid/Late-game advance: If perimeter is fortified, push towards Relic Sanctuary
        if obs.current_turn >= 60:
            for node in my_nodes:
                if node.units:
                    guards = node.units.get("guard", 0)
                    if guards >= 8:
                        path = self.get_path(obs, node.id, relic_id)
                        if len(path) >= 2:
                            orders.append(self.move(node.id, path[1], {UnitType.GUARD: guards - 4}))

        return orders
