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
    dose: str = ""
    frequency: str = ""
    indication: str = ""
    generic: str = ""
    rxcui: str = ""
    prescriber: str = ""
    source: str = "ehr"
    startDate: str = ""
    endDate: str = ""
    route: str = ""
    citations: list[Citation] = Field(default_factory=list)


class ConditionItem(BaseModel):
    id: str = ""
    name: str = ""
    snomedCode: str = ""
    icd10Code: str = ""
    clinicalStatus: str = ""
    verificationStatus: str = ""
    onsetDate: str = ""
    abatementDate: str = ""
    severity: str = ""
    citations: list[Citation] = Field(default_factory=list)


class AllergyItem(BaseModel):
    id: str = ""
    substance: str = ""
    rxcui: str = ""
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
    referenceRange: str = ""
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
    provider: str = ""
    specialty: str = ""
    citations: list[Citation] = Field(default_factory=list)


class CarePlanItem(BaseModel):
    id: str = ""
    title: str = ""
    status: str = ""
    description: str = ""
    instruction: str = ""
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
    summary: str = ""
    citations: list[Citation] = Field(default_factory=list)


class ConflictItem(BaseModel):
    id: str = ""
    kind: str = ""
    severity: str = ""
    message: str = ""
    relatedIds: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class AuthToken(BaseModel):
    access_token: str
    refresh_token: str | None = None
    patient_id: str
    clinic_id: str = ""
    expiry: str
    scope_list: list[str] = Field(default_factory=list)
    adapter_type: str = ""


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


class AsrTranscribeRequest(BaseModel):
    audioBase64: str = Field(min_length=1)
    mimeType: str = "audio/wav"
    language: str = ""
    fileName: str = "voice.wav"


class AsrTranscribeResponse(BaseModel):
    text: str
    language: str
    model: str = ""
    source: str = "nvidia-asr-nim"


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


class ContextSummary(BaseModel):
    patient_name: str
    medication_count: int
    condition_count: int
    allergy_count: int
    has_alert: bool
    alert_message: str | None = None
    next_appointment: str | None = None
    session_expires_at: str | None = None
    data_source: str | None = None


class WriteBackSessionSummaryRequest(BaseModel):
    sessionId: str = Field(min_length=1)
    patientId: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    clinicId: str = ""


class WriteBackObservationRequest(BaseModel):
    sessionId: str = Field(min_length=1)
    patientId: str = Field(min_length=1)
    loincCode: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str = ""
    clinicId: str = ""


class WriteBackFlagRequest(BaseModel):
    sessionId: str = Field(min_length=1)
    patientId: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    severity: str = "HIGH"
    clinicId: str = ""


class WriteBackResponse(BaseModel):
    ok: bool
    operation: str
    clinicId: str
    sourceType: str
    adapter: str
    resourceType: str
    detail: dict[str, Any] = Field(default_factory=dict)
