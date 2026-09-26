"""Patient endpoints backed by the new repository boundary."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from .auth import current_claims
from .config import MAX_UPLOAD_BYTES, USE_FIRESTORE
from .contracts import UserRecord
from .repositories import patient_repository, user_repository
from .db.sqlite import SQLiteDatabase
from .db.firestore_data import collection, records
from .firebase import firestore_client, storage_bucket

router = APIRouter(prefix="/api/v1/patients", tags=["Patients"])
_OCR_ENGINE = None


def current_patient(claims: dict = Depends(current_claims)):
    users = user_repository()
    user = users.get_by_firebase_uid(claims["uid"])
    if user is None:
        user = users.create_or_update(UserRecord(
            id="", firebase_uid=claims["uid"], email=claims.get("email", ""),
            name=claims.get("name") or claims.get("email", "").split("@")[0], role="patient",
        ))
    if user.role != "patient":
        raise HTTPException(status_code=403, detail="Patient access required")
    profile = patient_repository().get_by_user_id(user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Patient profile not found")
    return user, profile


@router.get("/me/recovery-plan")
def recovery_plan(patient=Depends(current_patient)):
    _, profile = patient
    items = patient_repository().recovery_items(profile.id)
    return [item.__dict__ for item in items]


@router.get("/me/alerts")
def alerts(patient=Depends(current_patient)):
    _, profile = patient
    return [alert.__dict__ for alert in patient_repository().alerts(profile.id)]


@router.get("/me/dashboard")
def dashboard(patient=Depends(current_patient)):
    user, profile = patient
    items = patient_repository().recovery_items(profile.id, profile.recovery_day)
    doctor_name = None
    if USE_FIRESTORE:
        client = firestore_client()
        if profile.doctor_id:
            doctor = collection(client, "doctor_profiles").document(profile.doctor_id).get()
            if doctor.exists:
                doctor_user = collection(client, "users").document(doctor.to_dict().get("user_id", "")).get()
                doctor_name = doctor_user.to_dict().get("name") if doctor_user.exists else None
        patient_orders = records(client, "orders", patient_id=profile.id)
        patient_orders.sort(key=lambda row: row.get("created_at", ""), reverse=True)
        active_order_reference = patient_orders[0].get("reference") if patient_orders else None
    else:
        with SQLiteDatabase() as database:
            database.initialize()
            doctor = database.execute(
                """
                SELECT clinician.name
                FROM patient_profiles patient
                JOIN doctor_profiles doctor ON doctor.id = patient.doctor_id
                JOIN users clinician ON clinician.id = doctor.user_id
                WHERE patient.id = ?
                """,
                (profile.id,),
            ).fetchone()
            doctor_name = doctor["name"] if doctor else None
            order = database.execute(
                "SELECT reference FROM orders WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1",
                (profile.id,),
            ).fetchone()
            active_order_reference = order["reference"] if order else None
    return {
        "patient_name": user.name,
        "recovery_day": profile.recovery_day,
        "recovery_total_days": profile.recovery_total_days,
        "confidence_score": profile.confidence_score,
        "doctor_name": doctor_name,
        "today_items": [item.__dict__ for item in items],
        "active_order_reference": active_order_reference,
    }


@router.get("/me/orders")
def patient_orders(patient=Depends(current_patient)):
    _, profile = patient
    if USE_FIRESTORE:
        rows = records(firestore_client(), "orders", patient_id=profile.id)
        rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
        return [
            {
                "id": row["id"],
                "reference": row.get("reference", ""),
                "items": row.get("items", []),
                "total_amount": row.get("total_amount", 0),
                "status": row.get("status", ""),
                "match_score": row.get("match_score", 0),
                "distance_km": row.get("distance_km", 0),
                "created_at": row.get("created_at", ""),
            }
            for row in rows
        ]
    with SQLiteDatabase() as database:
        database.initialize()
        rows = database.execute(
            "SELECT id, reference, items_json, total_amount, status, match_score, distance_km, created_at FROM orders WHERE patient_id = ? ORDER BY created_at DESC",
            (profile.id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "reference": row["reference"],
                "items": json.loads(row["items_json"]),
                "total_amount": row["total_amount"],
                "status": row["status"],
                "match_score": row["match_score"],
                "distance_km": row["distance_km"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def _extract_prescription_text(filename: str, content: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".text"}:
        return content.decode("utf-8", errors="replace").strip(), "text"
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            import io

            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip(), "pdf-text"
        except Exception as error:
            raise HTTPException(status_code=422, detail=f"Could not read this PDF: {error}") from error
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        try:
            import cv2
            import numpy as np
            from rapidocr_onnxruntime import RapidOCR

            image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise HTTPException(status_code=422, detail="The uploaded image could not be decoded")
            global _OCR_ENGINE
            if _OCR_ENGINE is None:
                _OCR_ENGINE = RapidOCR()
            results, _ = _OCR_ENGINE(image)
            lines = [str(result[1]).strip() for result in results or [] if len(result) > 1 and str(result[1]).strip()]
            return "\n".join(lines), "rapidocr"
        except Exception as error:
            if isinstance(error, HTTPException):
                raise
            raise HTTPException(status_code=503, detail=f"Image OCR is unavailable: {error}") from error
    raise HTTPException(status_code=415, detail="Upload a PDF, text file, or prescription image")


def _prescription_lines(text: str) -> list[str]:
    dosage = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?)\b", re.IGNORECASE)
    medicine_hint = re.compile(
        r"\b(?:tablet|tab|capsule|cap|syrup|ointment|cream|drops?|paracetamol|amoxicillin|"
        r"ibuprofen|parah|bandage|dressing|gel)\b",
        re.IGNORECASE,
    )
    entries = []
    for line in text.splitlines():
        candidate = line.strip(" •\t-")
        if not dosage.search(candidate) and not medicine_hint.search(candidate):
            continue
        candidate = re.sub(r"^(?:rx|prescription|medicine|medication)\s*[:\-]?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\bparah\b", "Paracetamol", candidate, flags=re.IGNORECASE)
        if candidate:
            entries.append(candidate)
    return list(dict.fromkeys(entries))


@router.get("/me/documents")
def list_documents(patient=Depends(current_patient)) -> list[dict]:
    _, profile = patient
    if USE_FIRESTORE:
        rows = records(firestore_client(), "documents", patient_id=profile.id)
        rows.sort(key=lambda row: row.get("uploaded_at", ""), reverse=True)
        return [
            {
                "id": row["id"],
                "filename": row.get("filename", ""),
                "ocr_text": row.get("ocr_text", ""),
                "extraction_mode": row.get("extraction_mode", ""),
                "medicines": row.get("medicines", []),
                "generated_plan_items": row.get("generated_plan_items", 0),
                "uploaded_at": row.get("uploaded_at", ""),
            }
            for row in rows
        ]
    with SQLiteDatabase() as database:
        database.initialize()
        rows = database.execute(
            "SELECT id, filename, ocr_text, nlp_pipeline_mode, extracted_medicines_json, generated_plan_items, uploaded_at FROM documents WHERE patient_id = ? ORDER BY uploaded_at DESC",
            (profile.id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "filename": row["filename"],
                "ocr_text": row["ocr_text"],
                "extraction_mode": row["nlp_pipeline_mode"],
                "medicines": json.loads(row["extracted_medicines_json"]),
                "generated_plan_items": row["generated_plan_items"],
                "uploaded_at": row["uploaded_at"],
            }
            for row in rows
        ]


@router.post("/me/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), patient=Depends(current_patient)) -> dict:
    _, profile = patient
    filename = Path(file.filename or "prescription").name
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit")
    text, extraction_mode = _extract_prescription_text(filename, content)
    medicines = _prescription_lines(text)
    document_id = str(uuid4())
    uploaded_at = datetime.now(timezone.utc).isoformat()
    if USE_FIRESTORE:
        object_path = f"private/patients/{profile.id}/documents/{document_id}{Path(filename).suffix.lower()}"
        storage_bucket().blob(object_path).upload_from_string(content, content_type=file.content_type or "application/octet-stream")
        collection(firestore_client(), "documents").document(document_id).set({
            "patient_id": profile.id,
            "filename": filename,
            "storage_path": object_path,
            "ocr_text": text,
            "extraction_mode": extraction_mode,
            "medicines": medicines,
            "generated_plan_items": 0,
            "uploaded_at": uploaded_at,
        })
    else:
        upload_dir = Path.cwd() / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_file = upload_dir / f"{document_id}{Path(filename).suffix.lower()}"
        stored_file.write_bytes(content)
        with SQLiteDatabase() as database:
            database.initialize()
            database.execute(
                """
                INSERT INTO documents
                (id, patient_id, filename, storage_path, ocr_text, nlp_pipeline_mode, extracted_medicines_json, generated_plan_items, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (document_id, profile.id, filename, str(stored_file), text, extraction_mode, json.dumps(medicines), uploaded_at),
            )
    return {
        "id": document_id,
        "filename": filename,
        "ocr_text": text,
        "extraction_mode": extraction_mode,
        "medicines": medicines,
        "uploaded_at": uploaded_at,
        "generated_plan_items": 0,
    }


@router.post("/me/documents/{document_id}/add-prescription-items")
def add_prescription_items(document_id: str, patient=Depends(current_patient)) -> dict:
    _, profile = patient
    if USE_FIRESTORE:
        client = firestore_client()
        document_ref = collection(client, "documents").document(document_id)
        snapshot = document_ref.get()
        if not snapshot.exists or snapshot.to_dict().get("patient_id") != profile.id:
            raise HTTPException(status_code=404, detail="Prescription document not found")
        document = snapshot.to_dict()
        medicines = document.get("medicines", [])
        if not medicines:
            raise HTTPException(status_code=422, detail="No medicine lines were found to add")
        plan_collection = collection(client, "recovery_plan_items")
        description = f"From {document['filename']}; confirm instructions with your care team."
        existing = list(plan_collection.where("patient_id", "==", profile.id).where("description", "==", description).stream())
        existing_titles = {item.to_dict().get("title") for item in existing}
        for medicine in medicines:
            if medicine in existing_titles:
                continue
            plan_collection.document(str(uuid4())).set({
                "patient_id": profile.id,
                "day": profile.recovery_day,
                "time": "Unscheduled",
                "title": medicine,
                "description": description,
                "category": "medicine",
                "doctor_adjusted": False,
            })
        document_ref.update({"generated_plan_items": len(medicines)})
        return {"added": medicines}
    with SQLiteDatabase() as database:
        database.initialize()
        document = database.execute(
            "SELECT filename, extracted_medicines_json FROM documents WHERE id = ? AND patient_id = ?",
            (document_id, profile.id),
        ).fetchone()
        if document is None:
            raise HTTPException(status_code=404, detail="Prescription document not found")
        medicines = json.loads(document["extracted_medicines_json"])
        if not medicines:
            raise HTTPException(status_code=422, detail="No medicine lines were found to add")
        for medicine in medicines:
            exists = database.execute(
                "SELECT 1 FROM recovery_plan_items WHERE patient_id = ? AND title = ? AND description = ? LIMIT 1",
                (profile.id, medicine, f"From {document['filename']}; confirm instructions with your care team."),
            ).fetchone()
            if exists:
                continue
            database.execute(
                """
                INSERT INTO recovery_plan_items (id, patient_id, day, time, title, description, category, doctor_adjusted)
                VALUES (?, ?, ?, 'Unscheduled', ?, ?, 'medicine', 0)
                """,
                (str(uuid4()), profile.id, profile.recovery_day, medicine, f"From {document['filename']}; confirm instructions with your care team."),
            )
        database.execute("UPDATE documents SET generated_plan_items = ? WHERE id = ?", (len(medicines), document_id))
        return {"added": medicines}


@router.get("/me/documents/{document_id}/suggestions")
def document_suggestions(document_id: str, patient=Depends(current_patient)) -> list[dict]:
    _, profile = patient
    if USE_FIRESTORE:
        client = firestore_client()
        document = collection(client, "documents").document(document_id).get()
        if not document.exists or document.to_dict().get("patient_id") != profile.id:
            raise HTTPException(status_code=404, detail="Prescription document not found")
        medicines = [str(item).lower() for item in document.to_dict().get("medicines", [])]
        inventory = records(client, "inventory_items")
        suggestions = []
        for item in inventory:
            if int(item.get("stock_pct", 0)) <= 0:
                continue
            lower_name = item.get("name", "").lower()
            if any(keyword in lower_name for keyword in ("bandage", "dressing", "pain relief", "gel")):
                reason = "Useful alongside prescription medicines during recovery."
            elif any(keyword in medicine for medicine in medicines for keyword in ("antibiotic", "amoxicillin")):
                reason = "Commonly kept available while following an antibiotic prescription."
            else:
                continue
            suggestions.append({
                "name": item.get("name", ""),
                "category": "Recovery supply",
                "reason": reason,
                "price": item.get("unit_price", 0),
                "triggered_by": ", ".join(medicines[:2]) or "your prescription",
            })
        return suggestions[:4]
    with SQLiteDatabase() as database:
        database.initialize()
        document = database.execute(
            "SELECT extracted_medicines_json FROM documents WHERE id = ? AND patient_id = ?",
            (document_id, profile.id),
        ).fetchone()
        if document is None:
            raise HTTPException(status_code=404, detail="Prescription document not found")
        medicines = [str(item).lower() for item in json.loads(document["extracted_medicines_json"])]
        inventory = database.execute(
            "SELECT name, unit_price FROM inventory_items WHERE stock_pct > 0 ORDER BY name",
        ).fetchall()

    suggestions: list[dict] = []
    for item in inventory:
        name = item["name"]
        lower_name = name.lower()
        if any(keyword in lower_name for keyword in ("bandage", "dressing", "pain relief", "gel")):
            reason = "Useful alongside prescription medicines during recovery."
        elif any(keyword in medicine for medicine in medicines for keyword in ("antibiotic", "amoxicillin")):
            reason = "Commonly kept available while following an antibiotic prescription."
        else:
            continue
        suggestions.append({
            "name": name,
            "category": "Recovery supply",
            "reason": reason,
            "price": item["unit_price"],
            "triggered_by": ", ".join(medicines[:2]) or "your prescription",
        })
    return suggestions[:4]
