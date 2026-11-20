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
        game = NodeWarGame()
        # P1 starts with 1 owned node (Node 0). Free cap = 10 + (4 * 1) = 14
        free_cap = game.get_player_free_supply_cap(PlayerId.PLAYER_1)
        self.assertEqual(free_cap, 14)

        # Place 40 guards at home node (Node 0)
        game.nodes[0].units = {ut: 0 for ut in UnitType}
        game.nodes[0].units[UnitType.GUARD] = 40
        initial_credits = game.player_credits[PlayerId.PLAYER_1]
        p1_income = sum(n.production for n in game.nodes.values() if n.owner == PlayerId.PLAYER_1)

        # Step 1 turn
        game.step(p1_orders=[], p2_orders=[])
        # Expected upkeep = (40 - 14) * 1 = 26
        expected = initial_credits + p1_income - (40 - free_cap) * 1
        self.assertEqual(game.player_credits[PlayerId.PLAYER_1], expected)

        # Test foreign unit upkeep (2 cr/unit)
        game2 = NodeWarGame()
        # 14 home units (covers free cap), plus 5 units stationed on unowned node
        game2.nodes[0].units = {UnitType.GUARD: 14, UnitType.RAIDER: 0, UnitType.SIEGE: 0, UnitType.SCOUT: 0}
        game2.nodes[1].owner = PlayerId.NONE
        game2.nodes[1].resident_player = PlayerId.PLAYER_1
        game2.nodes[1].units = {UnitType.RAIDER: 5, UnitType.GUARD: 0, UnitType.SIEGE: 0, UnitType.SCOUT: 0}
        
        init_cr2 = game2.player_credits[PlayerId.PLAYER_1]
        inc2 = sum(n.production for n in game2.nodes.values() if n.owner == PlayerId.PLAYER_1)
        game2.step(p1_orders=[], p2_orders=[])
        # 5 foreign units over free cap cost 2 credits each = 10
        self.assertEqual(game2.player_credits[PlayerId.PLAYER_1], init_cr2 + inc2 - 10)

    def test_tiered_yields_and_neutral_garrisons(self):
        nodes, _ = create_default_map()
        # Outer nodes: +4 prod, 1 Raider garrison
        for nid in [1, 2, 4, 10, 12, 13]:
            self.assertEqual(nodes[nid].production, 4)
            self.assertEqual(nodes[nid].units[UnitType.RAIDER], 1)

        # Mid chokes: +7 prod, 2 Guard garrison
        for nid in [3, 5, 6, 8, 9, 11]:
            self.assertEqual(nodes[nid].production, 7)
            self.assertEqual(nodes[nid].units[UnitType.GUARD], 2)

        # Relic node: +10 prod, 2 Guards + 1 Siege
        self.assertEqual(nodes[7].production, 10)
        self.assertEqual(nodes[7].units[UnitType.GUARD], 2)
        self.assertEqual(nodes[7].units[UnitType.SIEGE], 1)

        # Home nodes: +15 prod, +50% defense bonus
        self.assertEqual(nodes[0].production, 15)
        self.assertEqual(nodes[0].defense_bonus, 0.50)
        self.assertEqual(nodes[14].production, 15)
        self.assertEqual(nodes[14].defense_bonus, 0.50)

    def test_scout_combat_targeting_bonus(self):
        from engine.combat import calculate_damage
        army_a = {UnitType.GUARD: 5, UnitType.RAIDER: 0, UnitType.SIEGE: 0, UnitType.SCOUT: 0}
        army_b = {UnitType.GUARD: 5, UnitType.RAIDER: 0, UnitType.SIEGE: 0, UnitType.SCOUT: 0}

        dmg_normal = calculate_damage(army_a, army_b, has_friendly_scout=False, has_enemy_scout=False)
        dmg_with_scout = calculate_damage(army_a, army_b, has_friendly_scout=True, has_enemy_scout=False)
        dmg_blind = calculate_damage(army_a, army_b, has_friendly_scout=False, has_enemy_scout=True)

        self.assertAlmostEqual(dmg_with_scout, dmg_normal * 1.15, places=4)
        self.assertAlmostEqual(dmg_blind, dmg_normal * 0.85, places=4)

    def test_scout_capture_freeze(self):
        game = NodeWarGame()
        node1 = game.nodes[1]
        node1.units = {ut: 0 for ut in UnitType}
        node1.owner = PlayerId.NONE
        node1.capturing_player = PlayerId.PLAYER_1
        node1.capture_progress = 1
        node1.resident_player = PlayerId.PLAYER_1
        node1.units[UnitType.RAIDER] = 5

        # P2 sends a fleet with a scout arriving at Node 1
        from engine.models import Fleet
        game.fleets.append(Fleet(
            id=99,
            owner=PlayerId.PLAYER_2,
            origin_node=3,
            dest_node=1,
            turns_remaining=1,
            total_turns=1,
            units={UnitType.SCOUT: 1}
        ))

        # Advance step: scout contest should freeze progress at 1 instead of flipping to 2
        game.step(p1_orders=[], p2_orders=[])
        self.assertEqual(node1.owner, PlayerId.NONE)
        self.assertEqual(node1.capture_progress, 1)

    def test_variable_relic_charging(self):
        cfg = GameConfig(min_relic_turn=80, max_relic_turn=100, relic_spawn_turn=90)
        game = NodeWarGame(cfg)
        game.current_turn = 84
        self.assertFalse(game.relic_charging)
        self.assertFalse(game.relic_active)

        # At turn 85 (90 - 5), warning flag activates
        game.current_turn = 85
        self.assertTrue(game.relic_charging)
        self.assertFalse(game.relic_active)

        obs = game.get_player_observation(PlayerId.PLAYER_1)
        self.assertTrue(obs.relic_charging)
        self.assertFalse(obs.relic_active)

        # At turn 90, relic activates
        game.current_turn = 90
        self.assertFalse(game.relic_charging)
        self.assertTrue(game.relic_active)

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

    def test_tiebreaker_net_worth_parity(self):
        """Verifies that Banked Gold and Army Asset Value have 1:1 parity (no 10x Gold Dump exploit)."""
        game = NodeWarGame()
        game.scores[PlayerId.PLAYER_1] = 10
        game.scores[PlayerId.PLAYER_2] = 10
        game.relic_turns_held[PlayerId.PLAYER_1] = 0
        game.relic_turns_held[PlayerId.PLAYER_2] = 0

        # P1 has 101 banked Gold and 0 army units
        game.player_credits[PlayerId.PLAYER_1] = 101
        for n in game.nodes.values():
            if n.owner == PlayerId.PLAYER_1 or n.resident_player == PlayerId.PLAYER_1:
                n.units = {ut: 0 for ut in UnitType}

        # P2 has 0 banked Gold and 10 Raiders (cost 10 * 10 = 100 Gold army value)
        game.player_credits[PlayerId.PLAYER_2] = 0
        for n in game.nodes.values():
            if n.owner == PlayerId.PLAYER_2 or n.resident_player == PlayerId.PLAYER_2:
                n.units = {ut: 0 for ut in UnitType}
        game.nodes[14].units[UnitType.RAIDER] = 10

        # Under the old exploit, P2's army had a 10x multiplier (1000 tiebreak pts vs P1's 101 pts).
        # Under 1:1 net worth parity:
        # P1 net worth = 101 gold + 0 army = 101 pts
        # P2 net worth = 0 gold + 100 army = 100 pts
        # P1 must win!
        game.current_turn = 120
        game._resolve_tiebreak()
        self.assertEqual(game.winner, PlayerId.PLAYER_1)

    def test_bankruptcy_desertion_attrition(self):
        """Verifies that unpaid upkeep triggers desertion attrition instead of starvation immunity."""
        game = NodeWarGame()
        # Drain P1 treasury to 0
        game.player_credits[PlayerId.PLAYER_1] = 0

        # Set up a large army on P1 home node: free cap is 14. Place 20 Raiders (6 excess domestic = 6 deficit)
        game.nodes[0].units = {ut: 0 for ut in UnitType}
        game.nodes[0].units[UnitType.RAIDER] = 20
        # Income from home node is +15, so set node production to 0 for this isolated test to test deficit
        game.nodes[0].production = 0

        # Step 1 turn with 0 income and 0 treasury
        # Upkeep = (20 - 14) * 1 = 6 Gold deficit
        # Treasury drops to 0, 6 Raiders must desert!
        game.step(p1_orders=[], p2_orders=[])
        self.assertEqual(game.player_credits[PlayerId.PLAYER_1], 0)
        self.assertEqual(game.nodes[0].units[UnitType.RAIDER], 14)

    def test_mobilization_rule_same_turn_train_and_move(self):
        """Verifies that newly trained units defend same turn but cannot march until next turn."""
        game = NodeWarGame()
        game.player_credits[PlayerId.PLAYER_1] = 100
        # Node 0 has 2 existing Raiders
        game.nodes[0].units = {ut: 0 for ut in UnitType}
        game.nodes[0].units[UnitType.RAIDER] = 2

        # P1 trains 3 Raiders and orders 4 Raiders to march from Node 0 to Node 1
        # Node has 2 existing + 3 newly trained = 5 total.
        # But mobilized available = 5 - 3 = 2!
        # An order to move 4 Raiders must be rejected because newly trained units cannot march same turn!
        train_order = TrainOrder(node_id=0, unit_type=UnitType.RAIDER, count=3)
        illegal_move = MoveOrder(origin_node=0, dest_node=1, units={UnitType.RAIDER: 4})

        game.step(p1_orders=[train_order, illegal_move], p2_orders=[])
        # Move was rejected: no fleet launched for P1
        p1_fleets = [f for f in game.fleets if f.owner == PlayerId.PLAYER_1]
        self.assertEqual(len(p1_fleets), 0)
        # All 5 units remain at garrison
        self.assertEqual(game.nodes[0].units[UnitType.RAIDER], 5)

        # On the NEXT turn, all 5 units are now mobilized and can march!
        legal_move = MoveOrder(origin_node=0, dest_node=1, units={UnitType.RAIDER: 5})
        game.step(p1_orders=[legal_move], p2_orders=[])
        p1_fleets_next = [f for f in game.fleets if f.owner == PlayerId.PLAYER_1]
        self.assertEqual(len(p1_fleets_next), 1)
        self.assertEqual(p1_fleets_next[0].units[UnitType.RAIDER], 5)
        self.assertEqual(game.nodes[0].units[UnitType.RAIDER], 0)

if __name__ == "__main__":
    unittest.main()
