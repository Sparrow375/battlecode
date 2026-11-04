"""
Node War - Competitor Starter Bot Template
==========================================
Welcome to Node War! This template provides the boilerplate needed to implement
your custom competitive AI agent.

Game Rules Summary:
-------------------
- 15 Mirrored Nodes. P1 starts at Node 0, P2 starts at Node 14.
- Nodes produce Credits every turn.
- Rock-Paper-Scissors Combat:
    * Raiders (10 credits) beat Siege (2.0x)
    * Siege (18 credits) beat Guards (2.0x)
    * Guards (12 credits) beat Raiders (2.0x)
    * Scouts (6 credits) grant vision over enemy fleets on adjacent lanes
- Defenders stationed at an owned node get a +25% defense bonus.
- Captured nodes take 2 consecutive turns of occupation to flip ownership.
- Empire upkeep: unit counts over 30 cost 1 credit/unit/turn.
- Final 25 turns: Relic Sanctuary (Node 7) activates, giving +10 points/turn and doubling node scores!
"""

from __future__ import annotations
from typing import List, Dict
from engine.models import UnitType, Order, TrainOrder, MoveOrder
from engine.fog import BotObservation
from bots.base import BotBase

class StarterBot(BotBase):
    def __init__(self, player_id: int):
        super().__init__(player_id)
        # Store persistent bot memory/state here across turns

    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []

        # 1. Query your owned nodes
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        # 2. Inspect available credits & turn count
        credits = obs.my_credits
        current_turn = obs.current_turn

        # 3. Example: Train units at your home node
        # Home node ID: 0 for Player 1, 14 for Player 2
        home_id = 0 if self.player_id == 1 else 14
        home_node = next((n for n in my_nodes if n.id == home_id), my_nodes[0])

        if credits >= 20:
            # Train 1 Raider (cost 10) and 1 Guard (cost 12) if affordable
            orders.append(self.train(home_node.id, UnitType.RAIDER, 1))
            credits -= 10

        # 4. Example: Find closest neutral node and launch an expansion fleet
        neutral_nodes = self.get_neutral_nodes(obs)
        if neutral_nodes and home_node.units:
            closest_neutral = min(neutral_nodes, key=lambda n: self.get_distance(obs, home_node.id, n.id))
            
            # Check stationed units ready for dispatch
            stationed_raiders = home_node.units.get("raider", 0)
            if stationed_raiders >= 3:
                # Find the next immediate hop on the shortest path
                path = self.get_path(obs, home_node.id, closest_neutral.id)
                if len(path) >= 2:
                    next_node = path[1]
                    orders.append(self.move(home_node.id, next_node, {UnitType.RAIDER: 2}))

        # 5. Example: Contest the Relic in the endgame
        if obs.relic_active:
            relic_id = obs.relic_node_id
            for node in my_nodes:
                guards = node.units.get("guard", 0) if node.units else 0
                if guards >= 4:
                    path = self.get_path(obs, node.id, relic_id)
                    if len(path) >= 2:
                        orders.append(self.move(node.id, path[1], {UnitType.GUARD: 2}))

        return orders
