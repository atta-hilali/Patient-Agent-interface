# Phase 2 Startup Sheet (DGX)

Use this exact order every time.

## 0. Prepare session

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
source .venv/bin/activate
chmod +x scripts/*.sh
```

Make sure `.env` exists and is filled (`EPIC_*`, `REDIS_*`, `ASR_*`, `MEDGEMMA_*`, `NEMOGUARD_*`).

## 1. Terminal A - ASR NIM

```bash
export NGC_API_KEY="<YOUR_NGC_API_KEY>"
export LOCAL_NIM_CACHE="$HOME/.cache/nim"
./scripts/01_start_asr_nim.sh
```

Keep this terminal running.

## 2. Terminal B - MedGemma (vLLM)

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
./scripts/05_start_medgemma_vllm.sh
```

Keep this terminal running.

## 3. Terminal C - NemoGuard Content Safety (detached container)

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
export NGC_API_KEY="<YOUR_NGC_API_KEY>"
export LOCAL_NIM_CACHE="$HOME/.cache/nim"
./scripts/06_start_nemoguard_content_safety.sh
docker logs -f contentsafety
```

Wait until ready, then stop tail with `Ctrl+C`.

## 4. Terminal D - NemoGuard Topic Control (detached container)

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
export NGC_API_KEY="<YOUR_NGC_API_KEY>"
export LOCAL_NIM_CACHE="$HOME/.cache/nim"
./scripts/07_start_nemoguard_topic_control.sh
docker logs -f topiccontrol
```

Wait until ready, then stop tail with `Ctrl+C`.

## 5. Terminal E - Backend API

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
./scripts/02_start_backend.sh
```

Keep this terminal running.

## 6. Terminal F - Tunnel (for Vercel frontend)

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
./scripts/03_start_tunnel.sh
```

Copy the `https://...trycloudflare.com` URL and set it in `js/epic-config.js` as:

```js
backendBaseUrl: 'https://<YOUR_TUNNEL_URL>',
```

Then push frontend and redeploy Vercel.

## 7. Validate stack

```bash
cd /home/dev1/Desktop/data/features/feature_atta/Patient-Agent-interface/backend
./scripts/04_check_stack.sh
./scripts/08_check_phase2_models.sh
./scripts/10_run_tests.sh
```

Expected:
- backend health OK
- ASR probe reachable
- MedGemma health/models/chat OK
- Content Safety blocks unsafe text
- Topic Control blocks dosage/prescribing text

## 8. Daily stop commands

```bash
docker rm -f contentsafety topiccontrol 2>/dev/null || true
```

Then stop foreground terminals with `Ctrl+C` (ASR, MedGemma, backend, tunnel).

## 9. Common quick fixes

1. `address already in use`
```bash
ss -ltnp | grep -E ':8001|:8002|:8003|:9001'
```

2. Content Safety crashes on GB10
- Keep using forced profile in `06_start_nemoguard_content_safety.sh`.

3. Frontend says `Failed to fetch`
- tunnel URL changed or backend not running.

4. Epic callback/session issues
- verify `EPIC_REDIRECT_URI` exactly matches Epic app settings and frontend config.
