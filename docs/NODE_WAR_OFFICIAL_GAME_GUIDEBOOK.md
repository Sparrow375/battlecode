# NODE WAR // Official Competitor Guidebook
**Autonomous AI Strategy Tournament Manual**  
*Document Version: 4.0 — Official Participant Release*

---

## 1. Executive Summary: What is Node War?

**Node War** is a deterministic, turn-based strategy simulation fought on a symmetric 15-node network map:
- Two rival commanders start at opposite ends of the arena (Player 1 at Node 0 on the left, Player 2 at Node 14 on the right).
- At the center sits the **Relic Sanctuary (Node 7)**, an ancient objective that awakens dynamically in the late game.
- Each turn, both players submit orders simultaneously: managing Gold income, balancing empire supply lines, recruiting troops, dispatching fleets along travel lanes, observing movements through the fog of war, and conquering territory.
- Matches run for up to **120 turns**. There are strictly **no draws**; an exact mathematical tiebreaker guarantees a deterministic winner if both players survive to the end.

Competitors write an automated Python agent inheriting from `BotBase` (e.g. `class CompetitorBot(BotBase)`) that inspects the turn observation and returns valid recruitment and movement orders. A complete standalone toolkit (`nodewar.py`) ships with the starter kit, providing the bot base class, type definitions, a dry-run validator, and a full local simulator to test your bots against baseline opponents.

---

## 2. Game Overview & Turn Execution Lifecycle

### Victory Conditions
1. **Total Elimination**: A player loses all owned nodes and has zero active or traveling units.
2. **Relic & Territory Point Accumulation**: Controlling territory scores Victory Points each turn. Controlling the central Relic once awakened provides significant point acceleration.
3. **Turn 120 Limit**: If neither player is eliminated by Turn 120, a deterministic composite tiebreak score evaluates Victory Points, Relic control duration, and Total Net Worth.

### The 8 Turn Phases (Executed in Exact Sequence)
Every turn proceeds through eight clockwork phases executed simultaneously:
1. **Income Collection**: Every node you currently own deposits Gold into your treasury (+15 for Home Core, +10 for Relic, +7 for Chokepoint Outposts, +4 for Outer Bastions). Both players start Turn 1 with **30 Gold**.
2. **Empire Upkeep & Bankruptcy Check**: Free troop capacity is determined by territory: `10 + (4 × Owned Nodes)`. Units exceeding this cap incur maintenance (1 Gold/turn for domestic garrison defenders, 2 Gold/turn for foreign units abroad or in transit). If treasury Gold is insufficient to cover upkeep, Gold drops to 0, and unpaid units immediately suffer **desertion attrition** until the deficit is cleared (foreign forces first, then domestic; in order: Raiders -> Scouts -> Guards -> Siege).
3. **Recruitment & Mobilization**: Both players submit training orders simultaneously. Newly trained units immediately join the garrison to defend that castle against attacks arriving this turn. However, newly trained units cannot march out along roads on the same turn they are trained; they mobilize at the node and become available for movement orders on Turn T+1. Training orders evaluate against treasury Gold after Phase 1 Income and Phase 2 Upkeep have resolved.
4. **Troop Movements**: Both players dispatch mobilized garrison forces along travel lanes simultaneously. A single `MoveOrder` moves units across exactly one lane (origin and destination must be directly adjacent). All requested units must be available and mobilized at an owned node; if any requested unit type is missing, the entire `MoveOrder` is rejected atomically.
5. **Lane Travel**: Fleets decrement transit timers along travel lanes. Standard lanes take **2 turns**; long bridge lanes take **3 turns**. Fleets passing each other in opposite directions on the same lane do not clash mid-transit. Reinforcements arriving at an owned node on the same turn an attack hits immediately join the garrison and defend with the full stationary defense bonus.
6. **Simultaneous Combat**: Wherever opposing forces meet at a node (or encounter neutral defenders), combat resolves deterministically via multi-round Lanchester battle simulation (up to 10 rounds). If the defending garrison survives all 10 rounds, the attack is repelled and surviving attackers are eliminated.
7. **Two-Turn Capture Clock**: If all defenders at a node are eliminated, the occupying force begins capture progress. If held uncontested for **2 consecutive turns**, ownership transfers. A contesting enemy scout arriving at the node that turn freezes capture progress for that turn (scouts in transit along lanes do not freeze capture until they reach the node).
8. **Victory Point Scoring**: Each owned node awards **1 Victory Point per turn** (doubled to **2 Victory Points per node** once the Relic is active, plus **+10 bonus points per turn** for holding Node 7).

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
| **Scout** | 6 🪙 | 10 | 0 | None (Non-combat) | None | Unmasks enemy fleets; ±15% combat swing; freezes enemy capture on arrival |

### Proportional Damage Formula Against Mixed Armies
When attacking an enemy force containing a mix of unit types, damage is distributed proportionally across the target army's composition:

$$\text{Effective Multiplier} = \frac{2.0 \times N_{\text{countered}} + 1.0 \times N_{\text{neutral}} + 0.5 \times N_{\text{weak}}}{\text{Total Defender Units}}$$

- There is **no artificial damage floor**. Defending units of a counter-type properly dilute incoming damage.
- *Example*: 10 Raiders (base attack $10 \times 12 = 120$) attacking 10 Guards and 1 Siege (11 defenders total):
  $$\text{Effective Multiplier} = \frac{2.0 \times 1 + 1.0 \times 0 + 0.5 \times 10}{11} = \frac{7.0}{11} \approx 0.636\times$$
  Total outgoing damage is $120 \times 0.636 = 76.36$ damage. The 10 defending Guards successfully shield the solitary Siege engine.

### How Battles Resolve (Step-by-Step Algorithm)
Every battle at a contested node follows a strict multi-round simulation:
1. **10-Round Ceiling**: Combat runs for up to 10 micro-rounds within Phase 6 of a single turn.
2. **Simultaneous Damage Calculation**: In each round, both sides simultaneously compute outgoing damage using their current surviving unit counts, unit counter multipliers, and scout modifiers.
3. **Defense Bonus Reduction**: Defenders take reduced damage based on node type (incoming damage multiplied by $(1.0 - \text{defense\_bonus})$: 50% reduction at Home Citadels, 25% reduction at Outposts, 0% in neutral meeting engagements). Attackers take 100% incoming damage (0% reduction).
4. **Proportional Casualty Distribution**: Effective damage is distributed proportionally across all unit types in the army by their total HP share. Units are removed as damage thresholds are crossed. Non-combat Scouts absorb damage if damage share exceeds their 10 HP pool.
5. **Anti-Stalemate Attrition**: If a round deals insufficient damage to eliminate any unit on either side, the force dealing less total damage loses 1 combat unit to prevent infinite stalemates.
6. **Non-Combatant Elimination**: If all combat units (Raiders, Guards, Siege) of a side are eliminated, any remaining non-combat Scouts on that side are wiped out.
7. **Attacker Repulsion**: If the defending garrison has any surviving units after 10 rounds, the attack has failed; the surviving defenders retain the node, and any surviving attacking units are eliminated.

### Tactical Scout Impact (The ±15% Swing)
Scouts cost only **6 Gold** but create a decisive **30% relative combat differential**:
- Armies fighting with a friendly Scout present or stationed at an adjacent owned node receive a **+15% damage bonus**.
- Armies fighting blindly without scout coverage against an opponent who has scout coverage suffer a **-15% damage penalty**.
- *Empirical Impact*: In a clash of 12 Raiders vs 10 Raiders:
  - If attacker has a scout and defender does not: **6 attackers survive**.
  - If neither side has a scout: **4 attackers survive**.
  - If defender has a scout and attacker does not: **1 attacker survives**.
- Because of this swing, incorporating Scouts into major expeditionary forces and perimeter garrisons is effectively mandatory for competitive bot play.

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
  $$\text{Free Capacity} = 10 + (4 \times \text{Owned Nodes})$$
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
- **Scout Contest**: A contesting enemy scout arriving at the node that turn (even if eliminated during combat) freezes capture progress for that turn. Scouts traveling in transit along lanes do not freeze capture until the turn they reach the destination node.

### 5. Fog of War & Information Visibility
- **Always Visible**:
  - All nodes currently owned by your player.
  - Garrison unit compositions at all friendly owned nodes.
  - Garrison unit compositions at all nodes directly adjacent (connected by a lane) to territory you own (no scout required).
  - Opponent fleets in transit: origin node, destination node, turns remaining, and total unit count (radar silhouette).
- **Hidden by Default**:
  - Opponent fleet unit compositions (`units = None`, `is_revealed = False`).
  - Garrison unit compositions at nodes not connected to your territory (`units = None`). Forward scouts stationed at unowned nodes do not unmask adjacent enemy garrisons.
- **Unmasking Fleets (`is_revealed = True`)**:
  An enemy fleet's exact unit composition is unmasked if:
  1. A friendly Scout is stationed at an owned node connected to that lane (either origin or destination), OR
  2. A friendly fleet containing at least one Scout is traveling on that exact same lane.
  Fleets on other or intersecting lanes are not unmasked.

### 6. The Late-Game Relic Awakening
- The central **Relic Sanctuary (Node 7)** awakens dynamically between **Turn 80 and Turn 100** based on a deterministic match seed.
- Exactly 5 turns before activation, the engine broadcasts an alert: `obs.relic_charging = True`.
- Upon activation (`obs.relic_active = True`):
  - Controlling Node 7 awards **+10 Bonus Victory Points per turn**.
  - All owned nodes across the map award **2 Victory Points per turn** (doubled from 1).

---

## 5. Battlefield Geography & Mirrored Topology

The arena consists of **15 strategic nodes** connected by **31 travel lanes**. The network topology is bilaterally symmetrical across the vertical center line (Node 7), providing both commanders equal baseline travel distances and economic yields to all objectives.

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

| Node ID | Node Designation | Position (X, Y) | Initial Owner | Yield (Gold/Turn) | Defense Bonus | Starting / Neutral Garrison |
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

### Complete 31-Lane Directory Table

All lanes are bidirectional. Fleets move along lanes at fixed transit times:

| Lane ID | Node A | Node B | Travel Time | Sector / Strategic Description |
|:---:|:---:|:---:|:---:|:---|
| **L01** | 0 | 1 | 2 Turns | P1 Core to Alpha Bastion |
| **L02** | 0 | 2 | 2 Turns | P1 Core to Gamma Bastion |
| **L03** | 0 | 3 | 3 Turns | P1 Core to Vanguard Gate (Long Chokepoint Bridge) |
| **L04** | 1 | 3 | 2 Turns | Alpha Bastion to Vanguard Gate |
| **L05** | 2 | 3 | 2 Turns | Gamma Bastion to Vanguard Gate |
| **L06** | 1 | 4 | 2 Turns | Alpha Bastion to North Rig |
| **L07** | 1 | 5 | 2 Turns | Alpha Bastion to North Outpost |
| **L08** | 2 | 6 | 2 Turns | Gamma Bastion to South Outpost |
| **L09** | 4 | 5 | 2 Turns | North Rig to North Outpost |
| **L10** | 3 | 5 | 2 Turns | Vanguard Gate to North Outpost |
| **L11** | 3 | 6 | 2 Turns | Vanguard Gate to South Outpost |
| **L12** | 5 | 7 | 2 Turns | North Outpost to Relic Sanctuary |
| **L13** | 6 | 7 | 2 Turns | South Outpost to Relic Sanctuary |
| **L14** | 3 | 7 | 3 Turns | Vanguard Gate to Relic Sanctuary (Central Highway) |
| **L15** | 5 | 9 | 2 Turns | North Outpost to Zenith Outpost (Mid-lane Crossway) |
| **L16** | 6 | 8 | 2 Turns | South Outpost to Titan Outpost (Mid-lane Crossway) |
| **L17** | 4 | 10 | 3 Turns | North Rig to Apex Rig (Northern High Flank Bridge) |
| **L18** | 9 | 7 | 2 Turns | Zenith Outpost to Relic Sanctuary |
| **L19** | 8 | 7 | 2 Turns | Titan Outpost to Relic Sanctuary |
| **L20** | 11 | 7 | 3 Turns | Sentinel Gate to Relic Sanctuary (Central Highway) |
| **L21** | 14 | 13 | 2 Turns | P2 Core to Epsilon Bastion |
| **L22** | 14 | 12 | 2 Turns | P2 Core to Omega Bastion |
| **L23** | 14 | 11 | 3 Turns | P2 Core to Sentinel Gate (Long Chokepoint Bridge) |
| **L24** | 13 | 11 | 2 Turns | Epsilon Bastion to Sentinel Gate |
| **L25** | 12 | 11 | 2 Turns | Omega Bastion to Sentinel Gate |
| **L26** | 13 | 10 | 2 Turns | Epsilon Bastion to Apex Rig |
| **L27** | 13 | 9 | 2 Turns | Epsilon Bastion to Zenith Outpost |
| **L28** | 12 | 8 | 2 Turns | Omega Bastion to Titan Outpost |
| **L29** | 10 | 9 | 2 Turns | Apex Rig to Zenith Outpost |
| **L30** | 11 | 9 | 2 Turns | Sentinel Gate to Zenith Outpost |
| **L31** | 11 | 8 | 2 Turns | Sentinel Gate to Titan Outpost |

---

## 6. Match Scoring, Strict Tiebreaker & Replay Policy

Matches terminate when:
1. **Total Elimination**: A player loses all nodes and has zero active or traveling units.
2. **Turn 120 Limit**: If both players survive to Turn 120, a deterministic composite tiebreak score determines the winner:

$$\text{Tiebreak Score} = (\text{Victory Points} \times 100{,}000) + (\text{Relic Turns Held} \times 1{,}000) + \text{Total Net Worth}$$

Where:
$$\text{Total Net Worth} = \text{Total Army Asset Value} + \text{Banked Gold}$$

### The 1:1 Net Worth Parity Rule
- Every **1 Gold** in your treasury reserves provides exactly **1 tiebreak point**.
- Every **1 Gold** invested in surviving active military units provides exactly **1 tiebreak point** (evaluated using base recruitment costs: Raider = 10, Guard = 12, Siege = 18, Scout = 6).
- An empire with 100 Gold banked and 0 units has the identical Net Worth (100 points) as an empire with 0 Gold banked and 10 Raiders (100 points).
- Because this formula incorporates cumulative points, relic control duration, and total net worth in Gold, it resolves matches without draws.

### Tournament Replay & Spectator Policy
- Full god-view replays (revealing all hidden fleets and unit compositions) are exported for live spectator auditorium broadcasts and caster commentary.
- For practice ladders and scrimmages, match runners can be configured with fog-of-war replays or anonymized opponent identifiers to protect proprietary competitor strategies before tournament day.

---

## 7. Competitor Bot API & Runtime Contract

### Tournament Runtime Contract
1. **Python Version**: Python 3.10+ (tested up to Python 3.14).
2. **Turn Time Limit**: **50 milliseconds wall-clock time** per turn on a dedicated modern x86_64 host (AMD Ryzen / Intel i7). If `act()` exceeds 50 ms, the engine terminates execution for that turn and treats orders as empty (`[]`).
3. **Exception Handling**: Any unhandled exception or syntax error in `act()` forfeits orders for that turn. If a bot script fails to import or crashes during `__init__`, all turns return empty orders.
4. **Allowed Modules**: Python Standard Library only (`math`, `random`, `heapq`, `collections`, `itertools`, `typing`, `dataclasses`, `time`). The starter kit module `nodewar` is provided. Subprocesses, network sockets, filesystem writes, and multithreading are strictly prohibited.
5. **Fresh Bot Instance**: Each game in a series instantiates a fresh bot object (`bot = CompetitorBot(player_id)`). Memory stored on `self` persists across turns within that match, but resets between games.
6. **Player Seats**: Your bot must support playing as either Player 1 (`self.player_id == 1`, starting at Node 0) or Player 2 (`self.player_id == 2`, starting at Node 14). Tournament matches run as Best-of-3 series with alternating seats.
7. **Loader Discovery**: The tournament runner automatically inspects your submission file and instantiates any class inheriting from `BotBase` (e.g. `class CompetitorBot(BotBase)` or `class StarterBot(BotBase)`).

### Starting Gold & Observation Timing
- **Initial Treasury**: Each commander starts Turn 1 with **30 Gold**.
- **Observation Timing**: `obs.my_credits` represents your balance at turn start prior to Phase 1 Income collection and Phase 2 Upkeep deduction. In Phase 1 of `step()`, your node income (+15 from Home Core, etc.) is credited, and in Phase 2 upkeep is deducted before Phase 3 evaluates training orders. Your effective spending budget for training orders is:
  $$\text{Effective Budget} = \text{obs.my\_credits} + \text{current\_turn\_income} - \text{current\_turn\_upkeep}$$

### Standard Bot Implementation

```python
from __future__ import annotations
from typing import List
from nodewar import BotBase, BotObservation, Order, TrainOrder, MoveOrder, UnitType

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

        # 2. Movement: Dispatch 2 mobilized Raiders along a connected lane
        orders.append(self.move(self.home_id, 1, {UnitType.RAIDER: 2}))

        return orders
```

### Observation Schema Reference (`BotObservation`)

| Field | Type | Description |
|:---|:---:|:---|
| `obs.current_turn` | `int` | Current turn number (1 to 120) |
| `obs.max_turns` | `int` | Match duration limit (120) |
| `obs.my_player_id` | `int` | Your faction seat (1 or 2) |
| `obs.my_credits` | `int` | Treasury Gold balance at observation time |
| `obs.my_score` | `int` | Your current accumulated Victory Points |
| `obs.opponent_score` | `int` | Opponent's accumulated Victory Points |
| `obs.relic_charging` | `bool` | True during 5-turn warning window before Relic activates |
| `obs.relic_active` | `bool` | True once Relic Sanctuary is awakened |
| `obs.relic_node_id` | `int` | Node ID of Relic Sanctuary (7) |
| `obs.nodes` | `Dict[int, VisibleNode]` | Map of Node ID (0–14) to `VisibleNode` |
| `obs.lanes` | `List[Dict[str, Any]]` | List of 31 lane dicts (`node_a`, `node_b`, `travel_turns`) |
| `obs.my_fleets` | `List[VisibleFleet]` | All friendly fleets currently in transit |
| `obs.enemy_fleets` | `List[VisibleFleet]` | All enemy fleets currently in transit (radar silhouettes) |

### Node Schema Reference (`VisibleNode`)

| Field | Type | Description |
|:---|:---:|:---|
| `node.id` | `int` | Node integer ID (0 to 14) |
| `node.name` | `str` | Tactical designation (e.g. "Alpha Bastion") |
| `node.x` | `float` | X coordinate in arena (10.0 to 90.0) |
| `node.y` | `float` | Y coordinate in arena (15.0 to 75.0) |
| `node.owner` | `int` | Controlling faction: 0 (Neutral), 1 (Player 1), 2 (Player 2) |
| `node.production` | `int` | Gold produced per turn (+4, +7, +10, or +15) |
| `node.defense_bonus` | `float` | Damage reduction: 0.50 (Home Citadels), 0.25 (Outposts) |
| `node.capture_progress`| `int` | Consecutive turns occupied (0, 1, or 2) |
| `node.capturing_player`| `int` | Faction attempting capture: 0 (None), 1, or 2 |
| `node.units` | `Optional[Dict[str, int]]` | Stationed unit counts if visible; `None` if fog masked |
| `node.is_scouted` | `bool` | True if owned or directly monitored by a friendly scout |

### Fleet Schema Reference (`VisibleFleet`)

| Field | Type | Description |
|:---|:---:|:---|
| `fleet.id` | `int` | Unique integer identifier |
| `fleet.owner` | `int` | Faction commanding fleet (1 or 2) |
| `fleet.origin_node` | `int` | Departure node ID |
| `fleet.dest_node` | `int` | Destination node ID |
| `fleet.turns_remaining`| `int` | Turns until arrival at destination |
| `fleet.total_turns` | `int` | Total transit duration along lane (2 or 3) |
| `fleet.total_count` | `int` | Total unit count (always visible radar silhouette) |
| `fleet.is_revealed` | `bool` | True if unit composition is unmasked by scout coverage |
| `fleet.units` | `Optional[Dict[str, int]]` | Exact unit counts if revealed; `None` if obscured |

### Built-in Helper Methods on `BotBase`

- `self.get_my_nodes(obs) -> List[VisibleNode]`: Returns all nodes currently owned by you.
- `self.get_enemy_nodes(obs) -> List[VisibleNode]`: Returns nodes owned by your opponent.
- `self.get_neutral_nodes(obs) -> List[VisibleNode]`: Returns unowned neutral nodes.
- `self.get_distance(obs, u, v) -> int`: Returns shortest path travel turns between nodes u and v.
- `self.get_path(obs, u, v) -> List[int]`: Returns sequence of node IDs along shortest route (e.g. `[0, 1, 5, 7]`).
- `self.get_neighbors(obs, node_id) -> List[int]`: Returns adjacent connected node IDs.
- `self.train(node_id, unit_type, count) -> TrainOrder`: Creates a validated train command.
- `self.move(origin, dest, units) -> MoveOrder`: Creates a validated fleet move command.

---

## 8. Quick-Start, Testing & Local Simulation

The starter kit ships with `nodewar.py`, providing a complete local simulation environment.

1. **Copy the Starter Template**:
   ```bash
   cp starter_bot.py my_bot.py
   ```
2. **Dry-Run Validate Your Bot**:
   Test your bot against Player 1, Player 2, and late-game charging observations:
   ```bash
   python nodewar.py validate my_bot.py
   # Or using the validator wrapper:
   python validate_bot.py my_bot.py
   ```
3. **Simulate a Full Match Locally**:
   Run a full 120-turn simulated match against built-in baseline bots (`rusher`, `turtle`, `balanced`, or another bot file):
   ```bash
   python nodewar.py simulate my_bot.py rusher
   python nodewar.py simulate my_bot.py turtle --turns 120 --seed 42
   ```
4. **Run a Best-of-3 Series with Seat Swapping**:
   ```bash
   python nodewar.py bo3 my_bot.py balanced
   ```
5. **Submit Your Bot File**:
   Submit your standalone `.py` file according to tournament organizer instructions.

---

## 9. Rules of Engagement & Technical Constraints

1. **50 Millisecond Wall-Clock Limit**: Your bot must return orders within **50 milliseconds wall-clock time** per turn. Compute timeouts will forfeit orders for that turn.
2. **Pure Standard Library**: Submissions must use standard Python 3. Subprocesses, network sockets, thread pools, or disk modifications are strictly forbidden.
3. **Persistent Memory**: You may store cross-turn state on `self` (e.g. enemy sightings, internal counters). Memory persists throughout an individual match, but resets across games in a series.
4. **Order Validity**:
   - `MoveOrder` moves units across exactly one lane (`origin_node` and `dest_node` must be connected).
   - Atomic rejection: If any requested unit count exceeds mobilized units available, the entire `MoveOrder` is rejected.
   - Origin ownership constraint: You can only move units from nodes you currently own. Units stationed on unowned nodes (e.g. during 2-turn capture) cannot be ordered out.
5. **No Draws**: Every match terminates with an unambiguous winner via the deterministic composite tiebreaker.

---

## 10. Technical Notes & API Edge Cases

- **Mobilization Delay**: Units trained on Turn T join the local garrison immediately for defense, but cannot be moved on Turn T. They become eligible for `MoveOrder` dispatch on Turn T+1.
- **Budget Tracking**: Deduct Gold locally when creating multiple `TrainOrder`s in `act(obs)` to ensure commands do not exceed available funds.
- **Path Index Bounds**: `self.get_path(obs, u, v)` returns `[u, next_node, ..., v]`. Verify `len(path) >= 2` before indexing `path[1]`.
- **Contested Recruitment**: Training orders are not processed at a node while it is actively being contested (`node.capturing_player != 0`).
- **Fleet Origin Ownership**: Fleets can only be launched from nodes currently owned by your player.
