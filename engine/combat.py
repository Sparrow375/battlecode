from __future__ import annotations
import math
from typing import Dict, Tuple, Optional
from .models import UnitType, UNIT_STATS

def calculate_damage(
    attacker_units: Dict[UnitType, int],
    defender_units: Dict[UnitType, int],
    has_friendly_scout: bool = False,
    has_enemy_scout: bool = False
) -> float:
    """
    Calculates total outgoing damage from attacker_units targeted against defender_units.
    Prioritizes countered units (2.0x damage), then same-type/neutral (1.0x), then weak-to (0.5x).
    Applies +15% targeting bonus if friendly scout is present/adjacent, or -15% blind penalty if fighting
    blindly against a scouted enemy army.
    """
    total_defender_count = sum(defender_units.values())
    if total_defender_count == 0:
        return 0.0

    total_damage = 0.0
    for u_type, count in attacker_units.items():
        if count <= 0:
            continue
        stats = UNIT_STATS[u_type]
        base_power = count * stats.attack

        # Determine multiplier based on defender's army composition
        counters = stats.counters
        weak_to = stats.weak_to

        counter_targets = defender_units.get(counters, 0) if counters else 0
        weak_targets = defender_units.get(weak_to, 0) if weak_to else 0
        neutral_targets = total_defender_count - counter_targets - weak_targets

        if counter_targets > 0:
            # High priority: Strike the countered unit
            weight = counter_targets / total_defender_count
            eff_mult = 2.0 * weight + 1.0 * (neutral_targets / total_defender_count) + 0.5 * (weak_targets / total_defender_count)
            eff_mult = max(eff_mult, 1.6)
        elif neutral_targets > 0:
            weight_neutral = neutral_targets / total_defender_count
            weight_weak = weak_targets / total_defender_count
            eff_mult = 1.0 * weight_neutral + 0.5 * weight_weak
        else:
            eff_mult = 0.5

        total_damage += base_power * eff_mult

    # Scout targeting bonus (+15%) or blind penalty (-15%)
    if has_friendly_scout:
        total_damage *= 1.15
    elif has_enemy_scout:
        total_damage *= 0.85

    return total_damage

def apply_damage_to_army(
    army: Dict[UnitType, int],
    damage: float,
    damage_reduction: float = 0.0
) -> Dict[UnitType, int]:
    """
    Applies incoming damage to an army, distributing casualties across unit types.
    damage_reduction: e.g. 0.25 means 25% damage reduction (defenders take 75% damage).
    """
    effective_damage = damage * (1.0 - damage_reduction)
    if effective_damage <= 0 or sum(army.values()) == 0:
        return dict(army)

    # Total HP of the army
    total_hp = sum(count * UNIT_STATS[ut].max_hp for ut, count in army.items())
    if effective_damage >= total_hp:
        # Complete wipeout
        return {ut: 0 for ut in army}

    # Proportional casualties
    remaining_army = dict(army)
    damage_share_ratio = effective_damage / total_hp

    # Deduct casualties with integer rounding
    carried_damage = 0.0
    for ut in [UnitType.RAIDER, UnitType.SIEGE, UnitType.GUARD, UnitType.SCOUT]:
        count = remaining_army.get(ut, 0)
        if count <= 0:
            continue
        hp_per_unit = UNIT_STATS[ut].max_hp
        type_damage = (count * hp_per_unit) * damage_share_ratio + carried_damage
        lost_units = int(type_damage // hp_per_unit)
        rem = type_damage % hp_per_unit
        
        # Round up if more than half damage dealt to the next unit
        if rem >= (hp_per_unit * 0.5) and lost_units < count:
            lost_units += 1
            carried_damage = 0.0
        else:
            carried_damage = rem

        lost_units = min(count, lost_units)
        remaining_army[ut] = count - lost_units

    return remaining_army

def resolve_combat(
    defenders: Dict[UnitType, int],
    attackers: Dict[UnitType, int],
    defender_bonus: float = 0.25,
    max_rounds: int = 10,
    has_defender_scout: bool = False,
    has_attacker_scout: bool = False
) -> Tuple[Dict[UnitType, int], Dict[UnitType, int]]:
    """
    Simulates combat resolution between defenders and attackers.
    Returns (surviving_defenders, surviving_attackers).
    """
    cur_defenders = dict(defenders)
    cur_attackers = dict(attackers)

    def_scout = has_defender_scout or (cur_defenders.get(UnitType.SCOUT, 0) > 0)
    att_scout = has_attacker_scout or (cur_attackers.get(UnitType.SCOUT, 0) > 0)

    for _ in range(max_rounds):
        def_combat_count = cur_defenders.get(UnitType.RAIDER, 0) + cur_defenders.get(UnitType.SIEGE, 0) + cur_defenders.get(UnitType.GUARD, 0)
        att_combat_count = cur_attackers.get(UnitType.RAIDER, 0) + cur_attackers.get(UnitType.SIEGE, 0) + cur_attackers.get(UnitType.GUARD, 0)

        # If one side has no combat units, combat terminates
        if def_combat_count == 0 or att_combat_count == 0:
            break

        # Calculate simultaneous damage with scout modifier
        def_damage = calculate_damage(
            cur_defenders, cur_attackers,
            has_friendly_scout=def_scout,
            has_enemy_scout=att_scout
        )
        att_damage = calculate_damage(
            cur_attackers, cur_defenders,
            has_friendly_scout=att_scout,
            has_enemy_scout=def_scout
        )

        # Apply damage simultaneously (defenders receive damage reduction)
        new_defenders = apply_damage_to_army(cur_defenders, att_damage, damage_reduction=defender_bonus)
        new_attackers = apply_damage_to_army(cur_attackers, def_damage, damage_reduction=0.0)

        # Prevent infinite loop if damage is too low to cause kills
        if new_defenders == cur_defenders and new_attackers == cur_attackers:
            # Force attrition on least favored side
            if def_damage >= att_damage:
                for ut in [UnitType.RAIDER, UnitType.SIEGE, UnitType.GUARD]:
                    if new_attackers.get(ut, 0) > 0:
                        new_attackers[ut] -= 1
                        break
            else:
                for ut in [UnitType.RAIDER, UnitType.SIEGE, UnitType.GUARD]:
                    if new_defenders.get(ut, 0) > 0:
                        new_defenders[ut] -= 1
                        break

        cur_defenders = new_defenders
        cur_attackers = new_attackers

    # If combat units of one side are wiped, any non-combat units (Scouts) are eliminated
    def_combat = cur_defenders.get(UnitType.RAIDER, 0) + cur_defenders.get(UnitType.SIEGE, 0) + cur_defenders.get(UnitType.GUARD, 0)
    att_combat = cur_attackers.get(UnitType.RAIDER, 0) + cur_attackers.get(UnitType.SIEGE, 0) + cur_attackers.get(UnitType.GUARD, 0)

    if def_combat == 0 and att_combat > 0:
        cur_defenders[UnitType.SCOUT] = 0
    elif att_combat == 0 and def_combat > 0:
        cur_attackers[UnitType.SCOUT] = 0

    return cur_defenders, cur_attackers

def resolve_meeting_engagement(
    side_a: Dict[UnitType, int],
    side_b: Dict[UnitType, int],
    has_a_scout: bool = False,
    has_b_scout: bool = False
) -> Tuple[Dict[UnitType, int], Dict[UnitType, int]]:
    """
    Simulates a neutral meeting engagement where neither side receives defender bonus.
    """
    return resolve_combat(
        defenders=side_a,
        attackers=side_b,
        defender_bonus=0.0,
        has_defender_scout=has_a_scout,
        has_attacker_scout=has_b_scout
    )

