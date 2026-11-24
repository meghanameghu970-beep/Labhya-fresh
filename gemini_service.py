import json
import os
import uuid
from typing import Any

import requests

from database import get_connection, utc_now
from draft_engine import generate_application_draft
from eligibility_engine import evaluate_all_schemes, evaluate_scheme_eligibility

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _find_scheme_in_message(message: str, db_path: str | None = None) -> dict[str, Any] | None:
    q = message.lower()
    conn = get_connection(db_path)
    schemes = [dict(r) for r in conn.execute("SELECT * FROM schemes").fetchall()]
    conn.close()

    # Exact or keyword match against DB schemes
    aliases = {
        "gruha lakshmi": "gruha-lakshmi",
        "griha lakshmi": "gruha-lakshmi",
        "yuva nidhi": "yuva-nidhi",
        "shakti": "shakti-karnataka",
        "sandhya suraksha": "sandhya-suraksha",
        "manaswini": "manaswini-karnataka",
        "bhagyalakshmi": "bhagyalakshmi-karnataka",
        "bhagyalaxmi": "bhagyalakshmi-karnataka",
        "ssp": "ssp-post-matric",
        "vidyasiri": "ssp-post-matric",
        "arivu": "arivu-kmdc",
        "kmdc": "arivu-kmdc",
        "pm-kisan": "pm-kisan",
        "pm kisan": "pm-kisan",
        "ayushman": "ab-pmjay",
        "pm-jay": "ab-pmjay",
        "pmjay": "ab-pmjay",
        "pmegp": "pmegp",
        "udid": "igndps-disability",
        "igndps": "igndps-disability",
        "disability pension": "igndps-disability",
        "krishi bhagya": "krishi-bhagya",
        "anna bhagya": "anna-bhagya",
        "pmay": "pm-awas-yojana",
        "awas": "pm-awas-yojana",
        "pmmsy": "pmmsy-fisheries",
        "matsya": "pmmsy-fisheries",
        "artisan livelihood": "karnataka-unverified-livelihood-grant",
    }
    for key, sid in aliases.items():
        if key in q:
            for sc in schemes:
                if sc["id"] == sid:
                    return sc

    for sc in schemes:
        if sc["id"] in q or sc["name"].lower() in q:
            return sc
    return None


def _get_scheme_bundle(scheme_id: str, db_path: str | None = None) -> dict[str, Any]:
    conn = get_connection(db_path)
    sc = dict(conn.execute("SELECT * FROM schemes WHERE id = ?", (scheme_id,)).fetchone())
    benefits = [dict(r) for r in conn.execute("SELECT * FROM scheme_benefits WHERE scheme_id = ?", (scheme_id,)).fetchall()]
    docs = [dict(r) for r in conn.execute("SELECT * FROM required_documents WHERE scheme_id = ?", (scheme_id,)).fetchall()]
    steps = [dict(r) for r in conn.execute("SELECT * FROM application_steps WHERE scheme_id = ? ORDER BY step_number", (scheme_id,)).fetchall()]
    sources = [dict(r) for r in conn.execute("SELECT * FROM official_sources WHERE scheme_id = ?", (scheme_id,)).fetchall()]
    conn.close()
    return {"scheme": sc, "benefits": benefits, "documents": docs, "steps": steps, "sources": sources}


def _call_gemini_rest(system_prompt: str, user_prompt: str, context_json: dict[str, Any]) -> str | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"USER QUESTION: {user_prompt}\n\n"
                            f"VERIFIED DATABASE & ELIGIBILITY ENGINE OUTPUT (JSON):\n"
                            f"{json.dumps(context_json, ensure_ascii=False)}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None
    return None


def _build_grounded_fallback_response(
    message: str,
    profile: dict[str, Any],
    bundle: dict[str, Any] | None,
    elig: dict[str, Any] | None,
    all_elig: list[dict[str, Any]] | None,
    draft: dict[str, Any] | None,
) -> str:
    q = message.lower()

    if draft is not None:
        missing = ", ".join(draft["missing_fields"]) if draft["missing_fields"] else "None"
        return (
            f"I have prepared an application draft (ID: {draft['id']}, Status: {draft['status']}) for "
            f"**{draft['scheme_name']}**.\n"
            f"- Pre-filled fields: {len(draft['mapped_fields'])} from your profile\n"
            f"- Missing profile fields: {missing}\n"
            f"- Manual portal steps required: Aadhaar eKYC, Bank IFSC, document uploads, and self-declaration at {draft['application_portal'] or 'the official portal'}."
        )

    if all_elig is not None and ("other schemes" in q or "qualify" in q or "which schemes" in q or not bundle):
        eligible = [r for r in all_elig if r["outcome"] == "ELIGIBLE"]
        incomplete = [r for r in all_elig if r["outcome"] == "INCOMPLETE_INFORMATION"]
        lines = []
        if eligible:
            lines.append("**Schemes you currently qualify for (ELIGIBLE):** " + ", ".join(r["scheme_name"] for r in eligible) + ".")
        else:
            lines.append("No schemes are currently marked **ELIGIBLE** with your current profile.")
        if incomplete:
            lines.append("**Need more info to confirm (INCOMPLETE_INFORMATION):** " + ", ".join(r["scheme_name"] for r in incomplete[:4]) + ".")
        return "\n".join(lines)

    if not bundle:
        return "I could not find that scheme in our verified database. Please ask about a Karnataka or Central scheme such as Gruha Lakshmi, Yuva Nidhi, Shakti, Sandhya Suraksha, Manaswini, Bhagyalakshmi, SSP Scholarship, PM-KISAN, AB PM-JAY, or PMEGP."

    sc = bundle["scheme"]
    if sc["verification_status"] == "NOT_VERIFIED" or sc["operational_status"] == "NOT_VERIFIED":
        return (
            f"**{sc['name']}** is currently marked **{sc['verification_status']}** ({sc['operational_status']}). "
            "Official eligibility rules and application steps are not yet verified, so I cannot confirm eligibility or generate a draft."
        )

    if "benefit" in q:
        b_text = "; ".join(f"{b['benefit_type']}: {b['amount_or_value']}" for b in bundle["benefits"]) or "Benefits not verified yet."
        return f"**{sc['name']} Benefits:** {b_text}"

    if "document" in q or "docs" in q:
        mand = [d["document_name"] for d in bundle["documents"] if d["is_mandatory"]]
        opt = [d["document_name"] for d in bundle["documents"] if not d["is_mandatory"]]
        return (
            f"**Required Documents for {sc['name']}:**\n"
            f"- Mandatory: {', '.join(mand) or 'None listed'}\n"
            f"- Optional: {', '.join(opt) or 'None'}"
        )

    if "how" in q and "apply" in q or "guide" in q or "step" in q:
        top_steps = "\n".join(f"{st['step_number']}. {st['title']}: {st['instruction']}" for st in bundle["steps"])
        return f"**How to apply for {sc['name']}:**\n{top_steps}"

    if "eligib" in q or "am i" in q or "qualify" in q:
        assert elig is not None
        parts = [f"**Eligibility for {sc['name']}: {elig['outcome']}**", elig["explanation"]]
        if elig["missing_fields"]:
            missing_names = sorted({m["field_name"] for m in elig["missing_fields"]})
            parts.append(f"Please provide: {', '.join(missing_names)} so I can complete the check.")
        return "\n".join(parts)

    # General scheme overview
    b_summary = bundle["benefits"][0]["amount_or_value"] if bundle["benefits"] else "See official portal"
    src_urls = ", ".join(src["source_url"] for src in bundle["sources"]) or (sc["application_portal"] or "N/A")
    elig_line = f"\n**Your Current Status:** {elig['outcome']} — {elig['explanation']}" if elig else ""
    return (
        f"**{sc['name']}** ({sc['level']} · {sc['operational_status']} · {sc['verification_status']})\n"
        f"{sc['description']}\n"
        f"**Department:** {sc['department'] or 'Not specified'}\n"
        f"**Benefit:** {b_summary}\n"
        f"**Official Source(s):** {src_urls}{elig_line}"
    )


def handle_chat_turn(
    applicant_id: str,
    message: str,
    session_id: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    conn = get_connection(db_path)
    profile_row = conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (applicant_id,)).fetchone()
    if not profile_row:
        conn.close()
        raise ValueError("Applicant profile not found")
    profile = dict(profile_row)

    now = utc_now()
    if session_id:
        sess_row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
        if not sess_row:
            conn.close()
            raise ValueError("Chat session not found")
        if sess_row["applicant_id"] != applicant_id:
            conn.close()
            raise PermissionError("Access denied: chat session belongs to another applicant")
        session = dict(sess_row)
    else:
        session_id = "chat-" + uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO chat_sessions (id, applicant_id, selected_scheme_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, applicant_id, None, message[:60], now, now),
        )
        conn.commit()
        session = {"id": session_id, "applicant_id": applicant_id, "selected_scheme_id": None}

    conn.close()

    # Identify scheme from message or reuse session's selected_scheme_id
    matched = _find_scheme_in_message(message, db_path=db_path)
    selected_scheme_id = matched["id"] if matched else session.get("selected_scheme_id")

    bundle = _get_scheme_bundle(selected_scheme_id, db_path=db_path) if selected_scheme_id else None
    elig = evaluate_scheme_eligibility(profile, selected_scheme_id, db_path=db_path, persist=True) if selected_scheme_id else None

    q = message.lower()
    all_elig = None
    if "other schemes" in q or "qualify" in q or "which schemes" in q or not selected_scheme_id:
        all_elig = evaluate_all_schemes(profile, db_path=db_path, persist=False)

    draft = None
    if selected_scheme_id and ("draft" in q or "prepare my application" in q):
        try:
            draft = generate_application_draft(applicant_id, selected_scheme_id, db_path=db_path)
        except ValueError:
            draft = None

    system_prompt = (
        "You are Labhya's Government Scheme Assistant. You MUST answer ONLY using the verified "
        "SQLite database records and deterministic eligibility engine output provided in JSON. "
        "Never invent eligibility rules, benefits, or portal URLs. If a scheme is NOT_VERIFIED, "
        "state that honestly. Only ask for missing fields listed in missing_fields."
    )
    context_json = {
        "applicant_profile": {k: v for k, v in profile.items() if k != "auth_token"},
        "selected_scheme": bundle,
        "eligibility_evaluation": elig,
        "all_schemes_summary": (
            [{"scheme_id": r["scheme_id"], "scheme_name": r["scheme_name"], "outcome": r["outcome"]} for r in all_elig]
            if all_elig
            else None
        ),
        "generated_draft": draft,
    }

    reply = _call_gemini_rest(system_prompt, message, context_json)
    gemini_mode = "GEMINI_API" if reply else "DB_GROUNDED_DETERMINISTIC"
    if not reply:
        reply = _build_grounded_fallback_response(message, profile, bundle, elig, all_elig, draft)

    # Persist chat messages and update session's selected_scheme_id
    conn = get_connection(db_path)
    msg_time = utc_now()
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, selected_scheme_id, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, "user", message, selected_scheme_id, None, msg_time),
    )
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, selected_scheme_id, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            session_id,
            "assistant",
            reply,
            selected_scheme_id,
            json.dumps({"gemini_mode": gemini_mode, "outcome": elig["outcome"] if elig else None}),
            msg_time,
        ),
    )
    conn.execute(
        "UPDATE chat_sessions SET selected_scheme_id = ?, updated_at = ? WHERE id = ?",
        (selected_scheme_id, msg_time, session_id),
    )
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "selected_scheme_id": selected_scheme_id,
        "gemini_mode": gemini_mode,
        "reply": reply,
        "eligibility": elig,
        "draft": draft,
    }
