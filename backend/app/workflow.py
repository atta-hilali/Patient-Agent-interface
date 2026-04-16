from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .adapters import AdapterRegistry, build_default_registry
from .cache import WorkflowCache
from .config import Settings
from .models import ConflictItem, WorkflowSnapshot, WorkflowUnlockResponse
from .prompt_builder import build_prompt_package
from .session_cache import SessionCache
from .terminology import get_terminology_normalizer


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ConsentEntry:
    accepted_at: float


class ConsentStore:
    def __init__(self, ttl_sec: int) -> None:
        self.ttl_sec = ttl_sec
        self._store: dict[str, ConsentEntry] = {}

    def _cleanup(self) -> None:
        now = time.time()
        expired_keys = [key for key, value in self._store.items() if now - value.accepted_at > self.ttl_sec]
        for key in expired_keys:
            self._store.pop(key, None)

    def accept(self, cache_key: str) -> None:
        self._cleanup()
        self._store[cache_key] = ConsentEntry(accepted_at=time.time())

    def is_accepted(self, cache_key: str) -> bool:
        self._cleanup()
        return cache_key in self._store


class WorkflowService:
    def __init__(
        self,
        *,
        settings: Settings,
        cache: WorkflowCache,
        adapter_registry: AdapterRegistry | None = None,
        consent_store: ConsentStore | None = None,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.adapter_registry = adapter_registry or build_default_registry()
        self.consent_store = consent_store or ConsentStore(ttl_sec=settings.consent_session_ttl_sec)

    def _compute_allergy_conflicts(self, context: Any) -> list[ConflictItem]:
        conflicts: list[ConflictItem] = []
        substances = [item.substance.lower() for item in context.allergies if item.substance]
        if not substances:
            return conflicts

        for med in context.medications:
            med_name = (med.name or "").lower()
            if not med_name:
                continue
            for substance in substances:
                if substance and substance in med_name:
                    conflicts.append(
                        ConflictItem(
                            id=f"alg-{len(conflicts) + 1}",
                            kind="allergy_conflict",
                            severity="high",
                            message=f"Medication '{med.name}' may conflict with allergy '{substance}'.",
                            relatedIds=[med.id],
                            citations=med.citations[:1],
                        )
                    )
        return conflicts

    def _resolve_consent(self, *, cache_key: str, consent_accepted: bool) -> bool:
        if not self.settings.consent_required:
            return True
        if consent_accepted:
            self.consent_store.accept(cache_key)
            return True
        return self.consent_store.is_accepted(cache_key)

    async def ingest(
        self,
        *,
        source_type: str,
        source_id: str,
        patient_id: str,
        raw_payload: dict[str, Any],
        consent_accepted: bool = False,
        session_id: str | None = None,
        session_cache: SessionCache | None = None,
    ) -> dict[str, Any]:
        cache_key = self.cache.cache_key(source_id=source_id, patient_id=patient_id)
        consent_ok = self._resolve_consent(cache_key=cache_key, consent_accepted=consent_accepted)

        cached = await self.cache.get(source_id=source_id, patient_id=patient_id)
        if cached:
            snapshot = dict(cached)
            snapshot["cacheHit"] = True
            snapshot["updatedAt"] = _now_iso()
            snapshot["chatUnlock"] = bool(cached.get("context")) and consent_ok
            snapshot["consentBanner"] = self.settings.consent_required and not consent_ok
            if snapshot["chatUnlock"] != cached.get("chatUnlock") and consent_accepted:
                await self.cache.set(source_id=source_id, patient_id=patient_id, snapshot=snapshot)
            return snapshot

        resolution = self.adapter_registry.resolve(source_type)
        context = resolution.adapter.adapt(
            source_id=source_id,
            patient_id=patient_id,
            raw_payload=raw_payload,
        )
        context.sourceType = resolution.source_type
        context.sourceId = source_id
        context.patientId = context.patientId or patient_id
        context.fetchedAt = _now_iso()
        try:
            normalizer = get_terminology_normalizer()
            context = await normalizer.enrich_context(context)
            inferred_conflicts = await normalizer.infer_conflicts(context)
            context.allergyConflicts = inferred_conflicts or self._compute_allergy_conflicts(context)
        except Exception:  # noqa: BLE001
            context.allergyConflicts = self._compute_allergy_conflicts(context)
        context.meta["adapter"] = resolution.adapter_name

        prompt_package = build_prompt_package(context)
        chat_unlock = bool(context.patientId and context.demographics) and consent_ok
        if session_cache and session_id:
            await session_cache.set_context(session_id, context.patientId, context.model_dump(mode="json"))
            await session_cache.set_prompt(session_id, prompt_package.prompt)
        snapshot_model = WorkflowSnapshot(
            updatedAt=_now_iso(),
            sourceType=resolution.source_type,
            sourceId=source_id,
            patientId=context.patientId,
            adapter=resolution.adapter_name,
            cacheHit=False,
            cacheKey=cache_key,
            chatUnlock=chat_unlock,
            consentBanner=self.settings.consent_required and not consent_ok,
            context=context,
            prompt=prompt_package.prompt,
            promptCitations=prompt_package.citations,
            metrics={
                "medications": len(context.medications),
                "conditions": len(context.conditions),
                "allergies": len(context.allergies),
                "labs": len(context.labs),
                "appointments": len(context.appointments),
                "carePlan": len(context.carePlan),
                "documents": len(context.documents),
                "allergyConflicts": len(context.allergyConflicts),
            },
        )
        snapshot = snapshot_model.model_dump(mode="json")
        await self.cache.set(source_id=source_id, patient_id=patient_id, snapshot=snapshot)
        return snapshot

    async def check_unlock(
        self,
        *,
        source_id: str,
        patient_id: str,
        consent_accepted: bool,
    ) -> WorkflowUnlockResponse:
        cache_key = self.cache.cache_key(source_id=source_id, patient_id=patient_id)
        snapshot_exists = await self.cache.exists(source_id=source_id, patient_id=patient_id)
        consent_ok = self._resolve_consent(cache_key=cache_key, consent_accepted=consent_accepted)
        chat_unlock = snapshot_exists and consent_ok

        if not snapshot_exists:
            reason = "No normalized PatientContext found yet for this patient/source."
        elif not consent_ok:
            reason = "Consent required before chat unlock."
        else:
            reason = "Chat is unlocked."

        return WorkflowUnlockResponse(
            chatUnlock=chat_unlock,
            reason=reason,
            consentRequired=self.settings.consent_required,
            consentAccepted=consent_ok,
            snapshotExists=snapshot_exists,
            cacheKey=cache_key,
        )


async def run_workflow_pipeline(
    *,
    service: WorkflowService,
    source_type: str,
    source_id: str,
    patient_id: str,
    raw_payload: dict[str, Any],
    consent_accepted: bool = False,
    session_id: str | None = None,
    session_cache: SessionCache | None = None,
) -> dict[str, Any]:
    return await service.ingest(
        source_type=source_type,
        source_id=source_id,
        patient_id=patient_id,
        raw_payload=raw_payload,
        consent_accepted=consent_accepted,
        session_id=session_id,
        session_cache=session_cache,
    )


async def prefill_kv_cache(system_prompt: str):
    """Fire silent POST to vLLM to warm the KV-cache for this session."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post('http://localhost:8001/v1/chat/completions', json={
                'model': 'google/medgemma-4b-it',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user',   'content': ''},  # empty user turn = prefill only
                ],
                'max_tokens': 1,
                'temperature': 0.1,
            })
    except Exception:
        pass  # prefill failure is non-fatal — next turn just won't have cache benefit
