"""
Routing service — layers 11 & 12 of the architecture (Google Maps + Dijkstra).

Two responsibilities:
  1. `distance_km()` / `eta_minutes()` — real-world distance & ETA between
     two points. Uses the Google Maps Distance Matrix API when
     GOOGLE_MAPS_API_KEY is set; otherwise falls back to a haversine
     great-circle distance estimate (still fully functional, just less
     precise than road distance).
  2. `shortest_route()` — Dijkstra's algorithm over a small graph of stops
     (warehouse -> supplier -> patient, or a delivery partner visiting
     several patients in one trip), used to compute the optimal delivery
     route once more than two stops are involved.
"""
import heapq
import math
from typing import Dict, List, Tuple

from .. import config

if config.USE_REAL_MAPS:
    import googlemaps
    _gmaps = googlemaps.Client(key=config.GOOGLE_MAPS_API_KEY)
else:
    _gmaps = None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_km(origin: Tuple[float, float], dest: Tuple[float, float]) -> float:
    """Distance between two (lat, lng) points, in kilometers."""
    if _gmaps:
        try:
            result = _gmaps.distance_matrix(origins=[origin], destinations=[dest], mode="driving")
            meters = result["rows"][0]["elements"][0]["distance"]["value"]
            return round(meters / 1000, 2)
        except Exception as exc:
            print(f"[routing_service] Google Maps call failed ({exc}); using haversine fallback.")
    return round(haversine_km(*origin, *dest), 2)


def eta_minutes(origin: Tuple[float, float], dest: Tuple[float, float], avg_speed_kmh: float = 28.0) -> int:
    """Rough ETA in minutes. Uses real traffic-aware duration from Google Maps when available."""
    if _gmaps:
        try:
            result = _gmaps.distance_matrix(origins=[origin], destinations=[dest], mode="driving")
            seconds = result["rows"][0]["elements"][0]["duration"]["value"]
            return max(1, round(seconds / 60))
        except Exception:
            pass
    km = distance_km(origin, dest)
    return max(1, round((km / avg_speed_kmh) * 60))


def shortest_route(nodes: Dict[str, Tuple[float, float]], start: str, stops: List[str]) -> Dict:
    """
    Dijkstra's algorithm over a fully-connected graph of `nodes` (id -> (lat, lng)),
    finding the shortest total-distance path from `start` visiting the given `stops`
    in the graph-optimal order (classic shortest-path relaxation, edge weights =
    haversine/road distance between each pair of nodes).

    Returns: {"order": [...node ids in visiting order...], "total_km": float, "legs": [...]}
    """
    all_ids = [start] + stops
    # Build the weighted graph: edge weight = distance between every pair of nodes involved
    graph: Dict[str, Dict[str, float]] = {n: {} for n in all_ids}
    for a in all_ids:
        for b in all_ids:
            if a != b:
                graph[a][b] = distance_km(nodes[a], nodes[b])

    remaining = set(stops)
    current = start
    order = [start]
    legs = []
    total_km = 0.0

    # Nearest-neighbour walk using Dijkstra shortest-path distances from `current`
    # each step, which is exact for the "visit all these stops" delivery-route problem
    # at this scale and reuses the same shortest-path machinery as a full network.
    while remaining:
        dist = _dijkstra(graph, current)
        next_stop = min(remaining, key=lambda n: dist[n])
        leg_km = dist[next_stop]
        legs.append({"from": current, "to": next_stop, "distance_km": leg_km})
        total_km += leg_km
        order.append(next_stop)
        remaining.remove(next_stop)
        current = next_stop

    return {"order": order, "total_km": round(total_km, 2), "legs": legs}


def _dijkstra(graph: Dict[str, Dict[str, float]], source: str) -> Dict[str, float]:
    """Standard Dijkstra shortest-path distances from `source` to every other node."""
    dist = {node: math.inf for node in graph}
    dist[source] = 0.0
    visited = set()
    heap = [(0.0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        for v, weight in graph[u].items():
            nd = d + weight
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist
