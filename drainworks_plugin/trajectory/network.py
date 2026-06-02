"""Sewer network graph + Dijkstra shortest path over manholes.

Edge weight is pipe length (meters). Pure Python; no QGIS, no networkx.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Optional


@dataclass
class Path:
    """A route through the network."""

    manholes: list = field(default_factory=list)   # ordered manhole codes
    pipe_codes: list = field(default_factory=list)  # pipe per consecutive pair
    total_length: float = 0.0


class SewerNetwork:
    """Undirected weighted graph of manholes connected by pipes."""

    def __init__(self, pipes) -> None:
        # node -> list of (neighbor, pipe_code, weight)
        self._adj = defaultdict(list)
        for pipe in pipes:
            weight = pipe.length if pipe.length is not None else 1.0
            if weight <= 0:
                weight = 1.0
            self._adj[pipe.manhole1].append((pipe.manhole2, pipe.code, weight))
            self._adj[pipe.manhole2].append((pipe.manhole1, pipe.code, weight))

    def shortest_path(self, start: str, end: str) -> Path:
        """Dijkstra shortest path from ``start`` to ``end`` manhole."""
        if start not in self._adj:
            raise ValueError(f"Unknown manhole: {start}")
        dist = {start: 0.0}
        prev = {}            # node -> (prev_node, pipe_code)
        heap = [(0.0, start)]
        visited = set()

        while heap:
            d, node = heappop(heap)
            if node in visited:
                continue
            visited.add(node)
            if node == end:
                break
            for neighbor, pipe_code, weight in self._adj[node]:
                if neighbor in visited:
                    continue
                nd = d + weight
                if nd < dist.get(neighbor, float("inf")):
                    dist[neighbor] = nd
                    prev[neighbor] = (node, pipe_code)
                    heappush(heap, (nd, neighbor))

        if end not in dist:
            raise ValueError(f"No path from {start} to {end}")

        # Reconstruct.
        manholes = [end]
        pipe_codes = []
        cur = end
        while cur != start:
            pnode, pcode = prev[cur]
            pipe_codes.append(pcode)
            manholes.append(pnode)
            cur = pnode
        manholes.reverse()
        pipe_codes.reverse()
        return Path(manholes=manholes, pipe_codes=pipe_codes, total_length=dist[end])

    def route(self, waypoints: list) -> Path:
        """Chain shortest paths through an ordered list of manhole waypoints."""
        if len(waypoints) < 2:
            raise ValueError("Need at least two waypoints")
        full = Path(manholes=[waypoints[0]], pipe_codes=[], total_length=0.0)
        for a, b in zip(waypoints, waypoints[1:]):
            leg = self.shortest_path(a, b)
            full.manholes.extend(leg.manholes[1:])
            full.pipe_codes.extend(leg.pipe_codes)
            full.total_length += leg.total_length
        return full
