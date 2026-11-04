from __future__ import annotations
from typing import List, Dict, Optional
from engine.models import UnitType, Order, UNIT_STATS
from engine.fog import BotObservation
from .base import BotBase

class BalancedBot(BotBase):
    """
    Balanced / Tactical Scout Bot:
    - Techs into heavy Siege artillery supported by reconnaissance Scouts.
    - Exploits range and anti-armor superiority: Siege destroys fortified Guards (2.0x counter).
    - Can transition if given enough breathing room, but its high-tech Siege opening is vulnerable
      to hyper-aggressive early Raider swarms (Raiders counter Siege 2.0x).
    """
    def __init__(self, player_id: int):
        super().__init__(player_id)

    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        credits = obs.my_credits
        home_id = 0 if self.player_id == 1 else 14
        relic_id = obs.relic_node_id

        # 1. Intelligence Gathering
        enemy_units = {"raider": 0, "siege": 0, "guard": 0}
        for node in obs.nodes.values():
            if node.owner == self.opponent_id and node.units:
                for ut in ["raider", "siege", "guard"]:
                    enemy_units[ut] += node.units.get(ut, 0)

        for fleet in obs.enemy_fleets:
            if fleet.is_revealed and fleet.units:
                for ut in ["raider", "siege", "guard"]:
                    enemy_units[ut] += fleet.units.get(ut, 0)

        # Tactical unit composition:
        # Balanced's signature discipline is heavy Siege artillery (to break fortifications).
        # Only transitions to Guards if it has established strong defenses and sees massive Raiders.
        if enemy_units["guard"] >= 4:
            counter_type = UnitType.SIEGE  # Decisive counter to Guards
        elif obs.current_turn > 20 and enemy_units["raider"] > 6:
            counter_type = UnitType.GUARD
        else:
            # Default tech opening: Siege artillery
            counter_type = UnitType.SIEGE

        # 2. Production: Maintain Scout for intel, otherwise train Siege
        total_scouts = sum(n.units.get("scout", 0) for n in my_nodes if n.units)
        for fleet in obs.my_fleets:
            if fleet.units:
                total_scouts += fleet.units.get("scout", 0)

        home_node = next((n for n in my_nodes if n.id == home_id), my_nodes[0])

        # Train scout early
        if total_scouts < 1 and credits >= 6:
            orders.append(self.train(home_node.id, UnitType.SCOUT, 1))
            credits -= 6

        # Train primary Siege units
        unit_cost = UNIT_STATS[counter_type].cost
        if credits >= unit_cost:
            can_buy = credits // unit_cost
            if can_buy > 0:
                orders.append(self.train(home_node.id, counter_type, can_buy))
                credits -= can_buy * unit_cost

        # 3. Movements
        # Forward scouting
        if home_node.units and home_node.units.get("scout", 0) > 0:
            target_outpost = 5 if self.player_id == 1 else 9
            path = self.get_path(obs, home_node.id, target_outpost)
            if len(path) >= 2:
                orders.append(self.move(home_node.id, path[1], {UnitType.SCOUT: 1}))

        # Combat forces advancement: Siege moves methodically in strike groups
        for node in my_nodes:
            if not node.units:
                continue

            siege_count = node.units.get("siege", 0)
            guard_count = node.units.get("guard", 0)
            total_force = siege_count + guard_count

            # Advance when group reaches 3+ units
            if total_force >= 3:
                # Target nearest enemy bastion or outpost to dismantle with artillery
                enemies = self.get_enemy_nodes(obs)
                neutrals = self.get_neutral_nodes(obs)

                if obs.relic_active:
                    target_id = relic_id
                elif enemies:
                    target_id = min(enemies, key=lambda e: self.get_distance(obs, node.id, e.id)).id
                elif neutrals:
                    target_id = min(neutrals, key=lambda n: self.get_distance(obs, node.id, n.id)).id
                else:
                    target_id = relic_id

                path = self.get_path(obs, node.id, target_id)
                if len(path) >= 2:
                    move_payload: Dict[UnitType, int] = {}
                    if siege_count > 0:
                        move_payload[UnitType.SIEGE] = siege_count
                    if guard_count > 1:
                        move_payload[UnitType.GUARD] = guard_count - 1

                    if move_payload:
                        orders.append(self.move(node.id, path[1], move_payload))

        return orders
