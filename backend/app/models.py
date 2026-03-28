from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    tag: str = ""
    sourceType: str = ""
    sourceId: str = ""
    resourceType: str = ""
    resourceId: str = ""
    reference: str = ""
    note: str = ""


class PatientDemographics(BaseModel):
    patientId: str = ""
    fullName: str = ""
    givenName: str = ""
    familyName: str = ""
    birthDate: str = ""
    gender: str = ""
    mrn: str = ""
    citations: list[Citation] = Field(default_factory=list)


class MedicationItem(BaseModel):
    id: str = ""
    name: str = ""
    status: str = ""
    dosage: str = ""
    startDate: str = ""
    endDate: str = ""
    route: str = ""
    citations: list[Citation] = Field(default_factory=list)


class ConditionItem(BaseModel):
    id: str = ""
    name: str = ""
    clinicalStatus: str = ""
    verificationStatus: str = ""
    onsetDate: str = ""
    abatementDate: str = ""
    severity: str = ""
    citations: list[Citation] = Field(default_factory=list)


class AllergyItem(BaseModel):
    id: str = ""
    substance: str = ""
    criticality: str = ""
    status: str = ""
    reaction: str = ""
    category: str = ""
    citations: list[Citation] = Field(default_factory=list)


class LabItem(BaseModel):
    id: str = ""
    name: str = ""
    value: str = ""
    unit: str = ""
    interpretation: str = ""
    status: str = ""
    effectiveDate: str = ""
    citations: list[Citation] = Field(default_factory=list)


class AppointmentItem(BaseModel):
    id: str = ""
    description: str = ""
    status: str = ""
    start: str = ""
    end: str = ""
    location: str = ""
    citations: list[Citation] = Field(default_factory=list)


class CarePlanItem(BaseModel):
    id: str = ""
    title: str = ""
    status: str = ""
    description: str = ""
    start: str = ""
    end: str = ""
    citations: list[Citation] = Field(default_factory=list)


class DocumentItem(BaseModel):
    id: str = ""
    title: str = ""
    docType: str = ""
    date: str = ""
    author: str = ""
    url: str = ""
    citations: list[Citation] = Field(default_factory=list)


class ConflictItem(BaseModel):
    id: str = ""
    kind: str = ""
    severity: str = ""
    message: str = ""
    relatedIds: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class PatientContext(BaseModel):
    sourceType: str = ""
    sourceId: str = ""
    patientId: str = ""
    fetchedAt: str = ""
    demographics: PatientDemographics | None = None
    medications: list[MedicationItem] = Field(default_factory=list)
    conditions: list[ConditionItem] = Field(default_factory=list)
    allergies: list[AllergyItem] = Field(default_factory=list)
    labs: list[LabItem] = Field(default_factory=list)
    appointments: list[AppointmentItem] = Field(default_factory=list)
    carePlan: list[CarePlanItem] = Field(default_factory=list)
    documents: list[DocumentItem] = Field(default_factory=list)
    allergyConflicts: list[ConflictItem] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class WorkflowIngestRequest(BaseModel):
    sourceType: str = Field(min_length=1)
    sourceId: str = Field(min_length=1)
    patientId: str = Field(min_length=1)
    rawPayload: dict[str, Any]
    sessionId: str = ""
    consentAccepted: bool = False


class NormalizeRequest(WorkflowIngestRequest):
    pass


class Hl7IngestRequest(BaseModel):
    sourceId: str = "hl7-mllp"
    patientId: str = ""
    hl7Message: str = Field(min_length=1)
    consentAccepted: bool = False


class CdaIngestRequest(BaseModel):
    sourceId: str = "cda-upload"
    patientId: str = ""
    cdaXml: str = Field(min_length=1)
    xpathMap: dict[str, str] = Field(default_factory=dict)
    consentAccepted: bool = False


class CsvIngestRequest(BaseModel):
    sourceId: str = "csv-upload"
    patientId: str = ""
    csvText: str = Field(min_length=1)
    mapping: dict[str, str] = Field(default_factory=dict)
    consentAccepted: bool = False


class WorkflowSnapshot(BaseModel):
    updatedAt: str
    sourceType: str
    sourceId: str
    patientId: str
    adapter: str
    cacheHit: bool
    cacheKey: str
    chatUnlock: bool
    consentBanner: bool
    context: PatientContext
    prompt: str
    promptCitations: list[Citation] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class SafetyRuleMatch(BaseModel):
    rule: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class SafetyCheckRequest(BaseModel):
    text: str = Field(min_length=1)
    sourceType: str = ""
    sourceId: str = ""
    patientId: str = ""


class SafetyCheckResponse(BaseModel):
    safe: bool
    escalate: bool
    decision: str
    reason: str
    matchedRules: list[SafetyRuleMatch] = Field(default_factory=list)


class WorkflowUnlockRequest(BaseModel):
    sourceId: str = Field(min_length=1)
    patientId: str = Field(min_length=1)
    consentAccepted: bool = False


class WorkflowUnlockResponse(BaseModel):
    chatUnlock: bool
    reason: str
    consentRequired: bool
    consentAccepted: bool
    snapshotExists: bool
    cacheKey: str
