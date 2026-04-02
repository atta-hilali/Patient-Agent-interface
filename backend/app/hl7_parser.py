from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _field(fields: list[str], index: int) -> str:
    return fields[index] if index < len(fields) else ""


def _component(value: str, index: int) -> str:
    parts = value.split("^")
    return parts[index] if index < len(parts) else ""


def _clean_segments(message: str) -> list[str]:
    if not message:
        return []
    normalized = message.replace("\r\n", "\r").replace("\n", "\r")
    return [segment.strip() for segment in normalized.split("\r") if segment.strip()]


def parse_hl7_message(message: str) -> dict[str, Any]:
    segments = _clean_segments(message)
    patient: dict[str, Any] = {}
    medications: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    allergies: list[dict[str, Any]] = []
    appointments: list[dict[str, Any]] = []
    segment_meta: list[dict[str, Any]] = []

    for index, segment in enumerate(segments, start=1):
        fields = segment.split("|")
        segment_type = _field(fields, 0).upper()
        segment_meta.append({"index": index, "type": segment_type, "raw": segment})

        if segment_type == "MSH":
            patient.setdefault("messageControlId", _field(fields, 9))
            patient.setdefault("sendingApplication", _field(fields, 2))
            patient.setdefault("sendingFacility", _field(fields, 3))
            continue

        if segment_type == "PID":
            patient_id = _component(_field(fields, 3), 0) or _component(_field(fields, 2), 0)
            family = _component(_field(fields, 5), 0)
            given = _component(_field(fields, 5), 1)
            patient["id"] = patient_id or patient.get("id") or "hl7-patient"
            patient["name"] = f"{given} {family}".strip() or "Unknown Patient"
            patient["birthDate"] = _field(fields, 7)
            patient["gender"] = _field(fields, 8)
            continue

        if segment_type == "DG1":
            conditions.append(
                {
                    "id": f"dg1-{index}",
                    "name": _component(_field(fields, 3), 1) or _component(_field(fields, 3), 0),
                    "clinicalStatus": _field(fields, 6),
                    "onsetDate": _field(fields, 5),
                }
            )
            continue

        if segment_type == "OBX":
            observations.append(
                {
                    "id": f"obx-{index}",
                    "name": _component(_field(fields, 3), 1) or _component(_field(fields, 3), 0),
                    "value": _field(fields, 5),
                    "unit": _field(fields, 6),
                    "status": _field(fields, 11),
                    "effectiveDate": _field(fields, 14),
                }
            )
            continue

        if segment_type in {"RXE", "RXO", "RXA"}:
            medications.append(
                {
                    "id": f"{segment_type.lower()}-{index}",
                    "name": _component(_field(fields, 2), 1) or _component(_field(fields, 2), 0),
                    "dosage": _field(fields, 3),
                    "status": _field(fields, 21) or "active",
                    "startDate": _field(fields, 16) or _field(fields, 4),
                }
            )
            continue

        if segment_type == "AL1":
            allergies.append(
                {
                    "id": f"al1-{index}",
                    "substance": _component(_field(fields, 3), 1) or _component(_field(fields, 3), 0),
                    "reaction": _field(fields, 5),
                    "criticality": _field(fields, 4),
                    "status": "active",
                }
            )
            continue

        if segment_type == "SCH":
            appointments.append(
                {
                    "id": f"sch-{index}",
                    "description": _component(_field(fields, 7), 1) or _field(fields, 7),
                    "start": _field(fields, 11),
                    "end": _field(fields, 12),
                    "status": _field(fields, 25) or "booked",
                }
            )

    if "id" not in patient:
        patient["id"] = "hl7-patient"
    if "name" not in patient:
        patient["name"] = "Unknown Patient"

    return {
        "patient": patient,
        "medications": medications,
        "conditions": conditions,
        "observations": observations,
        "allergies": allergies,
        "appointments": appointments,
        "documents": [],
        "carePlan": [],
        "segments": segment_meta,
        "receivedAt": _now_iso(),
    }


def build_hl7_ack(original_message: str, *, ack_code: str = "AA", text: str = "Message accepted") -> str:
    segments = _clean_segments(original_message)
    msh_fields = segments[0].split("|") if segments and segments[0].startswith("MSH") else []
    sending_app = _field(msh_fields, 2)
    sending_fac = _field(msh_fields, 3)
    receiving_app = _field(msh_fields, 4)
    receiving_fac = _field(msh_fields, 5)
    control_id = _field(msh_fields, 9) or "unknown-control-id"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    ack_message_id = f"ACK-{timestamp}"
    msh = (
        f"MSH|^~\\&|{receiving_app}|{receiving_fac}|{sending_app}|{sending_fac}|"
        f"{timestamp}||ACK^A01|{ack_message_id}|P|2.5"
    )
    msa = f"MSA|{ack_code}|{control_id}|{text}"
    return "\r".join([msh, msa]) + "\r"
