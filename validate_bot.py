"""
Node War - Competitor Bot Validator Tool
========================================
This tool allows teams to dry-run validate their custom bot scripts locally.
It verifies inheritance, method signatures, return types, order schemas, and
symmetrical Player 1 / Player 2 compatibility without needing to run an entire match.

Usage:
------
    python validate_bot.py bots/starter_bot.py
    python validate_bot.py path/to/my_bot.py
"""

from __future__ import annotations
import sys
import os
import argparse
from typing import List, Dict, Any, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.models import UnitType, TrainOrder, MoveOrder, Order
from engine.fog import BotObservation, VisibleNode, VisibleFleet
from engine.map import create_default_map, MapGraph
from runner.match import load_bot_from_file

def create_mock_observation(player_id: int, turn: int = 1, relic_charging: bool = False, relic_active: bool = False) -> BotObservation:
    """Creates a realistic typed mock BotObservation for dry-run verification."""
    nodes_map, lanes = create_default_map()
    
    visible_nodes: Dict[int, VisibleNode] = {}
    for nid, node in nodes_map.items():
        is_owned = (node.owner == player_id)
        # In mock, give player vision on owned and adjacent nodes
        visible_nodes[nid] = VisibleNode(
            id=node.id,
            name=node.name,
            x=node.x,
            y=node.y,
            owner=int(node.owner),
            production=node.production,
            defense_bonus=node.defense_bonus,
            capture_progress=node.capture_progress,
            capturing_player=int(node.capturing_player),
            units={ut.value: cnt for ut, cnt in node.units.items()} if is_owned else None,
            is_scouted=is_owned
        )

    my_fleets = [
        VisibleFleet(
            id=101,
            owner=player_id,
            origin_node=0 if player_id == 1 else 14,
            dest_node=1 if player_id == 1 else 13,
            turns_remaining=2,
            total_turns=2,
            total_count=3,
            is_revealed=True,
            units={"raider": 3}
        )
    ]

    lanes_data = [lane.to_dict() for lane in lanes]

    return BotObservation(
        current_turn=turn,
        max_turns=120,
        my_player_id=player_id,
        my_credits=30,
        my_score=0,
        opponent_score=0,
        relic_active=relic_active,
        relic_charging=relic_charging,
        relic_node_id=7,
        nodes=visible_nodes,
        lanes=lanes_data,
        my_fleets=my_fleets,
        enemy_fleets=[]
    )

def validate_bot(file_path: str) -> bool:
    print("=" * 65)
    print("   NODE WAR - COMPETITOR BOT DRY-RUN VALIDATOR")
    print("=" * 65)
    print(f"Target Script: {file_path}")

    # 1. File existence & size
    if not os.path.exists(file_path):
        print(f"❌ ERROR: File does not exist: {file_path}")
        return False
    if os.path.getsize(file_path) == 0:
        print(f"❌ ERROR: File is empty (0 bytes): {file_path}")
        return False
    print("  ✓ File located and non-empty")

    # 2. Dynamic class loading
    try:
        bot_cls, cls_name = load_bot_from_file(file_path)
        print(f"  ✓ Found Bot class: '{cls_name}'")
    except Exception as e:
        print(f"❌ ERROR during class inspection: {e}")
        return False

    # 3. Test Player 1 Instantiation & Act
    try:
        bot_p1 = bot_cls(player_id=1)
        print("  ✓ Player 1 instance initialized successfully")
    except Exception as e:
        print(f"❌ ERROR during Player 1 __init__: {e}")
        return False

    # Test Turn 1 Observation
    mock_turn1 = create_mock_observation(player_id=1, turn=1)
    try:
        orders_t1 = bot_p1.act(mock_turn1)
        print(f"  ✓ act(obs) executed on Turn 1 -> Returned {len(orders_t1) if orders_t1 else 0} orders")
    except Exception as e:
        print(f"❌ ERROR during act() on Turn 1: {e}")
        return False

    # 4. Test Player 2 Instantiation & Act
    try:
        bot_p2 = bot_cls(player_id=2)
        print("  ✓ Player 2 instance initialized successfully")
    except Exception as e:
        print(f"❌ ERROR during Player 2 __init__: {e}")
        return False

    mock_turn1_p2 = create_mock_observation(player_id=2, turn=1)
    try:
        orders_p2 = bot_p2.act(mock_turn1_p2)
        print(f"  ✓ act(obs) executed for Player 2 -> Returned {len(orders_p2) if orders_p2 else 0} orders")
    except Exception as e:
        print(f"❌ ERROR during Player 2 act(): {e}")
        return False

    # 5. Test Late-Game / Relic Warning Observation
    mock_relic = create_mock_observation(player_id=1, turn=85, relic_charging=True, relic_active=False)
    try:
        orders_relic = bot_p1.act(mock_relic)
        print(f"  ✓ act(obs) executed with relic_charging=True -> {len(orders_relic) if orders_relic else 0} orders")
    except Exception as e:
        print(f"❌ ERROR during act() with relic_charging: {e}")
        return False

    # 6. Validate Returned Orders Schema
    all_order_sets = [("P1 Turn 1", orders_t1), ("P2 Turn 1", orders_p2), ("Relic Warning", orders_relic)]
    _, lanes = create_default_map()
    valid_lanes = set()
    for l in lanes:
        valid_lanes.add((l.node_a, l.node_b))
        valid_lanes.add((l.node_b, l.node_a))

    for label, orders in all_order_sets:
        if orders is None:
            continue
        if not isinstance(orders, list):
            print(f"❌ ERROR: act() must return a list of Orders, got {type(orders)} in {label}")
            return False

        for idx, order in enumerate(orders):
            if isinstance(order, TrainOrder):
                if order.node_id < 0 or order.node_id > 14:
                    print(f"❌ ERROR: Invalid node_id {order.node_id} in TrainOrder #{idx} ({label})")
                    return False
                if order.count <= 0:
                    print(f"❌ ERROR: TrainOrder count must be positive, got {order.count} in Order #{idx} ({label})")
                    return False
                if not isinstance(order.unit_type, UnitType):
                    print(f"❌ ERROR: Invalid unit_type '{order.unit_type}' in TrainOrder #{idx} ({label})")
                    return False

            elif isinstance(order, MoveOrder):
                if (order.origin_node, order.dest_node) not in valid_lanes:
                    print(f"❌ ERROR: No direct lane connects Node {order.origin_node} to Node {order.dest_node} in MoveOrder #{idx} ({label})")
                    return False
                if not isinstance(order.units, dict):
                    print(f"❌ ERROR: MoveOrder.units must be a dict, got {type(order.units)} in Order #{idx} ({label})")
                    return False
                for ut, cnt in order.units.items():
                    if cnt <= 0:
                        print(f"⚠️ WARNING: MoveOrder has non-positive count {cnt} for unit {ut} in Order #{idx} ({label})")
            else:
                print(f"❌ ERROR: Unknown order type '{type(order)}' in Order #{idx} ({label}). Must be TrainOrder or MoveOrder.")
                return False

    print("  ✓ All returned orders conform strictly to the Node War protocol")
    print("=" * 65)
    print("🎉 VALIDATION PASSED! Your bot is ready for tournament competition.")
    print("=" * 65)
    return True

def main():
    parser = argparse.ArgumentParser(description="Dry-run validator for Node War competitor bots.")
    parser.add_argument("bot_path", type=str, help="Path to competitor bot Python script (e.g. bots/starter_bot.py)")
    args = parser.parse_args()

    success = validate_bot(args.bot_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
