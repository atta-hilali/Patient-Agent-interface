const EPIC_CONFIG = Object.freeze({
  // Replace with your Epic Non-Production Client ID.
  clientId: 'ffbfa6c6-03a5-488a-9d01-e1b066e3030c',
  // Must exactly match a redirect URI registered in Epic (character-for-character).
  // Use your stable production hostname here (not window.location.origin, which can vary on preview/local URLs).
  redirectUri: 'https://patientagent.vercel.app/callback.html',
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
