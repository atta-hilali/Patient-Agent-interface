# Veldooc Python Backend (FastAPI)

This backend moves sensitive Epic OAuth/token/FHIR logic out of the browser.

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

## 2. Run

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

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

## 6. Render deployment (production)

Use these exact settings for a monorepo where backend lives in `backend/`:

- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Python version is pinned in `backend/.python-version`:

- `3.11.11`

If your existing Render service still builds with Python 3.14, also set:

- Environment Variable: `PYTHON_VERSION=3.11.11`

After changing Python version, trigger a fresh deploy.
