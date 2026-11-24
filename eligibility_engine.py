import json
from datetime import date, datetime
from typing import Any

from database import get_connection, utc_now


def compute_age_from_dob(dob_str: str | None) -> int | None:
    if not dob_str:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d %B %Y"):
        try:
            born = datetime.strptime(dob_str.strip(), fmt).date()
            today = date.today()
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except ValueError:
            continue
    return None


def _normalize_str(val: Any) -> str:
    return str(val).strip().lower() if val is not None else ""


def _evaluate_single_rule(profile: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    field = rule["field_name"]
    op = rule["operator"]
    raw_expected = rule["expected_value"]
    is_exclusion = bool(rule["is_exclusion"])
    desc = rule["description"]

    expected = json.loads(raw_expected) if raw_expected is not None else None
    actual = profile.get(field)

    # Derive age if missing but dob exists
    if field == "age" and actual is None and profile.get("dob"):
        actual = compute_age_from_dob(profile.get("dob"))

    # Missing data check: never treat unknown/missing as satisfied
    if actual is None or (isinstance(actual, str) and actual.strip() == ""):
        return {
            "rule_id": rule["id"],
            "field_name": field,
            "description": desc,
            "is_exclusion": is_exclusion,
            "status": "MISSING",
            "actual_value": None,
            "expected_value": expected,
            "reason": f"Missing required applicant field '{field}' ({desc}).",
        }

    passed = False
    if op == "eq":
        passed = _normalize_str(actual) == _normalize_str(expected)
    elif op == "neq":
        passed = _normalize_str(actual) != _normalize_str(expected)
    elif op == "in":
        opts = [_normalize_str(x) for x in (expected or [])]
        passed = _normalize_str(actual) in opts
    elif op == "not_in":
        opts = [_normalize_str(x) for x in (expected or [])]
        passed = _normalize_str(actual) not in opts
    elif op == "gte":
        passed = float(actual) >= float(expected)
    elif op == "lte":
        passed = float(actual) <= float(expected)
    elif op == "gt":
        passed = float(actual) > float(expected)
    elif op == "lt":
        passed = float(actual) < float(expected)
    elif op == "between":
        low, high = float(expected[0]), float(expected[1])
        passed = low <= float(actual) <= high
    elif op == "is_true":
        passed = bool(actual) is True and _normalize_str(actual) not in ("false", "0", "no")
    elif op == "is_false":
        passed = not bool(actual) or _normalize_str(actual) in ("false", "0", "no")

    # For exclusion rules, if the exclusion condition matches, the applicant FAILS the rule
    if is_exclusion:
        rule_ok = not passed
        reason = (
            f"Exclusion triggered: {desc} (applicant value: {actual})."
            if not rule_ok
            else f"Exclusion not triggered: {desc}."
        )
    else:
        rule_ok = passed
        reason = (
            f"Passed: {desc} (applicant value: {actual})."
            if rule_ok
            else f"Failed: {desc} (applicant value: {actual}, required: {expected})."
        )

    return {
        "rule_id": rule["id"],
        "field_name": field,
        "description": desc,
        "is_exclusion": is_exclusion,
        "status": "PASS" if rule_ok else "FAIL",
        "actual_value": actual,
        "expected_value": expected,
        "reason": reason,
    }


def evaluate_scheme_eligibility(
    profile: dict[str, Any],
    scheme_id: str,
    db_path: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    conn = get_connection(db_path)
    scheme_row = conn.execute("SELECT * FROM schemes WHERE id = ?", (scheme_id,)).fetchone()
    if not scheme_row:
        conn.close()
        raise ValueError(f"Scheme '{scheme_id}' not found")

    scheme = dict(scheme_row)
    rules_rows = conn.execute(
        "SELECT * FROM eligibility_rules WHERE scheme_id = ? ORDER BY rule_group, id",
        (scheme_id,),
    ).fetchall()
    rules = [dict(r) for r in rules_rows]

    # Check verification / operational status first
    if scheme["verification_status"] == "NOT_VERIFIED" or scheme["operational_status"] == "NOT_VERIFIED" or not rules:
        result = {
            "scheme_id": scheme_id,
            "scheme_name": scheme["name"],
            "outcome": "VERIFICATION_REQUIRED",
            "operational_status": scheme["operational_status"],
            "verification_status": scheme["verification_status"],
            "passed_rules": [],
            "failed_rules": [],
            "missing_fields": [],
            "rule_evaluations": [],
            "explanation": (
                f"Official eligibility rules for '{scheme['name']}' are currently marked "
                f"{scheme['verification_status']} / {scheme['operational_status']}. "
                "Labhya cannot declare eligibility without verified official rules."
            ),
            "evaluated_at": utc_now(),
        }
        if persist and profile.get("id"):
            _save_eligibility_result(conn, profile["id"], result)
        conn.close()
        return result

    if scheme["operational_status"] in ("DISCONTINUED", "APPLICATIONS_CLOSED"):
        result = {
            "scheme_id": scheme_id,
            "scheme_name": scheme["name"],
            "outcome": "NOT_ELIGIBLE",
            "operational_status": scheme["operational_status"],
            "verification_status": scheme["verification_status"],
            "passed_rules": [],
            "failed_rules": [
                {
                    "field_name": "operational_status",
                    "description": f"Scheme status is {scheme['operational_status']}",
                    "reason": f"Scheme is currently {scheme['operational_status']}.",
                }
            ],
            "missing_fields": [],
            "rule_evaluations": [],
            "explanation": f"'{scheme['name']}' is currently {scheme['operational_status']}.",
            "evaluated_at": utc_now(),
        }
        if persist and profile.get("id"):
            _save_eligibility_result(conn, profile["id"], result)
        conn.close()
        return result

    # Group rules by rule_group to support AND / OR logic
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rules:
        groups.setdefault(r["rule_group"], []).append(r)

    passed_rules: list[dict[str, Any]] = []
    failed_rules: list[dict[str, Any]] = []
    missing_fields: list[dict[str, Any]] = []
    all_evals: list[dict[str, Any]] = []

    for group_name, group_rules in groups.items():
        logic = group_rules[0]["logic_operator"]
        group_evals = [_evaluate_single_rule(profile, r) for r in group_rules]
        all_evals.extend(group_evals)

        if logic == "AND":
            for ev in group_evals:
                if ev["status"] == "PASS":
                    passed_rules.append(ev)
                elif ev["status"] == "FAIL":
                    failed_rules.append(ev)
                else:
                    missing_fields.append(ev)
        else:  # OR group: satisfied if ANY rule in group passes
            any_pass = any(ev["status"] == "PASS" for ev in group_evals)
            any_missing = any(ev["status"] == "MISSING" for ev in group_evals)
            if any_pass:
                for ev in group_evals:
                    if ev["status"] == "PASS":
                        passed_rules.append(ev)
            elif any_missing:
                for ev in group_evals:
                    if ev["status"] == "MISSING":
                        missing_fields.append(ev)
            else:
                failed_rules.extend(group_evals)

    # Deterministic outcome decision:
    # 1. If any mandatory rule FAILED -> NOT_ELIGIBLE (even if other fields are missing)
    # 2. Else if any required field is MISSING -> INCOMPLETE_INFORMATION
    # 3. Else if scheme is PARTIALLY_VERIFIED -> VERIFICATION_REQUIRED
    # 4. Else -> ELIGIBLE
    if failed_rules:
        outcome = "NOT_ELIGIBLE"
        explanation = (
            f"Not eligible for {scheme['name']}: "
            + "; ".join(f["reason"] for f in failed_rules)
        )
    elif missing_fields:
        outcome = "INCOMPLETE_INFORMATION"
        missing_names = sorted({m["field_name"] for m in missing_fields})
        explanation = (
            f"Cannot determine full eligibility for {scheme['name']} yet. "
            f"Missing required details: {', '.join(missing_names)}."
        )
    elif scheme["verification_status"] == "PARTIALLY_VERIFIED":
        outcome = "VERIFICATION_REQUIRED"
        explanation = (
            f"All checked rules passed for {scheme['name']}, but some scheme guidelines "
            "require official portal verification."
        )
    else:
        outcome = "ELIGIBLE"
        explanation = (
            f"Eligible for {scheme['name']}: all {len(passed_rules)} verified conditions passed."
        )

    result = {
        "scheme_id": scheme_id,
        "scheme_name": scheme["name"],
        "outcome": outcome,
        "operational_status": scheme["operational_status"],
        "verification_status": scheme["verification_status"],
        "passed_rules": passed_rules,
        "failed_rules": failed_rules,
        "missing_fields": missing_fields,
        "rule_evaluations": all_evals,
        "explanation": explanation,
        "evaluated_at": utc_now(),
    }

    if persist and profile.get("id"):
        _save_eligibility_result(conn, profile["id"], result)
    conn.close()
    return result


def _save_eligibility_result(conn, applicant_id: str, result: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO eligibility_results (
            applicant_id, scheme_id, outcome, passed_rules_json,
            failed_rules_json, missing_fields_json, explanation, evaluated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            applicant_id,
            result["scheme_id"],
            result["outcome"],
            json.dumps(result["passed_rules"]),
            json.dumps(result["failed_rules"]),
            json.dumps(result["missing_fields"]),
            result["explanation"],
            result["evaluated_at"],
        ),
    )
    conn.commit()


def evaluate_all_schemes(profile: dict[str, Any], db_path: str | None = None, persist: bool = True) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    rows = conn.execute("SELECT id FROM schemes ORDER BY name").fetchall()
    conn.close()
    results = [evaluate_scheme_eligibility(profile, r["id"], db_path=db_path, persist=persist) for r in rows]
    order = {"ELIGIBLE": 0, "INCOMPLETE_INFORMATION": 1, "VERIFICATION_REQUIRED": 2, "NOT_ELIGIBLE": 3}
    results.sort(key=lambda x: (order.get(x["outcome"], 9), x["scheme_name"]))
    return results
