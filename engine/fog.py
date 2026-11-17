from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from .models import PlayerId, UnitType, Fleet, Node, Lane

@dataclass
class VisibleFleet:
    id: int
    owner: int
    origin_node: int
    dest_node: int
    turns_remaining: int
    total_turns: int
    total_count: int
    is_revealed: bool
    units: Optional[Dict[str, int]]  # None if hidden, otherwise dict of unit counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "owner": self.owner,
            "origin_node": self.origin_node,
            "dest_node": self.dest_node,
            "turns_remaining": self.turns_remaining,
            "total_turns": self.total_turns,
            "total_count": self.total_count,
            "is_revealed": self.is_revealed,
            "units": self.units
        }

@dataclass
class VisibleNode:
    id: int
    name: str
    x: float
    y: float
    owner: int
    production: int
    defense_bonus: float
    capture_progress: int
    capturing_player: int
    units: Optional[Dict[str, int]]  # Visible if owned or scouted/adjacent
    is_scouted: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "owner": self.owner,
            "production": self.production,
            "defense_bonus": self.defense_bonus,
            "capture_progress": self.capture_progress,
            "capturing_player": self.capturing_player,
            "units": self.units,
            "is_scouted": self.is_scouted
        }

@dataclass
class BotObservation:
    current_turn: int
    max_turns: int
    my_player_id: int
    my_credits: int
    my_score: int
    opponent_score: int
    relic_active: bool
    relic_node_id: int
    nodes: Dict[int, VisibleNode]
    lanes: List[Dict[str, Any]]
    my_fleets: List[VisibleFleet]
    enemy_fleets: List[VisibleFleet]
    relic_charging: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_turn": self.current_turn,
            "max_turns": self.max_turns,
            "my_player_id": self.my_player_id,
            "my_credits": self.my_credits,
            "my_score": self.my_score,
            "opponent_score": self.opponent_score,
            "relic_active": self.relic_active,
            "relic_charging": self.relic_charging,
            "relic_node_id": self.relic_node_id,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "lanes": self.lanes,
            "my_fleets": [f.to_dict() for f in self.my_fleets],
            "enemy_fleets": [f.to_dict() for f in self.enemy_fleets],
        }

def generate_player_observation(
    player_id: PlayerId,
    turn: int,
    max_turns: int,
    player_credits: int,
    scores: Dict[PlayerId, int],
    relic_active: bool,
    relic_node_id: int,
    nodes: Dict[int, Node],
    lanes: List[Lane],
    fleets: List[Fleet],
    relic_charging: bool = False
) -> BotObservation:
    """
    Creates a fog-of-war filtered observation for the given player.
    Enemy fleet compositions are masked unless scouted.
    """
    opponent_id = player_id.opponent

    # Determine nodes where player has scouting vision
    # A node is scouted by player if player owns it, or has stationed scouts,
    # or has an incoming fleet with a scout arriving or adjacent
    scouted_nodes = set()
    for nid, node in nodes.items():
        if node.owner == player_id:
            scouted_nodes.add(nid)
        elif node.units.get(UnitType.SCOUT, 0) > 0 and node.owner == player_id:
            scouted_nodes.add(nid)

    # Check fleets carrying scouts for adjacent lane vision
    scouted_lanes = set()
    for fleet in fleets:
        if fleet.owner == player_id and fleet.has_scout:
            scouted_lanes.add((fleet.origin_node, fleet.dest_node))
            scouted_lanes.add((fleet.dest_node, fleet.origin_node))

    # Also, any node with an allied scout grants vision over all connected lanes
    for nid in scouted_nodes:
        for lane in lanes:
            other = lane.get_other(nid)
            if other is not None and nodes[nid].has_scout:
                scouted_lanes.add((nid, other))
                scouted_lanes.add((other, nid))

    # Process nodes
    visible_nodes: Dict[int, VisibleNode] = {}
    for nid, node in nodes.items():
        is_scouted = (node.owner == player_id) or (nid in scouted_nodes)
        
        # Check if any adjacent node is owned or scouted
        adjacent_visibility = False
        for lane in lanes:
            other = lane.get_other(nid)
            if other is not None and other in scouted_nodes:
                adjacent_visibility = True
                break

        units_dict = {ut.value: count for ut, count in node.units.items()} if (is_scouted or adjacent_visibility) else None

        visible_nodes[nid] = VisibleNode(
            id=node.id,
            name=node.name,
            x=node.x,
            y=node.y,
            owner=int(node.owner),
            production=node.production,
            defense_bonus=node.defense_bonus,
            capture_progress=node.capture_progress,
            capturing_player=int(node.capturing_player),
            units=units_dict,
            is_scouted=is_scouted
        )

    # Process fleets
    my_fleets: List[VisibleFleet] = []
    enemy_fleets: List[VisibleFleet] = []

    for fleet in fleets:
        if fleet.owner == player_id:
            my_fleets.append(VisibleFleet(
                id=fleet.id,
                owner=int(fleet.owner),
                origin_node=fleet.origin_node,
                dest_node=fleet.dest_node,
                turns_remaining=fleet.turns_remaining,
                total_turns=fleet.total_turns,
                total_count=fleet.total_count,
                is_revealed=True,
                units={ut.value: count for ut, count in fleet.units.items()}
            ))
        else:
            # Enemy fleet - check if revealed by scout
            lane_key = (fleet.origin_node, fleet.dest_node)
            is_revealed = (lane_key in scouted_lanes) or (fleet.dest_node in scouted_nodes and nodes[fleet.dest_node].has_scout)

            enemy_fleets.append(VisibleFleet(
                id=fleet.id,
                owner=int(fleet.owner),
                origin_node=fleet.origin_node,
                dest_node=fleet.dest_node,
                turns_remaining=fleet.turns_remaining,
                total_turns=fleet.total_turns,
                total_count=fleet.total_count,
                is_revealed=is_revealed,
                units={ut.value: count for ut, count in fleet.units.items()} if is_revealed else None
            ))

    lanes_data = [lane.to_dict() for lane in lanes]

    return BotObservation(
        current_turn=turn,
        max_turns=max_turns,
        my_player_id=int(player_id),
        my_credits=player_credits,
        my_score=scores.get(player_id, 0),
        opponent_score=scores.get(opponent_id, 0),
        relic_active=relic_active,
        relic_charging=relic_charging,
        relic_node_id=relic_node_id,
        nodes=visible_nodes,
        lanes=lanes_data,
        my_fleets=my_fleets,
        enemy_fleets=enemy_fleets
    )

