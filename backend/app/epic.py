import base64
import asyncio
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.parse import quote

import httpx

from .config import Settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def random_string(length: int = 64) -> str:
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    token = secrets.token_urlsafe(length * 2)
    return "".join(chars[ord(ch) % len(chars)] for ch in token[:length])


def sha256_base64url(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def build_authorize_url(settings: Settings, state: str, code_challenge: str) -> str:
    query = {
        "response_type": "code",
        "redirect_uri": settings.epic_redirect_uri,
        "client_id": settings.epic_client_id,
        "state": state,
        "aud": settings.epic_aud,
        "scope": settings.epic_scope,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{settings.epic_authorize_url}?{urlencode(query)}"


async def exchange_code_for_token(
    *,
    settings: Settings,
    code: str,
    code_verifier: str,
) -> dict[str, Any]:
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.epic_redirect_uri,
        "client_id": settings.epic_client_id,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            settings.epic_token_url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    response.raise_for_status()
    return response.json()


async def fetch_fhir_json(*, settings: Settings, access_token: str, path_with_query: str) -> dict[str, Any]:
    url = f"{settings.epic_aud}/{path_with_query}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/fhir+json",
            },
        )
    response.raise_for_status()
    return response.json()


def _scope_hint(required_scopes: list[str], granted_scope: str) -> str:
    if not required_scopes:
        return ""
    if not granted_scope:
        return f"Likely missing SMART scopes. Add one of: {', '.join(required_scopes)}."
    granted = {scope.strip() for scope in granted_scope.split() if scope.strip()}
    if any(scope in granted or "patient/*.read" in granted for scope in required_scopes):
        return ""
    return (
        "Likely missing SMART scope. "
        f"Granted: {', '.join(sorted(granted))}. "
        f"Expected one of: {', '.join(required_scopes)}."
    )


def _operation_outcome_from_exception(
    *,
    request_path: str,
    exc: Exception,
    required_scopes: list[str],
    granted_scope: str,
) -> dict[str, Any]:
    status_code = 0
    error_text = str(exc)
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        status_code = exc.response.status_code
        response_text = (exc.response.text or "").strip()
        if response_text:
            error_text = response_text

    hint = ""
    if status_code == 403:
        hint = _scope_hint(required_scopes, granted_scope)
    elif status_code == 400:
        hint = "Search parameter mismatch for this tenant; fallback query variants were attempted."

    return {
        "resourceType": "OperationOutcome",
        "request": request_path,
        "statusCode": status_code,
        "error": error_text,
        "hint": hint,
    }


async def _fetch_with_fallback_paths(
    *,
    settings: Settings,
    access_token: str,
    candidate_paths: list[str],
    required_scopes: list[str],
    granted_scope: str,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for path_with_query in candidate_paths:
        try:
            return await fetch_fhir_json(
                settings=settings,
                access_token=access_token,
                path_with_query=path_with_query,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                # Try fallback query variants for 400/404, otherwise stop.
                if exc.response.status_code in {400, 404}:
                    continue
            break

    return _operation_outcome_from_exception(
        request_path=candidate_paths[0] if candidate_paths else "",
        exc=last_error or RuntimeError("Unknown Epic fetch error"),
        required_scopes=required_scopes,
        granted_scope=granted_scope,
    )


async def try_fetch_fhir_json(
    *,
    settings: Settings,
    access_token: str,
    path_with_query: str,
    required_scopes: list[str] | None = None,
    granted_scope: str = "",
) -> dict[str, Any]:
    try:
        return await fetch_fhir_json(
            settings=settings,
            access_token=access_token,
            path_with_query=path_with_query,
        )
    except Exception as exc:  # noqa: BLE001
        return _operation_outcome_from_exception(
            request_path=path_with_query,
            exc=exc,
            required_scopes=required_scopes or [],
            granted_scope=granted_scope,
        )


def _patient_name(patient: dict[str, Any]) -> str:
    names = patient.get("name") or []
    if not names:
        return "Unknown Patient"
    first = names[0]
    given = " ".join(first.get("given", [])) if isinstance(first.get("given"), list) else ""
    family = first.get("family", "")
    full = f"{given} {family}".strip()
    return full or "Unknown Patient"


def _mask_token(token: str) -> str:
    if len(token) <= 12:
        return token
    return f"{token[:8]}...{token[-4:]}"


async def fetch_epic_patient_data(*, settings: Settings, token_response: dict[str, Any]) -> dict[str, Any]:
    access_token = token_response.get("access_token", "")
    if not access_token:
        raise ValueError("Token response does not include access_token.")

    patient_id = token_response.get("patient", "")
    if not patient_id:
        patient_search = await try_fetch_fhir_json(
            settings=settings,
            access_token=access_token,
            path_with_query="Patient?_count=1",
        )
        patient_id = (
            patient_search.get("entry", [{}])[0].get("resource", {}).get("id", "")
            if isinstance(patient_search.get("entry"), list) and patient_search.get("entry")
            else ""
        )
    if not patient_id:
        raise ValueError("No patient ID in token response and no patient found.")

    granted_scope = str(token_response.get("scope") or "")
    encoded_patient_id = quote(str(patient_id), safe="")
    patient_reference = quote(f"Patient/{patient_id}", safe="")

    patient = await fetch_fhir_json(
        settings=settings,
        access_token=access_token,
        path_with_query=f"Patient/{patient_id}",
    )

    conditions_task = _fetch_with_fallback_paths(
        settings=settings,
        access_token=access_token,
        candidate_paths=[
            f"Condition?patient={encoded_patient_id}&_count=20",
            f"Condition?subject={patient_reference}&_count=20",
            f"Condition?subject={encoded_patient_id}&_count=20",
        ],
        required_scopes=["patient/Condition.read"],
        granted_scope=granted_scope,
    )
    observations_task = _fetch_with_fallback_paths(
        settings=settings,
        access_token=access_token,
        candidate_paths=[
            f"Observation?patient={encoded_patient_id}&_count=20",
            f"Observation?subject={patient_reference}&_count=20",
            f"Observation?subject={encoded_patient_id}&_count=20",
        ],
        required_scopes=["patient/Observation.read"],
        granted_scope=granted_scope,
    )
    medications_task = _fetch_with_fallback_paths(
        settings=settings,
        access_token=access_token,
        candidate_paths=[
            f"MedicationRequest?patient={encoded_patient_id}&_count=20&_include=MedicationRequest:medication",
            f"MedicationRequest?subject={patient_reference}&_count=20&_include=MedicationRequest:medication",
            f"MedicationRequest?subject={encoded_patient_id}&_count=20&_include=MedicationRequest:medication",
        ],
        required_scopes=["patient/MedicationRequest.read"],
        granted_scope=granted_scope,
    )
    documents_task = _fetch_with_fallback_paths(
        settings=settings,
        access_token=access_token,
        candidate_paths=[
            f"DocumentReference?patient={encoded_patient_id}&_count=20",
            f"DocumentReference?subject={patient_reference}&_count=20",
        ],
        required_scopes=["patient/DocumentReference.read"],
        granted_scope=granted_scope,
    )
    allergies_task = _fetch_with_fallback_paths(
        settings=settings,
        access_token=access_token,
        candidate_paths=[
            f"AllergyIntolerance?patient={encoded_patient_id}&_count=20",
            f"AllergyIntolerance?subject={patient_reference}&_count=20",
            f"AllergyIntolerance?subject={encoded_patient_id}&_count=20",
        ],
        required_scopes=["patient/AllergyIntolerance.read"],
        granted_scope=granted_scope,
    )
    appointments_task = _fetch_with_fallback_paths(
        settings=settings,
        access_token=access_token,
        candidate_paths=[
            f"Appointment?patient={encoded_patient_id}&_count=20",
            f"Appointment?actor={patient_reference}&_count=20",
        ],
        required_scopes=["patient/Appointment.read"],
        granted_scope=granted_scope,
    )
    care_plan_task = _fetch_with_fallback_paths(
        settings=settings,
        access_token=access_token,
        candidate_paths=[
            f"CarePlan?patient={encoded_patient_id}&_count=20",
            f"CarePlan?subject={patient_reference}&_count=20",
        ],
        required_scopes=["patient/CarePlan.read"],
        granted_scope=granted_scope,
    )

    (
        conditions,
        observations,
        medications,
        documents,
        allergies,
        appointments,
        care_plan,
    ) = await asyncio.gather(
        conditions_task,
        observations_task,
        medications_task,
        documents_task,
        allergies_task,
        appointments_task,
        care_plan_task,
    )

    return {
        "fetchedAt": _now_iso(),
        "patientId": patient_id,
        "patientName": _patient_name(patient),
        "token": {
            "tokenType": token_response.get("token_type", ""),
            "expiresIn": token_response.get("expires_in"),
            "scope": token_response.get("scope", ""),
            "patient": token_response.get("patient", ""),
            "accessTokenPreview": _mask_token(access_token),
        },
        "raw": {
            "token": token_response,
            "patient": patient,
            "conditions": conditions,
            "observations": observations,
            "medications": medications,
            "documents": documents,
            "allergies": allergies,
            "appointments": appointments,
            "carePlan": care_plan,
        },
    }
