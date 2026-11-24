import os
import tempfile
import unittest

from fastapi.testclient import TestClient

# Use an isolated temporary database for tests
TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["LABHYA_DB_PATH"] = TMP_DB

import database
database.DB_PATH = TMP_DB

from database import get_connection, init_db
from draft_engine import generate_application_draft, update_application_draft
from eligibility_engine import evaluate_all_schemes, evaluate_scheme_eligibility
from gemini_service import handle_chat_turn
from seed_schemes import seed_database
from server import app


class LabhyaEngineTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db(TMP_DB)
        seed_database(TMP_DB)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TMP_DB):
            os.remove(TMP_DB)

    def _create_applicant(self, mobile: str, profile_data: dict) -> tuple[str, str]:
        r1 = self.client.post("/api/auth/request-otp", json={"mobile": mobile})
        self.assertEqual(r1.status_code, 200)
        otp = r1.json()["mock_otp"]
        r2 = self.client.post("/api/auth/verify-otp", json={"mobile": mobile, "otp": otp})
        self.assertEqual(r2.status_code, 200)
        token = r2.json()["token"]
        app_id = r2.json()["profile"]["id"]
        r3 = self.client.put(
            "/api/profile",
            json=profile_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r3.status_code, 200)
        return app_id, token

    def test_01_eligible_applicant(self):
        # Eligible for Gruha Lakshmi & Shakti
        app_id, token = self._create_applicant("9000000001", {
            "name": "Lakshmi Devi",
            "age": 38,
            "gender": "Female",
            "state": "Karnataka",
            "district": "Bengaluru",
            "pincode": "560001",
            "ration_card_type": "BPL",
            "is_taxpayer": False,
        })
        res = self.client.get("/api/eligibility/evaluate/gruha-lakshmi", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["outcome"], "ELIGIBLE")

    def test_02_fail_income_condition(self):
        # Fails Sandhya Suraksha income <= 120000
        app_id, _ = self._create_applicant("9000000002", {
            "name": "Ramesh Kumar",
            "age": 68,
            "gender": "Male",
            "state": "Karnataka",
            "annual_family_income": 240000,
            "is_govt_employee": False,
        })
        conn = get_connection(TMP_DB)
        prof = dict(conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (app_id,)).fetchone())
        conn.close()
        res = evaluate_scheme_eligibility(prof, "sandhya-suraksha", db_path=TMP_DB)
        self.assertEqual(res["outcome"], "NOT_ELIGIBLE")
        self.assertTrue(any(f["field_name"] == "annual_family_income" for f in res["failed_rules"]))

    def test_03_fail_age_condition(self):
        # Fails Sandhya Suraksha age >= 65
        app_id, _ = self._create_applicant("9000000003", {
            "name": "Suresh Rao",
            "age": 55,
            "gender": "Male",
            "state": "Karnataka",
            "annual_family_income": 80000,
            "is_govt_employee": False,
        })
        conn = get_connection(TMP_DB)
        prof = dict(conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (app_id,)).fetchone())
        conn.close()
        res = evaluate_scheme_eligibility(prof, "sandhya-suraksha", db_path=TMP_DB)
        self.assertEqual(res["outcome"], "NOT_ELIGIBLE")
        self.assertTrue(any(f["field_name"] == "age" for f in res["failed_rules"]))

    def test_04_missing_information(self):
        # Missing ration_card_type & is_taxpayer for Gruha Lakshmi -> INCOMPLETE_INFORMATION
        app_id, _ = self._create_applicant("9000000004", {
            "name": "Kavitha",
            "age": 32,
            "gender": "Female",
            "state": "Karnataka",
        })
        conn = get_connection(TMP_DB)
        prof = dict(conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (app_id,)).fetchone())
        conn.close()
        res = evaluate_scheme_eligibility(prof, "gruha-lakshmi", db_path=TMP_DB)
        self.assertEqual(res["outcome"], "INCOMPLETE_INFORMATION")
        self.assertGreater(len(res["missing_fields"]), 0)

    def test_05_partial_match_fails_one_condition(self):
        # Meets Karnataka, Female, BPL, age 45, but Married (fails Manaswini marital_status)
        app_id, _ = self._create_applicant("9000000005", {
            "name": "Meena",
            "age": 45,
            "gender": "Female",
            "state": "Karnataka",
            "ration_card_type": "BPL",
            "marital_status": "Married",
        })
        conn = get_connection(TMP_DB)
        prof = dict(conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (app_id,)).fetchone())
        conn.close()
        res = evaluate_scheme_eligibility(prof, "manaswini-karnataka", db_path=TMP_DB)
        self.assertEqual(res["outcome"], "NOT_ELIGIBLE")
        self.assertGreater(len(res["passed_rules"]), 0)
        self.assertTrue(any(f["field_name"] == "marital_status" for f in res["failed_rules"]))

    def test_06_multiple_schemes_match(self):
        # Senior BPL woman in Karnataka matches Shakti, Gruha Lakshmi, Sandhya Suraksha, AB PM-JAY (OR rule: age>=70 or BPL)
        app_id, _ = self._create_applicant("9000000006", {
            "name": "Parvathamma",
            "age": 72,
            "gender": "Female",
            "state": "Karnataka",
            "annual_family_income": 60000,
            "ration_card_type": "BPL",
            "is_taxpayer": False,
            "is_govt_employee": False,
        })
        conn = get_connection(TMP_DB)
        prof = dict(conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (app_id,)).fetchone())
        conn.close()
        results = evaluate_all_schemes(prof, db_path=TMP_DB)
        eligible_ids = {r["scheme_id"] for r in results if r["outcome"] == "ELIGIBLE"}
        self.assertTrue({"gruha-lakshmi", "shakti-karnataka", "sandhya-suraksha", "ab-pmjay"}.issubset(eligible_ids))

    def test_07_unverified_scheme_returns_verification_required(self):
        app_id, _ = self._create_applicant("9000000007", {"name": "Test", "state": "Karnataka"})
        conn = get_connection(TMP_DB)
        prof = dict(conn.execute("SELECT * FROM applicant_profiles WHERE id = ?", (app_id,)).fetchone())
        conn.close()
        res = evaluate_scheme_eligibility(prof, "karnataka-unverified-livelihood-grant", db_path=TMP_DB)
        self.assertEqual(res["outcome"], "VERIFICATION_REQUIRED")

    def test_08_application_draft_and_step_by_step_guidance(self):
        app_id, token = self._create_applicant("9000000008", {
            "name": "Anita",
            "age": 30,
            "gender": "Female",
            "state": "Karnataka",
            "district": "Mysuru",
            "pincode": "570001",
            "ration_card_type": "BPL",
            "is_taxpayer": False,
        })
        draft_res = self.client.post(
            "/api/drafts",
            json={"scheme_id": "gruha-lakshmi", "applicant_notes": "Review before Seva Sindhu upload"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(draft_res.status_code, 200)
        draft = draft_res.json()
        self.assertEqual(draft["scheme_id"], "gruha-lakshmi")
        self.assertEqual(draft["mapped_fields"]["applicant_name"], "Anita")
        self.assertGreaterEqual(len(draft["manual_fields"]), 4)

        # Update draft
        upd = self.client.put(
            f"/api/drafts/{draft['id']}",
            json={"status": "SAVED", "applicant_notes": "Updated note"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(upd.status_code, 200)
        self.assertEqual(upd.json()["status"], "SAVED")

        # Step-by-step guidance has 10 structured steps
        detail = self.client.get("/api/schemes/gruha-lakshmi")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["application_steps"]), 10)

    def test_09_gemini_chat_grounding_and_persistence(self):
        app_id, token = self._create_applicant("9000000009", {
            "name": "Deepa",
            "age": 29,
            "gender": "Female",
            "state": "Karnataka",
            "ration_card_type": "BPL",
            "is_taxpayer": False,
        })
        c1 = self.client.post("/api/chat", json={"message": "Tell me about Gruha Lakshmi"}, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(c1.status_code, 200)
        sid = c1.json()["session_id"]
        self.assertEqual(c1.json()["selected_scheme_id"], "gruha-lakshmi")

        # Follow-up without repeating scheme name -> remembers selected_scheme_id
        c2 = self.client.post("/api/chat", json={"session_id": sid, "message": "Am I eligible for this scheme?"}, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(c2.status_code, 200)
        self.assertEqual(c2.json()["selected_scheme_id"], "gruha-lakshmi")
        self.assertEqual(c2.json()["eligibility"]["outcome"], "ELIGIBLE")
        self.assertIn("ELIGIBLE", c2.json()["reply"])

        # Chat history persisted
        hist = self.client.get(f"/api/chat/sessions/{sid}", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(hist.status_code, 200)
        self.assertEqual(len(hist.json()["messages"]), 4)

    def test_10_access_control_and_scheme_versioning(self):
        _, token_a = self._create_applicant("9000000010", {"name": "User A", "state": "Karnataka"})
        _, token_b = self._create_applicant("9000000011", {"name": "User B", "state": "Karnataka"})
        draft_a = self.client.post("/api/drafts", json={"scheme_id": "shakti-karnataka"}, headers={"Authorization": f"Bearer {token_a}"}).json()
        # User B cannot update User A's draft
        forbidden = self.client.put(f"/api/drafts/{draft_a['id']}", json={"status": "SAVED"}, headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(forbidden.status_code, 403)

        # Scheme update preserves previous version
        upd = self.client.post("/api/schemes/shakti-karnataka/update", json={
            "operational_status": "ACTIVE",
            "change_summary": "Smart card rollout approved",
            "source_url": "https://www.karnataka.com/govt/shakti-scheme-karnataka/",
            "effective_date": "2026-11-11",
        })
        self.assertEqual(upd.status_code, 200)
        self.assertTrue(upd.json()["archived_previous_version"])


if __name__ == "__main__":
    unittest.main()
