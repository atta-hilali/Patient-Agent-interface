from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import PatientContext


@dataclass
class ResolvedCitation:
    tag: str
    sourceType: str
    sourceId: str
    resourceType: str
    resourceId: str
    reference: str
    note: str


def _resource_collection(ctx: PatientContext, resource_type: str) -> list[Any]:
    normalized = (resource_type or "").strip().lower()
    if normalized in {"medicationrequest", "medication"}:
        return list(ctx.medications)
    if normalized == "condition":
        return list(ctx.conditions)
    if normalized in {"observation", "diagnosticreport"}:
        return list(ctx.labs)
    if normalized == "appointment":
        return list(ctx.appointments)
    if normalized == "careplan":
        return list(ctx.carePlan)
    if normalized in {"allergyintolerance", "allergy"}:
        return list(ctx.allergies)
    if normalized in {"documentreference", "document"}:
        return list(ctx.documents)
    return []


def _lookup_fallback_note(item: Any, resource_type: str) -> str:
    normalized = (resource_type or "").strip().lower()
    if normalized in {"medicationrequest", "medication"}:
        name = getattr(item, "name", "") or getattr(item, "id", "")
        dose = getattr(item, "dose", "") or getattr(item, "dosage", "")
        return " ".join(part for part in [name, dose] if part).strip()
    if normalized == "condition":
        return getattr(item, "name", "") or getattr(item, "id", "")
    if normalized in {"observation", "diagnosticreport"}:
        name = getattr(item, "name", "") or getattr(item, "id", "")
        value = getattr(item, "value", "")
        unit = getattr(item, "unit", "")
        return " ".join(part for part in [name, value, unit] if part).strip()
    if normalized == "appointment":
        desc = getattr(item, "description", "") or getattr(item, "specialty", "") or "Appointment"
        start = getattr(item, "start", "")
        return " | ".join(part for part in [desc, start] if part).strip()
    if normalized == "careplan":
        title = getattr(item, "title", "") or getattr(item, "id", "")
        instruction = getattr(item, "instruction", "") or getattr(item, "description", "")
        return " | ".join(part for part in [title, instruction] if part).strip()
    if normalized in {"allergyintolerance", "allergy"}:
        return getattr(item, "substance", "") or getattr(item, "id", "")
    if normalized in {"documentreference", "document"}:
        return getattr(item, "title", "") or getattr(item, "id", "")
    return ""


def _lookup_resource_id_from_tag(tag: str, resource_type: str, ctx: PatientContext) -> tuple[str, str]:
    # Tags usually follow patterns like MED-1 / COND-2 / LAB-3.
    parts = tag.split("-")
    if len(parts) < 2:
        return "", ""
    try:
        index = int(parts[-1]) - 1
    except ValueError:
        return "", ""
    if index < 0:
        return "", ""

    collection = _resource_collection(ctx, resource_type)
    if index >= len(collection):
        return "", ""
    item = collection[index]
    resource_id = str(getattr(item, "id", "") or "")
    note = _lookup_fallback_note(item, resource_type)
    return resource_id, note


def resolve_citations(raw: list[dict], ctx: PatientContext) -> list[ResolvedCitation]:
    if not isinstance(raw, list):
        return []

    resolved: list[ResolvedCitation] = []
    for index, citation in enumerate(raw, start=1):
        if not isinstance(citation, dict):
            continue

        tag = str(citation.get("tag") or citation.get("id") or f"CITE-{index}")
        resource_type = str(
            citation.get("resourceType")
            or citation.get("resource_type")
            or citation.get("type")
            or "source"
        )
        source_type = str(citation.get("sourceType") or citation.get("source_type") or ctx.sourceType or "")
        source_id = str(citation.get("sourceId") or citation.get("source_id") or ctx.sourceId or "")

        resource_id = str(citation.get("resourceId") or citation.get("resource_id") or "")
        note = str(citation.get("note") or "")
        if not resource_id or not note:
            lookup_id, lookup_note = _lookup_resource_id_from_tag(tag, resource_type, ctx)
            resource_id = resource_id or lookup_id
            note = note or lookup_note

        reference = str(citation.get("reference") or "")
        if not reference:
            reference = f"{resource_type}/{resource_id}" if resource_id else resource_type

        resolved.append(
            ResolvedCitation(
                tag=tag,
                sourceType=source_type,
                sourceId=source_id,
                resourceType=resource_type,
                resourceId=resource_id,
                reference=reference,
                note=note,
            )
        )
    return resolved

