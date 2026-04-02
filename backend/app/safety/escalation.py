# # app/safety/escalation.py
# app/safety/escalation.py
# # Escalation write-back: FHIR Flag, FHIR Observation, webhook, SMS alert.
# Escalation write-back: FHIR Flag, FHIR Observation, webhook, SMS alert.
# import httpx, os, hashlib, hmac, json
import httpx, os, hashlib, hmac, json
# from datetime import datetime, timezone
from datetime import datetime, timezone

# FHIR_BASE   = os.getenv('EPIC_AUD', '')
FHIR_BASE   = os.getenv('EPIC_AUD', '')
# WEBHOOK_URL = os.getenv('ESCALATION_WEBHOOK_URL', '')
WEBHOOK_URL = os.getenv('ESCALATION_WEBHOOK_URL', '')
# SMS_URL     = os.getenv('SMS_ALERT_URL', '')
SMS_URL     = os.getenv('SMS_ALERT_URL', '')
# WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')

# def _now_iso() -> str:
def _now_iso() -> str:
    # return datetime.now(timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()

# async def write_fhir_flag(patient_id: str, trigger: str, severity: str, session_id: str) -> bool:
async def write_fhir_flag(patient_id: str, trigger: str, severity: str, session_id: str) -> bool:
    # """Write a FHIR Flag resource to the patient's EHR record."""
    """Write a FHIR Flag resource to the patient's EHR record."""
    # if not FHIR_BASE:
    if not FHIR_BASE:
        # return False   # not configured — skip silently in dev
        return False   # not configured — skip silently in dev
    # flag = {
    flag = {
        # 'resourceType': 'Flag',
        'resourceType': 'Flag',
        # 'status': 'active',
        'status': 'active',
        # 'code': {'coding': [{'system': 'http://veldooc.ai/flags', 'code': trigger}]},
        'code': {'coding': [{'system': 'http://veldooc.ai/flags', 'code': trigger}]},
        # 'subject': {'reference': f'Patient/{patient_id}'},
        'subject': {'reference': f'Patient/{patient_id}'},
        # 'period': {'start': _now_iso()},
        'period': {'start': _now_iso()},
        # 'extension': [{'url': 'session_id', 'valueString': session_id},
        'extension': [{'url': 'session_id', 'valueString': session_id},
                      # {'url': 'severity',   'valueString': severity}],
                      {'url': 'severity',   'valueString': severity}],
    # }
    }
    # try:
    try:
        # async with httpx.AsyncClient(timeout=5.0) as c:
        async with httpx.AsyncClient(timeout=5.0) as c:
            # await c.post(f'{FHIR_BASE}/Flag', json=flag,
            await c.post(f'{FHIR_BASE}/Flag', json=flag,
                         # headers={'Content-Type': 'application/fhir+json'})
                         headers={'Content-Type': 'application/fhir+json'})
        # return True
        return True
    # except Exception:
    except Exception:
        # return False
        return False

# async def write_fhir_observation(patient_id: str, trigger: str, session_id: str) -> bool:
async def write_fhir_observation(patient_id: str, trigger: str, session_id: str) -> bool:
    # """Write pain score as FHIR Observation (LOINC 72514-3)."""
    """Write pain score as FHIR Observation (LOINC 72514-3)."""
    # if not FHIR_BASE:
    if not FHIR_BASE:
        # return False
        return False
    # # Extract score from trigger string if present
    # Extract score from trigger string if present
    # score = None
    score = None
    # for part in trigger.split(':'):
    for part in trigger.split(':'):
        # try: score = int(part.strip()); break
        try: score = int(part.strip()); break
        # except ValueError: continue
        except ValueError: continue
    # obs = {
    obs = {
        # 'resourceType': 'Observation',
        'resourceType': 'Observation',
        # 'status': 'final',
        'status': 'final',
        # 'code': {'coding': [{'system': 'http://loinc.org', 'code': '72514-3',
        'code': {'coding': [{'system': 'http://loinc.org', 'code': '72514-3',
                              # 'display': 'Pain severity — 0-10 numeric scale'}]},
                              'display': 'Pain severity — 0-10 numeric scale'}]},
        # 'subject': {'reference': f'Patient/{patient_id}'},
        'subject': {'reference': f'Patient/{patient_id}'},
        # 'effectiveDateTime': _now_iso(),
        'effectiveDateTime': _now_iso(),
        # 'valueInteger': score,
        'valueInteger': score,
    # }
    }
    # try:
    try:
        # async with httpx.AsyncClient(timeout=5.0) as c:
        async with httpx.AsyncClient(timeout=5.0) as c:
            # await c.post(f'{FHIR_BASE}/Observation', json=obs,
            await c.post(f'{FHIR_BASE}/Observation', json=obs,
                         # headers={'Content-Type': 'application/fhir+json'})
                         headers={'Content-Type': 'application/fhir+json'})
        # return True
        return True
    # except Exception:
    except Exception:
        # return False
        return False

# async def fire_webhook(session_id: str, patient_id: str, trigger: str) -> bool:
async def fire_webhook(session_id: str, patient_id: str, trigger: str) -> bool:
    # """POST HMAC-signed escalation payload to the clinic webhook."""
    """POST HMAC-signed escalation payload to the clinic webhook."""
    # if not WEBHOOK_URL:
    if not WEBHOOK_URL:
        # return False
        return False
    # payload = json.dumps({'session_id': session_id, 'patient_id': patient_id,
    payload = json.dumps({'session_id': session_id, 'patient_id': patient_id,
                          # 'trigger': trigger, 'timestamp': _now_iso()})
                          'trigger': trigger, 'timestamp': _now_iso()})
    # sig = hmac.new(WEBHOOK_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    sig = hmac.new(WEBHOOK_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    # try:
    try:
        # async with httpx.AsyncClient(timeout=5.0) as c:
        async with httpx.AsyncClient(timeout=5.0) as c:
            # await c.post(WEBHOOK_URL, content=payload,
            await c.post(WEBHOOK_URL, content=payload,
                         # headers={'Content-Type': 'application/json',
                         headers={'Content-Type': 'application/json',
                                  # 'X-Veldooc-Signature': sig})
                                  'X-Veldooc-Signature': sig})
        # return True
        return True
    # except Exception:
    except Exception:
        # return False
        return False

# async def send_sms_alert(session_id: str, trigger: str) -> bool:
async def send_sms_alert(session_id: str, trigger: str) -> bool:
    # """Send SMS to on-call coordinator (via configured SMS gateway)."""
    """Send SMS to on-call coordinator (via configured SMS gateway)."""
    # if not SMS_URL:
    if not SMS_URL:
        # return False
        return False
    # try:
    try:
        # async with httpx.AsyncClient(timeout=5.0) as c:
        async with httpx.AsyncClient(timeout=5.0) as c:
            # await c.post(SMS_URL, json={'session_id': session_id, 'trigger': trigger,
            await c.post(SMS_URL, json={'session_id': session_id, 'trigger': trigger,
                                        # 'timestamp': _now_iso()})
                                        'timestamp': _now_iso()})
        # return True
        return True
    # except Exception:
    except Exception:
        # return False
        return False
