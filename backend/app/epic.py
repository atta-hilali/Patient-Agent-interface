import base64
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

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


async def try_fetch_fhir_json(
    *,
    settings: Settings,
    access_token: str,
    path_with_query: str,
) -> dict[str, Any]:
    try:
        return await fetch_fhir_json(
            settings=settings,
            access_token=access_token,
            path_with_query=path_with_query,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "resourceType": "OperationOutcome",
            "request": path_with_query,
            "error": str(exc),
        }


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

    patient = await fetch_fhir_json(
        settings=settings,
        access_token=access_token,
        path_with_query=f"Patient/{patient_id}",
    )
    conditions = await try_fetch_fhir_json(
        settings=settings,
        access_token=access_token,
        path_with_query=f"Condition?patient={patient_id}&_count=20",
    )
    observations = await try_fetch_fhir_json(
        settings=settings,
        access_token=access_token,
        path_with_query=f"Observation?patient={patient_id}&_count=20",
    )
    medications = await try_fetch_fhir_json(
        settings=settings,
        access_token=access_token,
        path_with_query=f"MedicationRequest?patient={patient_id}&_count=20",
    )
    documents = await try_fetch_fhir_json(
        settings=settings,
        access_token=access_token,
        path_with_query=f"DocumentReference?patient={patient_id}&_count=20",
    )
    allergies = await try_fetch_fhir_json(
        settings=settings,
        access_token=access_token,
        path_with_query=f"AllergyIntolerance?patient={patient_id}&_count=20",
    )
    appointments = await try_fetch_fhir_json(
        settings=settings,
        access_token=access_token,
        path_with_query=f"Appointment?patient={patient_id}&_count=20",
    )
    care_plan = await try_fetch_fhir_json(
        settings=settings,
        access_token=access_token,
        path_with_query=f"CarePlan?patient={patient_id}&_count=20",
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
