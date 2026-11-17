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
   - `models.py`: Data classes for Nodes, Lanes, Fleets, Combat, Upkeep, Relic, and Orders. Tracks `resident_player` to distinguish stationed garrison troops from original node ownership during multi-turn captures.
   - `map.py`: Symmetrical mirrored graph generator (15 nodes, balanced paths, central relic node at Node 7).
   - `combat.py`: Deterministic RPS combat resolution with defender advantage (+25%) and Lanchester-style simultaneous damage.
   - `game.py`: Main state machine executing turn phases:
     1. Resource Production (disabled for contested nodes under active capture)
     2. Upkeep Deduction (1 credit/unit over free cap of 30)
     3. Order Validation & Fleet Launch (recruitment suspended at contested nodes)
     4. Fleet Movement & Lane Transit
     5. Scouting & Vision Resolution
     6. Combat Resolution at Nodes
     7. Two-Turn Node Capture Progress (uncontested turns required to flip ownership)
     8. Relic Spawning (Turns $\ge 95$) & Point Accumulation (+15 pts/turn + 2x multiplier)
     9. Victory / Tiebreak Check (unambiguous composite score)
   - `fog.py`: Strips hidden fleet compositions from opponent observation while preserving omniscient state for spectator replays.

2. **`bots/`**:
   - `base.py`: Competitor bot interface (`act(obs) -> list[Order]`), serialization, helper navigation utilities.
   - `rusher.py`: Aggressive Raider swarm targeting adjacent economy nodes early.
   - `turtle.py`: Heavy Guard defense, chokepoint consolidation, tech/economy buildup.
   - `balanced.py`: Recon-first strategy deploying scouts, reading enemy fleets, and recruiting counter-units (Siege against Guards, Guards against Raiders, Raiders against Siege).
   - Custom scripts (e.g. `bot1.py`, student submissions): Dynamically discovered and loaded by filename.

3. **`runner/`**:
   - `match.py`: Head-to-head match executor, per-turn time limits, exception isolation. Features `load_bot_from_file`, `discover_custom_bots`, and `resolve_bot` for loading custom scripts in `bots/`.
   - `tournament.py`: Automated round-robin matrix testing win-rates to verify RPS balance cycle.
   - `replay.py`: Compact, structured JSON replay serialization.

4. **`web/`**:
   - **Multi-Engine Spectator Frontend**: Offers an instant 1-click switcher between three distinct visualizer engines:
     1. **Cartoon Tower Defense View (`td_visualizer.js`, DEFAULT)**:
        - Modeled after classic 2D cartoon tower defense games (*Kingdom Rush* / *Tower Defender*).
        - Renders winding sandy dirt paths cutting across vibrant grass meadows with procedural trees, rocks, fences, and tribal huts.
        - Castles & Towers: Illustrated stone fortresses with blue/red conical roofs (Nodes 0 & 14), round stone guard towers with flags (Chokepoints 5, 6, 8, 9), fortified stone barracks (Refineries 1–4, 10–13), and the ancient mystical Relic Shrine (Node 7).
        - Animated Soldier Sprites: Knights with tower shields (Guards), running hooded Rogues with dual daggers (Raiders), wheeled iron Cannons (Siege), and flying Eagles with wing-flaps (Scouts). Every unit in a squad is drawn individually in tactical formation along the road with directional march chevrons (`>>`).
        - Garrison Defenders: Stationed soldier sprites stand guard directly at castle gates and battlements, accompanied by a clean troop breakdown strip (`🛡️x3 🗡️x2 💣x1`).
        - High-Visibility Battle Alerts: Animated crossed-swords badges (`⚔️ BATTLE! ⚔️`), expanding shockwave rings, floating combat casualties, and banner notifications.
        - Dynamic Cartoon Fog of War: Nighttime/twilight shroud parting with warm lantern light radii around castles and scouting eagles.
     2. **3D Isometric Arena (`three_visualizer.js`)**:
        - Three.js WebGL pipeline with procedural 3D citadels, animated squads, OrbitControls, and cinematic camera presets.
     3. **2D Tactical Canvas (`visualizer.js`)**:
        - High-contrast, minimalist esports node graph.
   - `visualizer.js`: Master orchestrator coordinating data fetching, match playback, scrubber scrubbing, Bot Lab, Tournament Matrix, and synchronizing frame state across all three render engines.
   - Match Control Center: 1v1 Arena match launcher supporting custom scripts in `bots/` with live discovery, interactive Tournament Matrix evaluator, Custom Bot Lab for live browser-based Python bot code compilation/inspection, and saved Replay Vault.
   - `serve.py`: HTTP server with endpoints (`/api/replays`, `/api/replay/<id>`, `/api/run-match`, `/api/run-tournament`, `/api/bots`, `/api/bot-source/<file>`) with automated `sys.path` resolution. Supported via root `serve.py` alias.

