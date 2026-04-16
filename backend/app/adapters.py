from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx

from .cda_parser import parse_cda_xml
from .connectors import ConnectorConfig
from .csv_mapper import apply_csv_mapping
from .hl7_parser import parse_hl7_message
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


def _resource_type(resource: dict[str, Any]) -> str:
    return _as_str(resource.get("resourceType")).strip()


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


def _is_human_friendly_med_name(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    # Internal EHR IDs/codes are often long opaque tokens without spaces.
    if len(text) > 22 and " " not in text and "." in text:
        return False
    if len(text) > 28 and " " not in text and "-" in text and text.count("-") >= 3:
        return False
    if len(text) > 24 and " " not in text and text.count(".") >= 2:
        return False
    if text.lower().startswith("medication/"):
        return False
    return True


def _extract_reference_id(reference: str) -> str:
    text = (reference or "").strip()
    if not text:
        return ""
    if "/" in text:
        return text.rsplit("/", 1)[-1]
    return text


def _extract_medication_name(resource: dict[str, Any], medication_lookup: dict[str, dict[str, Any]] | None = None) -> str:
    concept = resource.get("medicationCodeableConcept")
    if isinstance(concept, dict):
        text = _as_str(concept.get("text")).strip()
        if _is_human_friendly_med_name(text):
            return text
        coding = concept.get("coding")
        if isinstance(coding, list):
            for item in coding:
                if not isinstance(item, dict):
                    continue
                display = _as_str(item.get("display")).strip()
                if _is_human_friendly_med_name(display):
                    return display

    med_ref = resource.get("medicationReference")
    if isinstance(med_ref, dict):
        display = _as_str(med_ref.get("display")).strip()
        if _is_human_friendly_med_name(display):
            return display
        ref_id = _extract_reference_id(_as_str(med_ref.get("reference")))
        if ref_id and medication_lookup and ref_id in medication_lookup:
            med_resource = medication_lookup[ref_id]
            med_name = _first_coding_text(med_resource.get("code")) or _as_str(med_resource.get("name"))
            if _is_human_friendly_med_name(med_name):
                return med_name

    # Use text/code only as a final fallback when it looks human-readable.
    fallback = _first_coding_text(concept)
    if _is_human_friendly_med_name(fallback):
        return fallback
    if _resource_type(resource) == "Medication":
        direct = _first_coding_text(resource.get("code")) or _as_str(resource.get("name"))
        if _is_human_friendly_med_name(direct):
            return direct
    return ""


def _extract_rxnorm_code(value: Any) -> str:
    concept = value if isinstance(value, dict) else {}
    if not isinstance(concept, dict):
        return ""
    coding = concept.get("coding")
    if not isinstance(coding, list):
        return ""

    for item in coding:
        if not isinstance(item, dict):
            continue
        system = _as_str(item.get("system")).lower()
        code = _as_str(item.get("code")).strip()
        if not code:
            continue
        # RxNorm coding system usually contains "rxnorm".
        if "rxnorm" in system:
            return code
        # Fallback for common OID style representations.
        if "2.16.840.1.113883.6.88" in system:
            return code
    return ""


def _extract_code_by_system(value: Any, *, needles: tuple[str, ...]) -> str:
    concept = value if isinstance(value, dict) else {}
    if not isinstance(concept, dict):
        return ""
    coding = concept.get("coding")
    if not isinstance(coding, list):
        return ""
    for item in coding:
        if not isinstance(item, dict):
            continue
        system = _as_str(item.get("system")).lower()
        code = _as_str(item.get("code")).strip()
        if not code:
            continue
        if any(needle in system for needle in needles):
            return code
    return ""


def _extract_snomed_code(value: Any) -> str:
    return _extract_code_by_system(
        value,
        needles=("snomed", "2.16.840.1.113883.6.96"),
    )

def _extract_medication_rxcui(resource: dict[str, Any], medication_lookup: dict[str, dict[str, Any]] | None = None) -> str:
    concept = resource.get("medicationCodeableConcept")
    direct = _extract_rxnorm_code(concept)
    if direct:
        return direct
    if _resource_type(resource) == "Medication":
        direct_med = _extract_rxnorm_code(resource.get("code"))
        if direct_med:
            return direct_med
    med_ref = resource.get("medicationReference")
    if isinstance(med_ref, dict):
        ref_id = _extract_reference_id(_as_str(med_ref.get("reference")))
        if ref_id and medication_lookup and ref_id in medication_lookup:
            linked_med = medication_lookup[ref_id]
            linked_code = _extract_rxnorm_code(linked_med.get("code"))
            if linked_code:
                return linked_code
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

    async def write_session_summary(
        self,
        *,
        connector: ConnectorConfig,
        patient_id: str,
        summary: str,
        session_id: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "write_method": connector.write_back,
            "adapter": self.adapter_name,
            "resource_type": "session_summary",
            "message": "write_session_summary is not implemented for this adapter.",
        }

    async def write_observation(
        self,
        *,
        connector: ConnectorConfig,
        patient_id: str,
        loinc_code: str,
        value: str,
        unit: str,
        session_id: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "write_method": connector.write_back,
            "adapter": self.adapter_name,
            "resource_type": "observation",
            "message": "write_observation is not implemented for this adapter.",
        }

    async def write_flag(
        self,
        *,
        connector: ConnectorConfig,
        patient_id: str,
        reason: str,
        severity: str,
        session_id: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "write_method": connector.write_back,
            "adapter": self.adapter_name,
            "resource_type": "flag",
            "message": "write_flag is not implemented for this adapter.",
        }


class FhirAdapter(SourceAdapter):
    source_type = "fhir_r4"
    adapter_name = "fhir-adapter"

    def _parse_medications(
        self,
        resources: Iterable[dict[str, Any]],
        *,
        source_id: str,
    ) -> list[MedicationItem]:
        resources_list = list(resources)
        medication_lookup: dict[str, dict[str, Any]] = {}
        for resource in resources_list:
            if _resource_type(resource) != "Medication":
                continue
            resource_id = _as_str(resource.get("id")).strip()
            if resource_id:
                medication_lookup[resource_id] = resource

        medication_requests = [
            resource
            for resource in resources_list
            if _resource_type(resource) in {"MedicationRequest", "MedicationStatement", "MedicationDispense"}
        ]
        if not medication_requests:
            medication_requests = [resource for resource in resources_list if _resource_type(resource) == "Medication"]

        out: list[MedicationItem] = []
        for resource in medication_requests:
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
                    name=_extract_medication_name(resource, medication_lookup),
                    status=_as_str(resource.get("status")),
                    dosage=dosage,
                    rxcui=_extract_medication_rxcui(resource, medication_lookup),
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
                    snomedCode=_extract_snomed_code(resource.get("code")),
                    icd10Code=_extract_code_by_system(resource.get("code"), needles=("icd-10", "icd10", "2.16.840.1.113883.6.90")),
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
                    rxcui=_extract_rxnorm_code(resource.get("code")),
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

    async def write_session_summary(
        self,
        *,
        connector: ConnectorConfig,
        patient_id: str,
        summary: str,
        session_id: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        base_url = (connector.base_url or "").rstrip("/")
        if not base_url:
            return {
                "ok": False,
                "write_method": "fhir",
                "adapter": self.adapter_name,
                "resource_type": "Communication",
                "message": "FHIR base_url is missing for connector.",
            }

        payload = {
            "resourceType": "Communication",
            "status": "completed",
            "subject": {"reference": f"Patient/{patient_id}"},
            "topic": {"text": "Veldooc Patient Agent Session"},
            "payload": [{"contentString": summary}],
            "sent": _now_iso(),
            "meta": {"tag": [{"code": f"session:{session_id}"}]},
        }
        headers = {"Content-Type": "application/fhir+json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(f"{base_url}/Communication", json=payload, headers=headers)
        return {
            "ok": bool(200 <= response.status_code < 300),
            "status_code": response.status_code,
            "write_method": "fhir",
            "adapter": self.adapter_name,
            "resource_type": "Communication",
        }

    async def write_observation(
        self,
        *,
        connector: ConnectorConfig,
        patient_id: str,
        loinc_code: str,
        value: str,
        unit: str,
        session_id: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        base_url = (connector.base_url or "").rstrip("/")
        if not base_url:
            return {
                "ok": False,
                "write_method": "fhir",
                "adapter": self.adapter_name,
                "resource_type": "Observation",
                "message": "FHIR base_url is missing for connector.",
            }

        payload = {
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": loinc_code}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            "valueString": str(value or ""),
            "effectiveDateTime": _now_iso(),
            "note": [{"text": f"session:{session_id}"}],
        }
        if unit:
            payload["valueQuantity"] = {"value": value, "unit": unit}

        headers = {"Content-Type": "application/fhir+json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(f"{base_url}/Observation", json=payload, headers=headers)
        return {
            "ok": bool(200 <= response.status_code < 300),
            "status_code": response.status_code,
            "write_method": "fhir",
            "adapter": self.adapter_name,
            "resource_type": "Observation",
        }

    async def write_flag(
        self,
        *,
        connector: ConnectorConfig,
        patient_id: str,
        reason: str,
        severity: str,
        session_id: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        base_url = (connector.base_url or "").rstrip("/")
        if not base_url:
            return {
                "ok": False,
                "write_method": "fhir",
                "adapter": self.adapter_name,
                "resource_type": "Flag",
                "message": "FHIR base_url is missing for connector.",
            }

        payload = {
            "resourceType": "Flag",
            "status": "active",
            "category": [{"text": "Safety"}],
            "code": {"text": reason},
            "subject": {"reference": f"Patient/{patient_id}"},
            "period": {"start": _now_iso()},
            "extension": [
                {"url": "http://veldooc.ai/session-id", "valueString": session_id},
                {"url": "http://veldooc.ai/severity", "valueString": severity},
            ],
        }
        headers = {"Content-Type": "application/fhir+json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(f"{base_url}/Flag", json=payload, headers=headers)
        return {
            "ok": bool(200 <= response.status_code < 300),
            "status_code": response.status_code,
            "write_method": "fhir",
            "adapter": self.adapter_name,
            "resource_type": "Flag",
        }


class GenericStructuredAdapter(SourceAdapter):
    source_type = "generic"
    adapter_name = "generic-adapter"

    async def _write_via_webhook(
        self,
        *,
        connector: ConnectorConfig,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        target = (connector.base_url or "").strip()
        if not target:
            return {
                "ok": False,
                "write_method": connector.write_back,
                "adapter": self.adapter_name,
                "resource_type": event_type,
                "message": "Connector base_url is missing.",
            }
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(target, json={"event": event_type, "payload": payload})
        return {
            "ok": bool(200 <= response.status_code < 300),
            "status_code": response.status_code,
            "write_method": connector.write_back,
            "adapter": self.adapter_name,
            "resource_type": event_type,
        }

    async def write_session_summary(
        self,
        *,
        connector: ConnectorConfig,
        patient_id: str,
        summary: str,
        session_id: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "patient_id": patient_id,
            "summary": summary,
            "session_id": session_id,
            "source_type": self.source_type,
        }
        if connector.write_back == "hl7":
            return {
                "ok": True,
                "write_method": "hl7",
                "adapter": self.adapter_name,
                "resource_type": "ORU^R01",
                "payload_preview": f"MSH|^~\\&|VELDOOC|...|ORU^R01|{session_id}|",
            }
        if connector.write_back == "webhook":
            return await self._write_via_webhook(connector=connector, event_type="session_summary", payload=payload)
        if connector.write_back == "none":
            return {
                "ok": True,
                "write_method": "none",
                "adapter": self.adapter_name,
                "resource_type": "session_summary",
                "message": "Write-back disabled for this connector; operation skipped.",
            }
        return {
            "ok": False,
            "write_method": connector.write_back,
            "adapter": self.adapter_name,
            "resource_type": "session_summary",
            "message": f"Unsupported write_back mode '{connector.write_back}'.",
        }

    async def write_observation(
        self,
        *,
        connector: ConnectorConfig,
        patient_id: str,
        loinc_code: str,
        value: str,
        unit: str,
        session_id: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "patient_id": patient_id,
            "loinc_code": loinc_code,
            "value": value,
            "unit": unit,
            "session_id": session_id,
            "source_type": self.source_type,
        }
        if connector.write_back == "hl7":
            return {
                "ok": True,
                "write_method": "hl7",
                "adapter": self.adapter_name,
                "resource_type": "OBX",
                "payload_preview": f"OBX|1|NM|{loinc_code}|...|{value}|{unit}|",
            }
        if connector.write_back == "webhook":
            return await self._write_via_webhook(connector=connector, event_type="observation", payload=payload)
        if connector.write_back == "none":
            return {
                "ok": True,
                "write_method": "none",
                "adapter": self.adapter_name,
                "resource_type": "observation",
                "message": "Write-back disabled for this connector; operation skipped.",
            }
        return {
            "ok": False,
            "write_method": connector.write_back,
            "adapter": self.adapter_name,
            "resource_type": "observation",
            "message": f"Unsupported write_back mode '{connector.write_back}'.",
        }

    async def write_flag(
        self,
        *,
        connector: ConnectorConfig,
        patient_id: str,
        reason: str,
        severity: str,
        session_id: str,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "patient_id": patient_id,
            "reason": reason,
            "severity": severity,
            "session_id": session_id,
            "source_type": self.source_type,
        }
        if connector.write_back == "hl7":
            return {
                "ok": True,
                "write_method": "hl7",
                "adapter": self.adapter_name,
                "resource_type": "ADT^A08",
                "payload_preview": f"EVN|A08|...|{severity}|{reason}",
            }
        if connector.write_back == "webhook":
            return await self._write_via_webhook(connector=connector, event_type="flag", payload=payload)
        if connector.write_back == "none":
            return {
                "ok": True,
                "write_method": "none",
                "adapter": self.adapter_name,
                "resource_type": "flag",
                "message": "Write-back disabled for this connector; operation skipped.",
            }
        return {
            "ok": False,
            "write_method": connector.write_back,
            "adapter": self.adapter_name,
            "resource_type": "flag",
            "message": f"Unsupported write_back mode '{connector.write_back}'.",
        }

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
                    rxcui=_as_str(item.get("rxcui")),
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
                    snomedCode=_as_str(item.get("snomedCode")) or _as_str(item.get("snomed")),
                    icd10Code=_as_str(item.get("icd10Code")) or _as_str(item.get("icd10")),
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
                    rxcui=_as_str(item.get("rxcui")),
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

    def adapt(
        self,
        *,
        source_id: str,
        patient_id: str,
        raw_payload: dict[str, Any],
    ) -> PatientContext:
        payload = raw_payload
        message = raw_payload.get("hl7Message")
        if isinstance(message, str) and message.strip():
            payload = parse_hl7_message(message)
        return super().adapt(source_id=source_id, patient_id=patient_id, raw_payload=payload)


class CdaAdapter(GenericStructuredAdapter):
    source_type = "cda"
    adapter_name = "cda-adapter"

    def adapt(
        self,
        *,
        source_id: str,
        patient_id: str,
        raw_payload: dict[str, Any],
    ) -> PatientContext:
        payload = raw_payload
        cda_xml = raw_payload.get("cdaXml") or raw_payload.get("xml")
        xpath_map = raw_payload.get("xpathMap")
        if isinstance(cda_xml, str) and cda_xml.strip():
            parsed = parse_cda_xml(cda_xml, xpath_map=xpath_map if isinstance(xpath_map, dict) else None)
            payload = parsed
        return super().adapt(source_id=source_id, patient_id=patient_id, raw_payload=payload)


class RestApiAdapter(GenericStructuredAdapter):
    source_type = "rest"
    adapter_name = "rest-adapter"


class CsvAdapter(GenericStructuredAdapter):
    source_type = "csv"
    adapter_name = "csv-adapter"

    def adapt(
        self,
        *,
        source_id: str,
        patient_id: str,
        raw_payload: dict[str, Any],
    ) -> PatientContext:
        payload = raw_payload
        csv_text = raw_payload.get("csvText")
        mapping = raw_payload.get("mapping")
        if isinstance(csv_text, str) and csv_text.strip():
            payload = apply_csv_mapping(
                csv_text=csv_text,
                mapping=mapping if isinstance(mapping, dict) else None,
                patient_id_hint=patient_id,
            )
        return super().adapt(source_id=source_id, patient_id=patient_id, raw_payload=payload)


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
        # Backward-compatible aliases so older frontend payloads keep working.
        self._aliases = {
            "fhir": "fhir_r4",
            "hl7": "hl7_v2",
        }

    def resolve(self, source_type: str) -> AdapterResolution:
        normalized = (source_type or "").strip().lower()
        canonical = self._aliases.get(normalized, normalized)
        adapter = self._adapters.get(canonical)
        if not adapter:
            raise ValueError(
                f"Unsupported sourceType '{source_type}'. Supported: {', '.join(sorted(self._adapters.keys()))}"
            )
        return AdapterResolution(
            source_type=canonical,
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
