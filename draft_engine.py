import json
import uuid
from typing import Any

from database import get_connection, utc_now
from eligibility_engine import evaluate_scheme_eligibility


def generate_application_draft(
    applicant_id: str,
    scheme_id: str,
    applicant_notes: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    conn = get_connection(db_path)
    profile_row = conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (applicant_id,)).fetchone()
    if not profile_row:
        conn.close()
        raise ValueError("Applicant profile not found")
    profile = dict(profile_row)

    scheme_row = conn.execute("SELECT * FROM schemes WHERE id = ?", (scheme_id,)).fetchone()
    if not scheme_row:
        conn.close()
        raise ValueError(f"Scheme '{scheme_id}' not found")
    scheme = dict(scheme_row)

    if scheme["verification_status"] == "NOT_VERIFIED" or scheme["operational_status"] == "NOT_VERIFIED":
        conn.close()
        raise ValueError(
            f"Cannot generate an application draft for '{scheme['name']}' because its official requirements are NOT_VERIFIED."
        )

    docs = [dict(r) for r in conn.execute("SELECT * FROM required_documents WHERE scheme_id = ?", (scheme_id,)).fetchall()]
    elig = evaluate_scheme_eligibility(profile, scheme_id, db_path=db_path, persist=False)

    # Map verified profile fields to standard official application fields
    candidate_fields = {
        "applicant_name": profile.get("name"),
        "mobile_number": profile.get("mobile"),
        "date_of_birth": profile.get("dob"),
        "age": profile.get("age"),
        "gender": profile.get("gender"),
        "social_category": profile.get("social_category"),
        "annual_family_income": profile.get("annual_family_income"),
        "state": profile.get("state"),
        "district": profile.get("district"),
        "pincode": profile.get("pincode"),
        "area_type": profile.get("area_type"),
        "occupation": profile.get("occupation"),
        "education": profile.get("education"),
        "marital_status": profile.get("marital_status"),
        "disability_status": profile.get("disability_status"),
        "ration_card_type": profile.get("ration_card_type"),
    }

    mapped_fields = {k: v for k, v in candidate_fields.items() if v is not None and str(v).strip() != ""}
    missing_fields = sorted(
        {m["field_name"] for m in elig["missing_fields"]}
        | {k for k in ("applicant_name", "mobile_number", "state", "district", "pincode") if k not in mapped_fields}
    )

    manual_fields = [
        {
            "field": "aadhaar_ekyc_otp",
            "label": "Aadhaar eKYC & OTP Verification on Official Portal",
            "reason": "Must be completed directly by the applicant on the government portal.",
        },
        {
            "field": "bank_account_ifsc",
            "label": "Bank Account Number & IFSC Code (Aadhaar-seeded)",
            "reason": "Requires manual entry and verification for DBT.",
        },
        {
            "field": "document_uploads",
            "label": "Document Uploads: " + ", ".join(d["document_name"] for d in docs if d["is_mandatory"]),
            "reason": "Applicant must attach scanned originals before final submission.",
        },
        {
            "field": "self_declaration",
            "label": "Official Self-Declaration & Consent",
            "reason": "Labhya prepares drafts only and never submits applications automatically.",
        },
    ]

    draft_id = "draft-" + uuid.uuid4().hex[:12]
    status = "READY_FOR_REVIEW" if not missing_fields else "DRAFT"
    now = utc_now()

    conn.execute(
        """
        INSERT INTO application_drafts (
            id, applicant_id, scheme_id, status, mapped_fields_json,
            missing_fields_json, manual_fields_json, applicant_notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            draft_id,
            applicant_id,
            scheme_id,
            status,
            json.dumps(mapped_fields),
            json.dumps(missing_fields),
            json.dumps(manual_fields),
            applicant_notes,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "id": draft_id,
        "applicant_id": applicant_id,
        "scheme_id": scheme_id,
        "scheme_name": scheme["name"],
        "application_portal": scheme["application_portal"],
        "eligibility_outcome": elig["outcome"],
        "status": status,
        "mapped_fields": mapped_fields,
        "missing_fields": missing_fields,
        "manual_fields": manual_fields,
        "applicant_notes": applicant_notes,
        "created_at": now,
        "updated_at": now,
    }


def list_applicant_drafts(applicant_id: str, db_path: str | None = None) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT d.*, s.name AS scheme_name, s.application_portal
        FROM application_drafts d
        JOIN schemes s ON s.id = d.scheme_id
        WHERE d.applicant_id = ?
        ORDER BY d.updated_at DESC
        """,
        (applicant_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "applicant_id": r["applicant_id"],
            "scheme_id": r["scheme_id"],
            "scheme_name": r["scheme_name"],
            "application_portal": r["application_portal"],
            "status": r["status"],
            "mapped_fields": json.loads(r["mapped_fields_json"]),
            "missing_fields": json.loads(r["missing_fields_json"]),
            "manual_fields": json.loads(r["manual_fields_json"]),
            "applicant_notes": r["applicant_notes"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def update_application_draft(
    draft_id: str,
    applicant_id: str,
    mapped_fields_patch: dict[str, Any] | None = None,
    applicant_notes: str | None = None,
    status: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM application_drafts WHERE id = ?", (draft_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError("Draft not found")
    if row["applicant_id"] != applicant_id:
        conn.close()
        raise PermissionError("Access denied: draft belongs to another applicant")

    mapped = json.loads(row["mapped_fields_json"])
    if mapped_fields_patch:
        mapped.update(mapped_fields_patch)

    missing = [f for f in json.loads(row["missing_fields_json"]) if not mapped.get(f)]
    new_status = status or ("READY_FOR_REVIEW" if not missing else "DRAFT")
    now = utc_now()

    conn.execute(
        """
        UPDATE application_drafts
        SET mapped_fields_json = ?, missing_fields_json = ?, applicant_notes = ?, status = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            json.dumps(mapped),
            json.dumps(missing),
            applicant_notes if applicant_notes is not None else row["applicant_notes"],
            new_status,
            now,
            draft_id,
        ),
    )
    conn.commit()
    conn.close()
    return {
        "id": draft_id,
        "status": new_status,
        "mapped_fields": mapped,
        "missing_fields": missing,
        "applicant_notes": applicant_notes if applicant_notes is not None else row["applicant_notes"],
        "updated_at": now,
    }
