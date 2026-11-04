from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from .models import Node, Lane, PlayerId, UnitType

def create_default_map() -> Tuple[Dict[int, Node], List[Lane]]:
    """
    Creates the official mirrored 15-node tournament map for Node War.
    Mirrored horizontally across X=50.
    """
    nodes_data = [
        # (id, name, x, y, owner, production)
        (0, "P1 Core", 10.0, 50.0, PlayerId.PLAYER_1, 15),
        (1, "Alpha Bastion", 25.0, 25.0, PlayerId.NONE, 6),
        (2, "Gamma Bastion", 25.0, 75.0, PlayerId.NONE, 6),
        (3, "Vanguard Gate", 32.0, 50.0, PlayerId.NONE, 8),
        (4, "North Rig", 40.0, 15.0, PlayerId.NONE, 5),
        (5, "North Outpost", 45.0, 35.0, PlayerId.NONE, 7),
        (6, "South Outpost", 45.0, 65.0, PlayerId.NONE, 7),
        
        # Center Relic Sanctuary
        (7, "Relic Sanctuary", 50.0, 50.0, PlayerId.NONE, 4),
        
        # P2 Mirrored Nodes (100 - x)
        (8, "Titan Outpost", 55.0, 65.0, PlayerId.NONE, 7),
        (9, "Zenith Outpost", 55.0, 35.0, PlayerId.NONE, 7),
        (10, "Apex Rig", 60.0, 15.0, PlayerId.NONE, 5),
        (11, "Sentinel Gate", 68.0, 50.0, PlayerId.NONE, 8),
        (12, "Omega Bastion", 75.0, 75.0, PlayerId.NONE, 6),
        (13, "Epsilon Bastion", 75.0, 25.0, PlayerId.NONE, 6),
        (14, "P2 Core", 90.0, 50.0, PlayerId.PLAYER_2, 15),
    ]

    nodes: Dict[int, Node] = {}
    for nid, name, x, y, owner, prod in nodes_data:
        # Give home bases some starting garrison
        garrison = {UnitType.RAIDER: 0, UnitType.SIEGE: 0, UnitType.GUARD: 0, UnitType.SCOUT: 0}
        if owner == PlayerId.PLAYER_1 or owner == PlayerId.PLAYER_2:
            garrison[UnitType.GUARD] = 1
            garrison[UnitType.RAIDER] = 1
            garrison[UnitType.SCOUT] = 1

        nodes[nid] = Node(
            id=nid,
            name=name,
            x=x,
            y=y,
            owner=owner,
            production=prod,
            units=garrison,
            defense_bonus=0.25,
            capture_progress=0,
            capturing_player=PlayerId.NONE,
            resident_player=owner
        )

    # Lanes with travel times in turns
    lane_pairs = [
        # P1 local web
        (0, 1, 2),
        (0, 2, 2),
        (0, 3, 3),
        (1, 3, 2),
        (2, 3, 2),
        (1, 4, 2),
        (1, 5, 2),
        (2, 6, 2),
        (4, 5, 2),
        (3, 5, 2),
        (3, 6, 2),

        # Center bridge lanes
        (5, 7, 2),
        (6, 7, 2),
        (3, 7, 3),
        (5, 9, 2),
        (6, 8, 2),
        (4, 10, 3),

        # P2 local web (mirrored)
        (14, 13, 2),
        (14, 12, 2),
        (14, 11, 3),
        (13, 11, 2),
        (12, 11, 2),
        (13, 10, 2),
        (13, 9, 2),
        (12, 8, 2),
        (10, 9, 2),
        (11, 9, 2),
        (11, 8, 2),

        # P2 to Center
        (9, 7, 2),
        (8, 7, 2),
        (11, 7, 3),
    ]

    lanes: List[Lane] = [Lane(u, v, t) for u, v, t in lane_pairs]
    return nodes, lanes

class MapGraph:
    """Helper graph structure for pathfinding and adjacency lookups."""
    def __init__(self, nodes: Dict[int, Node], lanes: List[Lane]):
        self.nodes = nodes
        self.lanes = lanes
        self.adj: Dict[int, List[Tuple[int, int]]] = {nid: [] for nid in nodes}
        for lane in lanes:
            self.adj[lane.node_a].append((lane.node_b, lane.travel_turns))
            self.adj[lane.node_b].append((lane.node_a, lane.travel_turns))
        
        # Precompute all-pairs shortest paths using Floyd-Warshall
        self._dist: Dict[Tuple[int, int], int] = {}
        self._next_hop: Dict[Tuple[int, int], Optional[int]] = {}
        self._compute_all_pairs_shortest_path()

    def get_lane(self, u: int, v: int) -> Optional[Lane]:
        for lane in self.lanes:
            if lane.connects(u, v):
                return lane
        return None

    def get_neighbors(self, u: int) -> List[int]:
        return [v for v, _ in self.adj[u]]

    def get_distance(self, u: int, v: int) -> int:
        return self._dist.get((u, v), 999999)

    def get_next_step(self, u: int, v: int) -> Optional[int]:
        """Returns the next immediate node on the shortest path from u to v."""
        if u == v:
            return None
        return self._next_hop.get((u, v))

    def get_path(self, u: int, v: int) -> List[int]:
        if u == v:
            return [u]
        if self._next_hop.get((u, v)) is None:
            return []
        path = [u]
        curr = u
        while curr != v:
            nxt = self._next_hop.get((curr, v))
            if nxt is None:
                return []
            path.append(nxt)
            curr = nxt
        return path

    def _compute_all_pairs_shortest_path(self) -> None:
        node_ids = list(self.nodes.keys())
        inf = 999999
        for u in node_ids:
            for v in node_ids:
                if u == v:
                    self._dist[(u, v)] = 0
                    self._next_hop[(u, v)] = None
                else:
                    self._dist[(u, v)] = inf
                    self._next_hop[(u, v)] = None

        for lane in self.lanes:
            u, v, w = lane.node_a, lane.node_b, lane.travel_turns
            if w < self._dist[(u, v)]:
                self._dist[(u, v)] = w
                self._dist[(v, u)] = w
                self._next_hop[(u, v)] = v
                self._next_hop[(v, u)] = u

        for k in node_ids:
            for i in node_ids:
                for j in node_ids:
                    if self._dist[(i, k)] + self._dist[(k, j)] < self._dist[(i, j)]:
                        self._dist[(i, j)] = self._dist[(i, k)] + self._dist[(k, j)]
                        self._next_hop[(i, j)] = self._next_hop[(i, k)]
