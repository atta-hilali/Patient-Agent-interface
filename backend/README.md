# Veldooc Python Backend (FastAPI)

This backend moves sensitive Epic OAuth/token/FHIR logic out of the browser.
For DGX operations, see `backend/DGX_RUNBOOK.md`.

## 1. Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set:

- `EPIC_CLIENT_ID`
- `EPIC_REDIRECT_URI` (must exactly match Epic app redirect URI)
- optionally `ALLOWED_ORIGINS`
- `REDIS_URL` and `REDIS_REQUIRED=true` for Redis-only mode
- set `CONTEXT_ENCRYPTION_KEY` in production
- optional HL7 listener vars (`HL7_MLLP_*`)
- optional ASR vars for NVIDIA NIM (`ASR_*`)

## 2. Run

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### MedGemma / vLLM

MVP uses MedGemma 4B by default for faster iteration. Sprint 3 / larger deployments can switch to MedGemma 27B.

Example MVP vLLM command:

```powershell
vllm serve google/medgemma-4b-it --max-model-len 8192 --enable-chunked-prefill --dtype bfloat16 --port 8001
```

Example Sprint 3 command:

```powershell
vllm serve google/medgemma-27b-it --tensor-parallel-size 2 --max-model-len 8192 --enable-chunked-prefill --dtype bfloat16 --port 8001
```

Optional environment variables:

- `MEDGEMMA_BASE_URL`
- `MEDGEMMA_API_KEY`
- `MEDGEMMA_MODE` with `mvp` or `sprint3`
- `MEDGEMMA_MVP_MODEL`
- `MEDGEMMA_SPRINT3_MODEL`
- `MEDGEMMA_MAX_TOKENS`

## 3. Endpoints

- `GET /health`
- `GET /workflow/sources`
- `GET /hl7/mllp/status`
- `GET /hl7/mllp/messages`
- `GET /auth/epic/start?format=json` (returns authorize URL)
- `GET /auth/epic/start` (redirects to Epic authorize URL)
- `GET /auth/epic/callback?code=...&state=...` (token exchange + FHIR fetch + workflow pipeline)
- `POST /workflow/normalize` (legacy alias)
- `POST /workflow/ingest`
- `POST /workflow/ingest/hl7` (raw HL7 v2 message)
- `POST /workflow/ingest/cda` (CDA XML + optional XPath map)
- `POST /workflow/ingest/csv` (CSV text + mapping object)
- `POST /chat/preflight` (safety gate)
- `GET /voice/asr/probe` (Render-side DNS/TCP/HTTP reachability check to ASR)
- `POST /voice/transcribe` (base64 audio -> ASR NIM transcript)
- `POST /workflow/unlock-check`

## 4. Workflow architecture

- Adapter registry by source type: `fhir`, `hl7`, `cda`, `rest`, `csv`, `manual`
- Universal `PatientContext` schema (Pydantic)
- Session cache with TTL and Redis-first storage
- Cache payload encryption (Fernet)
- Prompt builder with citation tags (`[MED-1]`, `[COND-1]`, `[LAB-1]`)
- Pre-flight safety checks before LLM path
- Consent-based chat unlock
- HL7 MLLP listener with ACK support (optional)
- CDA XML parser with configurable XPath map
- CSV mapping ingestion support

## 5. Frontend config

In `js/epic-config.js`:

- `authMode: "backend"` to force backend
- `authMode: "hybrid"` to try backend then fallback to browser
- `backendBaseUrl: "http://127.0.0.1:8000"`
- optional `asrLanguage: "en-US"`

## 6. ASR NIM (voice input)

Set these environment variables in backend deployment:

- `ASR_BASE_URL` (example: `http://<dgx-host>:9000`)
- `ASR_HEALTH_PATH` (default: `/v1/health/ready`)
- `ASR_TRANSCRIBE_PATH` (default: `/v1/audio/transcriptions`)
- `ASR_DEFAULT_LANGUAGE` (default: `en-US`)
- `ASR_TIMEOUT_SEC` (default: `60`)
- `ASR_VERIFY_TLS` (`true` for HTTPS with trusted cert, `false` for self-signed lab setup)
- optional auth: `ASR_AUTH_HEADER`, `ASR_AUTH_TOKEN`

Quick health check:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

Quick ASR check from browser app:

- Open app chat screen
- Click microphone
- Speak
- Click microphone again to stop and transcribe

## 7. Render deployment (production)

Use these exact settings for a monorepo where backend lives in `backend/`:

- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Python version is pinned in `backend/.python-version`:

- `3.11.11`

If your existing Render service still builds with Python 3.14, also set:

- Environment Variable: `PYTHON_VERSION=3.11.11`

After changing Python version, trigger a fresh deploy.
