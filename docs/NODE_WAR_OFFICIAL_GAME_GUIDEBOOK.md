# NODE WAR // Official Competitor Guidebook
**Autonomous AI Tournament & Hackathon Manual**  
*Document Version: 3.4 — Official Participant Release*

---

## 1. Executive Summary: What is Node War?

Imagine a game of **Risk meets StarCraft on a mirrored Chess board**:
- Two rival commanders start at opposite ends of a 15-node network map (Player 1 at Node 0 on the left, Player 2 at Node 14 on the right).
- In the center sits the **Relic Sanctuary (Node 7)**, an ancient shrine that awakens in the late game.
- Each turn, both players submit orders simultaneously: collecting Gold, managing empire supply lines, recruiting troops, marching armies down winding roads, ambushing enemies through the fog of war, and conquering territory.
- Matches last up to **120 turns**. There are strictly **no draws**; an exact mathematical tiebreaker guarantees a winner if both players survive to the end.

Your goal as a human competitor is to design the strategy, decision-making, and game-theoretic logic for your automated Python bot (`class MyBot(BotBase)`).

---

## 2. How the Game Works: Plain English Strategic Guide

Before looking at any code or APIs, here is exactly how a match plays out from a strategic human perspective:

### The Three Paths to Victory
1. **Total Annihilation (Early / Mid-Game Knockout)**:
   Break through the enemy's defensive perimeter, assault their Home Base Citadel, and eliminate all enemy castles and active troops.
2. **Relic Domination (Late-Game Surge)**:
   Secure and hold the central Relic Sanctuary (Node 7) when it awakens between Turn 80 and Turn 100. Holding the Relic awards +10 bonus points per turn AND doubles all territory scoring across your entire empire.
3. **The Tiebreaker Precision (Turn 120 Limit)**:
   If neither player is eliminated by Turn 120, the winner is determined by a composite score of accumulated Victory Points, duration of Relic control, total army asset value, and banked treasury Gold.

### The 8 Steps of Every Turn (Like Clockwork)
Every single turn proceeds through eight strict phases executed simultaneously:
1. **Income Collection**: Every node you currently own deposits Gold into your treasury (+15 for Home Core, +10 for Relic, +7 for Chokepoint Outposts, +4 for Outer Bastions).
2. **Empire Upkeep (Supply Lines)**: Your empire supports a free troop capacity based on your territory: `10 + (4 × Owned Nodes)`. If your military exceeds this capacity, you must pay maintenance (1 Gold/turn for home defenders, 2 Gold/turn for expeditionary forces abroad).
3. **Bot Decisions & Recruitment**: Both players issue training commands. New soldiers instantly appear in your garrison to defend the castle this turn.
4. **Troop Movements**: Both players dispatch marching squads along travel lanes.
5. **Lane Travel**: Soldiers march along roads. Standard roads take **2 turns** to traverse; long chokepoint bridges take **3 turns**.
6. **Simultaneous Battles**: Wherever opposing soldiers meet at a node (or clash with neutral defenders), battle resolves instantly and deterministically.
7. **Two-Turn Capture Clock**: If you wipe out all defenders at a node, your troops occupy it. If you hold it uncontested for **2 consecutive turns**, the flag flips and it becomes 100% yours.
8. **Victory Point Scoring**: You score 1 Victory Point for every node you own (+2 points per node and +10 bonus points for Node 7 once the Relic awakens).

---

## 3. The 4 Units: Roles & The Combat Triangle

Node War combat is governed by a rock-paper-scissors counter system where units deal **double damage (2.0x)** against their counter targets:

```
                  RAIDER (10 Gold)
                 /                \
        2.0x vs /                  \ 0.5x vs
               v                    v
       SIEGE (18 Gold) <------- GUARD (12 Gold)
                       2.0x vs
```

### 1. The Raider (10 Gold // 20 HP // 12 ATK)
- **Role**: Fast shock cavalry, harasser, and artillery hunter.
- **Combat Dynamic**: **Shreds Siege (2.0x damage)**, but **gets slaughtered by Guards (0.5x damage)**.
- **When to Use**: Early-game territorial expansion, rushing unprotected economy nodes, or flanking behind enemy lines to assassinate slow Siege cannons.

### 2. The Guard (12 Gold // 30 HP // 14 ATK)
- **Role**: Armored shield-wall infantry, perimeter anchor, and gatekeeper.
- **Combat Dynamic**: **Shreds Raiders (2.0x damage)**, but **gets pulverized by Siege (0.5x damage)**.
- **When to Use**: Stationing at chokepoint gates to absorb and repel enemy Raider blitzes, fortifying the Relic Sanctuary, and protecting expanding borders.

### 3. The Siege (18 Gold // 35 HP // 22 ATK)
- **Role**: Heavy long-range artillery, fortress breaker, and high-health juggernaut.
- **Combat Dynamic**: **Pulverizes fortified Guards (2.0x damage)**, but **gets swarmed and dismantled by cheap Raiders (0.5x damage)**.
- **When to Use**: Dismantling heavily fortified enemy chokepoints, cracking the enemy's +50% Home Base defense, and breaking defensive stalemates.

### 4. The Scout (6 Gold // 10 HP // 0 ATK)
- **Role**: Non-combatant aerial reconnaissance eagle and tactical spotter.
- **Special Capabilities**:
  1. *Pierces Fog of War*: Unmasks the hidden unit compositions of enemy squads marching along connected roads.
  2. *Combat Spotter (+15% Damage)*: If your army fights with a friendly Scout present or stationed adjacent, your troops gain a +15% targeting damage bonus. (Fighting blindly against an enemy with a Scout inflicts a -15% penalty!).
  3. *Capture Freezer*: If an enemy is trying to capture your node, a Scout flying into that node freezes the capture clock, buying time for your relief army to arrive!

---

## 4. Key Strategic Mechanics: How to Think Like a Grandmaster

### 1. Defending Your Castles: The Fortress Advantage
- **Home Core Citadels (Nodes 0 & 14)**: Possess massive fortified stone walls granting stationed defenders a **+50% Defense Bonus** (incoming damage is halved!). Launching an early blind rush directly at the opponent's home base is suicidal unless their garrison is completely empty.
- **Outposts & Bastions (Nodes 1–13)**: Stationed defenders receive a **+25% Defense Bonus**. A small squad of Guards stationed at a castle can comfortably defeat a larger invading force.
- **Neutral Garrisons**: Unclaimed neutral nodes are defended by neutral garrisons (1 Raider on outer bastions, 2 Guards on chokepoint gates, 2 Guards + 1 Siege on the Relic). You cannot capture neutral territory with a lone Scout; you must send sufficient combat power to defeat the neutral garrison!

### 2. The 2-Turn Capture Rule & Relief Counter-Attacks
Capturing a castle is not instant:
- **Turn 1 of Occupation**: You wipe out the garrison. The node enters **Contested (1/2)** status. It does NOT generate Gold for you yet, and recruitment is frozen.
- **The Relief Counter-Attack**: Because travel takes 2 turns, an astute defender who notices their node falling can immediately dispatch a relief squad. When the relief squad arrives on the next turn, combat begins and the capture clock is halted!
- **Turn 2 of Occupation**: If your occupation remains uncontested for a second consecutive turn, ownership formally flips and the castle begins producing Gold and Victory Points under your banner.

### 3. Supply Lines: Balancing Military Size vs Territorial Growth
In Node War, you cannot simply spam infinite soldiers without expanding your territory:
- **Free Supply Cap = 10 + (4 × Owned Nodes)**
- If you own 1 node (your starting base), your free capacity is $10 + 4 = 14$ troops.
- If you own 5 nodes, your free capacity expands to $10 + 20 = 30$ troops.
- If your army exceeds your free capacity, your treasury suffers:
  - **1 Gold/turn** per excess unit stationed defensively at your own castles.
  - **2 Gold/turn** per excess unit marching on roads or stationed in foreign territory (overextension supply tax!).
- *Strategic Choice*: Do you maintain a lean, mobile strike force to keep your treasury full, or do you accept heavy supply taxes to build an unstoppable army for a decisive push?

### 4. The Fog of War & The Information Game
- You can always see your own castles and stationed troops.
- You can always see into adjacent nodes directly connected to territory you own.
- When an enemy marches a squad along a road, you see their **radar silhouette** (starting point, destination, arrival time, and total unit count).
- **The Catch**: You DO NOT know what unit types are in the squad! Is that approaching 6-unit squad made of 6 cheap Raiders, or 6 armored Guards, or 6 heavy Siege artillery? Unless you have a Scout observing the road, you are flying blind. Good players deploy Scouts early to scout enemy recruitment and build direct counter-units before the enemy arrives!

### 5. The Late-Game Relic Awakening (Turns 80 to 100)
- The central **Relic Sanctuary (Node 7)** awakens dynamically between **Turn 80 and Turn 100**.
- Exactly 5 turns before it awakens, a warning alert sounds: `obs.relic_charging = True`.
- When it awakens:
  - Controlling Node 7 awards an astounding **+10 Bonus Victory Points per turn**!
  - Every node you own across the entire map produces **2 Victory Points per turn** (doubled from 1).
- Matches that seem close in the mid-game can be won in 5 turns if one player captures the Relic while the other sits passively in their home base.

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
- **Standard Lanes**: Moving between adjacent bastions and outposts takes **2 turns**.
- **Chokepoint Bridges & High Flanks**: Long lanes ($0 \leftrightarrow 3$, $3 \leftrightarrow 7$, $11 \leftrightarrow 7$, $14 \leftrightarrow 11$, and $4 \leftrightarrow 10$) take **3 turns**.
- Both players have equal 6-turn travel routes from Home Core to the central Relic (e.g. $0 \rightarrow 3 \rightarrow 7$ vs $14 \rightarrow 11 \rightarrow 7$).

---

## 6. Strategic Playbook: Four Classic Archetypes

When designing your bot, you can explore several core strategic philosophies:

```
[BLITZKRIEG RUSHER]   --- Beats --->   [RECON ARTILLERY]
        ^                                      |
        |                                      |
      Beats                                  Beats
        |                                      v
[IRON FORTRESS TURTLE] <--- Beats --- [DYNAMIC ECONOMIST]
```

1. **The Blitzkrieg Rusher**:
   Trains pure Raiders from Turn 1, bypasses slow outer nodes, and rushes directly down the attack corridor to overwhelm the opponent before they can establish defenses.
2. **The Iron Fortress (Turtle)**:
   Anchors early chokepoints (Node 1, 2, 3) with heavy Guards, leverages the +25% defense bonus to shatter enemy Raider swarms, starves the attacker of momentum, and expands methodically toward the center.
3. **The Recon Artillery (Balanced / Tech)**:
   Deploys an early Scout to inspect enemy armies through the fog of war, identifies fortified Guard walls, and tech-transitions into heavy Siege artillery to dismantle enemy fortresses from afar.
4. **The Dynamic Economist**:
   Focuses on rapid multi-pronged expansion to claim outer rigs and outposts early, rapidly expanding free supply capacity and Gold income to overpower the opponent with an overwhelming late-game force.

---

## 7. Match Scoring & Strict Deterministic Tiebreaker

Matches terminate when:
1. **Total Elimination**: A player loses all nodes and has zero active or traveling units.
2. **Turn 120 Limit**: If both players survive to Turn 120, a deterministic composite tiebreak score is computed:

**Tiebreak Score = (Victory Points × 100,000) + (Relic Turns Held × 1,000) + (Total Army Asset Value × 10) + Banked Gold**

Because this formula incorporates cumulative points, relic control duration, total military asset value in Gold, and unspent treasury reserves, it is mathematically unique. **There are strictly no draws.**

---

## 8. Competitor Bot API & Order Protocol

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

        # 2. Movement: Dispatch 2 Raiders along the shortest path
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

## 9. Quick-Start & Testing Workflow

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

## 10. Rules of Engagement & Execution Constraints

1. **50 Millisecond Time Limit**: Your bot must return orders within **50 milliseconds** per turn. Compute timeouts will forfeit orders for that turn.
2. **Pure Standard Library**: Submissions must use standard Python 3. Subprocesses, network sockets, thread pools, or disk modifications are strictly forbidden.
3. **Persistent Memory**: You may store cross-turn strategic state on `self` (e.g. enemy sightings, build queues). Memory persists throughout an individual match.
4. **Order Validity**: Orders attempting to move units that do not exist at a node or training units without sufficient Gold will be safely ignored by the engine.
5. **No Draws**: Every match terminates with an unambiguous winner.

---

## 11. Debugging & Common Pitfalls

- **Path Index Bounds**: `self.get_path(obs, u, v)` returns `[u, next_node, ..., v]`. Always check `if len(path) >= 2:` before accessing `path[1]`.
- **Recruitment Lockout**: You cannot train units at a node while it is actively being contested (`node.capturing_player != 0`).
- **Moving from Unowned Nodes**: Units can only launch fleets from nodes you currently own. Wait for the 2-turn capture progress to flip before moving out!
- **Local Budget Tracking**: Always deduct Gold locally as you generate `TrainOrder`s within `act(obs)` to ensure you don't over-commit your reserves.
