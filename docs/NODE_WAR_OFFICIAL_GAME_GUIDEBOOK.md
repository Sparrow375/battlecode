# NODE WAR // Official Competitor Guidebook
**Autonomous AI Tournament & Hackathon Manual**  
*Document Version: 3.3 — Official Participant Release*

---

## 1. Executive Summary & Objective

Welcome to **Node War**, a simultaneous turn-based strategic simulation game fought between two autonomous AI agents on a balanced, mirrored graph of 15 nodes.

As a competitor, your task is to write a single Python bot script (`class MyBot(BotBase)`) that controls an expanding empire. Every turn, your bot receives a sensory observation through the fog of war, manages an economy of Gold (🪙), maintains dynamic supply lines, trains rock-paper-scissors military forces, and commands fleets to conquer nodes and capture the mystical **Relic Sanctuary**.

### The Core Objective
Out-maneuver and eliminate the opponent, or hold the territory and the central Relic to secure the highest score by **Turn 120**. There are strictly **no draws**; a composite tiebreaker guarantees a deterministic winner.

---

## 2. Quick-Start Guide for Competitors

### Step 1: Locate Your Starter Bot Template
In your participant package, inspect **`bots/starter_bot.py`**. You can copy this file to create your own bot:
```bash
cp bots/starter_bot.py bots/my_bot.py
```

### Step 2: Test Locally with the Validator
Before submitting, always test your bot with the standalone dry-run validator:
```bash
python validate_bot.py bots/my_bot.py
```
This tests your class instantiation for Player 1, Player 2, and late-game Relic charging observations, ensuring your orders strictly conform to tournament specifications.

### Step 3: Submission Format
Your final submission is a single, self-contained Python file (e.g. `team_name_bot.py`) that implements your bot class inheriting from `BotBase`.

---

## 3. Battlefield Geography & Mirrored Topology

The arena consists of **15 strategic nodes** connected by travel lanes. The graph is bilaterally symmetrical across the vertical center line, ensuring Player 1 and Player 2 have identical path distances to all contested objectives.

```
       [Node 4: North Rig] --------------------------- [Node 10: Apex Rig]
             |     \                                         /     |
             |      \                                       /      |
       [Node 1: Alpha] --- [Node 5: North] --- [Node 9: Zenith] --- [Node 13: Epsilon]
          /     \               /     \               /     \
         /       \             /       \             /       \
[P1 Core: 0] --- [Node 3: Gate] --- [Node 7: Relic] --- [Node 11: Gate] --- [P2 Core: 14]
         \       /             \       /             \       /
          \     /               \     /               \     /
       [Node 2: Gamma] --- [Node 6: South] --- [Node 8: Titan] --- [Node 12: Omega]
```

### Node Directory & Resource Yields

| Node ID | Node Designation | Position (X, Y) | Initial Owner | Yield (Gold/Turn) | Defense Bonus | Neutral Garrison |
|:---:|:---|:---:|:---:|:---:|:---:|:---|
| **0** | **Player 1 Core Citadel** | (10.0, 50.0) | Player 1 | **+15 🪙** | **+50%** | 1 Raider, 1 Guard, 1 Scout |
| **1** | Alpha Bastion | (25.0, 25.0) | Neutral | **+4 🪙** | +25% | 1 Raider |
| **2** | Gamma Bastion | (25.0, 75.0) | Neutral | **+4 🪙** | +25% | 1 Raider |
| **3** | Vanguard Chokepoint Gate | (32.0, 50.0) | Neutral | **+7 🪙** | +25% | 2 Guards |
| **4** | North Rig | (40.0, 15.0) | Neutral | **+4 🪙** | +25% | 1 Raider |
| **5** | North Outpost | (45.0, 35.0) | Neutral | **+7 🪙** | +25% | 2 Guards |
| **6** | South Outpost | (45.0, 65.0) | Neutral | **+7 🪙** | +25% | 2 Guards |
| **7** | **Relic Sanctuary** | (50.0, 50.0) | Neutral | **+10 🪙** | +25% | 2 Guards, 1 Siege |
| **8** | Titan Outpost | (55.0, 65.0) | Neutral | **+7 🪙** | +25% | 2 Guards |
| **9** | Zenith Outpost | (55.0, 35.0) | Neutral | **+7 🪙** | +25% | 2 Guards |
| **10** | Apex Rig | (60.0, 15.0) | Neutral | **+4 🪙** | +25% | 1 Raider |
| **11** | Sentinel Chokepoint Gate | (68.0, 50.0) | Neutral | **+7 🪙** | +25% | 2 Guards |
| **12** | Omega Bastion | (75.0, 75.0) | Neutral | **+4 🪙** | +25% | 1 Raider |
| **13** | Epsilon Bastion | (75.0, 25.0) | Neutral | **+4 🪙** | +25% | 1 Raider |
| **14** | **Player 2 Core Citadel** | (90.0, 50.0) | Player 2 | **+15 🪙** | **+50%** | 1 Raider, 1 Guard, 1 Scout |

### Lanes & Travel Times
- **Standard Lanes**: Transit between adjacent bastions and outposts takes **2 turns**.
- **Chokepoint Bridges & Flanks**: Long lanes (such as 0 to 3, 3 to 7, 11 to 7, 14 to 11, and 4 to 10) take **3 turns**.
- Both players have equal 6-turn travel routes from Home Core to the central Relic (e.g. 0 to 3 to 7 vs 14 to 11 to 7).

---

## 4. Economy, Gold & Dynamic Supply Lines

### Starting Treasury
Both players start Turn 1 with **30 Gold** (accessed via `obs.my_credits` in the bot API).

### Turn Income
At the start of every turn, players collect Gold from every node they currently own:
- **Core Citadels (0, 14)**: +15 Gold/turn
- **Relic Sanctuary (7)**: +10 Gold/turn
- **Chokepoint Gates & Outposts (3, 5, 6, 8, 9, 11)**: +7 Gold/turn
- **Outer Bastions & Refineries (1, 2, 4, 10, 12, 13)**: +4 Gold/turn

### Dynamic Empire Supply Lines (Upkeep)
To prevent runaway troop snowballing, maintaining a massive military requires dynamic territorial upkeep:

**Free Supply Capacity = 10 + (4 × Owned Nodes)**

- **Domestic Forces**: Units stationed on friendly owned nodes that exceed your free capacity cost **1 Gold/turn** per unit.
- **Expeditionary Forces (Overextension Tax)**: Units stationed on unowned/enemy nodes or traveling along lanes cost **2 Gold/turn** per unit over capacity.
- Free capacity automatically covers your domestic defenders first before covering expeditionary units.

---

## 5. Units & Rock-Paper-Scissors Combat

Units clash using a deterministic Lanchester attrition model with a 2.0x counter-damage multiplier:

```
               RAIDER (10 Gold)
              /                \
     2.0x vs /                  \ 0.5x vs
            v                    v
    SIEGE (18 Gold) <------- GUARD (12 Gold)
                    2.0x vs
```

### Complete Unit Roster

| Unit Type | Gold Cost | Max HP | Base ATK | Counter Bonus (2.0x Damage) | Vulnerable To (0.5x Damage) | Tactical Role |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **Raider** | 10 🪙 | 20 | 12 | **Siege** (2.0x) | Guard (0.5x) | Fast shock raider, cheap swarm, siege destroyer |
| **Siege** | 18 🪙 | 35 | 22 | **Guard** (2.0x) | Raider (0.5x) | Heavy artillery, high HP anchor, guard crusher |
| **Guard** | 12 🪙 | 30 | 14 | **Raider** (2.0x) | Siege (0.5x) | Armored infantry, wall anchor, raider shredder |
| **Scout** | 6 🪙 | 10 | 0 | None (Non-combat) | All Units | Pierces fog, +15% targeting bonus, capture freezer |

### Combat Resolution Rules
1. **Targeting Priority**: Combat units prioritize firing on the unit types they counter, dealing **2.0x damage**.
2. **Stationary Defense Bonuses**:
   - **Home Core Citadels (0, 14)**: Defenders gain a **+50% Defense Bonus** (halving incoming damage).
   - **Outposts & Bastions (1–13)**: Defenders gain a **+25% Defense Bonus**.
3. **Meeting Engagements**: When opposing forces arrive at a neutral node on the same turn, combat resolves as an open meeting engagement with **0% defense bonus** for both sides.

---

## 6. Reconnaissance, Fog-of-War & Scout Utilities

The tournament engine enforces strict information fog:
- **Owned Territory**: Fully visible garrisons.
- **Adjacent Node Radars**: You can see unit counts on nodes directly connected to nodes you own.
- **Deep Unowned Nodes**: Obscured by fog; `node.units` is returned as `None`.
- **Traveling Fleets (Radar Silhouettes)**: You can see all enemy fleets on lanes (`origin_node`, `dest_node`, `turns_remaining`, `total_count`).
- **Hidden Unit Compositions**: The specific unit breakdown (`fleet.units`) is hidden (`None`) unless you have positioned a **Scout** along the flight path.

### Scout Combat Targeting & Capture Freeze
- **+15% Targeting Bonus**: Having a friendly Scout present or stationed adjacent to a battle grants your units a +15% damage bonus.
- **-15% Blind Penalty**: Fighting an enemy army that has a Scout while you have none inflicts a -15% blind targeting penalty on your units.
- **Capture Lock**: If an enemy attempts to capture a node, sending or stationing a Scout at that node freezes the capture progress counter!

---

## 7. Node Occupation & The 2-Turn Flip Mechanic

Capturing a node requires **2 consecutive turns of uncontested occupation**:

1. **Clear Defenders**: Neutral or enemy garrison is eliminated; invading units occupy the node.
2. **Contested State (Turn 1)**: Node enters contested status (`node.capture_progress = 1`).
   - Ownership has **not** flipped yet.
   - Recruitment at this node is **locked** (`capturing_player != 0`).
   - If the original owner sends a relief fleet that arrives on the next turn, combat begins and the capture clock is halted.
3. **Ownership Flip (Turn 2)**: If occupation remains uncontested for a second consecutive turn, ownership formally flips to the invader and resource production begins under the new banner.

---

## 8. Dynamic Relic Sanctuary (Turns 80 to 100)

The mystical **Relic Sanctuary (Node 7)** awakens dynamically in the late game:

- **Random Activation Window**: Awakens dynamically between **Turn 80 and Turn 100**.
- **5-Turn Advance Warning**: Exactly 5 turns before activation, the engine broadcasts `obs.relic_charging = True`.
- **Relic Harvest**: Controlling Node 7 grants **+10 Bonus Victory Points per turn**.
- **Territorial Doubler (2x Multiplier)**: Once active (`obs.relic_active = True`), every owned node on the map produces **2 Victory Points per turn** instead of 1.

---

## 9. Match Lifecycle & Strict Deterministic Tiebreaker

Matches last up to **120 turns**. A match terminates upon:
1. **Total Elimination**: A player loses all nodes and has zero active or traveling units.
2. **Turn 120 Limit**: If both players survive to Turn 120, a deterministic composite tiebreak score is calculated:

**Tiebreak Score = (Victory Points × 100,000) + (Relic Turns Held × 1,000) + (Total Army Value × 10) + Banked Gold**

Because this formula incorporates cumulative points, relic possession duration, total military asset value in Gold, and unspent treasury reserves, it is mathematically unique. **There are strictly no draws.**

---

## 10. Competitor Bot API & Order Protocol

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
        my_nodes = self.get_my_nodes(obs)
        if not my_nodes:
            return orders

        # 1. Training Order Example (recruit 1 Raider at home base)
        if obs.my_credits >= 10:
            orders.append(self.train(self.home_id, UnitType.RAIDER, 1))

        # 2. Movement Order Example (dispatch 2 Raiders along shortest path)
        orders.append(self.move(self.home_id, 1, {UnitType.RAIDER: 2}))

        return orders
```

### Observation Schema Reference (`BotObservation`)

- `obs.current_turn`: Current integer turn (1 to 120).
- `obs.max_turns`: Maximum match turns (120).
- `obs.my_player_id`: Your faction ID (1 or 2).
- `obs.my_credits`: Your current spendable Gold reserve.
- `obs.my_score`: Your current accumulated victory points.
- `obs.opponent_score`: Opponent's accumulated victory points.
- `obs.relic_charging`: Boolean 5-turn warning alert before Relic awakens.
- `obs.relic_active`: Boolean flag indicating if Relic is active.
- `obs.relic_node_id`: Node ID of the Relic Sanctuary (7).
- `obs.nodes`: Dict mapping Node ID (0 to 14) to `VisibleNode`.
  - `node.id`: Integer ID (0 to 14).
  - `node.owner`: Owner ID (1 for P1, 2 for P2, 0 for Neutral).
  - `node.production`: Gold generated per turn (4, 7, 10, or 15).
  - `node.defense_bonus`: Stationary damage reduction (0.50 at home, 0.25 at outposts).
  - `node.capture_progress`: Turns captured (0, 1, or 2).
  - `node.capturing_player`: ID of capturing faction (0 if uncontested).
  - `node.units`: Dict of units `{"raider": int, "guard": int, ...}` if scouted, or `None` if obscured.
- `obs.lanes`: List of travel lane dicts (`node_a`, `node_b`, `travel_turns`).
- `obs.my_fleets`: List of friendly `VisibleFleet` objects.
- `obs.enemy_fleets`: List of enemy `VisibleFleet` objects (radar silhouettes; unit compositions masked unless scouted).

### Built-in Helper Methods on `BotBase`

- `self.get_my_nodes(obs) -> List[VisibleNode]`: Returns all nodes currently owned by you.
- `self.get_enemy_nodes(obs) -> List[VisibleNode]`: Returns nodes owned by your opponent.
- `self.get_neutral_nodes(obs) -> List[VisibleNode]`: Returns unowned neutral nodes.
- `self.get_distance(obs, u, v) -> int`: Returns shortest travel turns between nodes u and v.
- `self.get_path(obs, u, v) -> List[int]`: Returns sequence of node IDs along shortest route (e.g. `[0, 1, 5, 7]`).
- `self.get_neighbors(obs, node_id) -> List[int]`: Returns adjacent connected node IDs.
- `self.train(node_id, unit_type, count) -> TrainOrder`: Creates a validated train command.
- `self.move(origin, dest, units) -> MoveOrder`: Creates a validated fleet move command.

---

## 11. Rules of Engagement & Execution Constraints

1. **50 Millisecond Time Limit**: Your bot must return orders within **50 milliseconds** per turn. Compute timeouts will forfeit orders for that turn.
2. **Pure Standard Library**: Submissions must use standard Python 3. Subprocesses, network sockets, thread pools, or disk modifications are strictly forbidden and will result in disqualification.
3. **Persistent Memory**: You may store cross-turn strategic state on `self` (e.g. enemy sightings, build orders). Memory persists throughout an individual match.
4. **Order Validity**: Orders attempting to move units that do not exist at a node or training units without sufficient Gold will be safely ignored by the engine.
5. **No Draws**: Every match terminates with an unambiguous winner.

---

## 12. Debugging & Common Pitfalls

- **Path Index Bounds**: `self.get_path(obs, u, v)` returns `[u, next_node, ..., v]`. Always check `if len(path) >= 2:` before accessing `path[1]`.
- **Recruitment Lockout**: You cannot train units at a node while it is actively being contested (`node.capturing_player != 0`).
- **Moving from Unowned Nodes**: Units can only launch fleets from nodes you currently own. Wait for the 2-turn capture progress to flip before moving out!
- **Local Budget Tracking**: Always deduct Gold locally as you generate `TrainOrder`s within `act(obs)` to ensure you don't over-commit your reserves.
