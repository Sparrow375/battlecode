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
│   ├── style.css         # Dark cyberpunk styling with 3D/2D viewport layout & controls
│   ├── three_visualizer.js # Three.js 3D Isometric Battlefield engine with procedural models & FX
│   ├── visualizer.js     # Dual-engine orchestrator, canvas fallback, scrubber & match controls
│   ├── vendor/           # Offline vendor libraries (three.min.js, OrbitControls.js)
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
- Stale server process on port 8000 stopped and restarted with latest endpoints.
- Web UI dropdowns hardened with fallbacks to guarantee populated options across all browsers.
- Dynamic bot loader enhanced with MRO inspection and duck-typing fallback, verified working with `bots/bot1.py` (ApexNodeBot) and `bots/equibot.py` (NemesisNodeBot).
- Comprehensive Game Specification & Mechanics Manual published at `GAME_SPECIFICATION.md` for distribution to event competitors.
- Three.js 3D Isometric Battlefield engine implemented and set as default:
  - Procedural 3D Fortresses: Multi-level Command Citadels (Nodes 0 & 14), Industrial Refineries (Nodes 1–4, 10–13), Chokepoint Pillboxes (Nodes 5, 6, 8, 9), and Ancient Relic Sanctuary (Node 7) with dynamic Turn 95 awakening, levitation, and golden skybeam.
  - Procedural 3D Soldier Models: Raiders (combat speeders), Guards (armored phalanx mechs with energy shields), Siege (heavy crawler artillery tanks), and Scouts (floating recon probes).
  - Tactical squad formations marching along 3D elevated cyber-rail lanes.
  - Combat clashing particle FX (spark bursts, laser fire, shield deflections, artillery impacts).
  - Dynamic Fog of War: Shrouds unscouted sectors in dark mist in P1 and P2 views; full omniscient clarity in Spectator view.
  - Dual-Engine Toggle: 1-click switch between 3D Arena and 2D Tactical canvas.
  - OrbitControls & Camera Presets: Isometric, P1 Core, Relic, P2 Core, and Spectator Auto-Orbit.
  - Fully offline-ready with local vendor libraries in `web/vendor/`.
  - All 16 unit, integration, and HTTP API tests passing.
