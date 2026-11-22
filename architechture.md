# Node War - Architecture

## System Architecture Overview

```mermaid
flowchart TD
    subgraph Engine Core [Python Simulation Engine]
        Map[Symmetric Map Generator & Graph]
        Rules[Game Rules & Combat Resolution]
        FOW[Fog-of-War & Observation Masker]
        Sim[Turn-Based Simulation Loop]
    end

    subgraph Bot Layer [Competitor Agents]
        Protocol[Bot Protocol & Abstract Base Class]
        Rusher[Rusher Bot]
        Turtle[Turtle Bot]
        Balanced[Balanced / Scout Bot]
        StudentBots[Student Submitted Bots]
    end

    subgraph Evaluation & Harness [Match & Tournament Runner]
        Runner[Head-to-Head Runner]
        Matrix[Balance Tournament Matrix]
        ReplayGen[Replay JSON Exporter]
    end

    subgraph Spectator & Web UI [Interactive Multi-Engine Visualizer]
        WebServer[Web Demo / Spectator Server]
        EngineSelector[Multi-Engine Switcher: TD (Default) | 3D Arena | 2D Tactical]
        TDUI[Cartoon Tower Defense Game Engine (td_visualizer.js)]
        ThreeUI[3D Isometric Battlefield (three_visualizer.js)]
        CanvasUI[2D Tactical Canvas Visualizer]
        AssetPack[Tower Defense Game Assets: Castles, Watchtowers, Knights, Rogues, Cannons, Eagles]
        FOWToggle[Spectator / P1 / P2 Fog-of-War Shroud]
        Playback[Scrubber, Speed Controls & Live Play]
    end

    Map --> Sim
    Rules --> Sim
    Sim --> FOW
    FOW -->|Player 1 Obs| Protocol
    FOW -->|Player 2 Obs| Protocol
    Protocol --> Rusher
    Protocol --> Turtle
    Protocol --> Balanced
    Protocol --> StudentBots
    Rusher -->|Orders| Sim
    Turtle -->|Orders| Sim
    Balanced -->|Orders| Sim
    StudentBots -->|Orders| Sim
    Sim --> Runner
    Runner --> Matrix
    Runner --> ReplayGen
    ReplayGen --> EngineSelector
    WebServer --> EngineSelector
    EngineSelector --> TDUI
    EngineSelector --> ThreeUI
    EngineSelector --> CanvasUI
    AssetPack --> TDUI
    FOWToggle --> TDUI
    FOWToggle --> ThreeUI
    FOWToggle --> CanvasUI
```

## Core Modules & Structure

1. **`engine/`**:
   - `models.py`: Data classes for Nodes, Lanes, Fleets, Combat, Upkeep, Relic, and Orders. Supports `relic_charging`, dynamic supply parameters, and typed observations.
   - `map.py`: Symmetrical mirrored graph generator (15 nodes) with tiered yields (+4 outer, +7 mid chokes, +10 Relic, +15 Home), neutral garrisons on unclaimed nodes (1 Raider outer, 2 Guards chokes, 2 Guards + 1 Siege Relic), and fortified Home citadels (+50% defense bonus).
   - `combat.py`: Deterministic RPS combat resolution with Scout combat targeting bonus (+15% with scout, -15% blind penalty), neutral meeting engagement resolution (0% defender bonus), and outpost/citadel defense bonuses.
   - `game.py`: Main state machine executing 100% simultaneous turn phases:
     1. Tiered Resource Production (+4/+7/+10/+15 credits/gold)
     2. Dynamic Empire Supply Lines Upkeep (`10 + 4*Owned Nodes`; 1 cr domestic, 2 cr foreign/in-transit) with **Bankruptcy Desertion Attrition** (`_apply_desertion_attrition` disbands foreign units first, then domestic; Raider -> Scout -> Guard -> Siege to resolve deficits)
     3. Simultaneous Train Orders Resolution (for both players; recruits defend garrison this turn)
     4. Simultaneous Move Orders Resolution & Fleet Launch (enforcing **Mobilization Rule**: newly trained units cannot march on the same turn)
     5. Fleet Movement & Lane Transit
     6. Vision Resolution & Scout Combat Modifier
     7. Combat Resolution (Neutral meeting engagements, neutral garrison clashes, and siege defenses)
     8. Two-Turn Node Capture Progress (freezes if actively contested by enemy Scout)
     9. Dynamic Relic Awakening (randomized between Turns 80–100 with 5-turn charging alert; +10 pts/turn + 2x multiplier)
     10. Victory / Deterministic Tiebreak Check (with **1:1 Net Worth Parity**: Total Army Asset Value + Banked Gold, eliminating late-game Gold Dump exploits)
   - `fog.py`: Strips hidden fleet compositions from opponent observation while preserving omniscient state for spectator replays; exposes `relic_charging` flag.

2. **`bots/`**:
   - `base.py`: Competitor bot interface (`act(obs) -> list[Order]`), serialization, helper navigation utilities.
   - `rusher.py`: Aggressive Raider swarm targeting adjacent economy nodes early.
   - `turtle.py`: Heavy Guard defense, chokepoint consolidation, tech/economy buildup.
   - `balanced.py`: Recon-first strategy deploying scouts, reading enemy fleets, and recruiting counter-units (Siege against Guards, Guards against Raiders, Raiders against Siege).
   - Custom scripts (e.g. `ctrl_alt_elite.py` [Champions League 2026 Winner], `starter_bot.py`): Dynamically discovered and loaded by filename.
   - `validate_bot.py`: Standalone dry-run validator tool with typed dataclass stubs for student competitors.

3. **`runner/`**:
   - `match.py`: Head-to-head match executor and **Best-of-3 Series Runner (`run_best_of_3_series`)** with alternating sides (P1/P2) to eliminate first-player bias.
   - `tournament.py`: Automated round-robin matrix testing win-rates and Best-of-3 tournament evaluation.
   - `replay.py`: Compact, structured JSON replay serialization including omniscient frames and dynamic `relic_spawn_turn` metadata.

4. **`web/`**:
   - **Multi-Engine Spectator Frontend**: Offers an instant 1-click switcher between three distinct visualizer engines:
     1. **Cartoon Tower Defense View (`td_visualizer.js`, DEFAULT)**:
        - Modeled after classic 2D cartoon tower defense games (*Kingdom Rush* / *Tower Defender*).
        - Renders winding sandy dirt paths cutting across vibrant grass meadows with procedural trees, rocks, fences, and tribal huts.
        - Castles & Towers: Illustrated stone fortresses with blue/red conical roofs (Nodes 0 & 14), round stone guard towers with flags (Chokepoints 5, 6, 8, 9), fortified stone barracks (Refineries 1–4, 10–13), and the ancient mystical Relic Shrine (Node 7).
        - Animated Soldier Sprites: Knights with tower shields (Guards), running hooded Rogues with dual daggers (Raiders), wheeled iron Cannons (Siege), and flying Eagles with wing-flaps (Scouts). Every unit in a squad is drawn individually in tactical formation along the road with directional facing (`scale(-1, 1)` when moving leftwards), walking stride bobs, ground shadows, and minimal sleek squad tags (`P1 · 5⚔️`).
        - Garrison Defenders & Animated Battle Duels: Stationed soldier sprites stand guard directly at castle gates and battlements (`[ 🛡️2  💣1 ]`). When battles occur, dynamic 2-soldier animated duels trigger at castle gates with sword lunges, shield blocks, explosive clash stars (`💥`), slash trails, and flying sparks.
        - Interactive Pan & Zoom: Mouse wheel zoom centered on cursor (0.75x–3.0x), drag-to-pan, and on-screen zoom control overlay (`+`, `−`, `⟲`, percentage badge).
        - High-Visibility Battle Alerts: Animated crossed-swords badges (`⚔️ BATTLE! ⚔️`), expanding shockwave rings, floating combat casualties, and banner notifications.
        - Dynamic Cartoon Fog of War: Nighttime/twilight shroud parting with warm lantern light radii around castles and scouting eagles.
     2. **3D Isometric Arena (`three_visualizer.js`)**:
        - Three.js WebGL pipeline with procedural 3D citadels, animated squads, OrbitControls, and cinematic camera presets.
     3. **2D Tactical Canvas (`visualizer.js`)**:
        - High-contrast, minimalist esports node graph.
   - `visualizer.js`: Master orchestrator coordinating data fetching, match playback, scrubber scrubbing, Bot Lab, Tournament Matrix, and synchronizing frame state across all three render engines.
   - Match Control Center: 1v1 Arena match launcher supporting custom scripts in `bots/` with live discovery, interactive Tournament Matrix evaluator, Custom Bot Lab for live browser-based Python bot code compilation/inspection, and saved Replay Vault.
   - `serve.py`: HTTP server with endpoints (`/api/replays`, `/api/replay/<id>`, `/api/run-match`, `/api/run-tournament`, `/api/bots`, `/api/bot-source/<file>`) with automated `sys.path` resolution. Supported via root `serve.py` alias.

