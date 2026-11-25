import json
import os
import random
import re
import uuid
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import DB_PATH, get_connection, init_db, utc_now
from draft_engine import generate_application_draft, list_applicant_drafts, update_application_draft
from eligibility_engine import compute_age_from_dob, evaluate_all_schemes, evaluate_scheme_eligibility
from gemini_service import handle_chat_turn
from seed_schemes import seed_database

app = FastAPI(title="Labhya Government Scheme Intelligence API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory OTP store for login flow
OTP_STORE: dict[str, str] = {}
STATIC_DIR = os.path.dirname(__file__)


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    seed_database()


def _normalize_mobile(mobile: str) -> str:
    digits = re.sub(r"\D", "", mobile or "")
    return digits[:10]


def _is_valid_indian_mobile(mobile: str) -> bool:
    return bool(re.fullmatch(r"[6-9]\d{9}", mobile or ""))


def get_current_applicant(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    conn = get_connection()
    row = conn.execute("SELECT * FROM applicant_profiles WHERE auth_token = ?", (token,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    return dict(row)


# --- Pydantic Models ---
class OtpRequest(BaseModel):
    mobile: str


class OtpVerify(BaseModel):
    mobile: str
    otp: str


class ProfileUpdate(BaseModel):
    name: str | None = None
    dob: str | None = None
    age: int | None = None
    gender: str | None = None
    social_category: str | None = None
    annual_family_income: float | None = None
    state: str | None = None
    district: str | None = None
    pincode: str | None = None
    area_type: str | None = None
    occupation: str | None = None
    education: str | None = None
    marital_status: str | None = None
    disability_status: str | None = None
    disability_percentage: float | None = None
    land_owned_acres: float | None = None
    ration_card_type: str | None = None
    is_taxpayer: bool | None = None
    is_govt_employee: bool | None = None
    language: str | None = None
    digilocker_connected: bool | None = None


class FamilyMemberCreate(BaseModel):
    relation: str
    name: str
    age: int | None = None
    gender: str | None = None
    occupation: str | None = None
    income: float | None = None
    disability_status: str | None = None


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class DraftCreateRequest(BaseModel):
    scheme_id: str
    applicant_notes: str | None = None


class DraftUpdateRequest(BaseModel):
    mapped_fields: dict[str, Any] | None = None
    applicant_notes: str | None = None
    status: str | None = None


class SchemeUpdateRequest(BaseModel):
    operational_status: str | None = None
    verification_status: str | None = None
    description: str | None = None
    change_summary: str
    source_url: str
    effective_date: str | None = None
    updated_by: str = "system_admin"


# --- Frontend Serve ---
@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"service": "Labhya Government Scheme Intelligence API", "status": "running"}


@app.get("/api/health")
def health_check():
    return {"status": "ok", "db": DB_PATH}


# --- Authentication ---
@app.post("/api/auth/request-otp")
def request_otp(body: OtpRequest):
    mobile = _normalize_mobile(body.mobile)
    if not _is_valid_indian_mobile(mobile):
        raise HTTPException(status_code=400, detail="Valid 10-digit Indian mobile number (starting with 6-9) required")
    otp = str(random.randint(100000, 999999))
    OTP_STORE[mobile] = otp
    return {"mobile": mobile, "mock_otp": otp, "message": "OTP generated"}


@app.post("/api/auth/verify-otp")
def verify_otp(body: OtpVerify):
    mobile = _normalize_mobile(body.mobile)
    expected = OTP_STORE.get(mobile)
    if expected and body.otp.strip() != expected:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    conn = get_connection()
    row = conn.execute("SELECT * FROM applicant_profiles WHERE mobile = ?", (mobile,)).fetchone()
    now = utc_now()
    token = "tok-" + uuid.uuid4().hex
    if row:
        is_returning = bool(row["name"])
        conn.execute("UPDATE applicant_profiles SET auth_token = ?, updated_at = ? WHERE id = ?", (token, now, row["id"]))
        conn.commit()
        profile = dict(conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (row["id"],)).fetchone())
    else:
        is_returning = False
        app_id = "app-" + uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO applicant_profiles (id, mobile, auth_token, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (app_id, mobile, token, now, now),
        )
        conn.commit()
        profile = dict(conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (app_id,)).fetchone())
    conn.close()
    profile.pop("auth_token", None)
    return {"token": token, "is_returning_user": is_returning, "profile": profile}


# --- Profile & Family ---
@app.get("/api/profile")
def get_profile(applicant: dict[str, Any] = Depends(get_current_applicant)):
    out = dict(applicant)
    out.pop("auth_token", None)
    return out


@app.put("/api/profile")
def update_profile(body: ProfileUpdate, applicant: dict[str, Any] = Depends(get_current_applicant)):
    data = (body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True))
    if "dob" in data and data.get("age") is None:
        computed = compute_age_from_dob(data["dob"])
        if computed is not None:
            data["age"] = computed
    for bfield in ("is_taxpayer", "is_govt_employee", "digilocker_connected"):
        if bfield in data and data[bfield] is not None:
            data[bfield] = 1 if data[bfield] else 0
    if not data:
        return get_profile(applicant)
    data["updated_at"] = utc_now()
    cols = ", ".join(f"{k} = ?" for k in data.keys())
    vals = list(data.values()) + [applicant["id"]]
    conn = get_connection()
    conn.execute(f"UPDATE applicant_profiles SET {cols} WHERE id = ?", vals)
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (applicant["id"],)).fetchone())
    conn.close()
    updated.pop("auth_token", None)
    return updated


@app.get("/api/family")
def get_family(applicant: dict[str, Any] = Depends(get_current_applicant)):
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("SELECT * FROM family_profiles WHERE applicant_id = ?", (applicant["id"],)).fetchall()]
    conn.close()
    return {"family_members": rows}


@app.post("/api/family")
def add_family_member(body: FamilyMemberCreate, applicant: dict[str, Any] = Depends(get_current_applicant)):
    conn = get_connection()
    now = utc_now()
    cur = conn.execute(
        "INSERT INTO family_profiles (applicant_id, relation, name, age, gender, occupation, income, disability_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (applicant["id"], body.relation, body.name, body.age, body.gender, body.occupation, body.income, body.disability_status, now),
    )
    conn.commit()
    member_id = cur.lastrowid
    conn.close()
    return {"id": member_id, "applicant_id": applicant["id"], **(body.model_dump() if hasattr(body, "model_dump") else body.dict())}


# --- Schemes Catalog & Maintenance ---
@app.get("/api/schemes")
def list_schemes(category: str | None = None, level: str | None = None, search: str | None = None):
    conn = get_connection()
    query = "SELECT * FROM schemes WHERE 1=1"
    params: list[Any] = []
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if level:
        query += " AND level = ?"
        params.append(level)
    if search:
        query += " AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(category) LIKE ?)"
        pat = f"%{search.lower()}%"
        params.extend([pat, pat, pat])
    query += " ORDER BY name"
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    for sc in rows:
        sc["benefits"] = [dict(b) for b in conn.execute("SELECT * FROM scheme_benefits WHERE scheme_id = ?", (sc["id"],)).fetchall()]
        sc["sources"] = [dict(src) for src in conn.execute("SELECT * FROM official_sources WHERE scheme_id = ?", (sc["id"],)).fetchall()]
    conn.close()
    return {"schemes": rows, "count": len(rows)}


@app.get("/api/schemes/{scheme_id}")
def get_scheme_detail(scheme_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM schemes WHERE id = ?", (scheme_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Scheme not found")
    sc = dict(row)
    sc["benefits"] = [dict(r) for r in conn.execute("SELECT * FROM scheme_benefits WHERE scheme_id = ?", (scheme_id,)).fetchall()]
    sc["rules"] = [dict(r) for r in conn.execute("SELECT * FROM eligibility_rules WHERE scheme_id = ?", (scheme_id,)).fetchall()]
    sc["documents"] = [dict(r) for r in conn.execute("SELECT * FROM required_documents WHERE scheme_id = ?", (scheme_id,)).fetchall()]
    sc["application_steps"] = [dict(r) for r in conn.execute("SELECT * FROM application_steps WHERE scheme_id = ? ORDER BY step_number", (scheme_id,)).fetchall()]
    sc["sources"] = [dict(r) for r in conn.execute("SELECT * FROM official_sources WHERE scheme_id = ?", (scheme_id,)).fetchall()]
    sc["faqs"] = [dict(r) for r in conn.execute("SELECT * FROM scheme_faqs WHERE scheme_id = ?", (scheme_id,)).fetchall()]
    sc["updates"] = [dict(r) for r in conn.execute("SELECT * FROM scheme_updates WHERE scheme_id = ? ORDER BY created_at DESC", (scheme_id,)).fetchall()]
    conn.close()
    return sc


@app.post("/api/schemes/{scheme_id}/update")
def update_scheme_version(scheme_id: str, body: SchemeUpdateRequest):
    conn = get_connection()
    row = conn.execute("SELECT * FROM schemes WHERE id = ?", (scheme_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Scheme not found")
    prev = dict(row)
    now = utc_now()
    conn.execute(
        "INSERT INTO scheme_updates (scheme_id, previous_version_json, change_summary, source_url, effective_date, updated_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (scheme_id, json.dumps(prev), body.change_summary, body.source_url, body.effective_date, body.updated_by, now),
    )
    conn.execute(
        """
        UPDATE schemes
        SET operational_status = COALESCE(?, operational_status),
            verification_status = COALESCE(?, verification_status),
            description = COALESCE(?, description),
            effective_date = COALESCE(?, effective_date),
            last_verified_date = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (body.operational_status, body.verification_status, body.description, body.effective_date, now[:10], now, scheme_id),
    )
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM schemes WHERE id = ?", (scheme_id,)).fetchone())
    conn.close()
    return {"scheme": updated, "archived_previous_version": True}


# --- Eligibility Evaluation ---
@app.post("/api/eligibility/evaluate")
def evaluate_all(applicant: dict[str, Any] = Depends(get_current_applicant)):
    results = evaluate_all_schemes(applicant, persist=True)
    return {"results": results}


@app.get("/api/eligibility/evaluate/{scheme_id}")
def evaluate_one(scheme_id: str, applicant: dict[str, Any] = Depends(get_current_applicant)):
    try:
        return evaluate_scheme_eligibility(applicant, scheme_id, persist=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/eligibility/history")
def eligibility_history(applicant: dict[str, Any] = Depends(get_current_applicant)):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT er.*, s.name AS scheme_name
        FROM eligibility_results er
        JOIN schemes s ON s.id = er.scheme_id
        WHERE er.applicant_id = ?
        ORDER BY er.evaluated_at DESC LIMIT 50
        """,
        (applicant["id"],),
    ).fetchall()
    conn.close()
    return {"history": [dict(r) for r in rows]}


# --- Application Drafts ---
@app.post("/api/drafts")
def create_draft(body: DraftCreateRequest, applicant: dict[str, Any] = Depends(get_current_applicant)):
    try:
        return generate_application_draft(applicant["id"], body.scheme_id, body.applicant_notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/drafts")
def get_drafts(applicant: dict[str, Any] = Depends(get_current_applicant)):
    return {"drafts": list_applicant_drafts(applicant["id"])}


@app.put("/api/drafts/{draft_id}")
def edit_draft(draft_id: str, body: DraftUpdateRequest, applicant: dict[str, Any] = Depends(get_current_applicant)):
    try:
        return update_application_draft(draft_id, applicant["id"], body.mapped_fields, body.applicant_notes, body.status)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Gemini Chat & Persistence ---
@app.post("/api/chat")
def chat_endpoint(body: ChatRequest, applicant: dict[str, Any] = Depends(get_current_applicant)):
    try:
        return handle_chat_turn(applicant["id"], body.message, body.session_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/chat/sessions")
def list_chat_sessions(applicant: dict[str, Any] = Depends(get_current_applicant)):
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("SELECT * FROM chat_sessions WHERE applicant_id = ? ORDER BY updated_at DESC", (applicant["id"],)).fetchall()]
    conn.close()
    return {"sessions": rows}


@app.get("/api/chat/sessions/{session_id}")
def get_chat_session(session_id: str, applicant: dict[str, Any] = Depends(get_current_applicant)):
    conn = get_connection()
    sess = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not sess:
        conn.close()
        raise HTTPException(status_code=404, detail="Chat session not found")
    if sess["applicant_id"] != applicant["id"]:
        conn.close()
        raise PermissionError("Access denied")
    msgs = [dict(r) for r in conn.execute("SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC", (session_id,)).fetchall()]
    conn.close()
    return {"session": dict(sess), "messages": msgs}
