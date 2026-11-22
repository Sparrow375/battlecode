# Node War - Competitive AI Strategy Game & Spectator Arena

A tournament-ready competitive strategy game engine and esports spectator visualizer. Two autonomous AI agents compete head-to-head on a balanced, mirrored network graph of 15 nodes.

---

## 🏆 Champions League 2026

**Tournament Champion**: **CTRL ALT ELITE**  
- **Source Code**: [`bots/ctrl_alt_elite.py`](bots/ctrl_alt_elite.py)
- **Champion Replay**: [`replays/championship_match_ctrl_alt_elite.json`](replays/championship_match_ctrl_alt_elite.json)
- **Winning Philosophy**: Predictive defense combining exact forward Lanchester combat simulation, binary-search force allocation, Bayesian opponent profiling, and dynamic supply line management.

---

## 🎮 Game Rules & Mechanics

### 1. Mirrored Network Map
- **15 Mirrored Nodes**:
  - `Node 0`: Player 1 Home Citadel (+15 Gold/turn, +50% defense bonus).
  - `Node 14`: Player 2 Home Citadel (+15 Gold/turn, +50% defense bonus).
  - `Node 7`: Central Relic Sanctuary (+10 Gold/turn, +25% defense bonus).
  - Bastions and outposts arranged with bilateral horizontal symmetry.
- **Lanes**: Connect adjacent nodes with transit delays (2 or 3 turns).

### 2. Units & Rock-Paper-Scissors Triangle
| Unit | Cost | HP | Base ATK | Counter Bonus (2.0x) | Vulnerable (0.5x) | Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Raider** | 10 🪙 | 20 | 12 | **Siege** | **Guard** | High-speed shock cavalry, swarm attacker, artillery hunter |
| **Guard** | 12 🪙 | 30 | 14 | **Raider** | **Siege** | Armored frontline infantry, chokepoint & fortress anchor |
| **Siege** | 18 🪙 | 35 | 22 | **Guard** | **Raider** | Heavy artillery, fortified wall & defense breaker |
| **Scout** | 6 🪙 | 10 | 0 | None (Non-combat) | None | Unmasks enemy fleets, +15% friendly combat damage bonus, freezes enemy node capture |

### 3. Fortress Defense & 2-Turn Capture
- **Fortress Advantage**: Stationed defenders receive defense bonuses (+50% at Home Citadels, +25% at outposts).
- **Two-Turn Flip**: When all defenders at an enemy or neutral node are eliminated, the node enters a **Contested (1/2)** state. It requires 2 consecutive turns of uncontested occupation to flip ownership. A relief force arriving on the next turn immediately engages the occupying army.
- **Recruitment Suspension**: Units cannot be trained at a node while it is actively contested.
- **The Mobilization Rule**: Recruits immediately join the garrison to defend that castle on the turn of recruitment, but require 1 turn of mobilization before they can march out along roads.

### 4. Economy & Empire Upkeep
- **Resource Income**: Owned nodes generate Gold every turn (+15 Core, +10 Relic, +7 Chokepoints, +4 Outer Bastions).
- **Dynamic Supply Lines**: Free troop capacity is scaled to territory:
  $$\text{Free Supply Cap} = 10 + (4 \times \text{Owned Nodes})$$
  Active units exceeding this cap incur per-turn maintenance: **1 Gold/turn** for domestic garrisons, or **2 Gold/turn** for expeditionary units (stationed on foreign nodes or in transit).
- **Bankruptcy Desertion Attrition**: If total upkeep exceeds treasury reserves, Gold drops to 0 and unpaid units desert from starvation (foreign units desert first, then domestic garrisons; in priority: Raiders -> Scouts -> Guards -> Siege).

### 5. Central Relic & Endgame Points
- **Standard Turns**: Owned nodes award **1 Victory Point/turn**.
- **Dynamic Relic Awakening (Turns 80–100)**:
  - 5-turn advance warning alert (`obs.relic_charging = True`).
  - Central **Relic Sanctuary (Node 7)** activates!
  - Controlling Node 7 awards **+10 bonus points per turn**!
  - All standard owned node values **double (2 points/turn)**.
- **Deterministic 1:1 Net Worth Tiebreaker**:
  $$\text{Tiebreak Score} = (\text{Victory Points} \times 100{,}000) + (\text{Relic Turns Held} \times 1{,}000) + \text{Total Net Worth}$$
  $$\text{Total Net Worth} = \text{Total Army Asset Value} + \text{Banked Gold}$$
  Every 1 Gold in treasury equals 1 tiebreak point; every 1 Gold in active soldiers equals 1 tiebreak point.

---

## 🤖 Included Bots

- **`bots/ctrl_alt_elite.py`**: **Champions League 2026 Champion**. Predictive combat simulation, binary search invasion sizing, and Bayesian counter-drafting.
- **`bots/rusher.py`**: Aggressive baseline bot swarming cheap Raiders down corridors.
- **`bots/turtle.py`**: Defensive baseline bot anchoring chokepoints with heavy Guards.
- **`bots/balanced.py`**: Reconnaissance baseline deploying Scouts and teching into Siege artillery.
- **`bots/starter_bot.py`**: Clean, documented reference template for building new bots.

---

## 🚀 Quick Start Guide

### 1. Launch Interactive Web Spectator Arena
Start the local spectator server:
```bash
python serve.py
```
Open **`http://localhost:8000`** in any web browser to:
- Watch live simulation runs between any bots.
- Switch between **Cartoon Tower Defense**, **3D Isometric Arena**, and **2D Tactical Schematic** engines.
- Load and replay match files from `replays/` with full scrubber and playback speed controls.

### 2. Run a 1v1 CLI Match
Simulate a head-to-head match between any two bots:
```bash
python -m runner.match --p1 bots/ctrl_alt_elite.py --p2 turtle --turns 120
```

### 3. Run a Best-of-3 Series with Alternating Sides
```bash
python -m runner.match --p1 bots/ctrl_alt_elite.py --p2 balanced --bo3
```

### 4. Run the Tournament Balance Matrix
Benchmark the balance cycle across canonical archetypes:
```bash
python -m runner.tournament --rounds 10
```

---

## 👨‍💻 Building Your Own Bot

1. Copy the starter template:
   ```bash
   cp bots/starter_bot.py bots/my_bot.py
   ```
2. Implement your decision logic inside `act(obs)`:
   ```python
   from nodewar import BotBase, BotObservation, Order, TrainOrder, MoveOrder, UnitType

   class MyBot(BotBase):
       def act(self, obs: BotObservation) -> list[Order]:
           orders = []
           my_nodes = self.get_my_nodes(obs)
           if not my_nodes:
               return orders

           # Train units when affordable
           if obs.my_credits >= 10:
               orders.append(self.train(my_nodes[0].id, UnitType.RAIDER, 1))

           # Dispatch mobilized squads
           return orders
   ```
3. Validate your bot with the dry-run validator:
   ```bash
   python validate_bot.py bots/my_bot.py
   ```

---

## 📄 License

This project is licensed under the MIT License.
