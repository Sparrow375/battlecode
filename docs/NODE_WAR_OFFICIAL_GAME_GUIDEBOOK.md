# NODE WAR // Official Tournament Guidebook & Competitor Manual
**College Hackathon & AI Tournament Edition**  
*Document Version: 3.2 — Final Production Release*

---

## Executive Summary & Quick-Start

Welcome to **Node War**, a simultaneous turn-based strategy simulation game designed for autonomous AI agents competing head-to-head on a balanced, mirrored graph of 15 nodes.

Your mission is to script an intelligent Python agent (`class CompetitorBot(BotBase)`) that manages an expanding empire: surveying unknown territory through fog of war, harvesting resources, managing dynamic supply lines, training specialized rock-paper-scissors armies, and executing decisive timing attacks on the late-game **Relic Sanctuary**.

### 5-Minute Setup & Quick-Start Guide
1. **Repository Setup**:
   Your workspace includes the complete tournament engine, spectator arena, dry-run validator, and starter kit.
2. **Starter Template**:
   Inspect `bots/starter_bot.py`. Copy it or use it as the foundation for your submission:
   ```bash
   cp bots/starter_bot.py bots/my_bot.py
   ```
3. **Dry-Run Validation**:
   Verify your bot structure, inheritance, and observation typing before running matches:
   ```bash
   python validate_bot.py bots/my_bot.py
   ```
4. **Local 1v1 Match Testing**:
   Simulate a head-to-head match against the baseline bots directly in the CLI:
   ```bash
   python -m runner.match --p1 my_bot.py --p2 rusher --turns 120
   ```
5. **Interactive Spectator Arena**:
   Launch the web spectator arena to watch match replays with animated soldier units, combat clashing FX, and live scrubbing:
   ```bash
   python serve.py
   ```
   Open `http://localhost:8000` in your browser.

---

## 1. Battlefield Geography & Mirrored Topology

The battlefield consists of **15 discrete strategic nodes** connected by travel lanes. The graph is mathematically symmetrical across the vertical axis $X = 50.0$, ensuring absolute parity between Player 1 and Player 2.

```
       [Node 4: North Rig] ---------------------------------- [Node 10: Apex Rig]
             |     \                                                /     |
             |      \                                              /      |
       [Node 1: Alpha Bastion] --- [Node 5: North Outpost] -- [Node 9: Zenith] --- [Node 13: Epsilon]
          /     \                      /            \                      /     \
         /       \                    /              \                    /       \
[P1 Core: 0] --- [Node 3: Vanguard] ----- [Node 7: Relic] ----- [Node 11: Sentinel] --- [P2 Core: 14]
         \       /                    \              /                    \       /
          \     /                      \            /                      \     /
       [Node 2: Gamma Bastion] --- [Node 6: South Outpost] -- [Node 8: Titan] --- [Node 12: Omega]
```

### Complete Node Directory & Yield Classification

| Node ID | Strategic Designation | Coordinates $(X, Y)$ | Default Owner | Production (Gold/Turn) | Defense Bonus | Initial Garrison |
|:---:|:---|:---:|:---:|:---:|:---:|:---|
| **0** | **Player 1 Core Citadel** | $(10.0, 50.0)$ | Player 1 | **+15 🪙** | **+50%** | 1 Raider, 1 Guard, 1 Scout |
| **1** | Alpha Bastion | $(25.0, 25.0)$ | Neutral | **+4 🪙** | +25% | 1 Raider (Neutral) |
| **2** | Gamma Bastion | $(25.0, 75.0)$ | Neutral | **+4 🪙** | +25% | 1 Raider (Neutral) |
| **3** | Vanguard Chokepoint Gate | $(32.0, 50.0)$ | Neutral | **+7 🪙** | +25% | 2 Guards (Neutral) |
| **4** | North Rig | $(40.0, 15.0)$ | Neutral | **+4 🪙** | +25% | 1 Raider (Neutral) |
| **5** | North Outpost | $(45.0, 35.0)$ | Neutral | **+7 🪙** | +25% | 2 Guards (Neutral) |
| **6** | South Outpost | $(45.0, 65.0)$ | Neutral | **+7 🪙** | +25% | 2 Guards (Neutral) |
| **7** | **Relic Sanctuary** | $(50.0, 50.0)$ | Neutral | **+10 🪙** | +25% | 2 Guards, 1 Siege (Neutral) |
| **8** | Titan Outpost | $(55.0, 65.0)$ | Neutral | **+7 🪙** | +25% | 2 Guards (Neutral) |
| **9** | Zenith Outpost | $(55.0, 35.0)$ | Neutral | **+7 🪙** | +25% | 2 Guards (Neutral) |
| **10** | Apex Rig | $(60.0, 15.0)$ | Neutral | **+4 🪙** | +25% | 1 Raider (Neutral) |
| **11** | Sentinel Chokepoint Gate | $(68.0, 50.0)$ | Neutral | **+7 🪙** | +25% | 2 Guards (Neutral) |
| **12** | Omega Bastion | $(75.0, 75.0)$ | Neutral | **+4 🪙** | +25% | 1 Raider (Neutral) |
| **13** | Epsilon Bastion | $(75.0, 25.0)$ | Neutral | **+4 🪙** | +25% | 1 Raider (Neutral) |
| **14** | **Player 2 Core Citadel** | $(90.0, 50.0)$ | Player 2 | **+15 🪙** | **+50%** | 1 Raider, 1 Guard, 1 Scout |

### Lanes & Travel Latencies
- Adjacent bastions and outposts require **2 turns** of lane travel.
- Central gateway bridges ($0 \leftrightarrow 3$, $3 \leftrightarrow 7$, $11 \leftrightarrow 7$, $14 \leftrightarrow 11$) and high flanks ($4 \leftrightarrow 10$) require **3 turns** of travel.
- Path lengths from Node 0 to Relic Node 7 equal exactly 6 turns along both the central artery ($0 \rightarrow 3 \rightarrow 7$) and flank corridors ($0 \rightarrow 1 \rightarrow 5 \rightarrow 7$).

---

## 2. Economy, Production & Empire Supply Lines

### Starting Capital
Both players begin Turn 1 with **30 Gold** (represented by `obs.my_credits` in the Python API).

### Turn Income Phase
At the start of every turn, players receive Gold equal to the sum of production values of all nodes they own:
$$\text{Income}_p = \sum_{n \in \text{Owned}_p} \text{Production}(n)$$
- **Home Citadels (0, 14)**: +15 Gold/turn
- **Relic Sanctuary (7)**: +10 Gold/turn
- **Contested Chokepoint Outposts (3, 5, 6, 8, 9, 11)**: +7 Gold/turn
- **Outer Bastions & Rigs (1, 2, 4, 10, 12, 13)**: +4 Gold/turn

### Dynamic Empire Supply Lines (Upkeep)
Rather than a fixed troop ceiling, army capacity scales dynamically with territorial expansion:
$$\text{Free Supply Cap}_p = 10 + (4 \times \text{Owned Nodes}_p)$$

- **Domestic Maintenance**: Units stationed at friendly owned nodes exceeding the supply cap cost **1 Gold/turn** per unit.
- **Expeditionary Maintenance (Supply Tax)**: Units operating on unowned/enemy nodes or traveling in transit lanes cost **2 Gold/turn** per unit over cap.
- Free capacity shields domestic defensive garrisons first before covering distant expeditionary forces.

---

## 3. Unit Roster & Lanchester Rock-Paper-Scissors Combat

```
                 RAIDER (10 Gold)
               /                  \
      2.0x vs /                    \ 0.5x vs
             v                      v
     SIEGE (18 Gold) <--------- GUARD (12 Gold)
                       2.0x vs
```

### Complete Unit Attribute Matrix

| Unit Type | Gold Cost | Max HP | Base ATK | Counter Target (2.0x Damage) | Vulnerable To (0.5x Damage) | Strategic Specialization |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **Raider** | 10 🪙 | 20 | 12 | **Siege** (2.0x) | Guard (0.5x) | Fast shock cavalry, harasser, siege destroyer |
| **Siege** | 18 🪙 | 35 | 22 | **Guard** (2.0x) | Raider (0.5x) | Heavy artillery, fortress breaker, high HP anchor |
| **Guard** | 12 🪙 | 30 | 14 | **Raider** (2.0x) | Siege (0.5x) | Armored infantry, choke point wall, raider shredder |
| **Scout** | 6 🪙 | 10 | 0 | None (Non-combat) | All Units | Pierces lane fog, +15% targeting bonus, capture freezer |

### Combat Resolution Mechanics
1. **Deterministic Resolution**: Combat resolves simultaneously across all contested nodes using Lanchester attrition equations. There is zero RNG in combat outcomes.
2. **Targeting Priority**: Squads focus incoming damage on units they counter (2.0x damage multiplier).
3. **Stationary Defense Bonuses**:
   - **Home Core Citadels (0, 14)**: Stationary defenders receive a **+50% Defense Bonus** (incoming damage halved).
   - **Outposts & Bastions (1–13)**: Stationary defenders receive a **+25% Defense Bonus**.
4. **Meeting Engagements**: When opposing fleets arrive at an unowned or neutral node on the same turn, combat resolves as an open meeting engagement (0% defender bonus for both sides).

---

## 4. Tactical Reconnaissance & The Fog-of-War System

The tournament engine enforces strict information asymmetry:

### Information Visibility Rules
- **Owned Nodes & Garrison**: Always fully visible.
- **Adjacent Node Radars**: You can inspect unit counts on nodes directly connected to any node you own.
- **Unscouted Nodes**: Deep unowned nodes obscured by fog display `node.units = None`.
- **Traveling Fleets (Radar Silhouettes)**: You always see enemy fleet trajectories (`origin_node`, `dest_node`, `turns_remaining`, and `total_count`).
- **Hidden Unit Compositions**: The specific unit breakdown of enemy fleets (`fleet.units`) is masked (`None`) unless you have positioned a **Scout** along the flight path.

### Scout Combat Targeting & Capture Freeze
- **+15% Targeting Bonus**: Having a friendly Scout present or stationed adjacent to a battle grants your combat units a +15% damage bonus.
- **-15% Blind Penalty**: Fighting an enemy army that possesses Scout reconnaissance while you have none inflicts a -15% blind targeting penalty on your units.
- **Capture Lock**: If an enemy attempts to capture a node, stationing or moving a friendly Scout to that node freezes the capture timer, preventing ownership from flipping!

---

## 5. Territorial Occupation & The 2-Turn Flip Mechanic

Nodes are not captured instantaneously. Controlling a node requires **2 consecutive turns of uncontested occupation**:

1. **Defenders Cleared**: Enemy garrison is wiped out; invading units occupy the node.
2. **Contested State (1/2)**: Node enters contested status (`node.capture_progress = 1`).
   - Ownership remains with the prior owner.
   - Recruitment at this node is **locked** (`capturing_player != 0`).
   - If the defender sends a relief force that arrives on the next turn, combat triggers and the capture is halted!
3. **Flipped Ownership (2/2)**: If occupation remains uncontested for a second consecutive turn, ownership formally flips to the invader, and production resumes under the new banner.

---

## 6. The Dynamic Relic Sanctuary (Turns 80 to 100)

To prevent hardcoded scripted timing exploits, the mystical **Relic Sanctuary (Node 7)** awakens dynamically:

- **Random Activation Window**: Node 7 awakens between **Turn 80 and Turn 100**.
- **5-Turn Advance Charging Alert**: Exactly 5 turns prior to awakening, the engine broadcasts `obs.relic_charging = True`.
- **Relic Harvest (+10 Bonus Points/Turn)**: The player controlling Node 7 receives +10 Victory Points per turn.
- **Territorial Point Doubler (2x Multiplier)**: Once active (`obs.relic_active = True`), every owned node on the map generates **2 Victory Points per turn** instead of 1.

---

## 7. Match Lifecycle, Scoring & Deterministic Tiebreakers

Matches terminate when:
1. **Total Elimination**: A player loses all nodes and has zero active or traveling units.
2. **Turn 120 Limit**: If neither player is eliminated by Turn 120, a deterministic composite tiebreak formula determines the winner:

$$\text{Tiebreak Score} = (\text{Points} \times 10^5) + (\text{Relic Turns} \times 10^3) + (\text{Total Army Value} \times 10) + \text{Banked Gold}$$

Because this incorporates cumulative victory points, duration of Relic control, total army asset value in Gold, and unspent treasury reserves, it is mathematically unique. **There are strictly no draws.**

---

## 8. Competitor Bot API & Order Protocol

Every bot inherits from `BotBase` and implements the `act(obs)` method:

```python
from __future__ import annotations
from typing import List
from engine.models import UnitType, Order, TrainOrder, MoveOrder
from engine.fog import BotObservation
from bots.base import BotBase

class CompetitorBot(BotBase):
    def __init__(self, player_id: int):
        super().__init__(player_id)
        # Store persistent bot memory across turns here
        self.home_id = 0 if self.player_id == 1 else 14

    def act(self, obs: BotObservation) -> List[Order]:
        orders: List[Order] = []
        
        # Access owned territory
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        # 1. Training Order Example
        if obs.my_credits >= 10:
            orders.append(self.train(self.home_id, UnitType.RAIDER, 1))

        # 2. Movement Order Example
        orders.append(self.move(self.home_id, 1, {UnitType.RAIDER: 1}))

        return orders
```

### Observation Schema Reference (`BotObservation`)

- `obs.current_turn`: Current integer turn ($1 \dots 120$).
- `obs.max_turns`: Maximum match turns (120).
- `obs.my_player_id`: Your player ID (`1` or `2`).
- `obs.my_credits`: Spendable Gold reserve.
- `obs.my_score`: Your accumulated victory points.
- `obs.opponent_score`: Opponent's accumulated victory points.
- `obs.relic_charging`: Boolean 5-turn warning alert before Relic awakens.
- `obs.relic_active`: Boolean flag indicating if Relic is active.
- `obs.relic_node_id`: Node ID of the Relic Sanctuary (`7`).
- `obs.nodes`: Dictionary mapping Node ID ($0 \dots 14$) to `VisibleNode`.
- `obs.lanes`: List of travel lane dicts (`node_a`, `node_b`, `travel_turns`).
- `obs.my_fleets`: List of friendly `VisibleFleet` objects.
- `obs.enemy_fleets`: List of enemy `VisibleFleet` objects (masked unless scouted).

### Built-in Helper Methods on `BotBase`

- `self.get_my_nodes(obs) -> List[VisibleNode]`: Returns nodes owned by your faction.
- `self.get_enemy_nodes(obs) -> List[VisibleNode]`: Returns nodes owned by your opponent.
- `self.get_neutral_nodes(obs) -> List[VisibleNode]`: Returns unowned neutral nodes.
- `self.get_distance(obs, u, v) -> int`: Returns travel turns between nodes $u$ and $v$.
- `self.get_path(obs, u, v) -> List[int]`: Returns sequence of node IDs along shortest route.
- `self.get_neighbors(obs, node_id) -> List[int]`: Returns connected node IDs.
- `self.train(node_id, unit_type, count) -> TrainOrder`: Factory for recruitment.
- `self.move(origin, dest, units) -> MoveOrder`: Factory for fleet movement.

---

## 9. Tournament Match Execution & Verification Tools

### Dry-Run Validator Tool
Always run the validator before submitting your bot:
```bash
python validate_bot.py bots/my_bot.py
```
This tool validates class inheritance, Player 1 / Player 2 instantiation, typing conformance, and late-game relic reaction.

### Running 1v1 Matches & Best-of-3 Series
- Standard 1v1 match:
  ```bash
  python -m runner.match --p1 my_bot.py --p2 turtle --turns 120
  ```
- Best-of-3 Series with Alternating Faction Sides:
  ```bash
  python -m runner.match --p1 my_bot.py --p2 balanced --bo3
  ```

### Evaluating Against the Canonical Balance Matrix
Benchmark your bot against the three baseline archetypes (`Rusher`, `Turtle`, `Balanced`):
```bash
python -m runner.tournament --rounds 10
```

---

## 10. Competitor Rules of Engagement & Constraints

1. **Execution Time Limit**: Bots must return orders within **50 milliseconds** per turn. Compute timeouts forfeit orders for that turn.
2. **Memory & State Persistence**: Bots may store state in `self` across turns. State persists throughout an individual match.
3. **No External Calls**: Bots must run purely in Python standard library. Subprocess execution, socket communication, file system tampering, or thread spawning are strictly prohibited.
4. **Order Validity**: Orders attempting to move units not physically stationed at a node or training units without adequate Gold are ignored.
5. **No Draws**: Every match terminates with an unambiguous winner.
