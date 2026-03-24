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
- optionally `REDIS_URL` (for shared cache instead of in-memory fallback)
- set `CONTEXT_ENCRYPTION_KEY` in production

## 2. Run

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 3. Endpoints

- `GET /health`
- `GET /workflow/sources`
- `GET /auth/epic/start?format=json` (returns authorize URL)
- `GET /auth/epic/start` (redirects to Epic authorize URL)
- `GET /auth/epic/callback?code=...&state=...` (token exchange + FHIR fetch + workflow pipeline)
- `POST /workflow/normalize` (legacy alias)
- `POST /workflow/ingest`
- `POST /chat/preflight` (safety gate)
- `POST /workflow/unlock-check`

## 4. Workflow architecture

- Adapter registry by source type: `fhir`, `hl7`, `cda`, `rest`, `csv`, `manual`
- Universal `PatientContext` schema (Pydantic)
- Session cache with TTL and optional Redis storage
- Cache payload encryption (Fernet)
- Prompt builder with citation tags (`[MED-1]`, `[COND-1]`, `[LAB-1]`)
- Pre-flight safety checks before LLM path
- Consent-based chat unlock

## 5. Frontend config

In `js/epic-config.js`:

- `authMode: "backend"` to force backend
- `authMode: "hybrid"` to try backend then fallback to browser
- `backendBaseUrl: "http://127.0.0.1:8000"`
