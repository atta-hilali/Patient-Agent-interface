from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.models import AllergyItem, MedicationItem, PatientContext
from app.terminology import TerminologyNormalizer


@dataclass
class _FakeSettings:
    terminology_enabled: bool = True
    terminology_use_network: bool = False
    terminology_timeout_sec: int = 1
    terminology_max_parallel: int = 2
    terminology_rxnorm_base_url: str = "https://rxnav.nlm.nih.gov"
    terminology_snomed_lookup_url: str = "https://clinicaltables.nlm.nih.gov/api/conditions/v3/search"
    terminology_icd10_lookup_url: str = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    terminology_umls_api_key: str = ""
    terminology_cache_ttl_sec: int = 60
    redis_url: str = ""


def test_infer_conflicts_detects_shared_rxcui():
    normalizer = TerminologyNormalizer(_FakeSettings())
    ctx = PatientContext(
        sourceType="fhir_r4",
        sourceId="demo",
        patientId="p-1",
        medications=[MedicationItem(id="m1", name="Aspirin", rxcui="1234")],
        allergies=[AllergyItem(id="a1", substance="Aspirin allergy", rxcui="1234")],
    )

    conflicts = __import__("asyncio").run(normalizer.infer_conflicts(ctx))
    assert len(conflicts) == 1
    assert conflicts[0].severity == "high"


def test_enrich_allergy_fills_fallback_label_when_missing():
    normalizer = TerminologyNormalizer(_FakeSettings())
    item = AllergyItem(id="alg-1", substance="")
    enriched = __import__("asyncio").run(normalizer.enrich_allergy(item))
    assert enriched.substance == "Allergy/alg-1"


def test_enrich_condition_fills_snomed_and_icd_codes():
    normalizer = TerminologyNormalizer(_FakeSettings())

    async def _fake_snomed(_name: str) -> str:
        return "22298006"

    async def _fake_icd(_name: str) -> str:
        return "R07.9"

    normalizer.resolve_snomed_from_condition = _fake_snomed  # type: ignore[method-assign]
    normalizer.resolve_icd10_from_condition = _fake_icd  # type: ignore[method-assign]

    from app.models import ConditionItem

    item = ConditionItem(id="c1", name="Chest pain")
    enriched = asyncio.run(normalizer.enrich_condition(item))

    assert enriched.snomedCode == "22298006"
    assert enriched.icd10Code == "R07.9"
