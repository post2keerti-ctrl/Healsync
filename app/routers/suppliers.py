"""
Supplier-facing endpoints — order queue, inventory, ranking score, and a
Dijkstra-optimized multi-stop delivery route across all of a supplier's
currently accepted orders (layers 11-13 of the architecture in action).
"""
from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from .. import database as db, schemas
from ..services import matching_service, routing_service
from .auth import require_role

router = APIRouter(prefix="/suppliers", tags=["Supplier App"])


def _profile(user: dict) -> dict:
    p = db.supplier_profiles.find_one({"user_id": user["_id"]})
    if not p:
        raise HTTPException(status_code=404, detail="Supplier profile not found")
    return p


def _order_out(o: dict, supplier_name: str) -> schemas.OrderOut:
    return schemas.OrderOut(
        id=str(o["_id"]), reference=o["reference"], status=o["status"], items=o["items"],
        total_amount=o["total_amount"], supplier_name=supplier_name, match_score=o["match_score"],
        distance_km=o.get("distance_km"), created_at=o["created_at"],
    )


@router.get("/me/orders", response_model=List[schemas.OrderOut])
def list_orders(user: dict = Depends(require_role("supplier"))):
    profile = _profile(user)
    orders = db.orders.find({"supplier_id": profile["_id"]}).sort("created_at", -1)
    return [_order_out(o, profile["business_name"]) for o in orders]


@router.post("/orders/{order_id}/accept", response_model=schemas.OrderOut)
def accept_order(order_id: str, user: dict = Depends(require_role("supplier"))):
    profile = _profile(user)
    order = db.orders.find_one({"_id": ObjectId(order_id), "supplier_id": profile["_id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] != "new":
        raise HTTPException(status_code=400, detail=f"Order is already '{order['status']}'")

    db.orders.update_one({"_id": order["_id"]}, {"$set": {"status": "accepted"}})
    order["status"] = "accepted"
    return _order_out(order, profile["business_name"])


@router.post("/orders/{order_id}/decline", response_model=schemas.OrderOut)
def decline_order(order_id: str, user: dict = Depends(require_role("supplier"))):
    profile = _profile(user)
    order = db.orders.find_one({"_id": ObjectId(order_id), "supplier_id": profile["_id"]})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.orders.update_one({"_id": order["_id"]}, {"$set": {"status": "declined"}})
    order["status"] = "declined"
    return _order_out(order, profile["business_name"])


@router.get("/me/inventory", response_model=List[schemas.InventoryItemOut])
def get_inventory(user: dict = Depends(require_role("supplier"))):
    profile = _profile(user)
    items = db.inventory_items.find({"supplier_id": profile["_id"]})
    return [schemas.InventoryItemOut(id=str(i["_id"]), name=i["name"], stock_pct=i["stock_pct"], unit_price=i["unit_price"]) for i in items]


@router.put("/me/inventory/{item_id}", response_model=schemas.InventoryItemOut)
def update_inventory_item(item_id: str, payload: schemas.InventoryItemUpdate, user: dict = Depends(require_role("supplier"))):
    profile = _profile(user)
    update = {k: v for k, v in payload.dict().items() if v is not None}
    result = db.inventory_items.find_one_and_update(
        {"_id": ObjectId(item_id), "supplier_id": profile["_id"]}, {"$set": update}, return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return schemas.InventoryItemOut(id=str(result["_id"]), name=result["name"], stock_pct=result["stock_pct"], unit_price=result["unit_price"])


@router.get("/me/score", response_model=schemas.SupplierScoreOut)
def get_score(user: dict = Depends(require_role("supplier"))):
    profile = _profile(user)
    all_suppliers = list(db.supplier_profiles.find({}))
    # Rank against a representative patient location (Chennai city center) for a stable demo score.
    reference_point = (13.0827, 80.2707)

    candidates = []
    for s in all_suppliers:
        inv = list(db.inventory_items.find({"supplier_id": s["_id"]}))
        avg_stock = sum(i["stock_pct"] for i in inv) / len(inv) if inv else 100.0
        candidates.append({
            "id": str(s["_id"]), "name": s["business_name"],
            "location": (s.get("location") or {"lat": 13.0827, "lng": 80.2707}).values(),
            "avg_stock_pct": avg_stock, "avg_item_cost": s.get("avg_item_cost", 6.0),
            "avg_dispatch_hours": s.get("avg_dispatch_hours", 4.0),
        })
    for c in candidates:
        c["location"] = tuple(c["location"])

    ranked = matching_service.rank_suppliers(candidates, reference_point)
    my_rank = next((i + 1 for i, c in enumerate(ranked) if c["id"] == str(profile["_id"])), len(ranked))
    mine = next(c for c in ranked if c["id"] == str(profile["_id"]))

    return schemas.SupplierScoreOut(
        rank=my_rank, total_suppliers=len(ranked), score=mine["score"],
        stock_availability_pct=round(mine["avg_stock_pct"], 1), distance_km=mine["distance_km"],
        avg_item_cost=profile.get("avg_item_cost", 6.0), avg_dispatch_hours=profile.get("avg_dispatch_hours", 4.0),
    )


@router.get("/me/delivery-route", response_model=schemas.RouteOut)
def get_delivery_route(user: dict = Depends(require_role("supplier"))):
    """
    Dijkstra's algorithm plans the shortest total-distance route for a
    delivery partner visiting every one of this supplier's currently
    'accepted' orders in one trip, starting from the supplier's location.
    """
    profile = _profile(user)
    accepted = list(db.orders.find({"supplier_id": profile["_id"], "status": "accepted"}))
    if not accepted:
        raise HTTPException(status_code=404, detail="No accepted orders to route right now")

    nodes = {"supplier": tuple((profile.get("location") or {"lat": 13.0827, "lng": 80.2707}).values())}
    stop_ids = []
    for o in accepted:
        patient = db.patient_profiles.find_one({"_id": o["patient_id"]})
        loc = patient.get("location") if patient else None
        node_id = o["reference"]
        nodes[node_id] = tuple((loc or {"lat": 13.0827, "lng": 80.2707}).values())
        stop_ids.append(node_id)

    route = routing_service.shortest_route(nodes, "supplier", stop_ids)
    return schemas.RouteOut(
        order=route["order"], total_km=route["total_km"],
        legs=[schemas.RouteLegOut(**leg) for leg in route["legs"]],
    )
