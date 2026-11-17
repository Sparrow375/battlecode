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
│   ├── style.css         # Styling with Multi-Engine Viewport layout & controls
│   ├── td_visualizer.js  # 2D Cartoon Tower Defense Engine with real animated game assets (DEFAULT)
│   ├── three_visualizer.js # Three.js 3D Isometric Battlefield engine with procedural models & FX
│   ├── visualizer.js     # Master multi-engine orchestrator, canvas fallback, scrubber & match controls
│   ├── assets/           # Tower Defense game asset pack (castles, towers, knights, rogues, cannons, eagles, trees)
│   ├── vendor/           # Offline vendor libraries (three.min.js, OrbitControls.js)
│   └── serve.py          # Local HTTP server with live simulation & tournament endpoints
├── tests/
│   ├── test_engine.py    # Unit tests for combat, symmetry, upkeep, capture, fog
│   ├── test_bots.py      # Integration tests for bots running full games
│   └── test_web_server.py# HTTP & API endpoint integration tests
├── replays/              # Saved match replay JSON files
├── validate_bot.py       # Standalone dry-run validator tool for student competitors
└── README.md             # Complete tournament guide & developer docs
```

## Current Status & Verification
- `sys.path` import issue resolved in `web/serve.py`; root `serve.py` convenience script added.
- Dynamic script discovery & loading added for `f:\Avaneesh\projects\battlecode\bots\`: any `.py` file (such as `bot1.py`, `equibot.py`) is automatically detected, populated in Player 1/2 dropdowns, and loadable via runner CLI (`python -m runner.match --p1 bot1.py --p2 turtle`).
- Web Spectator Arena upgraded with full match controls:
  - 1v1 Match Setup with custom bot script dropdown and "Refresh Bots" trigger.
  - Script source code loader in Bot Lab for inspecting and modifying files in `bots/`.
  - In-browser Tournament Matrix Evaluator with dynamic win rate bars.
  - Interactive Custom Bot Playground with live browser-based code compilation.
  - Replay Vault with load & refresh capabilities.
  - In-match quick navigation (Relic jump, Clash jump, Finish jump).
- Comprehensive Game Specification & Mechanics Manual published at `GAME_SPECIFICATION.md` for distribution to event competitors.
- **Node War 32-Team Tournament Balance Upgrade**:
  - **Tiered Node Yields**: Outer low-yield bastions `+4 cr/turn`, contested mid-lane chokepoints `+7 cr/turn`, Relic Sanctuary `+10 cr/turn`, Home cores `+15 cr/turn`.
  - **Neutral Defenders on Unclaimed Nodes**: 1 Raider on outer nodes, 2 Guards on mid-lane chokepoints, 2 Guards + 1 Siege on Node 7, halting mindless Turn-1 Raider swarms and ensuring tactical opening expansion.
  - **Dynamic Empire Supply Lines (Upkeep)**: Replaced flat 30-unit cliff with `10 + (4 × Owned Nodes)`. Units exceeding cap cost 1 credit/turn domestically or 2 credits/turn when stationed on unowned/enemy nodes or in transit (overextension supply tax).
  - **100% Simultaneous Phase Execution**: Train orders resolve simultaneously for both players, then Move orders resolve simultaneously. Neutral arrivals clash in meeting engagements with 0% defense bonus before capture progress begins.
  - **Tactical Scout Utility**: Units fighting with friendly Scouts present/adjacent receive a +15% combat targeting bonus (-15% blind penalty without one). Contesting Scouts freeze the 2-turn capture clock.
  - **Home Base Fortification**: Home nodes 0 and 14 receive a +50% defense bonus (halving incoming damage), eliminating early blitz knockouts and guaranteeing matches reach the late-game Relic phase.
  - **Variable Relic Activation Window**: Randomly awakens between Turn 80 and Turn 100 with a 5-turn warning broadcast (`obs.relic_charging = True`) and +10 pts/turn reward.
  - **Best-of-3 Series Runner with Side Swapping**: `run_best_of_3_series` alternates P1/P2 sides across games to eliminate first-player bias.
- **Visual Clarity & De-Cluttering Upgrades**:
  - **Full-Body Team Coloration**: Castles, watchtowers, and barracks SVGs tinted entirely in royal blue (`#1e3a8a`, `#2563eb`) for P1, crimson red (`#991b1b`, `#dc2626`) for P2, and slate grey for neutral, providing instant ownership recognition from across the auditorium.
  - **Glowing Base Aura Rings**: Faction-colored ellipses rendered under fortresses.
  - **Continuous Sub-Turn Motion Interpolation**: Marching squads glide continuously along winding road curves using `subTurnProgress` lerp rather than teleporting discretely on ticks.
  - **De-Cluttered Node Nameplates**: Compact badge `[ P1 CORE | +15 ]` and streamlined garrison pills showing only active unit types (`[ 🛡️2  💣1 ]`), omitting redundant boxes on empty nodes.
  - **Calibrated Pacing**: Default 1x playback speed adjusted to a comfortable 1000ms/turn (1.0 second per turn).
  - **HUD Banner Correction**: Relic banner corrected to `+10/TURN` (with charging warning support).
- **Competitor Starter Kit & Validation**:
  - `bots/starter_bot.py`: De-spoiled docstring with dynamic observation references.
  - `validate_bot.py`: Standalone dry-run validation script verifying inheritance, typed dataclass stubs, methods, and symmetrical P1/P2 execution.
- **Visual Bug Fixes & Dynamic Relic System Refinements**:
  - **Tower Defense Blank Canvas Fix**: Resolved a JS syntax error in `web/td_visualizer.js` caused by stray duplicate braces around line 585 that prevented the script from loading, enabling full castle, road, garrison, and animated squad rendering.
  - **2D Tactical Canvas Fix**: Fixed canvas dimension tracking in `web/visualizer.js` when switching from TD/3D to 2D mode, ensuring the tactical schematic grid, nodes, lanes, and fleets render immediately.
  - **Dynamic Relic Activation Integration**:
    - Replay metadata in `runner/replay.py` now exports `"relic_spawn_turn"`.
    - Preset Mode "Tournament Standard" sends `relic_spawn_turn: null` to activate the dynamic randomized awakening window (T80–T100).
    - Quick Navigation jump button dynamically reads the actual match relic turn (e.g. `⚡ Relic (T83)`).
    - Timeline scrubber marker and HUD status badge dynamically position and display the match's exact relic turn or `T80-100` window rather than a hardcoded `Turn 95`.
- All 20 unit tests, bot integration tests, and HTTP endpoints passing.
- Balance Matrix tournament evaluation verified: Rusher (0%) vs Turtle (100%), Turtle (0%) vs Balanced (100%), Balanced (0%) vs Rusher (100%) [100% Cycle Valid].
- All changes committed and pushed to remote git repository (`origin/master`).
