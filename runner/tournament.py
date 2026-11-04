from __future__ import annotations
import argparse
from typing import Dict, List, Tuple
from engine.models import GameConfig
from runner.match import run_match, BOT_REGISTRY

def run_balance_matrix(rounds_per_pair: int = 10, max_turns: int = 120) -> Dict[str, Any]:
    """
    Evaluates the rock-paper-scissors dynamic between baseline bots:
    Pairs:
    1. Rusher vs Turtle
    2. Turtle vs Balanced
    3. Balanced vs Rusher
    """
    cfg = GameConfig(max_turns=max_turns)
    matchups = [
        ("rusher", "turtle", "Turtle"),
        ("turtle", "balanced", "Balanced"),
        ("balanced", "rusher", "Rusher"),
    ]

    results: Dict[str, Dict[str, Any]] = {}

    print(f"\n=======================================================")
    print(f"   NODE WAR - BALANCE MATRIX TOURNAMENT EVALUATION")
    print(f"=======================================================")
    print(f"Rounds per matchup pair: {rounds_per_pair * 2} (alternating sides)\n")

    for bot_a_name, bot_b_name, expected_winner in matchups:
        bot_a_class = BOT_REGISTRY[bot_a_name]
        bot_b_class = BOT_REGISTRY[bot_b_name]

        wins_a = 0
        wins_b = 0
        total_turns = 0

        # Half games as A=P1, B=P2; half as B=P1, A=P2
        for i in range(rounds_per_pair):
            res1 = run_match(bot_a_class, bot_b_class, bot_a_name.capitalize(), bot_b_name.capitalize(), config=cfg, save_replay=False)
            total_turns += res1.total_turns
            if res1.winner == 1:
                wins_a += 1
            elif res1.winner == 2:
                wins_b += 1

            res2 = run_match(bot_b_class, bot_a_class, bot_b_name.capitalize(), bot_a_name.capitalize(), config=cfg, save_replay=False)
            total_turns += res2.total_turns
            if res2.winner == 2:
                wins_a += 1
            elif res2.winner == 1:
                wins_b += 1

        total_matches = rounds_per_pair * 2
        rate_a = (wins_a / total_matches) * 100
        rate_b = (wins_b / total_matches) * 100
        avg_turns = total_turns / total_matches

        key = f"{bot_a_name}_vs_{bot_b_name}"
        results[key] = {
            "bot_a": bot_a_name,
            "bot_b": bot_b_name,
            "wins_a": wins_a,
            "wins_b": wins_b,
            "rate_a": rate_a,
            "rate_b": rate_b,
            "avg_turns": avg_turns,
            "expected_winner": expected_winner
        }

        print(f"Matchup: {bot_a_name.capitalize()} vs {bot_b_name.capitalize()}")
        print(f"  {bot_a_name.capitalize()}: {wins_a}/{total_matches} ({rate_a:.1f}%)")
        print(f"  {bot_b_name.capitalize()}: {wins_b}/{total_matches} ({rate_b:.1f}%)")
        print(f"  Avg Turns: {avg_turns:.1f}")
        actual_winner = bot_a_name.capitalize() if wins_a > wins_b else bot_b_name.capitalize()
        status = "PASSED (Cycle Valid)" if actual_winner.lower() == expected_winner.lower() else "NEEDS TUNING"
        print(f"  Result: Expected {expected_winner} -> Actual {actual_winner} [{status}]\n")

    return results

def main():
    parser = argparse.ArgumentParser(description="Evaluate Node War baseline bot balance matrix.")
    parser.add_argument("--rounds", type=int, default=10, help="Rounds per side per matchup (total matches = rounds * 2)")
    parser.add_argument("--turns", type=int, default=120, help="Maximum match turns")
    args = parser.parse_args()

    run_balance_matrix(rounds_per_pair=args.rounds, max_turns=args.turns)

if __name__ == "__main__":
    main()

