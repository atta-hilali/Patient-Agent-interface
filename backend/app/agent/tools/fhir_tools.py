# from __future__ import annotations
from __future__ import annotations

import asyncio
import time

# from langchain_core.tools import tool
from langchain_core.tools import tool

# from app.agent.tools.schemas import (
from app.agent.tools.schemas import (
    # AppointmentRecord,
    AppointmentRecord,
    # CarePlanRecord,
    CarePlanRecord,
    # DocumentRecord,
    DocumentRecord,
    # LabRecord,
    LabRecord,
    # MedicationRecord,
    MedicationRecord,
    # SessionToolInput,
    SessionToolInput,
    # ToolTextResult,
    ToolTextResult,
    # dump_tool_result,
    dump_tool_result,
# )
)
# from app.cache import read_context_for_session
from app.cache import read_context_for_session


_RXCUI_NAME_TTL_SEC = 60 * 60
_rxcui_name_cache: dict[str, tuple[float, str]] = {}


async def _resolve_rxcui_name(rxcui: str) -> str:
    code = (rxcui or "").strip()
    if not code:
        return ""
    cached = _rxcui_name_cache.get(code)
    now = time.time()
    if cached and cached[0] > now:
        return cached[1]

    try:
        import httpx

        url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{code}/properties.json"
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        name = str(((payload or {}).get("properties") or {}).get("name") or "").strip()
        if name:
            _rxcui_name_cache[code] = (now + _RXCUI_NAME_TTL_SEC, name)
            return name
    except Exception:  # noqa: BLE001
        return ""
    return ""


async def _resolve_medication_display_name(item) -> str:
    for candidate in (
        getattr(item, "name", ""),
        getattr(item, "generic", ""),
    ):
        text = (candidate or "").strip()
        if text:
            return text
    rxcui = (getattr(item, "rxcui", "") or "").strip()
    if rxcui:
        resolved = await _resolve_rxcui_name(rxcui)
        if resolved:
            return resolved
        return f"Unknown medication (RxCUI: {rxcui})"
    item_id = (getattr(item, "id", "") or "").strip()
    if item_id:
        return f"Unknown medication (EHR id: {item_id})"
    return "Unknown medication"


# @tool(args_schema=SessionToolInput)
@tool(args_schema=SessionToolInput)
# async def get_medications(session_id: str) -> str:
async def get_medications(session_id: str) -> str:
    # """Return active medications with full dosing detail from cached patient context."""
    """Return active medications with full dosing detail from cached patient context."""
    # ctx = await read_context_for_session(session_id)
    ctx = await read_context_for_session(session_id)
    # if not ctx or not ctx.medications:
    if not ctx or not ctx.medications:
        # return dump_tool_result(ToolTextResult(tool_name="get_medications", summary="No active medications found."))
        return dump_tool_result(ToolTextResult(tool_name="get_medications", summary="No active medications found."))

    # medications = [
    names = await asyncio.gather(*[_resolve_medication_display_name(item) for item in ctx.medications])
    medications = []
    for item, name in zip(ctx.medications, names):
        medications.append(
            MedicationRecord(
                name=name,
                dose=item.dose or item.dosage or "",
                frequency=item.frequency or "",
                route=item.route or "",
                indication=item.indication or "",
            )
        )
    # summary = "\n".join(
    summary = "\n".join(
        # f"{record.name}: {record.dose or 'dose unavailable'}"
        f"{record.name}: {record.dose or 'dose unavailable'}"
        # + (f" | {record.frequency}" if record.frequency else "")
        + (f" | {record.frequency}" if record.frequency else "")
        # + (f" | {record.route}" if record.route else "")
        + (f" | {record.route}" if record.route else "")
        # + (f" | {record.indication}" if record.indication else "")
        + (f" | {record.indication}" if record.indication else "")
        # for record in medications
        for record in medications
    # )
    )
    # return dump_tool_result(
    return dump_tool_result(
        # ToolTextResult(
        ToolTextResult(
            # tool_name="get_medications",
            tool_name="get_medications",
            # summary=summary,
            summary=summary,
            # data={"medications": [record.model_dump(mode="json") for record in medications]},
            data={"medications": [record.model_dump(mode="json") for record in medications]},
        # )
        )
    # )
    )


# @tool(args_schema=SessionToolInput)
@tool(args_schema=SessionToolInput)
# async def get_labs(session_id: str) -> str:
async def get_labs(session_id: str) -> str:
    # """Return lab results with values, reference ranges, and interpretation."""
    """Return lab results with values, reference ranges, and interpretation."""
    # ctx = await read_context_for_session(session_id)
    ctx = await read_context_for_session(session_id)
    # if not ctx or not ctx.labs:
    if not ctx or not ctx.labs:
        # return dump_tool_result(ToolTextResult(tool_name="get_labs", summary="No lab results found."))
        return dump_tool_result(ToolTextResult(tool_name="get_labs", summary="No lab results found."))

    # labs = [
    labs = [
        # LabRecord(
        LabRecord(
            # name=lab.name,
            name=lab.name,
            # value=lab.value,
            value=lab.value,
            # unit=lab.unit,
            unit=lab.unit,
            # reference_range=lab.referenceRange,
            reference_range=lab.referenceRange,
            # interpretation=lab.interpretation,
            interpretation=lab.interpretation,
            # effective_date=lab.effectiveDate,
            effective_date=lab.effectiveDate,
        # )
        )
        # for lab in ctx.labs
        for lab in ctx.labs
    # ]
    ]
    # summary = "\n".join(
    summary = "\n".join(
        # f"{record.name}: {record.value} {record.unit} (ref: {record.reference_range or 'unavailable'})"
        f"{record.name}: {record.value} {record.unit} (ref: {record.reference_range or 'unavailable'})"
        # + (f" | interpretation: {record.interpretation}" if record.interpretation else "")
        + (f" | interpretation: {record.interpretation}" if record.interpretation else "")
        # + (f" | date: {record.effective_date}" if record.effective_date else "")
        + (f" | date: {record.effective_date}" if record.effective_date else "")
        # for record in labs
        for record in labs
    # )
    )
    # return dump_tool_result(
    return dump_tool_result(
        # ToolTextResult(
        ToolTextResult(
            # tool_name="get_labs",
            tool_name="get_labs",
            # summary=summary,
            summary=summary,
            # data={"labs": [record.model_dump(mode="json") for record in labs]},
            data={"labs": [record.model_dump(mode="json") for record in labs]},
        # )
        )
    # )
    )


# @tool(args_schema=SessionToolInput)
@tool(args_schema=SessionToolInput)
# async def get_appointments(session_id: str) -> str:
async def get_appointments(session_id: str) -> str:
    # """Return appointments and any available preparation notes from cached patient context."""
    """Return appointments and any available preparation notes from cached patient context."""
    # ctx = await read_context_for_session(session_id)
    ctx = await read_context_for_session(session_id)
    # if not ctx or not ctx.appointments:
    if not ctx or not ctx.appointments:
        # return dump_tool_result(ToolTextResult(tool_name="get_appointments", summary="No appointments found."))
        return dump_tool_result(ToolTextResult(tool_name="get_appointments", summary="No appointments found."))

    # appointments = [
    appointments = [
        # AppointmentRecord(
        AppointmentRecord(
            # label=appointment.description or appointment.specialty or "Appointment",
            label=appointment.description or appointment.specialty or "Appointment",
            # when=appointment.start or appointment.end or "",
            when=appointment.start or appointment.end or "",
            # provider=appointment.provider or "",
            provider=appointment.provider or "",
            # location=appointment.location or "",
            location=appointment.location or "",
            # prep_notes=appointment.description or "",
            prep_notes=appointment.description or "",
        # )
        )
        # for appointment in ctx.appointments
        for appointment in ctx.appointments
    # ]
    ]
    # summary = "\n".join(
    summary = "\n".join(
        # f"{record.label} | {record.when or 'time unavailable'}"
        f"{record.label} | {record.when or 'time unavailable'}"
        # + (f" | provider: {record.provider}" if record.provider else "")
        + (f" | provider: {record.provider}" if record.provider else "")
        # + (f" | location: {record.location}" if record.location else "")
        + (f" | location: {record.location}" if record.location else "")
        # + (f" | prep: {record.prep_notes}" if record.prep_notes else "")
        + (f" | prep: {record.prep_notes}" if record.prep_notes else "")
        # for record in appointments
        for record in appointments
    # )
    )
    # return dump_tool_result(
    return dump_tool_result(
        # ToolTextResult(
        ToolTextResult(
            # tool_name="get_appointments",
            tool_name="get_appointments",
            # summary=summary,
            summary=summary,
            # data={"appointments": [record.model_dump(mode="json") for record in appointments]},
            data={"appointments": [record.model_dump(mode="json") for record in appointments]},
        # )
        )
    # )
    )


# @tool(args_schema=SessionToolInput)
@tool(args_schema=SessionToolInput)
# async def get_care_plan(session_id: str) -> str:
async def get_care_plan(session_id: str) -> str:
    # """Return care plan activities, goals, and follow-up instructions from cached context."""
    """Return care plan activities, goals, and follow-up instructions from cached context."""
    # ctx = await read_context_for_session(session_id)
    ctx = await read_context_for_session(session_id)
    # if not ctx or not ctx.carePlan:
    if not ctx or not ctx.carePlan:
        # return dump_tool_result(ToolTextResult(tool_name="get_care_plan", summary="No care plan items found."))
        return dump_tool_result(ToolTextResult(tool_name="get_care_plan", summary="No care plan items found."))

    # care_plan = [
    care_plan = [
        # CarePlanRecord(
        CarePlanRecord(
            # title=item.title or item.id,
            title=item.title or item.id,
            # activity=item.instruction or item.description or "",
            activity=item.instruction or item.description or "",
            # goal=item.description or item.instruction or "",
            goal=item.description or item.instruction or "",
        # )
        )
        # for item in ctx.carePlan
        for item in ctx.carePlan
    # ]
    ]
    # summary = "\n".join(
    summary = "\n".join(
        # f"{record.title}: {record.activity or 'activity unavailable'}"
        f"{record.title}: {record.activity or 'activity unavailable'}"
        # + (f" | goal: {record.goal}" if record.goal else "")
        + (f" | goal: {record.goal}" if record.goal else "")
        # for record in care_plan
        for record in care_plan
    # )
    )
    # return dump_tool_result(
    return dump_tool_result(
        # ToolTextResult(
        ToolTextResult(
            # tool_name="get_care_plan",
            tool_name="get_care_plan",
            # summary=summary,
            summary=summary,
            # data={"care_plan": [record.model_dump(mode="json") for record in care_plan]},
            data={"care_plan": [record.model_dump(mode="json") for record in care_plan]},
        # )
        )
    # )
    )


# @tool(args_schema=SessionToolInput)
@tool(args_schema=SessionToolInput)
# async def get_documents(session_id: str) -> str:
async def get_documents(session_id: str) -> str:
    # """Return discharge or after-visit document content from cached context or object storage URL."""
    """Return discharge or after-visit document content from cached context or object storage URL."""
    # ctx = await read_context_for_session(session_id)
    ctx = await read_context_for_session(session_id)
    # if not ctx or not ctx.documents:
    if not ctx or not ctx.documents:
        # return dump_tool_result(ToolTextResult(tool_name="get_documents", summary="No clinical documents found."))
        return dump_tool_result(ToolTextResult(tool_name="get_documents", summary="No clinical documents found."))

    # documents = []
    documents = []
    # for document in ctx.documents:
    for document in ctx.documents:
        # content = document.summary or ""
        content = document.summary or ""
        # source = "cache"
        source = "cache"
        # if document.url:
        if document.url:
            # source = document.url
            source = document.url
        # documents.append(
        documents.append(
            # DocumentRecord(
            DocumentRecord(
                # title=document.title or document.id,
                title=document.title or document.id,
                # date=document.date or "",
                date=document.date or "",
                # source=source,
                source=source,
                # content=content or document.docType or document.author or "content unavailable",
                content=content or document.docType or document.author or "content unavailable",
            # )
            )
        # )
        )
    # summary = "\n".join(
    summary = "\n".join(
        # f"{record.title} ({record.date or 'date unavailable'}): {record.content}"
        f"{record.title} ({record.date or 'date unavailable'}): {record.content}"
        # for record in documents
        for record in documents
    # )
    )
    # return dump_tool_result(
    return dump_tool_result(
        # ToolTextResult(
        ToolTextResult(
            # tool_name="get_documents",
            tool_name="get_documents",
            # summary=summary,
            summary=summary,
            # data={"documents": [record.model_dump(mode="json") for record in documents]},
            data={"documents": [record.model_dump(mode="json") for record in documents]},
        # )
        )
    # )
    )
