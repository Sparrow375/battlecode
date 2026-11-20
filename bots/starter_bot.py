"""
Node War - Competitor Starter Bot Template
==========================================
Welcome to Node War! This template provides the boilerplate needed to implement
your custom competitive AI agent.

Core Concepts:
--------------
- 15 Mirrored Nodes. P1 starts at Node 0, P2 starts at Node 14.
- Nodes produce Gold (🪙) every turn (accessible via `obs.my_credits`):
    * +4 Gold/turn for outer bastions (Nodes 1, 2, 4, 10, 12, 13)
    * +7 Gold/turn for mid-lane chokepoints & outposts (Nodes 3, 5, 6, 8, 9, 11)
    * +10 Gold/turn for Relic Sanctuary (Node 7)
    * +15 Gold/turn for core citadels (Nodes 0, 14)
- Rock-Paper-Scissors Combat:
    * Raiders (10 Gold) counter Siege (2.0x damage)
    * Siege (18 Gold) counter Guards (2.0x damage)
    * Guards (12 Gold) counter Raiders (2.0x damage)
    * Scouts (6 Gold) grant lane vision, +15% combat targeting bonus, and contest enemy node captures.
- Defenders stationed at an owned node receive a defense bonus (+50% at home base, +25% at outposts).
- Captured nodes take 2 consecutive turns of occupation to flip ownership.
- Empire supply lines: armies exceeding free supply capacity (10 + 4 * Owned Nodes) incur per-turn upkeep costs.
- Endgame: Relic Sanctuary (Node 7) activates dynamically between Turns 80–100, granting +10 points/turn and doubling node scores!
  Watch for `obs.relic_charging` (5-turn warning) and `obs.relic_active`.
"""

from __future__ import annotations
from typing import List, Dict

try:
    from engine.models import UnitType, Order, TrainOrder, MoveOrder
    from engine.fog import BotObservation
    from bots.base import BotBase
except ImportError:
    # Standalone fallback when running outside the tournament engine
    from validate_bot import UnitType, Order, TrainOrder, MoveOrder, BotObservation, BotBase

class StarterBot(BotBase):
    def __init__(self, player_id: int):
        super().__init__(player_id)
        # Store persistent bot memory/state across turns here

    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []

        # 1. Query your owned nodes
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        credits = obs.my_credits

        # 2. Identify core base
        home_id = 0 if self.player_id == 1 else 14
        home_node = next((n for n in my_nodes if n.id == home_id), my_nodes[0])

        # 3. Recruitment: Train units when credits permit
        if credits >= 20 and home_node.capturing_player == 0:
            orders.append(self.train(home_node.id, UnitType.RAIDER, 1))
            credits -= 10

        # 4. Expansion: Dispatch exploration forces toward unclaimed or vulnerable nodes
        neutral_nodes = self.get_neutral_nodes(obs)
        if neutral_nodes and home_node.units:
            closest_neutral = min(neutral_nodes, key=lambda n: self.get_distance(obs, home_node.id, n.id))
            stationed_raiders = home_node.units.get("raider", 0)
            if stationed_raiders >= 3:
                path = self.get_path(obs, home_node.id, closest_neutral.id)
                if len(path) >= 2:
                    orders.append(self.move(home_node.id, path[1], {UnitType.RAIDER: 2}))

        # 5. Dynamic Relic Reaction: React to warning flag or active relic
        if obs.relic_charging or obs.relic_active:
            relic_id = obs.relic_node_id
            for node in my_nodes:
                guards = node.units.get("guard", 0) if node.units else 0
                if guards >= 3:
                    path = self.get_path(obs, node.id, relic_id)
                    if len(path) >= 2:
                        orders.append(self.move(node.id, path[1], {UnitType.GUARD: 2}))

        return orders

