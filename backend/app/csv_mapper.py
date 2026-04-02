from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any


DEFAULT_MAPPING = {
    "patientId": "patient_id",
    "patientName": "patient_name",
    "birthDate": "birth_date",
    "gender": "gender",
    "medicationName": "medication",
    "medicationStatus": "medication_status",
    "medicationDosage": "medication_dosage",
    "conditionName": "condition",
    "conditionStatus": "condition_status",
    "labName": "lab_name",
    "labValue": "lab_value",
    "labUnit": "lab_unit",
    "labDate": "lab_date",
    "allergySubstance": "allergy",
    "allergyReaction": "allergy_reaction",
    "allergyCriticality": "allergy_criticality",
    "appointmentDescription": "appointment",
    "appointmentStart": "appointment_start",
    "appointmentEnd": "appointment_end",
    "documentTitle": "document_title",
    "documentDate": "document_date",
    "carePlanTitle": "care_plan_title",
    "carePlanStatus": "care_plan_status",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_csv_text(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    if not csv_text.strip():
        raise ValueError("CSV text is empty.")
    stream = io.StringIO(csv_text)
    reader = csv.DictReader(stream)
    headers = reader.fieldnames or []
    rows = [{key: _text(val) for key, val in row.items()} for row in reader]
    if not headers:
        raise ValueError("CSV headers are missing.")
    return headers, rows


def apply_csv_mapping(
    *,
    csv_text: str,
    mapping: dict[str, str] | None = None,
    patient_id_hint: str = "",
) -> dict[str, Any]:
    headers, rows = parse_csv_text(csv_text)
    field_map = dict(DEFAULT_MAPPING)
    if mapping:
        field_map.update({key: value for key, value in mapping.items() if value})

    def row_value(row: dict[str, str], key: str) -> str:
        source_col = field_map.get(key, "")
        if not source_col:
            return ""
        return _text(row.get(source_col, ""))

    patient_id = ""
    patient_name = ""
    birth_date = ""
    gender = ""
    medications: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    allergies: list[dict[str, Any]] = []
    appointments: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    care_plan: list[dict[str, Any]] = []

    for idx, row in enumerate(rows, start=1):
        patient_id = patient_id or row_value(row, "patientId")
        patient_name = patient_name or row_value(row, "patientName")
        birth_date = birth_date or row_value(row, "birthDate")
        gender = gender or row_value(row, "gender")

        medication_name = row_value(row, "medicationName")
        if medication_name:
            medications.append(
                {
                    "id": f"csv-med-{idx}",
                    "name": medication_name,
                    "status": row_value(row, "medicationStatus"),
                    "dosage": row_value(row, "medicationDosage"),
                }
            )

        condition_name = row_value(row, "conditionName")
        if condition_name:
            conditions.append(
                {
                    "id": f"csv-cond-{idx}",
                    "name": condition_name,
                    "clinicalStatus": row_value(row, "conditionStatus"),
                }
            )

        lab_name = row_value(row, "labName")
        if lab_name:
            observations.append(
                {
                    "id": f"csv-lab-{idx}",
                    "name": lab_name,
                    "value": row_value(row, "labValue"),
                    "unit": row_value(row, "labUnit"),
                    "effectiveDate": row_value(row, "labDate"),
                }
            )

        allergy_substance = row_value(row, "allergySubstance")
        if allergy_substance:
            allergies.append(
                {
                    "id": f"csv-alg-{idx}",
                    "substance": allergy_substance,
                    "reaction": row_value(row, "allergyReaction"),
                    "criticality": row_value(row, "allergyCriticality"),
                    "status": "active",
                }
            )

        appointment_desc = row_value(row, "appointmentDescription")
        if appointment_desc:
            appointments.append(
                {
                    "id": f"csv-appt-{idx}",
                    "description": appointment_desc,
                    "start": row_value(row, "appointmentStart"),
                    "end": row_value(row, "appointmentEnd"),
                    "status": "booked",
                }
            )

        document_title = row_value(row, "documentTitle")
        if document_title:
            documents.append(
                {
                    "id": f"csv-doc-{idx}",
                    "title": document_title,
                    "date": row_value(row, "documentDate"),
                }
            )

        care_plan_title = row_value(row, "carePlanTitle")
        if care_plan_title:
            care_plan.append(
                {
                    "id": f"csv-cp-{idx}",
                    "title": care_plan_title,
                    "status": row_value(row, "carePlanStatus"),
                }
            )

    resolved_patient_id = patient_id or patient_id_hint or "csv-patient"
    resolved_patient_name = patient_name or "CSV Patient"

    return {
        "patient": {
            "id": resolved_patient_id,
            "name": resolved_patient_name,
            "birthDate": birth_date,
            "gender": gender,
        },
        "medications": medications,
        "conditions": conditions,
        "observations": observations,
        "allergies": allergies,
        "appointments": appointments,
        "documents": documents,
        "carePlan": care_plan,
        "csvMeta": {
            "headers": headers,
            "rowCount": len(rows),
            "mappingApplied": field_map,
            "parsedAt": _now_iso(),
        },
    }
