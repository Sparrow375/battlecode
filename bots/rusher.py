from __future__ import annotations
from typing import List, Dict
from engine.models import UnitType, Order
from engine.fog import BotObservation
from .base import BotBase

class RusherBot(BotBase):
    """
    Rusher Bot:
    - Dedicated blitzkrieg strategy: trains pure Raiders every single turn.
    - Moves fast strike teams immediately down the shortest attack corridor to breach enemy core.
    - If enemy core falls, hunts down any lingering enemy outposts to achieve total elimination.
    """
    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        home_id = 0 if self.player_id == 1 else 14
        enemy_home_id = 14 if self.player_id == 1 else 0

        # Fast corridor towards enemy base:
        # P1 corridor: 0 -> 1 -> 5 -> 9 -> 13 -> 14
        # P2 corridor: 14 -> 13 -> 9 -> 5 -> 1 -> 0
        corridor = [0, 1, 5, 9, 13, 14] if self.player_id == 1 else [14, 13, 9, 5, 1, 0]

        # 1. Production: 100% Raiders
        credits = obs.my_credits
        raider_cost = 10
        # Train at forward-most owned node
        train_node = my_nodes[0]
        for cid in reversed(corridor):
            match_node = next((n for n in my_nodes if n.id == cid), None)
            if match_node and match_node.capturing_player == 0:
                train_node = match_node
                break

        can_buy = credits // raider_cost
        if can_buy > 0:
            orders.append(self.train(train_node.id, UnitType.RAIDER, can_buy))

        # 2. Aggressive Forward Movement
        enemy_nodes = self.get_enemy_nodes(obs)
        enemy_core_owned_by_me = (obs.nodes[enemy_home_id].owner == self.player_id)

        for node in my_nodes:
            if not node.units:
                continue
            raiders = node.units.get("raider", 0)
            if raiders <= 0:
                continue

            target_id = None
            if enemy_core_owned_by_me and enemy_nodes:
                # Hunt down remaining enemy nodes
                target_id = min(enemy_nodes, key=lambda e: self.get_distance(obs, node.id, e.id)).id
            else:
                # Follow the blitz corridor
                curr_idx = corridor.index(node.id) if node.id in corridor else -1
                if curr_idx != -1 and curr_idx < len(corridor) - 1:
                    target_id = corridor[curr_idx + 1]
                elif enemy_nodes:
                    target_id = min(enemy_nodes, key=lambda e: self.get_distance(obs, node.id, e.id)).id
                else:
                    target_id = enemy_home_id

            path = self.get_path(obs, node.id, target_id)
            if len(path) >= 2:
                next_hop = path[1]
                orders.append(self.move(node.id, next_hop, {UnitType.RAIDER: raiders}))

        return orders
