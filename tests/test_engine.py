from __future__ import annotations
import unittest
from engine.models import PlayerId, UnitType, GameConfig, TrainOrder, MoveOrder, UNIT_STATS
from engine.map import create_default_map, MapGraph
from engine.combat import resolve_combat
from engine.game import NodeWarGame
from engine.fog import generate_player_observation

class TestEngine(unittest.TestCase):
    def test_map_symmetry(self):
        nodes, lanes = create_default_map()
        self.assertEqual(len(nodes), 15)
        self.assertEqual(nodes[0].owner, PlayerId.PLAYER_1)
        self.assertEqual(nodes[14].owner, PlayerId.PLAYER_2)
        self.assertEqual(nodes[7].owner, PlayerId.NONE)

        graph = MapGraph(nodes, lanes)
        # Distance from Home base to Relic Sanctuary must be identical
        d_p1_relic = graph.get_distance(0, 7)
        d_p2_relic = graph.get_distance(14, 7)
        self.assertEqual(d_p1_relic, d_p2_relic)

        # Distance between home bases must be symmetric
        self.assertEqual(graph.get_distance(0, 14), graph.get_distance(14, 0))

    def test_rps_combat(self):
        # 1. Raiders beat Siege
        raiders = {UnitType.RAIDER: 10, UnitType.SIEGE: 0, UnitType.GUARD: 0, UnitType.SCOUT: 0}
        siege = {UnitType.RAIDER: 0, UnitType.SIEGE: 10, UnitType.GUARD: 0, UnitType.SCOUT: 0}
        surv_raiders, surv_siege = resolve_combat(raiders, siege, defender_bonus=0.0)
        self.assertGreater(sum(surv_raiders.values()), 0)
        self.assertEqual(sum(surv_siege.values()), 0)

        # 2. Siege beats Guards
        guards = {UnitType.RAIDER: 0, UnitType.SIEGE: 0, UnitType.GUARD: 10, UnitType.SCOUT: 0}
        surv_siege2, surv_guards = resolve_combat(siege, guards, defender_bonus=0.0)
        self.assertGreater(sum(surv_siege2.values()), 0)
        self.assertEqual(sum(surv_guards.values()), 0)

        # 3. Guards beat Raiders
        surv_guards2, surv_raiders2 = resolve_combat(guards, raiders, defender_bonus=0.0)
        self.assertGreater(sum(surv_guards2.values()), 0)
        self.assertEqual(sum(surv_raiders2.values()), 0)

    def test_defender_bonus(self):
        # Even numbers of same unit: defenders should win due to 25% defense bonus
        defenders = {UnitType.GUARD: 10, UnitType.RAIDER: 0, UnitType.SIEGE: 0, UnitType.SCOUT: 0}
        attackers = {UnitType.GUARD: 10, UnitType.RAIDER: 0, UnitType.SIEGE: 0, UnitType.SCOUT: 0}
        surv_def, surv_att = resolve_combat(defenders, attackers, defender_bonus=0.25)
        self.assertGreater(sum(surv_def.values()), 0)
        self.assertEqual(sum(surv_att.values()), 0)

    def test_two_turn_capture(self):
        game = NodeWarGame()
        # Clean out Node 1 so it is empty neutral
        node1 = game.nodes[1]
        node1.units = {ut: 0 for ut in UnitType}
        node1.owner = PlayerId.NONE
        node1.capture_progress = 0

        # P1 moves 5 raiders from Node 0 to Node 1 (travel time 2 turns)
        game.nodes[0].units[UnitType.RAIDER] = 10
        game.player_credits[PlayerId.PLAYER_1] = 100
        
        move_order = MoveOrder(origin_node=0, dest_node=1, units={UnitType.RAIDER: 5})
        
        # Turn 1: Launch fleet
        game.step(p1_orders=[move_order], p2_orders=[])
        self.assertEqual(node1.owner, PlayerId.NONE)
        self.assertEqual(node1.capture_progress, 0)

        # Turn 2: Fleet arrives at Node 1 -> Contested (turn 1 of capture)
        game.step(p1_orders=[], p2_orders=[])
        self.assertEqual(node1.owner, PlayerId.NONE)
        self.assertEqual(node1.capturing_player, PlayerId.PLAYER_1)
        self.assertEqual(node1.capture_progress, 1)

        # Turn 3: Uncontested occupation continues -> Flipped!
        game.step(p1_orders=[], p2_orders=[])
        self.assertEqual(node1.owner, PlayerId.PLAYER_1)
        self.assertEqual(node1.capture_progress, 0)
        self.assertEqual(node1.capturing_player, PlayerId.NONE)

    def test_upkeep_deduction(self):
        config = GameConfig(free_upkeep_cap=30, upkeep_cost_per_unit=1)
        game = NodeWarGame(config)
        # Give P1 exactly 40 units (10 over free cap of 30)
        game.nodes[0].units = {ut: 0 for ut in UnitType}
        game.nodes[0].units[UnitType.GUARD] = 40
        initial_credits = game.player_credits[PlayerId.PLAYER_1]
        p1_income = sum(n.production for n in game.nodes.values() if n.owner == PlayerId.PLAYER_1)

        # Step 1 turn
        game.step(p1_orders=[], p2_orders=[])
        # Expected credits = initial + income - (40 - 30)*1
        expected = initial_credits + p1_income - 10
        self.assertEqual(game.player_credits[PlayerId.PLAYER_1], expected)

    def test_relic_scoring(self):
        config = GameConfig(max_turns=100, relic_spawn_turn=50, relic_node_id=7, relic_points_per_turn=10, relic_point_multiplier=2)
        game = NodeWarGame(config)
        game.current_turn = 50  # Activate relic
        game.nodes[7].owner = PlayerId.PLAYER_1

        p1_score_before = game.scores[PlayerId.PLAYER_1]
        p1_owned_nodes = sum(1 for n in game.nodes.values() if n.owner == PlayerId.PLAYER_1)

        game.step(p1_orders=[], p2_orders=[])
        # Points gained = (p1_owned_nodes * 2) + 10 for Relic
        gained = game.scores[PlayerId.PLAYER_1] - p1_score_before
        self.assertEqual(gained, (p1_owned_nodes * 2) + 10)

    def test_fog_of_war_masking_and_scouts(self):
        game = NodeWarGame()
        # Clean Node 1
        game.nodes[1].owner = PlayerId.PLAYER_1
        game.nodes[1].units = {ut: 0 for ut in UnitType}

        # P2 launches a fleet towards Node 1 without P1 having a scout
        game.nodes[14].units[UnitType.SIEGE] = 5
        p2_move = MoveOrder(origin_node=14, dest_node=13, units={UnitType.SIEGE: 5})
        game.step(p1_orders=[], p2_orders=[p2_move])

        obs_p1 = game.get_player_observation(PlayerId.PLAYER_1)
        self.assertEqual(len(obs_p1.enemy_fleets), 1)
        enemy_fleet = obs_p1.enemy_fleets[0]
        self.assertFalse(enemy_fleet.is_revealed)
        self.assertIsNone(enemy_fleet.units)
        self.assertEqual(enemy_fleet.total_count, 5)

        # Now place a Scout at Node 13 (the destination node)
        game.nodes[13].owner = PlayerId.PLAYER_1
        game.nodes[13].units[UnitType.SCOUT] = 1

        obs_p1_scouted = game.get_player_observation(PlayerId.PLAYER_1)
        enemy_fleet_scouted = obs_p1_scouted.enemy_fleets[0]
        self.assertTrue(enemy_fleet_scouted.is_revealed)
        self.assertIsNotNone(enemy_fleet_scouted.units)
        self.assertEqual(enemy_fleet_scouted.units["siege"], 5)

if __name__ == "__main__":
    unittest.main()
