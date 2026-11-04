from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from engine.models import UnitType, TrainOrder, MoveOrder, Order
from engine.fog import BotObservation, VisibleNode, VisibleFleet

class BotBase(ABC):
    def __init__(self, player_id: int):
        self.player_id: int = player_id
        self.opponent_id: int = 2 if player_id == 1 else 1
        self._graph_cache: Optional[Dict[Tuple[int, int], int]] = None
        self._adj_cache: Optional[Dict[int, List[Tuple[int, int]]]] = None

    @abstractmethod
    def act(self, obs: BotObservation) -> List[Order]:
        """
        Receives the current turn observation and returns a list of orders.
        """
        pass

    # ==========================================
    # Helper Utilities for Bot Authors
    # ==========================================

    def get_my_nodes(self, obs: BotObservation) -> List[VisibleNode]:
        return [node for node in obs.nodes.values() if node.owner == self.player_id]

    def get_enemy_nodes(self, obs: BotObservation) -> List[VisibleNode]:
        return [node for node in obs.nodes.values() if node.owner == self.opponent_id]

    def get_neutral_nodes(self, obs: BotObservation) -> List[VisibleNode]:
        return [node for node in obs.nodes.values() if node.owner == 0]

    def get_neighbors(self, obs: BotObservation, node_id: int) -> List[int]:
        self._ensure_graph(obs)
        return [other for other, _ in self._adj_cache.get(node_id, [])]

    def get_distance(self, obs: BotObservation, u: int, v: int) -> int:
        self._ensure_graph(obs)
        return self._graph_cache.get((u, v), 999999)

    def get_path(self, obs: BotObservation, u: int, v: int) -> List[int]:
        """Returns shortest path sequence of node IDs from u to v."""
        self._ensure_graph(obs)
        if u == v:
            return [u]
        
        # Simple BFS / Dijkstra
        import heapq
        queue = [(0, u, [u])]
        visited = set()
        while queue:
            dist, curr, path = heapq.heappop(queue)
            if curr == v:
                return path
            if curr in visited:
                continue
            visited.add(curr)
            for nxt, weight in self._adj_cache.get(curr, []):
                if nxt not in visited:
                    heapq.heappush(queue, (dist + weight, nxt, path + [nxt]))
        return []

    def train(self, node_id: int, unit_type: UnitType | str, count: int) -> TrainOrder:
        ut = UnitType(unit_type) if isinstance(unit_type, str) else unit_type
        return TrainOrder(node_id=node_id, unit_type=ut, count=count)

    def move(self, origin_node: int, dest_node: int, units: Dict[UnitType | str, int]) -> MoveOrder:
        norm_units: Dict[UnitType, int] = {}
        for k, v in units.items():
            ut = UnitType(k) if isinstance(k, str) else k
            if v > 0:
                norm_units[ut] = v
        return MoveOrder(origin_node=origin_node, dest_node=dest_node, units=norm_units)

    def _ensure_graph(self, obs: BotObservation) -> None:
        if self._graph_cache is not None and self._adj_cache is not None:
            return

        adj: Dict[int, List[Tuple[int, int]]] = {nid: [] for nid in obs.nodes}
        for lane in obs.lanes:
            u, v, t = lane["node_a"], lane["node_b"], lane["travel_turns"]
            adj[u].append((v, t))
            adj[v].append((u, t))
        self._adj_cache = adj

        # Compute all-pairs shortest paths
        node_ids = list(obs.nodes.keys())
        inf = 999999
        dist: Dict[Tuple[int, int], int] = {}
        for u in node_ids:
            for v in node_ids:
                dist[(u, v)] = 0 if u == v else inf

        for lane in obs.lanes:
            u, v, t = lane["node_a"], lane["node_b"], lane["travel_turns"]
            dist[(u, v)] = min(dist[(u, v)], t)
            dist[(v, u)] = min(dist[(v, u)], t)

        for k in node_ids:
            for i in node_ids:
                for j in node_ids:
                    if dist[(i, k)] + dist[(k, j)] < dist[(i, j)]:
                        dist[(i, j)] = dist[(i, k)] + dist[(k, j)]

        self._graph_cache = dist
