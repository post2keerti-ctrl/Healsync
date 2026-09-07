"""
Supplier matching service — layer 13 of the architecture
(Weighting Score Algorithm -> "Best supplier based on availability, price...").

Same weighted-score idea as the prototype's "Best Supplier" screen, but now
also folds in real geographic distance via `routing_service.distance_km()`
(Google Maps when configured, haversine fallback otherwise) instead of a
stored static number.
"""
from typing import Dict, List, Tuple

from . import routing_service

# Tune these to match real business priorities.
WEIGHTS = {"stock": 0.35, "distance": 0.25, "cost": 0.20, "speed": 0.20}


def score_supplier(
    avg_stock_pct: float,
    supplier_location: Tuple[float, float],
    patient_location: Tuple[float, float],
    avg_item_cost: float,
    avg_dispatch_hours: float,
) -> Dict:
    dist_km = routing_service.distance_km(supplier_location, patient_location)

    stock_score = avg_stock_pct / 100
    distance_score = max(0.0, 1 - dist_km / 20)
    cost_score = max(0.0, 1 - avg_item_cost / 15)
    speed_score = max(0.0, 1 - avg_dispatch_hours / 12)

    weighted = (
        WEIGHTS["stock"] * stock_score
        + WEIGHTS["distance"] * distance_score
        + WEIGHTS["cost"] * cost_score
        + WEIGHTS["speed"] * speed_score
    )
    return {
        "score": round(weighted, 3),
        "distance_km": dist_km,
        "stock_score": round(stock_score, 2),
        "distance_score": round(distance_score, 2),
        "cost_score": round(cost_score, 2),
        "speed_score": round(speed_score, 2),
    }


def rank_suppliers(candidates: List[Dict], patient_location: Tuple[float, float]) -> List[Dict]:
    """
    `candidates`: list of dicts with keys:
        id, name, location (lat,lng), avg_stock_pct, avg_item_cost, avg_dispatch_hours
    Returns the same list, each augmented with its score breakdown, sorted best-first.
    """
    ranked = []
    for c in candidates:
        breakdown = score_supplier(
            c["avg_stock_pct"], c["location"], patient_location, c["avg_item_cost"], c["avg_dispatch_hours"],
        )
        ranked.append({**c, **breakdown})
    ranked.sort(key=lambda c: c["score"], reverse=True)
    return ranked
