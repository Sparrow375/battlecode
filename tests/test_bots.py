from __future__ import annotations
import unittest
from engine.models import GameConfig
from runner.match import run_match, BOT_REGISTRY

class TestBots(unittest.TestCase):
    def test_rusher_vs_turtle_completes(self):
        res = run_match(
            BOT_REGISTRY["rusher"],
            BOT_REGISTRY["turtle"],
            config=GameConfig(max_turns=30),
            save_replay=False
        )
        self.assertIn(res.winner, [1, 2])
        self.assertTrue(len(res.win_reason) > 0)

    def test_starter_bot(self):
        res = run_match(
            BOT_REGISTRY["starter"],
            BOT_REGISTRY["rusher"],
            config=GameConfig(max_turns=20),
            save_replay=False
        )
        self.assertIn(res.winner, [1, 2])

if __name__ == "__main__":
    unittest.main()

