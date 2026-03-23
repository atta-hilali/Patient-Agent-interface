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
- `js/navigation.js`: Screen router with hash-based navigation.
- `js/epic-config.js`: Epic sandbox OAuth/FHIR config values.
- `js/epic-auth.js`: PKCE generation, authorize redirect, token exchange, and FHIR fetch helpers.
- `js/epic-ui.js`: Injects fetched Epic data into chat chips/header/debug panel.
- `js/callback.js`: Runs callback processing in `callback.html`.
- `js/ehr-flow.js`: EHR selection and Epic launch trigger.
- `js/login-flow.js`: Login step transitions (credentials -> MFA -> consent).
- `js/loading-flow.js`: Loading-state observation and auto-advance to chat.
- `js/session-timer.js`: Chat session timer.
- `js/chat-flow.js`: Static chat interaction layer (quick replies, send, voice/image simulation, toasts).
- `js/app-init.js`: Central startup/init wiring for all screen flows.

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
