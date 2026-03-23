const EPIC_CONFIG = Object.freeze({
  // Replace with your Epic Non-Production Client ID.
  clientId: 'ffbfa6c6-03a5-488a-9d01-e1b066e3030c',
  // Must exactly match a redirect URI registered in Epic.
  redirectUri: `${window.location.origin}/callback.html`,
  authorizeUrl: 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize',
  tokenUrl: 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token',
  aud: 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4',
  scope: [
    'openid',
    'fhirUser',
    'Patient.Read',
    'Patient.Search',
    'Condition.Read',
    'Condition.Search',
    'Observation.Read',
    'Observation.Search',
    'Medication.Read',
    'Medication.Search',
    'DocumentReference.Read',
    'DocumentReference.Search'
  ].join(' ')
});
