# from __future__ import annotations
from __future__ import annotations

# from typing import Any
from typing import Any

# from pydantic import BaseModel, Field
from pydantic import BaseModel, Field


# class SessionToolInput(BaseModel):
class SessionToolInput(BaseModel):
    # session_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


# class InteractionToolInput(BaseModel):
class InteractionToolInput(BaseModel):
    # rxcuis: list[str] = Field(default_factory=list)
    rxcuis: list[str] = Field(default_factory=list)
    # session_id: str | None = None
    session_id: str | None = None


# class GuidelineSearchInput(BaseModel):
class GuidelineSearchInput(BaseModel):
    # query: str = Field(min_length=1)
    query: str = Field(min_length=1)


# class ImageAnalysisInput(BaseModel):
class ImageAnalysisInput(BaseModel):
    # image_b64: str = Field(min_length=1)
    image_b64: str = Field(min_length=1)
    # patient_context_summary: str = ""
    patient_context_summary: str = ""


# class EscalationToolInput(BaseModel):
class EscalationToolInput(BaseModel):
    # session_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    # patient_id: str | None = None
    patient_id: str | None = None
    # reason: str = Field(min_length=1)
    reason: str = Field(min_length=1)


# class ToolTextResult(BaseModel):
class ToolTextResult(BaseModel):
    # tool_name: str
    tool_name: str
    # summary: str
    summary: str
    # data: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


# class MedicationRecord(BaseModel):
class MedicationRecord(BaseModel):
    # name: str
    name: str
    # dose: str = ""
    dose: str = ""
    # frequency: str = ""
    frequency: str = ""
    # route: str = ""
    route: str = ""
    # indication: str = ""
    indication: str = ""


# class LabRecord(BaseModel):
class LabRecord(BaseModel):
    # name: str
    name: str
    # value: str = ""
    value: str = ""
    # unit: str = ""
    unit: str = ""
    # reference_range: str = ""
    reference_range: str = ""
    # interpretation: str = ""
    interpretation: str = ""
    # effective_date: str = ""
    effective_date: str = ""


# class AppointmentRecord(BaseModel):
class AppointmentRecord(BaseModel):
    # label: str
    label: str
    # when: str = ""
    when: str = ""
    # provider: str = ""
    provider: str = ""
    # location: str = ""
    location: str = ""
    # prep_notes: str = ""
    prep_notes: str = ""


# class CarePlanRecord(BaseModel):
class CarePlanRecord(BaseModel):
    # title: str
    title: str
    # activity: str = ""
    activity: str = ""
    # goal: str = ""
    goal: str = ""


# class DocumentRecord(BaseModel):
class DocumentRecord(BaseModel):
    # title: str
    title: str
    # date: str = ""
    date: str = ""
    # source: str = ""
    source: str = ""
    # content: str = ""
    content: str = ""


# class InteractionRecord(BaseModel):
class InteractionRecord(BaseModel):
    # severity: str
    severity: str
    # description: str
    description: str


# class GuidelineChunk(BaseModel):
class GuidelineChunk(BaseModel):
    # chunk_id: str
    chunk_id: str
    # content: str
    content: str


# class ImageFinding(BaseModel):
class ImageFinding(BaseModel):
    # finding: str
    finding: str


# def dump_tool_result(result: ToolTextResult) -> str:
def dump_tool_result(result: ToolTextResult) -> str:
    # return result.model_dump_json()
    return result.model_dump_json()
