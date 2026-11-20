# NODE WAR // Official Competitor Guidebook
**Autonomous AI Tournament & Hackathon Manual**  
*Document Version: 3.6 — Official Participant Release*

---

## 1. Executive Summary: What is Node War?

**Node War** is a deterministic, turn-based strategy simulation fought on a symmetric 15-node network map:
- Two rival commanders start at opposite ends of the arena (Player 1 at Node 0 on the left, Player 2 at Node 14 on the right).
- At the center sits the **Relic Sanctuary (Node 7)**, an ancient objective that awakens dynamically in the late game.
- Each turn, both players submit orders simultaneously: managing Gold income, balancing empire supply lines, recruiting troops, dispatching fleets along travel lanes, observing movements through the fog of war, and conquering territory.
- Matches run for up to **120 turns**. There are strictly **no draws**; an exact mathematical tiebreaker guarantees a deterministic winner if both players survive to the end.

Competitors write an automated Python agent (`class CompetitorBot(BotBase)`) that inspects the game state each turn and returns valid orders.

---

## 2. Game Overview & Turn Execution Lifecycle

### Victory Conditions
1. **Total Elimination**: A player loses all owned nodes and has zero active or traveling units.
2. **Relic & Territory Point Accumulation**: Controlling territory scores Victory Points each turn. Controlling the central Relic once awakened provides significant point acceleration.
3. **Turn 120 Limit**: If neither player is eliminated by Turn 120, a deterministic composite tiebreak score evaluates Victory Points, Relic control duration, and Total Net Worth.

### The 8 Turn Phases (Executed in Exact Sequence)
Every turn proceeds through eight deterministic phases:
1. **Income Collection**: Every node you currently own deposits Gold into your treasury (+15 for Home Core, +10 for Relic, +7 for Chokepoint Outposts, +4 for Outer Bastions).
2. **Empire Upkeep & Bankruptcy Check**: Free troop capacity is determined by territory: `10 + (4 × Owned Nodes)`. Units exceeding this cap incur maintenance (1 Gold/turn for domestic garrison defenders, 2 Gold/turn for foreign units abroad or in transit). If treasury Gold is insufficient to cover upkeep, Gold is set to 0, and unpaid units immediately suffer **desertion attrition** until the deficit is cleared (foreign forces first, then domestic; in order: Raiders -> Scouts -> Guards -> Siege).
3. **Recruitment & Mobilization**: Both players submit training orders simultaneously. Newly trained units immediately join the garrison to defend that castle against attacks arriving this turn. However, newly trained units cannot march out along roads on the same turn they are trained; they become available for movement orders on subsequent turns.
4. **Troop Movements**: Both players dispatch mobilized garrison forces along travel lanes simultaneously.
5. **Lane Travel**: Fleets decrement transit timers along travel lanes. Standard lanes take **2 turns**; long bridge lanes take **3 turns**.
6. **Simultaneous Combat**: Wherever opposing forces meet at a node (or encounter neutral defenders), combat resolves deterministically.
7. **Two-Turn Capture Clock**: If all defenders at a node are eliminated, the occupying force begins capture progress. If held uncontested for **2 consecutive turns**, ownership transfers.
8. **Victory Point Scoring**: Each owned node awards 1 Victory Point (+2 points per node and +10 bonus points for Node 7 once the Relic is active).

---

## 3. Units & Combat Model

Combat operates under a deterministic rock-paper-scissors counter system where units deal **double damage (2.0x)** against their counter targets:

```
                  RAIDER (10 Gold)
                 /                \
        2.0x vs /                  \ 0.5x vs
               v                    v
       SIEGE (18 Gold) <------- GUARD (12 Gold)
                       2.0x vs
```

### Complete Unit Specifications

| Unit Type | Cost | HP | Attack | Counter Target (2.0x Damage) | Vulnerable To (0.5x Damage) | Tactical Capabilities |
|:---|:---:|:---:|:---:|:---|:---|:---|
| **Raider** | 10 🪙 | 20 | 12 | **Siege** | **Guard** | High-speed shock unit; counters artillery; low recruitment cost |
| **Guard** | 12 🪙 | 30 | 14 | **Raider** | **Siege** | Armored frontline unit; high health pool; counters raiders |
| **Siege** | 18 🪙 | 35 | 22 | **Guard** | **Raider** | Heavy artillery; high damage output; counters fortified guards |
| **Scout** | 6 🪙 | 10 | 0 | None (Non-combat) | None | Unmasks enemy fleets; +15% ally combat bonus; freezes enemy capture clock |

### Unit Properties & Capabilities

#### 1. Raider (10 Gold // 20 HP // 12 ATK)
- **Combat Multipliers**: 2.0x vs Siege, 1.0x vs Raider, 0.5x vs Guard.
- **Base Cost**: 10 Gold.

#### 2. Guard (12 Gold // 30 HP // 14 ATK)
- **Combat Multipliers**: 2.0x vs Raider, 1.0x vs Guard, 0.5x vs Siege.
- **Base Cost**: 12 Gold.

#### 3. Siege (18 Gold // 35 HP // 22 ATK)
- **Combat Multipliers**: 2.0x vs Guard, 1.0x vs Siege, 0.5x vs Raider.
- **Base Cost**: 18 Gold.

#### 4. Scout (6 Gold // 10 HP // 0 ATK)
- Non-combatant reconnaissance unit with three mechanical functions:
  1. *Fog-of-War Penetration*: Stationed at a node or traveling along connected lanes, unmasks the unit composition of passing enemy fleets.
  2. *Combat Spotter (+15% Damage)*: Armies fighting with a friendly Scout present or stationed at an adjacent connected node receive a **+15% damage bonus**. Armies fighting without a scout against an opponent who has scout coverage suffer a **-15% damage penalty**.
  3. *Capture Freeze*: If an enemy is actively occupying your node (Turn 1 of capture), a friendly Scout contesting the node freezes capture progress for that turn.

---

## 4. Core Game Mechanics & Resolution Rules

### 1. Castle Defense Bonuses & Neutral Garrisons
- **Home Core Citadels (Nodes 0 & 14)**: Stationed defenders receive a **+50% Defense Bonus** (incoming damage is reduced by 50%).
- **Outposts & Bastions (Nodes 1–13)**: Stationed defenders receive a **+25% Defense Bonus** (incoming damage is reduced by 25%).
- **Neutral Meeting Engagements**: If Player 1 and Player 2 enter an unclaimed neutral node on the same turn, they clash with **0% defense bonus** (neither side receives defender advantage). Surviving units then engage any neutral garrison defenders.
- **Neutral Garrisons on Unclaimed Nodes**:
  - Outer bastions (Nodes 1, 2, 4, 10, 12, 13): 1 Raider.
  - Chokepoints and outposts (Nodes 3, 5, 6, 8, 9, 11): 2 Guards.
  - Relic Sanctuary (Node 7): 2 Guards + 1 Siege.

### 2. The Mobilization Rule
- Units recruited on Turn T immediately join the garrison at their recruitment node and participate in defending that node against any attacks arriving on Turn T.
- Units recruited on Turn T cannot be included in a `MoveOrder` on Turn T. They must spend that turn mobilizing at the node and become available for dispatch into travel lanes on Turn T+1 or later.

### 3. Dynamic Supply Lines & Bankruptcy Desertion
- **Free Supply Capacity**:
  `Free Capacity = 10 + (4 × Owned Nodes)`
- **Maintenance Upkeep Costs** (charged per unit exceeding free capacity):
  - **1 Gold/turn** per excess unit stationed at friendly owned nodes.
  - **2 Gold/turn** per excess unit stationed at foreign/unowned nodes or traveling in transit fleets.
  - Free supply capacity shields domestic garrison units first before covering foreign forces.
- **Bankruptcy Desertion Attrition**:
  - If total upkeep exceeds available treasury Gold, the player's Gold is set to **0**, and unpaid units immediately suffer desertion attrition until the deficit is eliminated.
  - Foreign units stationed at unowned/enemy nodes desert first (saving 2 Gold each).
  - Foreign units in transit fleets desert second (saving 2 Gold each).
  - Domestic garrison units on friendly nodes desert third (saving 1 Gold each).
  - Disband priority within each category: **Raiders -> Scouts -> Guards -> Siege**.

### 4. Two-Turn Node Capture Progress
- **Turn 1 (Hostile Occupation)**: If an attacking fleet eliminates all defenders at an enemy or neutral node, the node enters `capturing_player = invader` and `capture_progress = 1`. The original owner cannot train units at this node while it is contested, and the capturer does not collect income from it yet.
- **Turn 2 (Uncontested Confirmation)**: If the invading force remains uncontested at the node on the subsequent turn, `capture_progress = 2`. Ownership officially flips, and capture progress resets to 0.
- **Relief Interventions**: If the defender sends a relief force that arrives on the next turn, battle begins immediately. If the invading force is destroyed, the capture attempt is broken and progress resets to 0.
- **Scout Contest**: A contesting friendly Scout prevents capture progress from advancing for that turn.

### 5. Fog of War & Information Visibility
- **Always Visible**:
  - All nodes currently owned by your player.
  - Stationed unit counts at friendly nodes.
  - Nodes directly connected by a lane to territory you own.
  - Opponent fleets in transit: origin node, destination node, turns remaining, and total unit count (radar silhouette).
- **Hidden by Default**:
  - Opponent fleet unit compositions (`units = None`, `is_revealed = False`).
- **Unmasking Fleets (`is_revealed = True`)**:
  - A friendly Scout is stationed at the origin node.
  - A friendly Scout is stationed at the destination node.
  - A friendly fleet containing at least one Scout travels along the same lane or an intersecting lane.

### 6. The Late-Game Relic Awakening
- The central **Relic Sanctuary (Node 7)** awakens dynamically between **Turn 80 and Turn 100**.
- Exactly 5 turns before activation, the engine broadcasts an alert: `obs.relic_charging = True`.
- Upon activation (`obs.relic_active = True`):
  - Controlling Node 7 awards **+10 Bonus Victory Points per turn**.
  - All owned nodes across the map award **2 Victory Points per turn** (doubled from 1).

---

## 5. Battlefield Geography & Mirrored Topology

The arena consists of **15 strategic nodes** connected by travel lanes. The graph is bilaterally symmetrical across the vertical center line, ensuring Player 1 and Player 2 have mathematically identical travel distances to all objectives.

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

### Complete Node Directory & Yield Table

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

### Lanes & Travel Delays
- **Standard Lanes**: Adjacent bastions and outposts require **2 turns** of lane travel.
- **Chokepoint Bridges & High Flanks**: Long lanes (0 <-> 3, 3 <-> 7, 11 <-> 7, 14 <-> 11, and 4 <-> 10) require **3 turns** of lane travel.
- Both players have equal 6-turn travel routes from Home Core to the central Relic (e.g. 0 -> 3 -> 7 vs 14 -> 11 -> 7).

---

## 6. Match Scoring & Strict Deterministic Tiebreaker

Matches terminate when:
1. **Total Elimination**: A player loses all nodes and has zero active or traveling units.
2. **Turn 120 Limit**: If both players survive to Turn 120, a deterministic composite tiebreak score determines the winner:

**Tiebreak Score = (Victory Points × 100,000) + (Relic Turns Held × 1,000) + Total Net Worth**

Where:
**Total Net Worth = Total Army Asset Value + Banked Gold**

### The 1:1 Net Worth Parity Rule
- Every **1 Gold** in your treasury reserves provides exactly **1 tiebreak point**.
- Every **1 Gold** invested in surviving active military units provides exactly **1 tiebreak point** (evaluated using base recruitment costs: Raider = 10, Guard = 12, Siege = 18, Scout = 6).
- An empire with 100 Gold banked and 0 units has the identical Net Worth (100 points) as an empire with 0 Gold banked and 10 Raiders (100 points).

Because this formula incorporates cumulative points, relic control duration, and total net worth in Gold, it is mathematically unique. **There are strictly no draws.**

---

## 7. Competitor Bot API & Order Protocol

Every competitor bot inherits from `BotBase` and implements the `act(obs)` method:

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

        # 1. Training: Recruit 1 Raider at home if affordable
        if obs.my_credits >= 10:
            orders.append(self.train(self.home_id, UnitType.RAIDER, 1))

        # 2. Movement: Dispatch 2 mobilized Raiders along the shortest path
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

## 8. Quick-Start & Testing Workflow

1. **Copy the Starter Template**:
   ```bash
   cp bots/starter_bot.py bots/my_bot.py
   ```
2. **Validate Your Bot Locally**:
   Run the official dry-run validator to test your bot across Player 1, Player 2, and late-game charging states:
   ```bash
   python validate_bot.py bots/my_bot.py
   ```
3. **Submit Your Bot File**:
   Submit your single standalone `.py` file according to tournament organizer instructions.

---

## 9. Rules of Engagement & Technical Constraints

1. **50 Millisecond Time Limit**: Your bot must return orders within **50 milliseconds** per turn. Compute timeouts will forfeit orders for that turn.
2. **Pure Standard Library**: Submissions must use standard Python 3. Subprocesses, network sockets, thread pools, or disk modifications are strictly forbidden.
3. **Persistent Memory**: You may store cross-turn state on `self` (e.g. enemy sightings, internal counters). Memory persists throughout an individual match.
4. **Order Validity**: Orders attempting to move units that do not exist at a node or training units without sufficient Gold are ignored by the engine.
5. **No Draws**: Every match terminates with an unambiguous winner.

---

## 10. Technical Notes & API Edge Cases

- **Mobilization Timing**: Units trained on Turn T join the local garrison immediately for defense, but cannot be moved on Turn T. They become eligible for `MoveOrder` dispatch on Turn T+1.
- **Budget Tracking**: Deduct Gold locally when creating multiple `TrainOrder`s in `act(obs)` to ensure commands do not exceed available funds.
- **Path Index Bounds**: `self.get_path(obs, u, v)` returns `[u, next_node, ..., v]`. Verify `len(path) >= 2` before indexing `path[1]`.
- **Contested Recruitment**: Training orders are not processed at a node while it is actively being contested (`node.capturing_player != 0`).
- **Fleet Origin Ownership**: Fleets can only be launched from nodes currently owned by your player.
