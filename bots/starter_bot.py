"""
Node War - Competitor Starter Bot Template
==========================================
Welcome to Node War! This template provides the standard boilerplate to implement
your custom competitive AI agent.

Tournament Runtime Contract:
----------------------------
- Python Version: Python 3.10+ (standard library only; no external packages, network, or disk writes).
- Turn Time Limit: 50 ms wall-clock time per turn. Computations exceeding 50 ms forfeit orders for that turn.
- State Persistence: An instance of your bot class is initialized once per game (`bot = CompetitorBot(player_id)`).
  Any state stored on `self` persists across turns within that match. In a Best-of-3 series, each game gets a fresh instance.
- Error Handling: Any unhandled exception during `act()` forfeits orders for that turn (engine defaults to []).
- Economy & Timing:
    * You start Turn 1 with 30 Gold (🪙).
    * `obs.my_credits` is observed at turn start prior to Phase 1 Income collection and Phase 2 Upkeep deduction.
    * Node production (+15 Core, +10 Relic, +7 Chokepoint Outpost, +4 Outer Bastion) is added in Phase 1 before training orders execute.
    * Mobilization Delay: Units trained on Turn T join local garrison defense immediately, but cannot move until Turn T+1.

Combat Counter Triangle:
------------------------
- Raiders (10 Gold) counter Siege (2.0x damage)
- Siege (18 Gold) counter Guards (2.0x damage)
- Guards (12 Gold) counter Raiders (2.0x damage)
- Scouts (6 Gold) provide vision, grant a massive +15% ally damage bonus (-15% blind penalty if missing), and freeze enemy capture on arrival.

Local Testing & Simulation:
---------------------------
    python nodewar.py starter_bot.py                 # Dry-run validation
    python nodewar.py simulate starter_bot.py rusher # Simulate full 1v1 match locally
    python nodewar.py bo3 starter_bot.py turtle      # Run Best-of-3 with seat swapping
"""

from __future__ import annotations
from typing import List, Dict

try:
    from nodewar import BotBase, BotObservation, UnitType, Order, TrainOrder, MoveOrder
except ImportError:
    try:
        from validate_bot import BotBase, BotObservation, UnitType, Order, TrainOrder, MoveOrder
    except ImportError:
        from engine.models import UnitType, Order, TrainOrder, MoveOrder
        from engine.fog import BotObservation
        from bots.base import BotBase


class CompetitorBot(BotBase):
    """
    Official competitor bot template.
    The tournament loader discovers any subclass of BotBase in your submission file.
    """
    def __init__(self, player_id: int):
        super().__init__(player_id)
        # Store persistent bot memory/state across turns here
        self.home_id = 0 if self.player_id == 1 else 14

    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []

        # 1. Query your owned nodes
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        credits = obs.my_credits

        # 2. Identify core base
        home_node = next((n for n in my_nodes if n.id == self.home_id), my_nodes[0])

        # 3. Recruitment: Train units when credits permit (home node must be uncontested)
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

        # 5. Dynamic Relic Reaction: React to 5-turn warning alert or active Relic
        if obs.relic_charging or obs.relic_active:
            relic_id = obs.relic_node_id
            for node in my_nodes:
                guards = node.units.get("guard", 0) if node.units else 0
                if guards >= 3:
                    path = self.get_path(obs, node.id, relic_id)
                    if len(path) >= 2:
                        orders.append(self.move(node.id, path[1], {UnitType.GUARD: 2}))

        return orders


# Alias for backward compatibility with existing runner registries and scripts
StarterBot = CompetitorBot
