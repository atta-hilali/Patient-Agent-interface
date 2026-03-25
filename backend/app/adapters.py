from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import (
    AllergyItem,
    AppointmentItem,
    CarePlanItem,
    Citation,
    ConditionItem,
    DocumentItem,
    LabItem,
    MedicationItem,
    PatientContext,
    PatientDemographics,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _bundle_entries(bundle: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(bundle, dict):
        return []
    entries = bundle.get("entry")
    if not isinstance(entries, list):
        return []
    resources: list[dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("resource"), dict):
            resources.append(entry["resource"])
    return resources


def _first_coding_text(value: Any) -> str:
    if isinstance(value, dict):
        text = value.get("text")
        if text:
            return _as_str(text)
        coding = value.get("coding")
        if isinstance(coding, list):
            for item in coding:
                if not isinstance(item, dict):
                    continue
                display = item.get("display")
                code = item.get("code")
                if display:
                    return _as_str(display)
                if code:
                    return _as_str(code)
    if isinstance(value, list):
        for item in value:
            text = _first_coding_text(item)
            if text:
                return text
    return ""


def _build_citation(
    *,
    source_type: str,
    source_id: str,
    resource_type: str,
    resource_id: str = "",
    note: str = "",
) -> Citation:
    reference = f"{resource_type}/{resource_id}" if resource_id else resource_type
    return Citation(
        sourceType=source_type,
        sourceId=source_id,
        resourceType=resource_type,
        resourceId=resource_id,
        reference=reference,
        note=note,
    )


def _first_identifier(resource: dict[str, Any]) -> str:
    identifiers = resource.get("identifier")
    if not isinstance(identifiers, list):
        return ""
    for item in identifiers:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if value:
            return _as_str(value)
    return ""


def _name_parts(resource: dict[str, Any]) -> tuple[str, str, str]:
    names = resource.get("name")
    if not isinstance(names, list) or not names:
        return ("", "", "")
    primary = names[0]
    if not isinstance(primary, dict):
        return ("", "", "")
    given_val = primary.get("given")
    if isinstance(given_val, list):
        given = " ".join(_as_str(item) for item in given_val if item)
    else:
        given = _as_str(given_val)
    family = _as_str(primary.get("family"))
    full_name = f"{given} {family}".strip()
    return (full_name, given, family)


def _extract_demographics(
    *,
    source_type: str,
    source_id: str,
    patient_resource: dict[str, Any],
    patient_id: str,
) -> PatientDemographics:
    full_name, given_name, family_name = _name_parts(patient_resource)
    resolved_id = _as_str(patient_resource.get("id")) or patient_id
    citation = _build_citation(
        source_type=source_type,
        source_id=source_id,
        resource_type="Patient",
        resource_id=resolved_id,
    )
    return PatientDemographics(
        patientId=resolved_id,
        fullName=full_name or "Unknown Patient",
        givenName=given_name,
        familyName=family_name,
        birthDate=_as_str(patient_resource.get("birthDate")),
        gender=_as_str(patient_resource.get("gender")),
        mrn=_first_identifier(patient_resource),
        citations=[citation],
    )


class SourceAdapter:
    source_type: str = "unknown"
    adapter_name: str = "unknown-adapter"

    def adapt(
        self,
        *,
        source_id: str,
        patient_id: str,
        raw_payload: dict[str, Any],
    ) -> PatientContext:
        raise NotImplementedError


class FhirAdapter(SourceAdapter):
    source_type = "fhir_r4"
    adapter_name = "fhir-adapter"

    def _parse_medications(
        self,
        resources: Iterable[dict[str, Any]],
        *,
        source_id: str,
    ) -> list[MedicationItem]:
        out: list[MedicationItem] = []
        for resource in resources:
            resource_id = _as_str(resource.get("id"))
            dosage = ""
            route = ""
            dosage_instructions = resource.get("dosageInstruction")
            if isinstance(dosage_instructions, list) and dosage_instructions:
                first = dosage_instructions[0]
                if isinstance(first, dict):
                    dosage = _as_str(first.get("text"))
                    route = _first_coding_text(first.get("route"))

            out.append(
                MedicationItem(
                    id=resource_id,
                    name=_first_coding_text(resource.get("medicationCodeableConcept")),
                    status=_as_str(resource.get("status")),
                    dosage=dosage,
                    startDate=_as_str(resource.get("authoredOn")),
                    endDate=_as_str(
                        (
                            resource.get("dispenseRequest", {})
                            .get("validityPeriod", {})
                            .get("end")
                        )
                    ),
                    route=route,
                    citations=[
                        _build_citation(
                            source_type=self.source_type,
                            source_id=source_id,
                            resource_type=_as_str(resource.get("resourceType")) or "MedicationRequest",
                            resource_id=resource_id,
                        )
                    ],
                )
            )
        return out

    def _parse_conditions(
        self,
        resources: Iterable[dict[str, Any]],
        *,
        source_id: str,
    ) -> list[ConditionItem]:
        out: list[ConditionItem] = []
        for resource in resources:
            resource_id = _as_str(resource.get("id"))
            out.append(
                ConditionItem(
                    id=resource_id,
                    name=_first_coding_text(resource.get("code")),
                    clinicalStatus=_first_coding_text(resource.get("clinicalStatus")),
                    verificationStatus=_first_coding_text(resource.get("verificationStatus")),
                    onsetDate=_as_str(resource.get("onsetDateTime"))
                    or _as_str((resource.get("onsetPeriod", {}) or {}).get("start")),
                    abatementDate=_as_str(resource.get("abatementDateTime"))
                    or _as_str((resource.get("abatementPeriod", {}) or {}).get("end")),
                    severity=_first_coding_text(resource.get("severity")),
                    citations=[
                        _build_citation(
                            source_type=self.source_type,
                            source_id=source_id,
                            resource_type=_as_str(resource.get("resourceType")) or "Condition",
                            resource_id=resource_id,
                        )
                    ],
                )
            )
        return out

    def _parse_allergies(
        self,
        resources: Iterable[dict[str, Any]],
        *,
        source_id: str,
    ) -> list[AllergyItem]:
        out: list[AllergyItem] = []
        for resource in resources:
            resource_id = _as_str(resource.get("id"))
            reaction = ""
            reactions = resource.get("reaction")
            if isinstance(reactions, list) and reactions:
                reaction = _first_coding_text(reactions[0].get("manifestation"))
            categories = resource.get("category")
            category = ""
            if isinstance(categories, list):
                category = ", ".join(_as_str(item) for item in categories if item)

            out.append(
                AllergyItem(
                    id=resource_id,
                    substance=_first_coding_text(resource.get("code")),
                    criticality=_as_str(resource.get("criticality")),
                    status=_first_coding_text(resource.get("clinicalStatus"))
                    or _as_str(resource.get("verificationStatus")),
                    reaction=reaction,
                    category=category,
                    citations=[
                        _build_citation(
                            source_type=self.source_type,
                            source_id=source_id,
                            resource_type=_as_str(resource.get("resourceType")) or "AllergyIntolerance",
                            resource_id=resource_id,
                        )
                    ],
                )
            )
        return out

    def _parse_labs(
        self,
        resources: Iterable[dict[str, Any]],
        *,
        source_id: str,
    ) -> list[LabItem]:
        out: list[LabItem] = []
        for resource in resources:
            resource_id = _as_str(resource.get("id"))
            value = ""
            unit = ""
            if isinstance(resource.get("valueQuantity"), dict):
                value_quantity = resource["valueQuantity"]
                value = _as_str(value_quantity.get("value"))
                unit = _as_str(value_quantity.get("unit"))
            else:
                value = _as_str(resource.get("valueString")) or _as_str(resource.get("valueCodeableConcept"))

            out.append(
                LabItem(
                    id=resource_id,
                    name=_first_coding_text(resource.get("code")),
                    value=value,
                    unit=unit,
                    interpretation=_first_coding_text(resource.get("interpretation")),
                    status=_as_str(resource.get("status")),
                    effectiveDate=_as_str(resource.get("effectiveDateTime")) or _as_str(resource.get("issued")),
                    citations=[
                        _build_citation(
                            source_type=self.source_type,
                            source_id=source_id,
                            resource_type=_as_str(resource.get("resourceType")) or "Observation",
                            resource_id=resource_id,
                        )
                    ],
                )
            )
        return out

    def _parse_appointments(
        self,
        resources: Iterable[dict[str, Any]],
        *,
        source_id: str,
    ) -> list[AppointmentItem]:
        out: list[AppointmentItem] = []
        for resource in resources:
            resource_id = _as_str(resource.get("id"))
            location = ""
            participants = resource.get("participant")
            if isinstance(participants, list):
                for part in participants:
                    if not isinstance(part, dict):
                        continue
                    actor = part.get("actor")
                    if isinstance(actor, dict):
                        location = _as_str(actor.get("display")) or _as_str(actor.get("reference"))
                        if location:
                            break

            out.append(
                AppointmentItem(
                    id=resource_id,
                    description=_as_str(resource.get("description"))
                    or _first_coding_text(resource.get("serviceType")),
                    status=_as_str(resource.get("status")),
                    start=_as_str(resource.get("start")),
                    end=_as_str(resource.get("end")),
                    location=location,
                    citations=[
                        _build_citation(
                            source_type=self.source_type,
                            source_id=source_id,
                            resource_type=_as_str(resource.get("resourceType")) or "Appointment",
                            resource_id=resource_id,
                        )
                    ],
                )
            )
        return out

    def _parse_documents(
        self,
        resources: Iterable[dict[str, Any]],
        *,
        source_id: str,
    ) -> list[DocumentItem]:
        out: list[DocumentItem] = []
        for resource in resources:
            resource_id = _as_str(resource.get("id"))
            author = ""
            authors = resource.get("author")
            if isinstance(authors, list) and authors:
                first_author = authors[0]
                if isinstance(first_author, dict):
                    author = _as_str(first_author.get("display")) or _as_str(first_author.get("reference"))
            url = ""
            contents = resource.get("content")
            if isinstance(contents, list) and contents:
                first = contents[0]
                if isinstance(first, dict):
                    url = _as_str((first.get("attachment") or {}).get("url"))

            out.append(
                DocumentItem(
                    id=resource_id,
                    title=_as_str(resource.get("description")) or _first_coding_text(resource.get("type")),
                    docType=_first_coding_text(resource.get("type")),
                    date=_as_str(resource.get("date")),
                    author=author,
                    url=url,
                    citations=[
                        _build_citation(
                            source_type=self.source_type,
                            source_id=source_id,
                            resource_type=_as_str(resource.get("resourceType")) or "DocumentReference",
                            resource_id=resource_id,
                        )
                    ],
                )
            )
        return out

    def _parse_care_plans(
        self,
        resources: Iterable[dict[str, Any]],
        *,
        source_id: str,
    ) -> list[CarePlanItem]:
        out: list[CarePlanItem] = []
        for resource in resources:
            resource_id = _as_str(resource.get("id"))
            out.append(
                CarePlanItem(
                    id=resource_id,
                    title=_as_str(resource.get("title")) or _first_coding_text(resource.get("category")),
                    status=_as_str(resource.get("status")),
                    description=_as_str(resource.get("description")),
                    start=_as_str((resource.get("period") or {}).get("start")),
                    end=_as_str((resource.get("period") or {}).get("end")),
                    citations=[
                        _build_citation(
                            source_type=self.source_type,
                            source_id=source_id,
                            resource_type=_as_str(resource.get("resourceType")) or "CarePlan",
                            resource_id=resource_id,
                        )
                    ],
                )
            )
        return out

    def adapt(
        self,
        *,
        source_id: str,
        patient_id: str,
        raw_payload: dict[str, Any],
    ) -> PatientContext:
        patient = raw_payload.get("patient") if isinstance(raw_payload.get("patient"), dict) else {}
        demographics = _extract_demographics(
            source_type=self.source_type,
            source_id=source_id,
            patient_resource=patient,
            patient_id=patient_id,
        )
        resolved_patient_id = demographics.patientId or patient_id

        context = PatientContext(
            sourceType=self.source_type,
            sourceId=source_id,
            patientId=resolved_patient_id,
            fetchedAt=_now_iso(),
            demographics=demographics,
            medications=self._parse_medications(_bundle_entries(raw_payload.get("medications")), source_id=source_id),
            conditions=self._parse_conditions(_bundle_entries(raw_payload.get("conditions")), source_id=source_id),
            allergies=self._parse_allergies(_bundle_entries(raw_payload.get("allergies")), source_id=source_id),
            labs=self._parse_labs(_bundle_entries(raw_payload.get("observations")), source_id=source_id),
            appointments=self._parse_appointments(
                _bundle_entries(raw_payload.get("appointments")),
                source_id=source_id,
            ),
            documents=self._parse_documents(_bundle_entries(raw_payload.get("documents")), source_id=source_id),
            carePlan=self._parse_care_plans(
                _bundle_entries(raw_payload.get("carePlan"))
                or _bundle_entries(raw_payload.get("careplan")),
                source_id=source_id,
            ),
            meta={
                "adapter": self.adapter_name,
                "rawKeys": sorted(raw_payload.keys()),
            },
        )
        return context


class GenericStructuredAdapter(SourceAdapter):
    source_type = "generic"
    adapter_name = "generic-adapter"

    def _ctx_citation(
        self,
        *,
        source_id: str,
        resource_type: str,
        resource_id: str = "",
    ) -> Citation:
        return _build_citation(
            source_type=self.source_type,
            source_id=source_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    def _list_dicts(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def adapt(
        self,
        *,
        source_id: str,
        patient_id: str,
        raw_payload: dict[str, Any],
    ) -> PatientContext:
        patient = raw_payload.get("patient")
        if not isinstance(patient, dict):
            patient = raw_payload.get("demographics") if isinstance(raw_payload.get("demographics"), dict) else {}

        demo = PatientDemographics(
            patientId=_as_str(patient.get("patientId")) or _as_str(patient.get("id")) or patient_id,
            fullName=_as_str(patient.get("fullName")) or _as_str(patient.get("name")) or "Unknown Patient",
            givenName=_as_str(patient.get("givenName")),
            familyName=_as_str(patient.get("familyName")),
            birthDate=_as_str(patient.get("birthDate")),
            gender=_as_str(patient.get("gender")),
            mrn=_as_str(patient.get("mrn")),
            citations=[self._ctx_citation(source_id=source_id, resource_type="PatientInput")],
        )

        meds: list[MedicationItem] = []
        for item in self._list_dicts(raw_payload.get("medications")):
            meds.append(
                MedicationItem(
                    id=_as_str(item.get("id")),
                    name=_as_str(item.get("name")) or _as_str(item.get("medication")),
                    status=_as_str(item.get("status")),
                    dosage=_as_str(item.get("dosage")),
                    startDate=_as_str(item.get("startDate")),
                    endDate=_as_str(item.get("endDate")),
                    route=_as_str(item.get("route")),
                    citations=[self._ctx_citation(source_id=source_id, resource_type="MedicationInput", resource_id=_as_str(item.get("id")))],
                )
            )

        conditions: list[ConditionItem] = []
        for item in self._list_dicts(raw_payload.get("conditions")):
            conditions.append(
                ConditionItem(
                    id=_as_str(item.get("id")),
                    name=_as_str(item.get("name")) or _as_str(item.get("condition")),
                    clinicalStatus=_as_str(item.get("clinicalStatus")),
                    verificationStatus=_as_str(item.get("verificationStatus")),
                    onsetDate=_as_str(item.get("onsetDate")),
                    abatementDate=_as_str(item.get("abatementDate")),
                    severity=_as_str(item.get("severity")),
                    citations=[self._ctx_citation(source_id=source_id, resource_type="ConditionInput", resource_id=_as_str(item.get("id")))],
                )
            )

        labs: list[LabItem] = []
        lab_source = raw_payload.get("labs")
        if lab_source is None:
            lab_source = raw_payload.get("observations")
        for item in self._list_dicts(lab_source):
            labs.append(
                LabItem(
                    id=_as_str(item.get("id")),
                    name=_as_str(item.get("name")),
                    value=_as_str(item.get("value")),
                    unit=_as_str(item.get("unit")),
                    interpretation=_as_str(item.get("interpretation")),
                    status=_as_str(item.get("status")),
                    effectiveDate=_as_str(item.get("effectiveDate")),
                    citations=[self._ctx_citation(source_id=source_id, resource_type="LabInput", resource_id=_as_str(item.get("id")))],
                )
            )

        allergies: list[AllergyItem] = []
        for item in self._list_dicts(raw_payload.get("allergies")):
            allergies.append(
                AllergyItem(
                    id=_as_str(item.get("id")),
                    substance=_as_str(item.get("substance")),
                    criticality=_as_str(item.get("criticality")),
                    status=_as_str(item.get("status")),
                    reaction=_as_str(item.get("reaction")),
                    category=_as_str(item.get("category")),
                    citations=[self._ctx_citation(source_id=source_id, resource_type="AllergyInput", resource_id=_as_str(item.get("id")))],
                )
            )

        appointments: list[AppointmentItem] = []
        for item in self._list_dicts(raw_payload.get("appointments")):
            appointments.append(
                AppointmentItem(
                    id=_as_str(item.get("id")),
                    description=_as_str(item.get("description")),
                    status=_as_str(item.get("status")),
                    start=_as_str(item.get("start")),
                    end=_as_str(item.get("end")),
                    location=_as_str(item.get("location")),
                    citations=[self._ctx_citation(source_id=source_id, resource_type="AppointmentInput", resource_id=_as_str(item.get("id")))],
                )
            )

        documents: list[DocumentItem] = []
        for item in self._list_dicts(raw_payload.get("documents")):
            documents.append(
                DocumentItem(
                    id=_as_str(item.get("id")),
                    title=_as_str(item.get("title")),
                    docType=_as_str(item.get("docType")) or _as_str(item.get("type")),
                    date=_as_str(item.get("date")),
                    author=_as_str(item.get("author")),
                    url=_as_str(item.get("url")),
                    citations=[self._ctx_citation(source_id=source_id, resource_type="DocumentInput", resource_id=_as_str(item.get("id")))],
                )
            )

        care_plan: list[CarePlanItem] = []
        for item in self._list_dicts(raw_payload.get("carePlan")):
            care_plan.append(
                CarePlanItem(
                    id=_as_str(item.get("id")),
                    title=_as_str(item.get("title")),
                    status=_as_str(item.get("status")),
                    description=_as_str(item.get("description")),
                    start=_as_str(item.get("start")),
                    end=_as_str(item.get("end")),
                    citations=[self._ctx_citation(source_id=source_id, resource_type="CarePlanInput", resource_id=_as_str(item.get("id")))],
                )
            )

        return PatientContext(
            sourceType=self.source_type,
            sourceId=source_id,
            patientId=demo.patientId or patient_id,
            fetchedAt=_now_iso(),
            demographics=demo,
            medications=meds,
            conditions=conditions,
            allergies=allergies,
            labs=labs,
            appointments=appointments,
            documents=documents,
            carePlan=care_plan,
            meta={
                "adapter": self.adapter_name,
                "rawKeys": sorted(raw_payload.keys()),
            },
        )


class Hl7v2Adapter(GenericStructuredAdapter):
    source_type = "hl7_v2"
    adapter_name = "hl7v2-adapter"


class CdaAdapter(GenericStructuredAdapter):
    source_type = "cda"
    adapter_name = "cda-adapter"


class RestApiAdapter(GenericStructuredAdapter):
    source_type = "rest"
    adapter_name = "rest-adapter"


class CsvAdapter(GenericStructuredAdapter):
    source_type = "csv"
    adapter_name = "csv-adapter"


class ManualAdapter(GenericStructuredAdapter):
    source_type = "manual"
    adapter_name = "manual-adapter"


@dataclass
class AdapterResolution:
    source_type: str
    adapter_name: str
    adapter: SourceAdapter


class AdapterRegistry:
    def __init__(self, adapters: list[SourceAdapter]) -> None:
        self._adapters = {adapter.source_type: adapter for adapter in adapters}

    def resolve(self, source_type: str) -> AdapterResolution:
        normalized = (source_type or "").strip().lower()
        adapter = self._adapters.get(normalized)
        if not adapter:
            raise ValueError(
                f"Unsupported sourceType '{source_type}'. Supported: {', '.join(sorted(self._adapters.keys()))}"
            )
        return AdapterResolution(
            source_type=normalized,
            adapter_name=adapter.adapter_name,
            adapter=adapter,
        )

    def supported_source_types(self) -> list[str]:
        return sorted(self._adapters.keys())


def build_default_registry() -> AdapterRegistry:
    return AdapterRegistry(
        adapters=[
            FhirAdapter(),
            Hl7v2Adapter(),
            CdaAdapter(),
            RestApiAdapter(),
            CsvAdapter(),
            ManualAdapter(),
        ]
    )
