import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("LABHYA_DB_PATH", os.path.join(os.path.dirname(__file__), "labhya.db"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str | None = None) -> None:
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.executescript(
        """
        -- 1. schemes
        CREATE TABLE IF NOT EXISTS schemes (
            id TEXT PRIMARY KEY,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            level TEXT NOT NULL CHECK(level IN ('KARNATAKA_STATE', 'CENTRAL', 'JOINT')),
            category TEXT NOT NULL,
            department TEXT,
            target_beneficiaries TEXT,
            application_portal TEXT,
            notification_ref TEXT,
            deadline TEXT,
            verification_status TEXT NOT NULL CHECK(verification_status IN ('VERIFIED', 'PARTIALLY_VERIFIED', 'NOT_VERIFIED')),
            operational_status TEXT NOT NULL CHECK(operational_status IN ('ACTIVE', 'APPLICATIONS_CLOSED', 'UPCOMING', 'DISCONTINUED', 'UNDER_REVIEW', 'NOT_VERIFIED')),
            effective_date TEXT,
            last_verified_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 2. eligibility_rules
        CREATE TABLE IF NOT EXISTS eligibility_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
            rule_group TEXT NOT NULL DEFAULT 'default',
            logic_operator TEXT NOT NULL DEFAULT 'AND' CHECK(logic_operator IN ('AND', 'OR')),
            field_name TEXT NOT NULL,
            operator TEXT NOT NULL CHECK(operator IN ('eq', 'neq', 'in', 'not_in', 'gte', 'lte', 'gt', 'lt', 'between', 'is_true', 'is_false')),
            expected_value TEXT,
            is_exclusion INTEGER NOT NULL DEFAULT 0,
            is_mandatory INTEGER NOT NULL DEFAULT 1,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        -- 3. scheme_benefits
        CREATE TABLE IF NOT EXISTS scheme_benefits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
            benefit_type TEXT NOT NULL,
            amount_or_value TEXT,
            frequency TEXT,
            disbursement_mode TEXT,
            notes TEXT
        );

        -- 4. required_documents
        CREATE TABLE IF NOT EXISTS required_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
            document_name TEXT NOT NULL,
            is_mandatory INTEGER NOT NULL DEFAULT 1,
            notes TEXT
        );

        -- 5. application_steps
        CREATE TABLE IF NOT EXISTS application_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
            step_number INTEGER NOT NULL,
            step_category TEXT NOT NULL,
            title TEXT NOT NULL,
            instruction TEXT NOT NULL,
            mode TEXT NOT NULL CHECK(mode IN ('ONLINE', 'OFFLINE', 'CSC_SERVICE_CENTRE', 'HYBRID')),
            portal_url TEXT
        );

        -- 6. official_sources
        CREATE TABLE IF NOT EXISTS official_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_type TEXT NOT NULL,
            verified_date TEXT
        );

        -- 7. scheme_faqs
        CREATE TABLE IF NOT EXISTS scheme_faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        );

        -- 8. applicant_profiles
        CREATE TABLE IF NOT EXISTS applicant_profiles (
            id TEXT PRIMARY KEY,
            mobile TEXT UNIQUE NOT NULL,
            auth_token TEXT,
            name TEXT,
            dob TEXT,
            age INTEGER,
            gender TEXT,
            social_category TEXT,
            annual_family_income REAL,
            state TEXT,
            district TEXT,
            pincode TEXT,
            area_type TEXT,
            occupation TEXT,
            education TEXT,
            marital_status TEXT,
            disability_status TEXT,
            disability_percentage REAL,
            land_owned_acres REAL,
            ration_card_type TEXT,
            is_taxpayer INTEGER,
            is_govt_employee INTEGER,
            language TEXT NOT NULL DEFAULT 'en',
            digilocker_connected INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 9. family_profiles
        CREATE TABLE IF NOT EXISTS family_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_id TEXT NOT NULL REFERENCES applicant_profiles(id) ON DELETE CASCADE,
            relation TEXT NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            occupation TEXT,
            income REAL,
            disability_status TEXT,
            created_at TEXT NOT NULL
        );

        -- 10. eligibility_results
        CREATE TABLE IF NOT EXISTS eligibility_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_id TEXT NOT NULL REFERENCES applicant_profiles(id) ON DELETE CASCADE,
            scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
            outcome TEXT NOT NULL CHECK(outcome IN ('ELIGIBLE', 'NOT_ELIGIBLE', 'INCOMPLETE_INFORMATION', 'VERIFICATION_REQUIRED')),
            passed_rules_json TEXT NOT NULL,
            failed_rules_json TEXT NOT NULL,
            missing_fields_json TEXT NOT NULL,
            explanation TEXT NOT NULL,
            evaluated_at TEXT NOT NULL
        );

        -- 11. application_drafts
        CREATE TABLE IF NOT EXISTS application_drafts (
            id TEXT PRIMARY KEY,
            applicant_id TEXT NOT NULL REFERENCES applicant_profiles(id) ON DELETE CASCADE,
            scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT', 'READY_FOR_REVIEW', 'SAVED')),
            mapped_fields_json TEXT NOT NULL,
            missing_fields_json TEXT NOT NULL,
            manual_fields_json TEXT NOT NULL,
            applicant_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 12. chat_sessions
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            applicant_id TEXT NOT NULL REFERENCES applicant_profiles(id) ON DELETE CASCADE,
            selected_scheme_id TEXT REFERENCES schemes(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- 13. chat_messages
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            selected_scheme_id TEXT REFERENCES schemes(id) ON DELETE SET NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL
        );

        -- 14. scheme_updates
        CREATE TABLE IF NOT EXISTS scheme_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scheme_id TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
            previous_version_json TEXT NOT NULL,
            change_summary TEXT NOT NULL,
            source_url TEXT,
            effective_date TEXT,
            updated_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_schemes_category ON schemes(category);
        CREATE INDEX IF NOT EXISTS idx_schemes_status ON schemes(operational_status, verification_status);
        CREATE INDEX IF NOT EXISTS idx_rules_scheme ON eligibility_rules(scheme_id);
        CREATE INDEX IF NOT EXISTS idx_docs_scheme ON required_documents(scheme_id);
        CREATE INDEX IF NOT EXISTS idx_steps_scheme ON application_steps(scheme_id);
        CREATE INDEX IF NOT EXISTS idx_sources_scheme ON official_sources(scheme_id);
        CREATE INDEX IF NOT EXISTS idx_applicant_mobile ON applicant_profiles(mobile);
        CREATE INDEX IF NOT EXISTS idx_applicant_token ON applicant_profiles(auth_token);
        CREATE INDEX IF NOT EXISTS idx_elig_applicant ON eligibility_results(applicant_id, scheme_id);
        CREATE INDEX IF NOT EXISTS idx_drafts_applicant ON application_drafts(applicant_id);
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_applicant ON chat_sessions(applicant_id);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
        """
    )

    conn.commit()
    conn.close()
