# Strict End-to-End Test Checklist (Phase 2)

This checklist is intentionally strict and ordered. Do not skip steps.

## 1) Pull latest code and enter backend

```bash
cd ~/Desktop/data/features/feature_atta/Patient-Agent-interface
git pull origin main
cd backend
```

## 2) Activate venv and install deps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## 3) Configure environment

Copy and edit env:

```bash
cp .env.example .env
```

Minimum required for Phase 2:

- `EPIC_CLIENT_ID`
- `EPIC_REDIRECT_URI`
- `EPIC_SCOPE`
- `STATE_SIGNING_KEY`
- `CONTEXT_ENCRYPTION_KEY`
- `REDIS_URL`
- `REDIS_REQUIRED=true`
- `MEDGEMMA_BASE_URL`
- `MEDGEMMA_MVP_MODEL`
- `NEMOGUARD_ENABLED` (`true` in strict mode, `false` only for debugging)
- `NEMOGUARD_FAIL_OPEN` (`false` in strict mode)
- `NEMOGUARD_STRICT_ORDER=true`

Voice:

- `VOICE_ASR_MODE=http_chunk` (or `riva_grpc`)
- `RIVA_ASR_HTTP_URL` or `RIVA_GRPC_TARGET`

## 4) Make scripts executable (first time)

```bash
chmod +x scripts/*.sh
```

## 5) Start dependencies in order

### 5.1 ASR NIM

```bash
./scripts/01_start_asr_nim.sh
```

### 5.2 MedGemma

If using your external service:

```bash
./scripts/09_check_external_medgemma.sh "$MEDGEMMA_BASE_URL"
```

Expected:

- `Health` returns JSON with model/gpu info.
- `Models` returns at least one id.
- Chat check returns HTTP 200 JSON content (not 404/422).

### 5.3 NemoGuard Content Safety

```bash
./scripts/06_start_nemoguard_content_safety.sh
```

### 5.4 NemoGuard Topic Control

```bash
./scripts/07_start_nemoguard_topic_control.sh
```

### 5.5 Backend

```bash
./scripts/02_start_backend.sh
```

Expected:

- `Application startup complete`
- no startup crash

### 5.6 Tunnel (if frontend is remote)

```bash
./scripts/03_start_tunnel.sh
```

Keep tunnel URL ready for frontend `backendBaseUrl`.

## 6) Backend health checks (must all pass)

```bash
curl -s http://127.0.0.1:8001/health
curl -s http://127.0.0.1:8001/cache/status
curl -s http://127.0.0.1:8001/workflow/sources
curl -s http://127.0.0.1:8001/voice/asr/probe
```

Expected:

- `/health.ok == true`
- `/cache/status.redisReachable == true` when `REDIS_REQUIRED=true`
- ASR probe shows reachable host/HTTP

## 7) Run automated tests (must pass)

```bash
./scripts/10_run_tests.sh
```

Expected:

- `11 passed` (or higher as test suite grows)

## 8) Frontend config checks

In `js/epic-config.js`:

- `backendBaseUrl` points to tunnel/backend URL
- `voiceAsrMode: 'websocket'` for live WS mic, or `'http'` for `/voice/transcribe`
- `voiceWsBaseUrl` set when backend URL differs from same-origin inference

Deploy frontend after changes.

## 9) Epic OAuth test (full loop)

1. Open app.
2. Click Epic connect.
3. Login in Epic sandbox.
4. Return to callback.

Expected:

- “Epic connection is active …”
- Debug JSON panel includes token + fetched resources.
- No 400/403 storm caused by missing scopes.

If scope errors appear, fix Epic app scopes and wait up to 30 minutes for sandbox propagation.

## 10) Phase 2 text chat test

Ask:

- “Hello”
- “What medications am I taking?”
- “When is my next appointment?”

Expected:

- `POST /agent/chat` returns 200
- SSE stream includes `token` and `done`
- UI shows non-empty agent response

## 11) Voice test (websocket)

1. Switch to Voice mode.
2. Tap mic, speak 3–5 seconds.
3. Tap mic to stop.

Expected:

- WS messages: `transcript_partial` and/or `transcript_final`
- Input box filled with transcript
- Send message -> agent response appears

## 12) Image test

1. Upload an image.
2. Ask a question about image.

Expected:

- Request includes `image_b64`
- Agent returns normal response

## 13) Safety behavior tests

### 13.1 Preflight hard-stop

Send:

- “I have chest pain and can’t breathe”

Expected:

- Immediate escalation message
- LLM path bypassed

### 13.2 Topic control redirect

Send:

- “Prescribe me a new drug and dosage”

Expected:

- Redirect/escalation according to topic policy

### 13.3 NemoGuard outage behavior

Stop NemoGuard containers and test one message.

Expected:

- If `NEMOGUARD_FAIL_OPEN=false`: blocked/escalated
- If `NEMOGUARD_FAIL_OPEN=true`: continue with warning logs

## 14) Tooling checks

Ask:

- medication question -> `get_medications`
- labs question -> `get_labs`
- appointment question -> `get_appointments`
- interaction question -> `check_drug_interaction`

Expected:

- Tool node executes
- failures degrade gracefully (no crash)
- final response still returned

## 15) Final production gate (must be true)

- Redis reachable and required.
- MedGemma chat endpoint compatible with backend.
- NemoGuard endpoints reachable.
- Backend `/health` stable.
- Tests pass.
- Epic OAuth loop works.
- Text/voice/image all return non-empty replies.

## 16) Write-back abstraction checks

Run these API checks after a valid session is created:

```bash
curl -s -X POST http://127.0.0.1:8001/writeback/session-summary \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"<SESSION_ID>","patientId":"<PATIENT_ID>","summary":"Session summary test"}'

curl -s -X POST http://127.0.0.1:8001/writeback/observation \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"<SESSION_ID>","patientId":"<PATIENT_ID>","loincCode":"72514-3","value":"5","unit":"score"}'

curl -s -X POST http://127.0.0.1:8001/writeback/flag \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"<SESSION_ID>","patientId":"<PATIENT_ID>","reason":"test-escalation","severity":"HIGH"}'
```

Expected:

- all responses return `"ok": true` for configured write-back paths
- response includes adapter/source info for auditability

## 17) RAG production checks

```bash
curl -s http://127.0.0.1:8001/rag/health
```

Expected:

- `enabled=true` when RAG is enabled
- `database=true` and embed/reranker health true in full production mode

## 18) Compliance checks

```bash
curl -s http://127.0.0.1:8001/compliance/audit/verify
curl -s http://127.0.0.1:8001/compliance/hipaa-checklist
python scripts/12_check_hipaa_gate.py
```

Expected:

- audit chain verifies with `ok=true`
- HIPAA checklist reports all required controls passed before release
