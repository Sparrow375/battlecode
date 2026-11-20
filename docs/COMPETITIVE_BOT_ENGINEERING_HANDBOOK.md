# THE ART OF TOURNAMENT BOT CRAFT // Competitive AI Playbook
**A Systematic Framework for Strategy Bot Tournaments & Hackathons**  
*Document Version: 2.1 — Competitor Strategy & Engineering Manual*

---

## Executive Summary

Competitive AI programming tournaments (such as Battlecode, Node War, Halite, and Screeps) present a unique software engineering challenge. Unlike traditional competitive programming (which tests algorithmic problem solving on static inputs) or academic machine learning (which prioritizes statistical convergence over thousands of GPU hours), **tournament bot engineering tests real-time strategic decision making under tight execution latency and strict incomplete information constraints.**

This playbook provides teams with a battle-tested engineering methodology, architectural patterns, team workflow divisions, and debugging safeguards to build a podium-contending bot in a 24-hour sprint.

---

## 1. The Competitive AI Mindset: Engineering vs Academic ML

```
Academic / Pure ML Approach             Competitive Engineering Approach
---------------------------------       ----------------------------------
- Heavy Deep RL / Policy Nets           - Deterministic Heuristics & Utility Models
- Requires 100,000+ training epochs     - Immediate 100% deterministic test loop
- Prone to non-deterministic edge cases - Bounded execution latency (< 50ms)
- Opaque debugging when behavior fails  - Explicit, transparent state transitions
- Brittle against unseen human tactics  - Robust fail-safes and fallback behaviors
```

> **The Golden Rule of Bot Hackathons**:  
> A simple, robust, well-instrumented heuristic agent that makes zero illegal moves and never crashes will defeat a complex, half-tuned minimax or neural policy 9 times out of 10. Start simple, measure everything, and iterate methodically.

---

## 2. The 24-Hour Tournament Engineering Lifecycle

A successful hackathon team divides their timeline into five disciplined phases:

```
[Hours 0-2]    PHASE 1: Environment Setup, Validator Pass & "Do-Nothing" Smoke Test
[Hours 2-6]    PHASE 2: Economic Foundation & Greedy Macro-Expansion
[Hours 6-12]   PHASE 3: Combat Micro, Counter-Drafting & Threat Maps
[Hours 12-18]  PHASE 4: Hierarchical State Machine & Adaptive Opponent Profiling
[Hours 18-22]  PHASE 5: Automated Regression Matrix, Scrimmage & Parameter Tuning
[Hours 22-24]  PHASE 6: Code Freeze, Defensive Error Guards & Final Submission
```

### Phase 1: Environment & Tooling Verification (Hours 0–2)
- Get the local match runner, test harness, and visualizer operating immediately.
- Run the official dry-run validator on the reference starter bot.
- Implement an automated "smoke test" script that runs a 10-game headless series in under 5 seconds.
- Create your team's repository with automated branch protections or a clean versioning convention (`bot_v1.py`, `bot_v2.py`).

### Phase 2: Macro-Economics & Expansion (Hours 2–6)
- **Do not touch combat yet.** In strategy games, economy dictates firepower.
- Solve territorial expansion: Build a greedy expansion priority queue based on travel distance and resource yield.
- Establish clean budget partitioning (e.g. 50% expansion, 30% military defense, 20% liquid reserve).
- Ensure your bot never wastes money or sits at max resources while under-developed.

### Phase 3: Tactical Micro & Counter-Drafting (Hours 6–12)
- Implement tactical reconnaissance: Track enemy unit sightings, movement directions, and army sizes in persistent memory.
- Build reactive recruitment: If enemy unit composition is observed, shift production weighting immediately toward its direct counter.
- Implement tactical staging: Never send single isolated units into meat-grinders. Gather strike forces into critical mass thresholds before launching offensive maneuvers.

### Phase 4: State Machine & Meta-Adaptation (Hours 12–18)
- Implement a **Hierarchical Finite State Machine (HFSM)** to shift behaviors across match phases (Early Opening, Mid-Game Expansion, Fortified Standoff, Endgame Objective Rush).
- Add opponent profiling: Detect whether the enemy is a blind rusher, an ultra-passive turtle, or a balanced macro player, and pivot your strategy dynamically.

### Phase 5: Automated Scrimmaging & Balance Testing (Hours 18–22)
- Never rely on visual intuition alone. Build a local automated evaluation script:
  - Run 50 games against your baseline bots.
  - Run 50 games against previous iterations of your own bot (`v4` vs `v3`).
- Track win rate, average game duration, and loss reasons. Reject any change that regresses overall win rate, even if it looks clever in the visualizer.

### Phase 6: Code Freeze & Submission Hardening (Hours 22–24)
- **Absolute code freeze 2 hours before the deadline.** No new features.
- Wrap all core decision routines in defensive `try/catch` blocks with safe fallbacks.
- Verify memory consumption and CPU execution latency per turn.
- Run final validation checks and submit your locked build.

---

## 3. Team Roles & Division of Labor (3 to 4 Person Teams)

| Team Role | Primary Ownership | Deliverables |
|:---|:---|:---|
| **Role 1: Systems & Infrastructure Lead** | Match harness, local CI test runner, visualizer automation, regression tracking. | Automated benchmarking scripts, head-to-head win rate matrix, submission packager. |
| **Role 2: Macro & Economy Strategist** | Pathfinding, territory expansion, resource yield optimization, supply maintenance. | Optimal expansion algorithms, budget managers, dynamic supply calculators. |
| **Role 3: Tactical Micro & Combat Specialist** | Unit composition weighting, target selection, combat simulators, retreat triggers. | Lanchester combat estimators, rock-paper-scissors counter-drafters, squad staging logic. |
| **Role 4: Game Theory & Meta Specialist** | Opponent archetype classification, mixed strategies, objective timing attacks. | State machines, endgame timing triggers, anti-predictability logic. |

---

## 4. Fundamental Bot Architectural Patterns

### Pattern A: Hierarchical Finite State Machine (HFSM)

Organize your agent's macro strategy into clear operational states:

```
               [OPENING EXPANSION]
                       |
            (Territory threshold met)
                       v
               [MID-GAME CONSOLIDATION]
               /                      \
   (Enemy rush detected)       (Relic charging alert)
             v                                v
    [PERIMETER DEFENSE]            [OBJECTIVE CONVERGENCE]
```

- **State Transitions**: Conditioned on unambiguous game flags (`obs.current_turn`, territory ratio, army counts, charging alerts).
- **Sub-States**: Each macro state specifies distinct production ratios, target priorities, and risk tolerance thresholds.

### Pattern B: Utility-Based Scoring Architecture

Instead of hardcoding hundreds of fragile `if/else` statements, evaluate decisions using continuous mathematical utility functions:

$$\text{Utility}(\text{Action}) = \sum_{i} w_i \cdot f_i(\text{Action})$$

For example, when evaluating candidate nodes to expand toward or attack:
$$\text{Score}(N) = w_1 \cdot \frac{\text{Yield}(N)}{\text{Distance}(N)} + w_2 \cdot \text{Vulnerability}(N) - w_3 \cdot \text{ThreatLevel}(N)$$

- **Advantage**: Smooth behavior tuning. You adjust numerical weights ($w_1, w_2, w_3$) rather than rewriting branching code.
- **Priority Queue Execution**: Sort all potential actions by utility score and execute the highest-scoring orders until turn Gold is exhausted.

### Pattern C: The Blackboard & World Model Pattern

In games featuring fog of war, you cannot react to what you do not remember:

- **Allied World Model**: Maintain a dedicated class instance (`self.memory`) that tracks:
  - Last observed location and headcount of enemy units.
  - Estimated travel trajectories of enemy fleets.
  - Node ownership transition timers.
  - Cumulative opponent production tendencies.
- **Decoupled Architecture**: Perception updates the Blackboard at the start of each turn; Decision modules read from the Blackboard to issue orders.

### Pattern D: Mixed Strategies (Game-Theoretic Anti-Exploitation)

Purely deterministic bots are vulnerable to counter-AI (bots designed specifically to dismantle predictable scripts).

- **Seed-Controlled Randomization**: Use a deterministic pseudo-random generator seeded with match metadata:
  ```python
  import random
  rng = random.Random(self.player_id * 1000 + obs.current_turn)
  ```
- **Stochastic Openings**: 70% standard expansion, 30% alternative flank pressure. This forces opponents to defend both wings and prevents hardcoded early counter-ambushes.

---

## 5. Overcoming the "Rock-Paper-Scissors" Trap

In triangular combat games, developing directly against one baseline bot creates severe blind spots:

```
Trained solely against Rusher  -->  Becomes hyper-defensive Turtle
Trained solely against Turtle  -->  Becomes slow, greedy Siege/Macro
Trained solely against Balanced -->  Leaves flanks open to cheap Raids
```

### The Solution: Multi-Opponent Evaluation
- Never consider your bot "improved" because it beat a specific test dummy.
- Measure performance against an **ensemble portfolio**:
  - 10 games vs Rusher
  - 10 games vs Turtle
  - 10 games vs Balanced
  - 10 games vs Your Previous Stable Version
- Only merge changes that maintain or elevate the aggregate portfolio win rate.

---

## 6. Defensive Coding & Execution Safety Rules

### 1. Fail-Safe Order Generation
Wrap order creation in boundary guards. Never assume list indices exist:
```python
path = self.get_path(obs, origin, target)
if len(path) >= 2:
    orders.append(self.move(origin, path[1], units))
```

### 2. Guard Against Resource Overdrafts
Always track remaining currency locally during turn order generation to prevent rejected orders:
```python
remaining_budget = obs.my_credits
for target, unit_type, count in planned_recruitment:
    cost = UNIT_COSTS[unit_type] * count
    if remaining_budget >= cost:
        orders.append(self.train(target, unit_type, count))
        remaining_budget -= cost
```

### 3. Strict Execution Timeout Profiling
- Time your turn calculations locally. If your bot takes 20ms on your laptop, it may take 45ms on the tournament host under system load.
- Avoid expensive operations inside inner loops (e.g. repeated Floyd-Warshall recalculations or deep copy operations). Cache static graph data once upon initialization.

### 4. Zero Console Spam in Final Build
Remove all verbose `print()` statements from your final submitted code. Console I/O is notoriously slow in Python and can cause unexpected turn timeouts.

---

## 7. The Final 2-Hour Pre-Flight Submission Checklist

Complete this checklist before submitting your final bot archive:

- [ ] **Validator Execution**: Bot passes the official dry-run validator with zero warnings or errors.
- [ ] **Symmetric Side Verification**: Bot functions identically whether playing as Player 1 or Player 2 (no hardcoded base IDs or directional biases).
- [ ] **Edge Case Testing**: Tested scenarios where:
  - Home base is under active enemy siege.
  - Treasury is at 0 Gold.
  - Active army count is completely wiped out.
  - All neutral nodes are captured.
- [ ] **Tiebreaker Optimization**: Bot actively banks endgame points and army asset value to win strict deterministic tiebreaks.
- [ ] **Clean Code Packaging**: All imports are part of the standard Python library; no external or untracked local modules required.
- [ ] **Version Tagging**: Final script committed and tagged in your version control repository.

---
*Good luck, engineers. May the most adaptable code prevail!*
