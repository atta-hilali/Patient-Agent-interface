# DGX Backend Runbook (Copy/Paste Ready)

Use this when you want to start the full backend stack on DGX without searching old chat history.

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
- `ASR_BASE_URL`
- `REDIS_REQUIRED` and `REDIS_URL`

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

## 6. Troubleshooting

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

4. `Failed to fetch` in frontend:
- Tunnel down or URL changed.
- CORS mismatch in `ALLOWED_ORIGINS`.

