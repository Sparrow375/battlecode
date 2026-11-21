from __future__ import annotations
import json
import os
from typing import Dict, List, Any
from engine.game import NodeWarGame

def export_replay_to_json(
    game: NodeWarGame,
    p1_name: str,
    p2_name: str,
    output_path: str
) -> str:
    """Exports a full omniscient match replay as a structured JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    replay_data = {
        "metadata": {
            "p1_name": p1_name,
            "p2_name": p2_name,
            "winner": int(game.winner) if game.winner else 0,
            "win_reason": game.win_reason,
            "total_turns": game.current_turn - 1,
            "seed": game.config.seed,
            "relic_spawn_turn": game.config.relic_spawn_turn,
            "final_scores": {
                "p1": game.scores.get(1, 0),
                "p2": game.scores.get(2, 0)
            },
            "relic_turns": {
                "p1": game.relic_turns_held.get(1, 0),
                "p2": game.relic_turns_held.get(2, 0)
            }
        },
        "map": {
            "nodes": [node.to_dict() for node in game.nodes.values()],
            "lanes": [lane.to_dict() for lane in game.lanes]
        },
        "frames": [snapshot.to_dict() for snapshot in game.history]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(replay_data, f, indent=2)

    return output_path

