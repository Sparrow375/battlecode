# Champions League 2026 // Frontend Architecture & Specification

## 1. Overview

The Champions League 2026 frontend (Node War Esports Arena) is an interactive, multi-engine spectator platform designed for real-time visualization and playback of competitive turn-based bot matches. The client runs entirely in modern browsers without external bundler dependencies, powered by native HTML5 Canvas, WebGL (Three.js), and vanilla ES6+ JavaScript.

---

## 2. Directory Structure (`web/`)

```
web/
├── index.html              # Main HTML markup, HUD, sidebar panels, modals, and viewport DOM
├── style.css               # Core styling, esports neon aesthetics, responsive layout & animations
├── visualizer.js           # Master orchestrator (NodeWarVisualizer), state manager, and 2D Tactical engine
├── td_visualizer.js        # 2D Cartoon Tower Defense engine (Default spectator mode)
├── three_visualizer.js     # Three.js 3D Isometric battlefield engine
├── arena_3d_art.js         # Procedural 3D model generation & materials for the 3D Arena
├── arena_themes.js         # Theme management, procedural terrain synthesis & atlas loader
├── cinematic.js            # Dynamic director camera system for Cinematic Battle view
├── victory.js              # Championship victory ceremony, audio synthesis, and trophy overlays
├── serve.py                # Python HTTP backend serving static files and simulation APIs
├── assets/
│   ├── td/                 # Vector/SVG assets for TD visualizer (buildings, units, environment)
│   └── arenas/             # Terrain, unit, and theme sprite atlases
└── vendor/
    ├── three.min.js        # Offline Three.js library (r128)
    └── OrbitControls.js    # Camera manipulation controller for 3D view
```

---

## 3. Multi-Engine Viewing Modes

The spectator viewport supports four distinct viewing modes arranged in exact operational order:

| Order | Viewing Mode | Identifier | Implementation | Description |
|:---:|---|:---:|---|---|
| **1** | **Tower Defense** *(Default)* | `td` | `td_visualizer.js` | High-readability 2D illustrated presentation with animated unit squads, road networks, and castle nodes. |
| **2** | **3D Arena** | `3d` | `three_visualizer.js` | Full Three.js WebGL isometric view with procedural towers, glowing fleets, hover tooltips, and dynamic camera presets. |
| **3** | **2D Tactical** | `2d` | `visualizer.js` | Ultra-clean schematic coordinate grid optimized for low-latency analysis and tactical oversight. |
| **4** | **Cinematic Battle** | `cinematic` | `cinematic.js` | Automated director perspective with smooth target tracking, action-cam zoom, and battle event focus. |

### Engine Mode Orchestration (`visualizer.js`)
* **State Switching**: Managed via `setEngineMode(mode)`. Switches DOM visibility between `#td-canvas`, `#three-container`, and `#game-canvas`.
* **Graceful Fallbacks**: If WebGL encounters context loss or initialization failures, the system invokes `graphicsFallback()`, alerting the user and smoothly falling back to the 2D Tower Defense view without disrupting match progress.

---

## 4. Arena Themes & Visual Environments (`arena_themes.js`)

The arena supports five visual environments, dynamically applied across all viewing modes:

1. **Medieval Conquest** (`medieval`)
   * Classic verdant meadow and dirt pathways with rustic fortifications and stone watchtowers.
2. **Cyber Warfare** (`cyber`)
   * High-contrast dark cybergrid with cyan/magenta neon traces, glowing circuit traces, and digital overlays.
3. **Galactic Dominion** (`galactic`)
   * Premium deep-space environment with dark navy and black background tones, subtle violet nebula clouds, restrained star density, and minimalist orbital rings to keep combat nodes as the focal point.
4. **Wasteland Survival** (`wasteland`)
   * Muted desert landscape featuring cracked earth textures, dusty amber lighting, worn sand path tracks, and strategic industrial ruins without visual clutter.
5. **The Ultimate Arena** (`championship`)
   * Grand esports colosseum featuring championship laurels, gold-trimmed borders, and dual team spotlights.

---

## 5. UI Layout & Component Breakdown

```
+---------------------------------------------------------------------------------------+
| TOP SCOREBOARD & ESPORTS HUD                                                         |
| [P1 HUD: Credits/Score]       [Turn Counter / Relic State / FOW]       [P2 HUD]       |
+---------------------+-------------------------------------------+---------------------+
| LEFT PANEL          | CENTER VIEWPORT                           | RIGHT PANEL         |
| 1. Tabs:            | - Top Bar: Mode Buttons, Theme, Quick Nav | - Node Inspector:   |
|    - 1v1 Arena      | - Battlefield Stage:                      |   Telemetry, Owner, |
|    - Matrix         |   * td-canvas (TD View)                   |   Garrison Counts   |
|    - Bot Lab        |   * three-container (3D View)             | - Live Battle Feed: |
|    - Replay Vault   |   * game-canvas (2D View)                 |   Combat events &   |
| 2. Match Setup      | - Overlays: Camera Bar, Zoom, Victory HUD |   Node captures     |
| 3. Combat Triangle  +-------------------------------------------+                     |
| 4. Championship     | BOTTOM PLAYBACK CONTROLS                                        |
|    Spectator        | [<<] [ > / || ] [>>] [Timeline Scrubber] [Speed: 0.5x - Max]    |
+---------------------+-----------------------------------------------------------------+
```

### 5.1. Navigation & Setup Sidebar (Left)
* **1v1 Arena Tab**:
  * Bot selectors for Player 1 (Cyan) and Player 2 (Crimson).
  * Match configuration presets: Standard (120T), Blitz (60T), Marathon (160T), and Custom.
  * **Combat Triangle Guide**: Interactive RPS cheatsheet (Raider > Siege > Guard > Raider).
  * **Championship Final Display**: Official pairing and status badge.
  * **Championship Spectator Settings**: Audio, celebration quality, winner commentary, and language toggles.
* **Balance Matrix Tab**: Automated round-robin match runner verifying strategy cycles.
* **Bot Lab Tab**: In-browser code editor for prototyping Python bots directly in the UI.
* **Replay Vault Tab**: Archive of historical match replays loadable with one click.

### 5.2. Viewport & Camera Stage (Center)
* **Engine Mode Toggle**: One-click switching (`Tower Defense` -> `3D Arena` -> `2D Tactical` -> `Cinematic Battle`).
* **Quick Navigation Buttons**: Jump immediately to Relic Activation, Next Battle, or Match Finish.
* **Interactive Controls**:
  * Pan and drag controls on 2D and TD canvases.
  * Orbit controls (rotate, pan, zoom) on 3D canvas.
  * Preset camera angles: Isometric, P1 Citadel, Relic Sanctuary, P2 Citadel, and Reset.

### 5.3. Telemetry & Analytics Sidebar (Right)
* **Node Inspector**: Displays hovered/selected node ownership, defense bonuses, income yield, capture progress, and detailed garrison breakdown.
* **Live Battle Feed**: Real-time event log with color-coded alerts for clashes, flips, and strategic milestones.

### 5.4. Bottom Playback Controls
* **Playback Actions**: Frame step backward/forward, play/pause toggle (Spacebar shortcut), and restart.
* **Timeline Scrubber**: Turn slider with dynamic indicators for Relic phase and match duration.
* **Speed Selectors**: 0.5x (1500ms/turn), 1x (1000ms/turn), 2x (500ms/turn), 4x (250ms/turn), and Max (50ms/turn).

---

## 6. Victory Ceremony & Commentary (`victory.js`)

When a championship match finishes or official celebration is triggered:
* **Audio Fanfare**: Synthesized brass chimes using Web Audio API oscillators.
* **Speech Synthesis**: Integrated text-to-speech commentary announcing winning teams, universities, and scores in English (`en-IN`) or Hindi (`hi-IN`).
* **Celebration FX**: Canvas-based 2D confetti cannons, 3D golden particle fireworks, and animated tournament laurel overlays.

---

## 7. Backend Integration Endpoints (`web/serve.py`)

The frontend communicates with the local simulation server via REST JSON APIs:

| Endpoint | Method | Description |
|---|:---:|---|
| `/api/bots` | `GET` | Returns available built-in bots and custom scripts located in `bots/`. |
| `/api/bot-source/<filename>` | `GET` | Fetches raw Python code of a bot script for the code editor. |
| `/api/run-match` | `POST` | Simulates a 1v1 match and returns full replay frame telemetry. |
| `/api/run-tournament` | `POST` | Executes multi-round balance evaluation across baseline bots. |
| `/api/replays` | `GET` | Lists all saved JSON replays in `replays/`. |
| `/api/replay/<filename>` | `GET` | Downloads specific replay frames and metadata for playback. |

---

## 8. Development & Quick Start

To launch the web frontend and spectator server:
```bash
# From workspace root:
python serve.py
# Or directly from web directory:
python web/serve.py
```
Open **`http://localhost:8000`** in any modern web browser.
