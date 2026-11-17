# Node War - Context

## Project Overview
Node War is a competitive turn-based strategy game engine designed for a college technical festival / hackathon. In this event, student teams write automated AI bots that compete head-to-head on a mirrored network map. The game combines tactical depth, rock-paper-scissors counter mechanics, fog-of-war fleet movements, economic management, and high-stakes late-game comeback mechanics (the central Relic).

The audience watches matches through a spectator visualizer showing full omniscient information (including hidden fleet compositions), creating exciting commentary and viewing experiences.

## Hardware & Environment
- **Platform**: Windows 11
- **CPU**: AMD Ryzen 5 7600X (6 cores / 12 threads)
- **RAM**: 32 GB DDR5
- **GPU**: NVIDIA GeForce RTX 5060 Ti (16 GB VRAM)
- **Python**: 3.14.7

## Project Structure
```
f:\Avaneesh\projects\battlecode\
├── serve.py              # Root launcher alias for the web spectator arena
├── engine/
│   ├── __init__.py
│   ├── models.py         # PlayerId, UnitType, Fleet, Node, Lane, GameConfig dataclasses
│   ├── map.py            # Mirrored 15-node tournament graph & Floyd-Warshall pathfinding
│   ├── combat.py         # Deterministic Lanchester RPS combat & defense bonus resolution
│   ├── fog.py            # Fog-of-war filter for bot observations
│   └── game.py           # Main turn loop state machine, 2-turn capture flip, relic scoring
├── bots/
│   ├── __init__.py
│   ├── base.py           # BotBase abstract class & pathfinding/order helpers
│   ├── rusher.py         # Pure Raider swarm blitzkrieg bot
│   ├── turtle.py         # Perimeter Guard fortification & relic anchor bot
│   ├── balanced.py       # Recon Scout & heavy Siege artillery bot
│   └── starter_bot.py    # Documented reference template for competitor teams
├── runner/
│   ├── __init__.py
│   ├── match.py          # 1v1 execution harness with timeout handling & JSON replay export
│   ├── tournament.py     # Pairwise tournament evaluator & balance matrix verifier
│   └── replay.py         # Replay serialization
├── web/
│   ├── index.html        # Modern esports spectator UI with 1v1, Matrix, Lab & Vault tabs
│   ├── style.css         # Dark cyberpunk styling with neon player accents
│   ├── visualizer.js     # Canvas renderer with smooth fleet interpolation & particle sparks
│   └── serve.py          # Local HTTP server with live simulation & tournament endpoints
├── tests/
│   ├── test_engine.py    # Unit tests for combat, symmetry, upkeep, capture, fog
│   ├── test_bots.py      # Integration tests for bots running full games
│   └── test_web_server.py# HTTP & API endpoint integration tests
├── replays/              # Saved match replay JSON files
└── README.md             # Complete tournament guide & developer docs
```

## Current Status & Verification
- `sys.path` import issue resolved in `web/serve.py`; root `serve.py` convenience script added.
- Dynamic script discovery & loading added for `f:\Avaneesh\projects\battlecode\bots\`: any `.py` file (such as `bot1.py`) is automatically detected, populated in Player 1/2 dropdowns, and loadable via runner CLI (`python -m runner.match --p1 bot1.py --p2 turtle`).
- Web Spectator Arena upgraded with full match controls:
  - 1v1 Match Setup with custom bot script dropdown and "Refresh Bots" trigger.
  - Script source code loader in Bot Lab for inspecting and modifying files in `bots/`.
  - In-browser Tournament Matrix Evaluator with dynamic win rate bars.
  - Interactive Custom Bot Playground with live browser-based code compilation.
  - Replay Vault with load & refresh capabilities.
  - In-match quick navigation (Relic jump, Clash jump, Finish jump).
- All 16 unit, integration, and HTTP API tests passing.
