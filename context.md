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
- **Visual Clarity, Economy Rebranding & Interactive Controls**:
  - **Gold Economy Conversion**: Rebranded all UI, scoreboard HUD, node inspector, and documentation references from "Credits" to **Gold (🪙)** (e.g. `Gold: 30 🪙`, `+15 Gold/T`).
  - **Road Milestone Cleanup**: Removed all intrusive brown circles and "2T" / "3T" text badges from winding dirt roads, leaving clean, natural paths.
  - **Animated Marching Soldier Sprites**: Replaced bulky moving text/HUD banner cards on roads with real individual animated soldier sprites (Knights, Rogues, Cannons, Eagles) marching along the path with ground shadows, horizontal facing flip towards the destination (`scale(-1, 1)` when moving left), walking stride bobs, and a sleek minimal squad tag (`P1 · 5⚔️`). Fixed an issue where referencing `fleet.fleet_id` instead of `(fleet.id || fleet.fleet_id || 0)` produced `NaN` in `walkBob`/`walkTilt`, causing HTML5 canvas `drawImage` to silently skip rendering the soldier sprites. Added strict numerical finite guards and fallbacks.
  - **Animated 2-Soldier Battle Duels**: Implemented dynamic clashing soldier animations at contested battle nodes: attacking and defending soldiers face off, lunge, jump, swing blades, strike with explosive clash starbursts (`💥`), crossed slash energy trails, and recoil.
  - **Interactive Pan & Zoom**: Added full mouse wheel zoom centered around cursor (0.75x to 3.0x), click-and-drag map panning with `grab`/`grabbing` cursor, and floating on-screen zoom control buttons (`+`, `−`, `⟲`, with dynamic zoom percentage badge).
- **Simulation Server & Browser Communication Fix**:
  - **Multi-Threaded HTTP Server**: Upgraded `web/serve.py` from synchronous single-threaded `socketserver.TCPServer` to `ThreadedHTTPServer` (`socketserver.ThreadingMixIn, http.server.HTTPServer`) with `daemon_threads = True` and `allow_reuse_address = True`, preventing Chrome persistent connections and parallel asset requests from blocking simulation API calls.
  - **CORS & HTTP OPTIONS Preflight Support**: Implemented `do_OPTIONS` and attached CORS headers (`Access-Control-Allow-Origin: *`, methods, headers) across all HTTP responses in `end_headers()`.
  - **Universal API URL Routing**: Implemented `getApiUrl()` in `web/visualizer.js`, automatically redirecting API endpoints to `http://localhost:8000` regardless of whether the UI is accessed via `http://localhost:8000`, VS Code Live Server (`localhost:5500`), or double-clicked as a local file (`file:///...`).
  - **Dynamic Bot Naming Sync**: Synced fallback labels in `web/index.html` and `web/visualizer.js` to `NemesisNodeBot` matching `bots/bot1.py`.
- **Production Esports Projector Stream Architecture (Latest)**:
  - **Git Branching Strategy**: Preserved `master` branch as an intact development backup; created and switched to `production` branch for live event delivery.
  - **Lag & Performance Optimization**:
    - **Engine Render Loop Suspension**: Added `setActive(active)` state to `NodeWarTDVisualizer`, `NodeWarThreeVisualizer`, and `NodeWarVisualizer`. When Tower Defense mode is active, the heavy 3D WebGL render loop and 2D canvas loops are paused, eliminating triple concurrent rendering and restoring buttery-smooth 60+ FPS on laptops.
    - **Hardware-Accelerated Grass Pattern**: Replaced 2,300+ raw `ctx.fillRect` calls per animation frame with a pre-rendered repeating pattern tile (`createGrassPattern()`), cutting background draw calls from thousands to just two.
    - **Particle Array Capping**: Capped combat spark bursts and particle lifetimes to prevent unbounded garbage collection during large multi-node engagements.
  - **Dynamic Responsive Coordinate & Asset Scaling**:
    - **Resolution-Independent Scale Factor**: Implemented `getScaleFactor()` dynamically mapping viewport aspect ratio (`scale = clamp(min(w/1400, h/850), 0.55, 1.35)`) with proportional screen padding.
    - **Collision-Free Proportions**: Scaled home castles (`112 * scale`), watchtowers (`76 * scale` x `94 * scale`), barracks (`82 * scale` x `72 * scale`), roads (`38 * scale` / `28 * scale`), nameplates, garrison pills, marching soldiers, and duel animations. Guaranteed zero asset overlap on smaller laptop screens (e.g. 13" 1366x768) while displaying large and crisp on 1080p projectors and 4K displays.
  - **Audience Projector Stream View (`web/index.html`)**:
    - Removed left setup/lab panel and right debug/inspector panel entirely, allowing the battleground arena to occupy 100% of the display.
    - **Esports Scoreboard Header**: High-contrast faction cards with team scores, gold, income, upkeep, territory count (`🏰`), dynamic turn counter, animated Relic badge, and discrete setup link.
    - **Redesigned Low-Profile Bottom Ticker**: Sleek broadcast strip with timeline scrubber, milestone badges (T1, Dynamic Relic Turn, End), speed toggles, fullscreen button (`⛶`), and presenter hotkeys (`Space`, arrows, `F` for fullscreen, `R` for restart).
  - **Tournament Control & Caster Deck (`web/setup.html` & `web/setup.js`)**:
    - Dedicated organizer workstation for bot selection, presets, custom game configs, balance matrix testing, custom bot playground, and replay library.
    - **Live Remote Deck Sync**: Built real-time caster remote controller communicating with the projector view via `BroadcastChannel('node_war_stream')` and persistent `/api/active-match` API (play, pause, scrub, step, jump to relic/clash, switch engine modes remotely from the laptop).
  - **URL Unquoting & Special Character Sanitization**: Added `urllib.parse.unquote()` for replay filenames, bot sources, and active match requests, ensuring URL-encoded characters (like `%20` spaces and parentheses) resolve correctly from disk.
  - **Critical Production Bug Fixes (Solid Green Canvas & Failed to Fetch)**:
    - **Solid Green Canvas Root Cause & Resolution**: A stray duplicate block at line 756 in `web/td_visualizer.js` caused a `SyntaxError: Unexpected token '.'`, preventing the browser from parsing `NodeWarTDVisualizer`. Consequently, `visualizer.js` fell back with `this.tdViz` undefined, leaving `#td-canvas` showing only its CSS placeholder background `#8ac926` while HUD scores ticked up. Fixed by removing the duplicate tokens, adding loose equality (`==`) to `getNodeScreenPos`, and wrapping all 7 render layers (`meadow`, `roads`, `decor`, `castles`, `squads`, `combat`, `fog`) in defensive `try/catch` blocks.
    - **Failed to Fetch & Port Collision Root Cause & Resolution**: On Windows, `allow_reuse_address = True` allowed multiple Python processes to bind to port 8000 simultaneously. A zombie process from the previous day was hijacking requests and rejecting `/api/active-match` with 404/connection aborts. Terminated zombie processes, updated `web/serve.py` with `allow_reuse_address = (sys.platform != "win32")` to enforce exclusive socket binding, added clean collision diagnostics, and streamlined `web/setup.js` to avoid redundant large JSON payloads.
  - Server actively running and verified live on `http://localhost:8000`.
- All 22 unit tests, bot integration tests, and HTTP endpoints passing.
- Balance Matrix tournament evaluation verified: Rusher (0%) vs Turtle (100%), Turtle (0%) vs Balanced (100%), Balanced (0%) vs Rusher (100%) [100% Cycle Valid].
- **Pre-Tournament Final Check & Starter Bot Audit**:
  - **Starter Bot Verification (`bots/starter_bot.py`)**: Full security and exploit audit completed. The starter template contains zero cheats, exploits, or private state bypasses. It uses solely the public `BotBase` and `BotObservation` interface.
  - **Documentation & Specification Synchronization**: Resolved legacy rules in `GAME_SPECIFICATION.md` and `README.md`. Synchronized dynamic empire supply upkeep (`10 + 4*Owned Nodes`), dynamic variable Relic awakening window (Turns 80–100 with 5-turn `relic_charging` alert), Home Core +50% defense bonus, and Scout targeting modifiers across all competitor-facing documentation.
  - **Currency & API Alignment**: Documented Gold (🪙) lore currency while preserving backward-compatible `obs.my_credits` attribute mapping in `bots/starter_bot.py`.
  - **Dry-Run Validation Pass**: `python validate_bot.py bots/starter_bot.py` passed with full compliance on Player 1, Player 2, and late-game charging observation schemas.
  - **Full Engine Regression Suite**: All 22 engine unit tests, bot integration tests, and 8-round balance matrix cycle tests passing cleanly with 100% determinism.
- **Tournament Guidebook & Competitor Playbook Release (Participant-Only Overhaul)**:
  - **Participant Information Scoping**: Completely stripped all organizer-only tools (`serve.py`, web visualizer, `runner.tournament`, baseline bot sources `rusher`/`turtle`/`balanced`) from competitor guidebooks. Participants receive only what is necessary: game mechanics, math, rules, `validate_bot.py`, and the `BotBase`/`BotObservation` API specification.
  - **Table & Typography Fixes**: Enabled `MarkdownIt().enable('table')` in `scripts/build_docs.py` to fix raw markdown pipe rendering, ensuring clean styled HTML tables with dark navy headers and shaded rows.
  - **Math & Diagram Sanitization**: Converted all uncompiled raw LaTeX expressions into clean human-readable formulas (e.g. `Tiebreak Score = (Points × 100,000) + (Relic Turns Held × 1,000) + (Total Army Value × 10) + Banked Gold`). Compressed the 15-node ASCII network topology diagram to fit standard portrait pages without horizontal clipping or scrollbars.
  - **Game-Agnostic Playbook**: Refactored `docs/COMPETITIVE_BOT_ENGINEERING_HANDBOOK.md` into a completely game-agnostic framework suitable for immediate handout tonight before the game is revealed.
  - Both `.pdf` and `.docx` recompiled cleanly and verified in `docs/`.
- **Human-First Strategic Rules & Plain-English Manual Release**:
  - Enriched `docs/NODE_WAR_OFFICIAL_GAME_GUIDEBOOK.md` with a comprehensive human-centric strategy breakdown ("Risk meets StarCraft on a Chess board"):
    - Detailed 8-step clockwork turn lifecycle (Income -> Upkeep -> Decisions -> Travel -> Battles -> Capture Progress -> Scoring).
    - In-depth tactical guide to the 4 unit roles (Raiders as artillery hunters, Guards as wall anchors, Siege as bunker busters, Scouts as aerial spotters and capture freezers).
    - High-level strategic decision-making guide: Fortress advantage (+50% home defense), 2-turn capture relief counter-attacks, territorial supply cap limits, fog-of-war radar silhouettes, and late-game dynamic Relic timing surges.
    - Added the 4 Strategic Archetypes diagram and breakdown (Blitzkrieg Rusher, Iron Fortress, Recon Artillery, Dynamic Economist).
  - Recompiled both Word (.docx) and PDF (.pdf) via `scripts/build_docs.py` with 100% clean formatting and verified zero table or formula corruption.
- **Engine Patch & Comprehensive Exploit Elimination (Champions League Release)**:
  - **1:1 Net Worth Parity (Patched Turn 120 Gold Dump Exploit)**: Equalized Banked Gold and Army Asset Value 1:1 in `_resolve_tiebreak`. 1 Gold in treasury = 1 tiebreaker point; 1 Gold in army units = 1 tiebreaker point. Completely eliminates late-game artificial 10x score dumping on Turn 119/120.
  - **Bankruptcy Desertion Attrition (Patched Starvation Immunity Exploit)**: Added `_apply_desertion_attrition` in Phase 2 Upkeep. If treasury cannot cover upkeep deficit, gold drops to 0 and unpaid units desert from starvation until deficit is cleared. Foreign expeditionary units (saving 2 Gold each) desert first, then domestic garrisons (saving 1 Gold each), in order Raider -> Scout -> Guard -> Siege.
  - **Mobilization Delay Rule (Patched Same-Turn Train & Move Tempo Advantage)**: `_process_train_orders` tracks recruits by node. In `_process_move_orders`, `mobilized_available = node.units - newly_trained`. Units trained on Turn T immediately join garrisons to defend against enemy attacks arriving that turn, but cannot be launched into transit fleets until Turn T+1.
  - **Regression Test Suite**: Added 3 new unit tests in `tests/test_engine.py` verifying all 3 patched mechanics. All 25 engine unit tests, bot integration tests, and 8-round balance matrix tests pass with 100% determinism.
  - **Documentation & Guidebook Alignment**: Updated `GAME_SPECIFICATION.md` and participant guidebook `docs/NODE_WAR_OFFICIAL_GAME_GUIDEBOOK.md` with human-friendly strategic rules explaining mobilization, bankruptcy desertion, and net worth parity, with clean unit summary tables and zero unrendered LaTeX.
  - Recompiled Word (.docx), HTML (.html), and PDF (.pdf) via `scripts/build_docs.py`. Both documents verified clean and ready for immediate distribution.
- **Participant Guidebook Coaching & Strategy Elimination**:
  - Removed all spoon-fed strategic takeaways, "the catch" callouts, coaching advice ("When to Use"), and the four archetypes playbook from `docs/NODE_WAR_OFFICIAL_GAME_GUIDEBOOK.md`.
  - Re-anchored the document strictly to objective mechanics: clear turn phases, unit properties and counter multipliers, castle defense bonuses, dynamic supply limits, mobilization delays, fog-of-war rules, tiebreak net worth parity, and API references.
  - Empowered student participants to analyze the rules and discover strategies, meta archetypes, and tactical counters independently.
  - Recompiled both Word (.docx), HTML (.html), and high-resolution PDF (.pdf) files in `docs/`.
- **Competitor Starter Kit Packaging**:
  - Upgraded `validate_bot.py` into a 100% self-contained standalone validator bundling the dataclasses (`UnitType`, `TrainOrder`, `MoveOrder`, `Order`, `VisibleNode`, `VisibleFleet`, `BotObservation`, `BotBase`), 15-node map graph, observation generator, and dynamic bot loader with zero external dependencies.
  - Added synthetic module registration (`engine.models`, `engine.fog`, `bots.base`) in `validate_bot.py` and fallback import handling in `bots/starter_bot.py`.
  - Packaged `node_war_starter_kit.zip` containing strictly:
    1. `NODE_WAR_OFFICIAL_GAME_GUIDEBOOK.pdf`
    2. `starter_bot.py`
    3. `validate_bot.py`
  - Verified end-to-end extraction and dry-run validation in an isolated directory with zero dependencies. Ready for direct distribution to hackathon teams.
