from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings, get_settings
from .models import AllergyItem, ConditionItem, ConflictItem, MedicationItem, PatientContext

try:
    from redis.asyncio import Redis
except Exception:  # noqa: BLE001
    Redis = None  # type: ignore[assignment]


def _clean_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def _norm_token(value: str) -> str:
    return _clean_text(value).lower()


def _looks_opaque_name(value: str) -> bool:
    text = _clean_text(value)
    if not text:
        return True
    if len(text) > 22 and " " not in text and "." in text:
        return True
    if len(text) > 28 and " " not in text and "-" in text and text.count("-") >= 3:
        return True
    if len(text) > 24 and " " not in text and text.count(".") >= 2:
        return True
    return False


def _first_json_path(payload: dict[str, Any], *path: str) -> str:
    cursor: Any = payload
    for key in path:
        if not isinstance(cursor, dict):
            return ""
        cursor = cursor.get(key)
    return str(cursor or "").strip()


def _word_set(value: str) -> set[str]:
    text = _norm_token(value)
    if not text:
        return set()
    tokens = set()
    for token in text.replace("/", " ").replace("-", " ").split():
        token = token.strip()
        if len(token) < 3:
            continue
        tokens.add(token)
    return tokens


@dataclass(frozen=True)
class _CacheEntry:
    expires_at: float
    value: str


class TerminologyNormalizer:
    """
    Terminology normalization bridge.

    - RxNorm: name <-> RxCUI
    - ICD-10 lookup for condition canonicalization
    - medication/allergy conflict inference with deterministic fallback
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = settings.terminology_enabled
        self.use_network = settings.terminology_use_network
        self.timeout = float(max(settings.terminology_timeout_sec, 1))
        self.max_parallel = max(settings.terminology_max_parallel, 1)
        self.rxnorm_base_url = settings.terminology_rxnorm_base_url.rstrip("/")
        self.snomed_lookup_url = settings.terminology_snomed_lookup_url
        self.icd10_lookup_url = settings.terminology_icd10_lookup_url
        self.umls_api_key = settings.terminology_umls_api_key
        self._cache: dict[str, _CacheEntry] = {}
        self._redis: Redis | None = None
        if settings.redis_url and Redis is not None:
            try:
                self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
            except Exception:  # noqa: BLE001
                self._redis = None

    async def _cache_get(self, key: str) -> str:
        now = time.time()
        memory_hit = self._cache.get(key)
        if memory_hit and memory_hit.expires_at > now:
            return memory_hit.value
        if self._redis:
            try:
                value = await self._redis.get(f"terminology:{key}")
                if value:
                    self._cache[key] = _CacheEntry(expires_at=now + self.settings.terminology_cache_ttl_sec, value=value)
                    return value
            except Exception:  # noqa: BLE001
                self._redis = None
        if memory_hit and memory_hit.expires_at <= now:
            self._cache.pop(key, None)
        return ""

    async def _cache_set(self, key: str, value: str) -> None:
        if not value:
            return
        ttl = self.settings.terminology_cache_ttl_sec
        self._cache[key] = _CacheEntry(expires_at=time.time() + ttl, value=value)
        if self._redis:
            try:
                await self._redis.set(f"terminology:{key}", value, ex=ttl)
            except Exception:  # noqa: BLE001
                self._redis = None

    async def _http_get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.use_network:
            return {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def resolve_rxcui_from_name(self, medication_name: str) -> str:
        name = _clean_text(medication_name)
        if not name:
            return ""
        cache_key = f"rxnorm:name:{_norm_token(name)}"
        cached = await self._cache_get(cache_key)
        if cached:
            return cached
        try:
            payload = await self._http_get_json(f"{self.rxnorm_base_url}/REST/rxcui.json", params={"name": name})
        except Exception:  # noqa: BLE001
            return ""
        ids = (((payload.get("idGroup") or {}).get("rxnormId")) or [])
        rxcui = str(ids[0]).strip() if isinstance(ids, list) and ids else ""
        if rxcui:
            await self._cache_set(cache_key, rxcui)
        return rxcui

    async def resolve_name_from_rxcui(self, rxcui: str) -> str:
        code = _clean_text(rxcui)
        if not code:
            return ""
        cache_key = f"rxnorm:rxcui:{code}"
        cached = await self._cache_get(cache_key)
        if cached:
            return cached
        try:
            payload = await self._http_get_json(f"{self.rxnorm_base_url}/REST/rxcui/{code}/properties.json")
        except Exception:  # noqa: BLE001
            return ""
        name = _first_json_path(payload, "properties", "name")
        if name:
            await self._cache_set(cache_key, name)
        return name

    async def resolve_icd10_from_condition(self, condition_name: str) -> str:
        term = _clean_text(condition_name)
        if not term:
            return ""
        cache_key = f"icd10:term:{_norm_token(term)}"
        cached = await self._cache_get(cache_key)
        if cached:
            return cached
        try:
            payload = await self._http_get_json(
                self.icd10_lookup_url,
                params={"sf": "code,name", "terms": term},
            )
        except Exception:  # noqa: BLE001
            return ""
        # NLM Clinical Tables returns list-like JSON, but some gateways wrap payload.
        code = ""
        if isinstance(payload, dict):
            # fallback when gateway wraps
            code = _first_json_path(payload, "code")
        if not code:
            # Parse list form using a second request with text mode fallback.
            try:
                if self.use_network:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                        response = await client.get(
                            self.icd10_lookup_url,
                            params={"sf": "code,name", "terms": term},
                        )
                        response.raise_for_status()
                        parsed = response.json()
                    if isinstance(parsed, list) and len(parsed) >= 4 and isinstance(parsed[3], list) and parsed[3]:
                        first_row = parsed[3][0]
                        if isinstance(first_row, list) and first_row:
                            code = str(first_row[0] or "").strip()
            except Exception:  # noqa: BLE001
                code = ""
        if code:
            await self._cache_set(cache_key, code)
        return code

    async def resolve_snomed_from_condition(self, condition_name: str) -> str:
        term = _clean_text(condition_name)
        if not term:
            return ""
        cache_key = f"snomed:term:{_norm_token(term)}"
        cached = await self._cache_get(cache_key)
        if cached:
            return cached
        code = ""
        try:
            if self.use_network:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                    response = await client.get(
                        self.snomed_lookup_url,
                        params={"sf": "consumer_name,code", "terms": term},
                    )
                    response.raise_for_status()
                    parsed = response.json()
                if isinstance(parsed, list) and len(parsed) >= 4 and isinstance(parsed[3], list) and parsed[3]:
                    first_row = parsed[3][0]
                    if isinstance(first_row, list) and len(first_row) >= 2:
                        code = str(first_row[1] or "").strip()
                    elif isinstance(first_row, list) and first_row:
                        code = str(first_row[0] or "").strip()
        except Exception:  # noqa: BLE001
            code = ""
        if code:
            await self._cache_set(cache_key, code)
        return code

    async def map_snomed_to_icd10(self, snomed_code: str) -> str:
        code = _clean_text(snomed_code)
        if not code or not self.umls_api_key:
            return ""
        cache_key = f"umls:snomed:{code}"
        cached = await self._cache_get(cache_key)
        if cached:
            return cached
        try:
            payload = await self._http_get_json(
                f"https://uts-ws.nlm.nih.gov/rest/crosswalk/current/source/SNOMEDCT_US/{code}",
                params={"targetSource": "ICD10CM", "apiKey": self.umls_api_key},
            )
        except Exception:  # noqa: BLE001
            return ""
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, list) or not result:
            return ""
        first = result[0] if isinstance(result[0], dict) else {}
        icd = str(first.get("ui") or "").strip()
        if icd:
            await self._cache_set(cache_key, icd)
        return icd

    async def enrich_medication(self, item: MedicationItem) -> MedicationItem:
        if not self.enabled:
            return item
        name = _clean_text(item.name or item.generic)
        rxcui = _clean_text(item.rxcui)

        if not rxcui and name:
            rxcui = await self.resolve_rxcui_from_name(name)
            if rxcui:
                item.rxcui = rxcui

        if (not name or _looks_opaque_name(name)) and rxcui:
            resolved_name = await self.resolve_name_from_rxcui(rxcui)
            if resolved_name:
                item.name = resolved_name
                if not item.generic:
                    item.generic = resolved_name

        return item

    async def enrich_allergy(self, item: AllergyItem) -> AllergyItem:
        if not self.enabled:
            return item
        substance = _clean_text(item.substance)
        # Keep category/status untouched; only fill missing substance names.
        if (not substance or _looks_opaque_name(substance)) and item.id:
            # Keep deterministic fallback label; avoids blank allergy rows.
            item.substance = substance or f"Allergy/{item.id}"
        if not _clean_text(item.rxcui) and _clean_text(item.substance):
            item.rxcui = await self.resolve_rxcui_from_name(item.substance)
        return item

    async def enrich_condition(self, item: ConditionItem) -> ConditionItem:
        if not self.enabled:
            return item
        name = _clean_text(item.name)
        if not name:
            return item

        if not _clean_text(item.snomedCode):
            item.snomedCode = await self.resolve_snomed_from_condition(name)

        if not _clean_text(item.icd10Code):
            if _clean_text(item.snomedCode):
                item.icd10Code = await self.map_snomed_to_icd10(item.snomedCode)
            if not _clean_text(item.icd10Code):
                item.icd10Code = await self.resolve_icd10_from_condition(name)

        if not _clean_text(item.verificationStatus) and _clean_text(item.icd10Code):
            item.verificationStatus = f"ICD10:{item.icd10Code}"
        return item

    async def enrich_context(self, ctx: PatientContext) -> PatientContext:
        if not self.enabled:
            return ctx

        semaphore = asyncio.Semaphore(self.max_parallel)

        async def _guard(coro):
            async with semaphore:
                return await coro

        ctx.medications = list(await asyncio.gather(*[_guard(self.enrich_medication(item)) for item in ctx.medications]))
        ctx.allergies = list(await asyncio.gather(*[_guard(self.enrich_allergy(item)) for item in ctx.allergies]))
        ctx.conditions = list(await asyncio.gather(*[_guard(self.enrich_condition(item)) for item in ctx.conditions]))
        return ctx

    async def _interaction_signal(self, med_rxcui: str, allergy_rxcui: str) -> tuple[bool, str]:
        if not med_rxcui or not allergy_rxcui:
            return False, ""
        cache_key = f"rxnorm:pair:{med_rxcui}:{allergy_rxcui}"
        cached = await self._cache_get(cache_key)
        if cached:
            try:
                parsed = json.loads(cached)
                return bool(parsed.get("flag")), str(parsed.get("desc") or "")
            except Exception:  # noqa: BLE001
                return False, ""
        try:
            payload = await self._http_get_json(
                f"{self.rxnorm_base_url}/REST/interaction/list.json",
                params={"rxcuis": f"{med_rxcui}+{allergy_rxcui}"},
            )
        except Exception:  # noqa: BLE001
            return False, ""
        description = ""
        flagged = False
        groups = payload.get("fullInteractionTypeGroup")
        if isinstance(groups, list):
            for group in groups:
                for interaction_type in (group or {}).get("fullInteractionType", []):
                    for pair in (interaction_type or {}).get("interactionPair", []):
                        desc = str((pair or {}).get("description") or "").strip()
                        if desc:
                            description = desc
                            flagged = True
                            break
                    if flagged:
                        break
                if flagged:
                    break
        await self._cache_set(cache_key, json.dumps({"flag": flagged, "desc": description}, ensure_ascii=True))
        return flagged, description

    async def infer_conflicts(self, ctx: PatientContext) -> list[ConflictItem]:
        if not ctx.medications or not ctx.allergies:
            return []

        conflicts: list[ConflictItem] = []
        seen: set[str] = set()
        allergy_rxcuis = set()
        for item in ctx.allergies:
            if _clean_text(item.rxcui):
                allergy_rxcuis.add(_clean_text(item.rxcui))
                continue
            if item.category.startswith("RxCUI:"):
                allergy_rxcuis.add(_clean_text(item.category.replace("RxCUI:", "")))

        for med in ctx.medications:
            med_id = med.id or med.name
            med_name = _clean_text(med.name or med.generic)
            med_tokens = _word_set(med_name)
            med_rxcui = _clean_text(med.rxcui)

            for allergy in ctx.allergies:
                allergy_id = allergy.id or allergy.substance
                allergy_name = _clean_text(allergy.substance)
                allergy_tokens = _word_set(allergy_name)
                key = f"{med_id}:{allergy_id}"
                if key in seen:
                    continue

                severity = ""
                message = ""
                if med_rxcui and allergy_rxcuis and med_rxcui in allergy_rxcuis:
                    severity = "high"
                    message = f"Medication '{med_name or med_id}' shares RxCUI with documented allergy '{allergy_name or allergy_id}'."
                elif med_tokens and allergy_tokens and (med_tokens & allergy_tokens):
                    severity = "high"
                    matched = ", ".join(sorted(med_tokens & allergy_tokens))
                    message = (
                        f"Medication '{med_name or med_id}' contains terms matching allergy '{allergy_name or allergy_id}' "
                        f"({matched})."
                    )
                elif med_rxcui:
                    allergy_rxcui = ""
                    if _clean_text(allergy.rxcui):
                        allergy_rxcui = _clean_text(allergy.rxcui)
                    elif allergy.category.startswith("RxCUI:"):
                        allergy_rxcui = _clean_text(allergy.category.replace("RxCUI:", ""))
                    if allergy_rxcui:
                        flagged, description = await self._interaction_signal(med_rxcui, allergy_rxcui)
                        if flagged:
                            severity = "medium"
                            message = description or (
                                f"Potential interaction signal between medication '{med_name or med_id}' and allergy profile."
                            )

                if not severity:
                    continue

                seen.add(key)
                conflicts.append(
                    ConflictItem(
                        id=f"alg-{len(conflicts) + 1}",
                        kind="allergy_conflict",
                        severity=severity,
                        message=message,
                        relatedIds=[med.id, allergy.id],
                        citations=[*(med.citations[:1] or []), *(allergy.citations[:1] or [])],
                    )
                )

        return conflicts


_normalizer: TerminologyNormalizer | None = None


def get_terminology_normalizer() -> TerminologyNormalizer:
    global _normalizer
    if _normalizer is None:
        _normalizer = TerminologyNormalizer(get_settings())
    return _normalizer
