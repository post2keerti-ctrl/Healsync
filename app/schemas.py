"""Pydantic schemas — request/response shapes for every endpoint."""
from datetime import datetime
from typing import List, Optional, Tuple

from pydantic import BaseModel, EmailStr, Field


class Location(BaseModel):
    lat: float
    lng: float


# ---------- Auth ----------
class DevLoginRequest(BaseModel):
    email: EmailStr
    password: str  # not checked for real strength — dev-only convenience login


class SyncProfileRequest(BaseModel):
    name: str
    role: str = Field(pattern="^(patient|doctor|supplier)$")
    location: Optional[Location] = None
    device_token: Optional[str] = ""  # FCM device token registered by the Flutter app


class UserOut(BaseModel):
    id: str
    firebase_uid: str
    name: str
    email: str
    role: str


# ---------- Patient ----------
class RecoveryPlanItemOut(BaseModel):
    id: str
    day: int
    time: str
    title: str
    description: str
    category: str
    doctor_adjusted: bool = False


class DashboardOut(BaseModel):
    patient_name: str
    recovery_day: int
    recovery_total_days: int
    confidence_score: int
    doctor_name: Optional[str]
    today_items: List[RecoveryPlanItemOut]
    active_order_reference: Optional[str]


class DocumentOut(BaseModel):
    id: str
    filename: str
    ocr_text: str
    nlp_pipeline_mode: str
    extracted_medicines: list
    generated_plan_items: int
    uploaded_at: datetime


class CartItemOut(BaseModel):
    name: str
    category: str
    qty: int
    unit_price: float
    subtotal: float


class CartOut(BaseModel):
    items: List[CartItemOut]
    total_amount: float


class OrderOut(BaseModel):
    id: str
    reference: str
    status: str
    items: list
    total_amount: float
    supplier_name: Optional[str] = None
    match_score: float
    distance_km: Optional[float] = None
    eta_minutes: Optional[int] = None
    created_at: datetime


class AlertOut(BaseModel):
    id: str
    severity: str
    message: str
    resolved: bool
    created_at: datetime


# ---------- Doctor ----------
class PatientSummaryOut(BaseModel):
    id: str
    name: str
    surgery_type: str
    recovery_day: int
    confidence_score: int
    flagged: bool


class PlanAdjustment(BaseModel):
    item_id: str
    time: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


class PlanReview(BaseModel):
    adjustments: List[PlanAdjustment] = []
    approve: bool = True


# ---------- Supplier ----------
class InventoryItemOut(BaseModel):
    id: str
    name: str
    stock_pct: int
    unit_price: float


class InventoryItemUpdate(BaseModel):
    stock_pct: Optional[int] = None
    unit_price: Optional[float] = None


class SupplierScoreOut(BaseModel):
    rank: int
    total_suppliers: int
    score: float
    stock_availability_pct: float
    distance_km: float
    avg_item_cost: float
    avg_dispatch_hours: float


# ---------- Routing ----------
class RouteRequest(BaseModel):
    stop_ids: List[str]  # order ids (or patient ids) to visit, in any order


class RouteLegOut(BaseModel):
    from_: str = Field(alias="from")
    to: str
    distance_km: float

    class Config:
        populate_by_name = True


class RouteOut(BaseModel):
    order: List[str]
    total_km: float
    legs: List[RouteLegOut]
