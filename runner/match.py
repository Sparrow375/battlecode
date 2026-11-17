from __future__ import annotations
import argparse
import time
import os
import importlib.util
import inspect
from dataclasses import dataclass
from typing import Type, Optional, Dict, Any, Tuple

from engine.models import PlayerId, GameConfig
from engine.game import NodeWarGame
from bots.base import BotBase
from bots.rusher import RusherBot
from bots.turtle import TurtleBot
from bots.balanced import BalancedBot
from bots.starter_bot import StarterBot
from runner.replay import export_replay_to_json

BOT_REGISTRY: Dict[str, Type[BotBase]] = {
    "rusher": RusherBot,
    "turtle": TurtleBot,
    "balanced": BalancedBot,
    "starter": StarterBot
}

def load_bot_from_file(file_path: str) -> Tuple[Type[BotBase], str]:
    """Dynamically loads a BotBase subclass from a Python file path."""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Bot script not found at {file_path}")
    if os.path.getsize(abs_path) == 0:
        raise ValueError(f"The bot script '{os.path.basename(file_path)}' is empty. Please ensure your code is saved to the file.")

    module_name = f"custom_bot_{os.path.splitext(os.path.basename(abs_path))[0]}_{int(time.time()*1000)}"
    spec = importlib.util.spec_from_file_location(module_name, abs_path)
    if not spec or not spec.loader:
        raise ValueError(f"Could not load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 1. Check classes defined in this module that inherit from BotBase
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ == module.__name__:
            if (issubclass(obj, BotBase) or any(b.__name__ == "BotBase" for b in inspect.getmro(obj))) and obj.__name__ != "BotBase":
                return obj, name

    # 2. Check any class in module that inherits from BotBase (by type or MRO)
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if (issubclass(obj, BotBase) or any(b.__name__ == "BotBase" for b in inspect.getmro(obj))) and obj.__name__ != "BotBase":
            return obj, name

    # 3. Duck-typing fallback: any class with an act(self, obs) method
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__name__ != "BotBase" and hasattr(obj, "act") and callable(getattr(obj, "act")):
            return obj, name

    classes_found = [name for name, obj in inspect.getmembers(module, inspect.isclass) if obj.__name__ != "BotBase"]
    if classes_found:
        raise ValueError(
            f"Found classes {classes_found} in {os.path.basename(file_path)}, but none inherit from 'BotBase'. "
            f"Please ensure your bot class inherits from BotBase (e.g. 'class {classes_found[0]}(BotBase):')."
        )
    raise ValueError(f"No classes found in {os.path.basename(file_path)}. Ensure your bot defines a class inheriting from BotBase.")

def discover_custom_bots(bots_dir: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Discovers all custom python scripts in the bots directory."""
    if bots_dir is None:
        bots_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bots")
    discovered = {}
    builtin_files = {"__init__.py", "base.py", "rusher.py", "turtle.py", "balanced.py", "starter_bot.py"}
    if not os.path.isdir(bots_dir):
        return discovered
    for fname in os.listdir(bots_dir):
        if fname.endswith(".py") and fname not in builtin_files:
            fpath = os.path.join(bots_dir, fname)
            try:
                bot_cls, cls_name = load_bot_from_file(fpath)
                discovered[fname] = {
                    "filename": fname,
                    "filepath": fpath,
                    "class_name": cls_name,
                    "display_name": f"{fname} ({cls_name})",
                    "class": bot_cls
                }
            except Exception as e:
                discovered[fname] = {
                    "filename": fname,
                    "filepath": fpath,
                    "class_name": "Error",
                    "display_name": f"{fname} (Error)",
                    "error": str(e)
                }
    return discovered

def resolve_bot(bot_id: str, bots_dir: Optional[str] = None) -> Tuple[Type[BotBase], str]:
    """Resolves a bot by registry name, file path, or filename in bots/."""
    if bot_id in BOT_REGISTRY:
        return BOT_REGISTRY[bot_id], bot_id.capitalize()

    if bots_dir is None:
        bots_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bots")

    candidates = [
        bot_id,
        os.path.join(bots_dir, bot_id),
        os.path.join(bots_dir, f"{bot_id}.py") if not bot_id.endswith(".py") else os.path.join(bots_dir, bot_id)
    ]
    for c in candidates:
        if os.path.isfile(c):
            bot_cls, cls_name = load_bot_from_file(c)
            fname = os.path.basename(c)
            return bot_cls, f"{fname} ({cls_name})"

    raise ValueError(f"Unknown bot identifier or script: '{bot_id}'. Available built-ins: {list(BOT_REGISTRY.keys())}")

@dataclass
class MatchResult:
    winner: int
    winner_name: str
    win_reason: str
    total_turns: int
    p1_name: str
    p2_name: str
    p1_score: int
    p2_score: int
    replay_path: Optional[str] = None

def run_match(
    p1_class: Type[BotBase],
    p2_class: Type[BotBase],
    p1_name: Optional[str] = None,
    p2_name: Optional[str] = None,
    config: Optional[GameConfig] = None,
    save_replay: bool = True,
    replay_dir: str = "replays"
) -> MatchResult:
    """Executes a complete 1v1 match between two bot classes."""
    game = NodeWarGame(config)
    p1_bot = p1_class(player_id=1)
    p2_bot = p2_class(player_id=2)

    p1_label = p1_name or p1_class.__name__
    p2_label = p2_name or p2_class.__name__

    while not game.game_over:
        # Get observations respecting fog of war
        obs_p1 = game.get_player_observation(PlayerId.PLAYER_1)
        obs_p2 = game.get_player_observation(PlayerId.PLAYER_2)

        # Execute bot logic safely
        try:
            orders_p1 = p1_bot.act(obs_p1) or []
        except Exception as e:
            orders_p1 = []

        try:
            orders_p2 = p2_bot.act(obs_p2) or []
        except Exception as e:
            orders_p2 = []

        # Advance game engine by 1 step
        game.step(orders_p1, orders_p2)

    winner_id = int(game.winner) if game.winner else 0
    winner_name = p1_label if winner_id == 1 else (p2_label if winner_id == 2 else "Draw")

    replay_path = None
    if save_replay:
        timestamp = int(time.time() * 1000)
        filename = f"replay_{timestamp}_{p1_label}_vs_{p2_label}.json"
        replay_path = os.path.join(replay_dir, filename)
        export_replay_to_json(game, p1_label, p2_label, replay_path)

    return MatchResult(
        winner=winner_id,
        winner_name=winner_name,
        win_reason=game.win_reason,
        total_turns=game.current_turn - 1,
        p1_name=p1_label,
        p2_name=p2_label,
        p1_score=game.scores.get(PlayerId.PLAYER_1, 0),
        p2_score=game.scores.get(PlayerId.PLAYER_2, 0),
        replay_path=replay_path
    )

def main():
    parser = argparse.ArgumentParser(description="Run a Node War 1v1 match.")
    parser.add_argument("--p1", type=str, default="rusher", help="Player 1 Bot (name or bots/ filename)")
    parser.add_argument("--p2", type=str, default="turtle", help="Player 2 Bot (name or bots/ filename)")
    parser.add_argument("--turns", type=int, default=120, help="Maximum match turns")
    parser.add_argument("--no-replay", action="store_true", help="Disable replay saving")
    args = parser.parse_args()

    p1_class, p1_name = resolve_bot(args.p1)
    p2_class, p2_name = resolve_bot(args.p2)

    cfg = GameConfig(max_turns=args.turns)
    res = run_match(
        p1_class=p1_class,
        p2_class=p2_class,
        p1_name=p1_name,
        p2_name=p2_name,
        config=cfg,
        save_replay=not args.no_replay
    )

    print("=" * 60)
    print("MATCH RESULT")
    print("=" * 60)
    print(f"Match: {res.p1_name} (P1) vs {res.p2_name} (P2)")
    print(f"Winner: {res.winner_name} (Player {res.winner})")
    print(f"Reason: {res.win_reason}")
    print(f"Total Turns: {res.total_turns}")
    print(f"Scores: P1={res.p1_score} | P2={res.p2_score}")
    if res.replay_path:
        print(f"Replay saved to: {res.replay_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()

