# Veldooc Patient Interface Structure

This UI has been split from one monolithic file into clear frontend layers:

- `index.html`: Main app entrypoint and screen markup for Vercel/static hosting.
- `veldooc_patient_app.html`: Compatibility redirect to `index.html`.
- `terms/index.html`: Public Terms & Conditions page in its own folder for separate deployment management.
- `terms.html`: Compatibility redirect to `terms/`.
- `callback.html`: OAuth callback page for Epic code/token/FHIR test flow.
- `styles/main.css`: CSS entry file that imports all style modules.
- `styles/core.css`: Global tokens, reset, and shared router styles.
- `styles/screens/*.css`: Per-screen styling (`welcome`, `ehr`, `login`, `loading`, `chat`).
- `styles/screens/csv.css`: CSV mapping/import screen styling.
- `js/navigation.js`: Screen router with hash-based navigation.
- `js/epic-config.js`: Epic sandbox OAuth/FHIR config values.
- `js/epic-auth.js`: PKCE generation, authorize redirect, token exchange, and FHIR fetch helpers.
- `js/epic-ui.js`: Injects fetched Epic data into chat chips/header/debug panel.
- `js/workflow-adapter-registry.js`: Pluggable source adapters (`fhir`, `hl7`, `cda`, `rest`, `csv`, `manual`).
- `js/workflow-normalizer.js`: Universal PatientContext normalizer.
- `js/workflow-cache.js`: Session cache (5-minute TTL) keyed by `patient_id + source_id`.
- `js/workflow-prompt.js`: System prompt builder from normalized context.
- `js/workflow-engine.js`: Adapter -> normalizer -> cache -> prompt orchestration.
- `js/workflow-mock-sources.js`: Mock-source seeding for non-Epic adapters during UI development.
- `js/workflow-ui.js`: Renders normalized context/prompt debug panels in chat.
- `js/callback.js`: Runs callback processing in `callback.html`.
- `js/ehr-flow.js`: EHR selection and Epic launch trigger.
- `js/login-flow.js`: Login step transitions (credentials -> MFA -> consent).
- `js/loading-flow.js`: Loading-state observation and auto-advance to chat.
- `js/session-timer.js`: Chat session timer.
- `js/chat-flow.js`: Static chat interaction layer (quick replies, send, voice/image simulation, toasts).
- `js/csv-mapping-ui.js`: CSV upload + column mapping UI and backend ingest integration.
- `js/app-init.js`: Central startup/init wiring for all screen flows.
- `backend/app/main.py`: FastAPI service with Epic OAuth callback and workflow APIs.
- `backend/app/epic.py`: Epic OAuth/token/FHIR client helpers.
- `backend/app/workflow.py`: Python adapter/normalizer/cache/prompt pipeline.
- `backend/app/hl7_parser.py`: HL7 v2 segment parser + ACK builder.
- `backend/app/hl7_mllp.py`: HL7 MLLP socket listener (optional service).
- `backend/app/cda_parser.py`: CDA XML parser with configurable XPath map.
- `backend/app/csv_mapper.py`: CSV text parser + mapping-to-context transformer.
- `backend/app/oauth_state.py`: PKCE state store with TTL.
- `backend/app/config.py`: Backend settings/env loading.
- `backend/requirements.txt`: Python dependencies.
- `backend/.env.example`: Backend environment template.
- `backend/README.md`: Backend setup and run guide.

## Screen IDs (for backend wiring)

- `screen-welcome`: landing view.
- `screen-ehr`: clinic/EHR picker.
- `screen-login`: OAuth-style login + MFA + consent.
- `screen-loading`: data pull/loading state.
- `screen-chat`: assistant chat interface.

## JavaScript Functions (current behavior)

- `goTo(id)`: route between screens.
- `selectEhr(id)`: store EHR provider and enable continue button.
- `filterEhr(query)`: filter EHR options in UI.
- `startEpicLogin()`: build and launch Epic OAuth authorize URL with PKCE.
- `handleEpicCallbackPage()`: validate code/state, exchange token, fetch FHIR, persist session.
- `showMfa()` / `showConsent()`: login step transitions.

## Suggested Next Backend Integration Steps

- Move token exchange/FHIR calls to a backend service for production security controls.
- Replace sandbox config values and scopes with your final Epic-approved scope set.
- Add API-level auditing, refresh-token lifecycle handling, and error telemetry.

## Python Backend Mode

- Frontend config uses `EPIC_CONFIG.authMode` in `js/epic-config.js`.
- `authMode: "browser"` keeps the original browser-only flow.
- `authMode: "backend"` routes OAuth callback/token/FHIR through FastAPI.
- `authMode: "hybrid"` tries backend first and falls back to browser flow.
