from __future__ import annotations

from dataclasses import dataclass

from .models import Citation, PatientContext


@dataclass
class PromptBuildResult:
    prompt: str
    citations: list[Citation]


def _copy_with_tag(citation: Citation, tag: str) -> Citation:
    return citation.model_copy(update={"tag": tag})


def _first_citation_or_fallback(
    *,
    existing: list[Citation],
    tag: str,
    source_type: str,
    source_id: str,
    resource_type: str,
    resource_id: str = "",
) -> Citation:
    if existing:
        return _copy_with_tag(existing[0], tag)
    reference = f"{resource_type}/{resource_id}" if resource_id else resource_type
    return Citation(
        tag=tag,
        sourceType=source_type,
        sourceId=source_id,
        resourceType=resource_type,
        resourceId=resource_id,
        reference=reference,
    )


def build_prompt_package(context: PatientContext) -> PromptBuildResult:
    citations: list[Citation] = []
    citation_map_lines: list[str] = []

    for index, item in enumerate(context.medications, start=1):
        tag = f"MED-{index}"
        citation = _first_citation_or_fallback(
            existing=item.citations,
            tag=tag,
            source_type=context.sourceType,
            source_id=context.sourceId,
            resource_type="Medication",
            resource_id=item.id,
        )
        citations.append(citation)
        if index <= 3:
            citation_map_lines.append(f"[{tag}] medication: {item.name or item.id or 'unknown'}")

    for index, item in enumerate(context.conditions, start=1):
        tag = f"COND-{index}"
        citation = _first_citation_or_fallback(
            existing=item.citations,
            tag=tag,
            source_type=context.sourceType,
            source_id=context.sourceId,
            resource_type="Condition",
            resource_id=item.id,
        )
        citations.append(citation)
        if index <= 3:
            citation_map_lines.append(f"[{tag}] condition: {item.name or item.id or 'unknown'}")

    for index, item in enumerate(context.labs, start=1):
        tag = f"LAB-{index}"
        citation = _first_citation_or_fallback(
            existing=item.citations,
            tag=tag,
            source_type=context.sourceType,
            source_id=context.sourceId,
            resource_type="Lab",
            resource_id=item.id,
        )
        citations.append(citation)
        if index <= 3:
            citation_map_lines.append(f"[{tag}] lab: {item.name or item.id or 'unknown'}")

    for index, item in enumerate(context.allergies, start=1):
        tag = f"ALG-{index}"
        citation = _first_citation_or_fallback(
            existing=item.citations,
            tag=tag,
            source_type=context.sourceType,
            source_id=context.sourceId,
            resource_type="Allergy",
            resource_id=item.id,
        )
        citations.append(citation)
        if index <= 3:
            citation_map_lines.append(f"[{tag}] allergy: {item.substance or item.id or 'unknown'}")

    for index, item in enumerate(context.documents, start=1):
        tag = f"DOC-{index}"
        citation = _first_citation_or_fallback(
            existing=item.citations,
            tag=tag,
            source_type=context.sourceType,
            source_id=context.sourceId,
            resource_type="Document",
            resource_id=item.id,
        )
        citations.append(citation)
        if index <= 2:
            citation_map_lines.append(f"[{tag}] document: {item.title or item.id or 'unknown'}")

    allergy_hard_stops = ", ".join(conflict.message for conflict in context.allergyConflicts[:3])
    if not allergy_hard_stops:
        allergy_hard_stops = "none detected in pre-compute stage"

    patient_name = context.demographics.fullName if context.demographics else "Unknown Patient"
    prompt_lines = [
        "You are Veldooc clinical assistant.",
        "Use only the provided PatientContext. If data is missing, explicitly say it is missing.",
        "Allowed: explain existing medication instructions from the record (timing, with-food notes, route, frequency).",
        "If exact timing is missing, provide safe general education (follow the prescription label, do not change dose on your own, contact prescriber for personalized schedule).",
        f"Patient: {patient_name} (patient_id={context.patientId})",
        (
            f"Provenance: source_type={context.sourceType}; "
            f"source_id={context.sourceId}; fetched_at={context.fetchedAt}"
        ),
        (
            "Inventory counts: "
            f"medications={len(context.medications)}, "
            f"conditions={len(context.conditions)}, "
            f"allergies={len(context.allergies)}, "
            f"labs={len(context.labs)}, "
            f"appointments={len(context.appointments)}, "
            f"care_plan={len(context.carePlan)}, "
            f"documents={len(context.documents)}"
        ),
        f"Allergy hard-stops: {allergy_hard_stops}",
        "Safety: never invent medications, allergies, or lab values.",
        "When making claims, cite with available tags such as [MED-1], [COND-1], [LAB-1].",
        "Citation map:",
    ]

    if citation_map_lines:
        prompt_lines.extend(citation_map_lines)
    else:
        prompt_lines.append("No source citations were generated from this payload.")

    return PromptBuildResult(prompt="\n".join(prompt_lines), citations=citations)
