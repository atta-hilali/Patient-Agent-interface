# DGX Backend Runbook (Phase 2, Copy/Paste Ready)

Use this when you want to start the full backend stack on DGX without searching old chat history.

This runbook covers:
- Epic SMART on FHIR login via backend callback
- Phase 2 `/agent/chat` SSE
- Phase 2 `/ws/audio/{session_id}` WebSocket
- Voice `/voice/transcribe` (ASR NIM)

## 1. Expected local structure on DGX

```text
Patient-Agent-interface/
  backend/
    .env
    .venv/
    app/
    scripts/
      01_start_asr_nim.sh
      02_start_backend.sh
      03_start_tunnel.sh
      04_check_stack.sh
```

## 2. One-time setup on DGX

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x scripts/*.sh
```

Put real values in `backend/.env` (not `.env.example`), especially:

- `EPIC_CLIENT_ID`
- `EPIC_REDIRECT_URI`
- `ALLOWED_ORIGINS`
- `STATE_SIGNING_KEY`
- `REDIS_REQUIRED` and `REDIS_URL`
- `ASR_BASE_URL`
- `VOICE_ASR_MODE`, `RIVA_ASR_HTTP_URL` (or gRPC values)
- `MEDGEMMA_BASE_URL`
- `NEMOGUARD_CONTENT_SAFETY_URL`
- `NEMOGUARD_TOPIC_CONTROL_URL`
- `TTS_NIM_URL` (optional)

## 3. Start sequence (three terminals)

### Terminal A: ASR NIM

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
export NGC_API_KEY="<YOUR_NGC_API_KEY>"
./scripts/01_start_asr_nim.sh
```

### Terminal B: FastAPI backend

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
./scripts/02_start_backend.sh
```

### Terminal C: HTTPS tunnel for Vercel frontend

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
./scripts/03_start_tunnel.sh
```

Copy the `https://...trycloudflare.com` URL shown in terminal C.

## 4. Frontend update (required for quick tunnel)

Set `backendBaseUrl` in `js/epic-config.js` to the current tunnel URL, then deploy frontend.

```js
backendBaseUrl: 'https://<YOUR_TRYCLOUDFLARE_URL>',
```

Quick tunnel URLs change on every restart, so repeat this step each time.

## 5. Verify everything

From DGX:

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
./scripts/04_check_stack.sh
```

Expected:

- `/health` returns `ok: true`
- `/cache/status` shows expected Redis mode
- `/voice/asr/probe` shows `tcpReachable: true` and `httpReachable: true`
- `/workflow/sources` returns source adapter list
- `/agent/chat` returns `401` without session (this is expected)

Manual check for SSE after Epic login:

```bash
curl -N -X POST "http://127.0.0.1:8001/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<SESSION_ID_FROM_CALLBACK>","message":"what are my medications?"}'
```

Manual check for audio WebSocket route availability:

```bash
curl -i "http://127.0.0.1:8001/ws/audio/test-session"
```

Expected: HTTP upgrade required/handshake-related response (route exists).

## 6. Optional model services (Phase 2 full path)

If you are running local model services on DGX, verify these URLs from `.env`:

- `MEDGEMMA_BASE_URL` (vLLM OpenAI-compatible endpoint, e.g. `http://127.0.0.1:8001/v1`)
- `NEMOGUARD_CONTENT_SAFETY_URL` (e.g. `http://127.0.0.1:8002/v1/guardrail`)
- `NEMOGUARD_TOPIC_CONTROL_URL` (e.g. `http://127.0.0.1:8003/v1/guardrail`)
- `TTS_NIM_URL` (optional, e.g. `http://127.0.0.1:8000/v1/tts`)

The backend can start without these, but Phase 2 responses may escalate/fallback if unreachable.

## 7. Troubleshooting

1. `address already in use` on backend:
```bash
ss -ltnp | grep :8001
```
Change port with:
```bash
BACKEND_PORT=8002 ./scripts/02_start_backend.sh
```

2. Voice error `ASR response did not contain transcript text`:
- Check ASR response shape and logs.
- Ensure backend code is latest and restarted.

3. Epic error `The request is invalid`:
- In backend `.env`, verify `EPIC_REDIRECT_URI` exactly matches Epic app config.
- Verify scopes and client id.
- Verify frontend `EPIC_CONFIG.redirectUri` exactly matches Epic registration.

4. `Failed to fetch` in frontend:
- Tunnel down or URL changed.
- CORS mismatch in `ALLOWED_ORIGINS`.

5. `/agent/chat` returns `401 Session expired`:
- Epic callback did not complete on this backend instance.
- Run Epic login again and confirm callback returns `session.sessionId`.
- Confirm Redis is shared/reachable if using multiple instances.
