const EPIC_CONFIG = Object.freeze({
  // Replace with your Epic Non-Production Client ID.
  clientId: 'ffbfa6c6-03a5-488a-9d01-e1b066e3030c',
  // Auth execution mode:
  // browser = current direct-in-browser OAuth/token/FHIR flow
  // backend = force Python backend flow
  // hybrid  = try backend first, fallback to browser
  authMode: 'backend',
  // Python backend base URL (FastAPI). Keep same-origin if using reverse proxy.
  backendBaseUrl: 'https://dense-cases-equipment-sure.trycloudflare.com',
  // Voice input mode:
  // websocket = stream PCM to /ws/audio/{session_id} (production-like path)
  // http      = record chunk then POST /voice/transcribe (fallback)
  voiceAsrMode: 'websocket',
  // Optional explicit WS base URL. Leave empty to derive from backendBaseUrl.
  voiceWsBaseUrl: '',
  // Preferred ASR language passed to backend /voice/transcribe.
  asrLanguage: 'en-US',
  // Must exactly match a redirect URI registered in Epic (character-for-character).
  // Use your stable production hostname here (not window.location.origin, which can vary on preview/local URLs).
  redirectUri: 'https://patient-agent-interface.vercel.app/callback.html',
  authorizeUrl: 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize',
  tokenUrl: 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token',
  aud: 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4',
  scope: [
    'openid',
    'fhirUser',
    'launch/patient',
    'patient/*.read'
  ].join(' ')
});

window.EPIC_CONFIG = EPIC_CONFIG;
