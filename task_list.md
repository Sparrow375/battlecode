# Node War - Task List

- [x] Task 1: Complete and publish `/plan` technical specification artifact for user approval.
- [x] Task 2: Implement Game Engine Core (`engine/models.py`, `engine/map.py`, `engine/combat.py`, `engine/fog.py`, `engine/game.py`).
- [x] Task 3: Implement Unit Tests for Game Engine (verifying RPS combat, lane transit, capture timer, upkeep, relic bonus, fog-of-war masking).
- [x] Task 4: Implement Bot Protocol and Three Baseline Bots (`rusher.py`, `turtle.py`, `balanced.py`, `starter_bot.py`).
- [x] Task 5: Build Match Runner and Tournament Balance Matrix Tester (`runner/match.py`, `runner/tournament.py`, `runner/replay.py`).
- [x] Task 6: Run Balance Matrix experiments and fine-tune numerical parameters to ensure the rock-paper-scissors dynamic (cycle).
- [x] Task 7: Build Interactive Web Spectator & Replay Visualizer.
- [x] Task 8: Verification, Documentation, Student Starter Kit, walkthrough, initial git commit.
- [x] Task 9: Fix `sys.path` import issue in `web/serve.py` and provide root `serve.py` launcher.
- [x] Task 10: Expand Web App Match Controls.
- [x] Task 11: Verification of web controls, update `context.md`, `architechture.md`, and commit to git.
- [x] Task 12: Implement dynamic custom bot file loading from `bots/`:
  - Add `load_bot_from_file`, `discover_custom_bots`, and `resolve_bot` in `runner/match.py`.
  - Update `web/serve.py` with dynamic `/api/bots` scanning and `/api/bot-source/<filename>` endpoint.
  - Update `web/index.html` and `web/visualizer.js` to populate `select-p1` and `select-p2` with custom scripts from `bots/` (e.g. `bot1.py`), add "Refresh Bots" button, and add "Load into Editor" feature.
  - Run tests and verify with `bots/bot1.py`.
  - Update `context.md`, `architechture.md`, and commit to git.
