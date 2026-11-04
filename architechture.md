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

    subgraph Spectator & Web UI [Interactive Visualizer]
        WebServer[Web Demo / Spectator Server]
        CanvasUI[Esports Graph & Canvas Visualizer]
        FOWToggle[Omniscient / Fog-of-War Toggle]
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
    ReplayGen --> CanvasUI
    WebServer --> CanvasUI
```

## Core Modules & Structure

1. **`engine/`**:
   - `models.py`: Data classes for Nodes, Lanes, Fleets, Combat, Upkeep, Relic, and Orders.
   - `map.py`: Symmetrical mirrored graph generator (~15 nodes, balanced paths, central relic node).
   - `combat.py`: Deterministic RPS combat resolution with defender advantage and Lanchester-style attrition.
   - `game.py`: Main state machine executing turn phases:
     1. Resource Production
     2. Upkeep Deduction
     3. Fleet Movement & ETA
     4. Scouting & Vision Resolution
     5. Combat Resolution at Nodes & Lane Collisions
     6. Two-Turn Node Capture Progress
     7. Relic Spawning (Turns $\ge T - 25$) & Point Accumulation
     8. Victory / Tiebreak Check
   - `fog.py`: Strips hidden fleet compositions from opponent observation while preserving omniscient state for spectator replays.

2. **`bots/`**:
   - `base.py`: Competitor bot interface (`act(obs) -> list[Order]`), serialization, helper navigation utilities.
   - `rusher.py`: Aggressive Raider swarm targeting adjacent economy nodes early.
   - `turtle.py`: Heavy Guard defense, chokepoint consolidation, tech/economy buildup.
   - `balanced.py`: Recon-first strategy deploying scouts, reading enemy fleets, and recruiting counter-units (Siege against Guards, Guards against Raiders, Raiders against Siege).

3. **`runner/`**:
   - `match.py`: Head-to-head match executor, per-turn time limits, exception isolation.
   - `tournament.py`: Automated round-robin matrix testing win-rates to verify RPS balance cycle.
   - `replay.py`: Compact, structured JSON replay serialization.

4. **`web/`**:
   - Web-based spectator frontend displaying interactive nodes, glowing lanes, traveling fleet badges, combat clash animations, spectator vs player view toggle, timeline scrubber, and real-time scoreboard.
