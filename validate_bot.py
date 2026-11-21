"""
Node War - Competitor Bot Validator Tool
========================================
This tool allows teams to dry-run validate their custom bot scripts locally.
It verifies inheritance, method signatures, return types, order schemas, and
symmetrical Player 1 / Player 2 compatibility without needing to run an entire match.

It is 100% self-contained and requires only a standard Python 3 installation.

Usage:
------
    python validate_bot.py starter_bot.py
    python validate_bot.py my_bot.py
"""

from __future__ import annotations
import sys
import os

from nodewar import (
    UnitType,
    UnitStats,
    UNIT_STATS,
    Order,
    TrainOrder,
    MoveOrder,
    VisibleNode,
    VisibleFleet,
    BotObservation,
    BotBase,
    StarterBot,
    CompetitorBot,
    RusherBot,
    TurtleBot,
    BalancedBot,
    LocalSimulator,
    validate_bot,
    simulate_match,
    simulate_bo3,
    calculate_damage,
    apply_damage_to_army,
    resolve_combat,
    resolve_meeting_engagement,
    MAP_NODES,
    MAP_LANES,
)

def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_bot.py <path_to_bot.py>")
        print("Tip: Use 'python nodewar.py simulate <path_to_bot.py>' to simulate a local match against a baseline bot.")
        sys.exit(1)

    target_path = sys.argv[1]
    success = validate_bot(target_path)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
