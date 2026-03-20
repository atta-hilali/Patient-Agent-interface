# Veldooc Patient Interface Structure

This UI has been split from one monolithic file into clear frontend layers:

- `index.html`: Main app entrypoint and screen markup for Vercel/static hosting.
- `veldooc_patient_app.html`: Compatibility redirect to `index.html`.
- `styles/main.css`: CSS entry file that imports all style modules.
- `styles/core.css`: Global tokens, reset, and shared router styles.
- `styles/screens/*.css`: Per-screen styling (`welcome`, `ehr`, `login`, `loading`, `chat`).
- `js/navigation.js`: Screen router with hash-based navigation.
- `js/ehr-flow.js`: EHR selection, filtering, and redirect simulation.
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
- `doRedirect()`: simulate OAuth redirect.
- `showMfa()` / `showConsent()`: login step transitions.

## Suggested Next Backend Integration Steps

- Replace `doRedirect()` simulation with real SMART on FHIR OAuth calls.
- Replace loading simulation with API progress events.
- Replace static chat messages with backend conversation API responses.
- Replace hardcoded context chips with patient-context payload from backend.
