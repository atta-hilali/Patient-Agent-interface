function randomString(length = 64) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  let out = '';
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  for (let i = 0; i < length; i += 1) {
    out += chars[bytes[i] % chars.length];
  }
  return out;
}

async function sha256Base64Url(value) {
  const data = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest('SHA-256', data);
  const bytes = Array.from(new Uint8Array(digest));
  const b64 = btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
  return b64;
}

function getQueryParams(search = window.location.search) {
  const p = new URLSearchParams(search);
  return {
    code: p.get('code'),
    state: p.get('state'),
    error: p.get('error'),
    errorDescription: p.get('error_description')
  };
}

function saveEpicSession(data) {
  sessionStorage.setItem('epic_session_data', JSON.stringify(data));
  document.dispatchEvent(new CustomEvent('epic:session-updated', { detail: data }));
}

function loadEpicSession() {
  const raw = sessionStorage.getItem('epic_session_data');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function clearEpicAuthArtifacts() {
  sessionStorage.removeItem('epic_state');
  sessionStorage.removeItem('epic_code_verifier');
}

async function startEpicLogin() {
  if (!EPIC_CONFIG || !EPIC_CONFIG.clientId || EPIC_CONFIG.clientId.includes('YOUR_NON_PRD')) {
    throw new Error('Set EPIC_CONFIG.clientId with your Epic Non-Production Client ID first.');
  }

  const state = randomString(32);
  const codeVerifier = randomString(64);
  const codeChallenge = await sha256Base64Url(codeVerifier);

  sessionStorage.setItem('epic_state', state);
  sessionStorage.setItem('epic_code_verifier', codeVerifier);

  const url =
    `${EPIC_CONFIG.authorizeUrl}?` +
    `response_type=code&` +
    `redirect_uri=${encodeURIComponent(EPIC_CONFIG.redirectUri)}&` +
    `client_id=${encodeURIComponent(EPIC_CONFIG.clientId)}&` +
    `state=${encodeURIComponent(state)}&` +
    `aud=${encodeURIComponent(EPIC_CONFIG.aud)}&` +
    `scope=${encodeURIComponent(EPIC_CONFIG.scope)}&` +
    `code_challenge=${encodeURIComponent(codeChallenge)}&` +
    `code_challenge_method=S256`;

  window.location.href = url;
}

async function exchangeCodeForToken(code) {
  const codeVerifier = sessionStorage.getItem('epic_code_verifier');
  if (!codeVerifier) throw new Error('Missing code_verifier in sessionStorage.');

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: EPIC_CONFIG.redirectUri,
    client_id: EPIC_CONFIG.clientId,
    code_verifier: codeVerifier
  });

  const res = await fetch(EPIC_CONFIG.tokenUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Token exchange failed: ${res.status} ${text}`);
  }

  return res.json();
}

async function fetchFhirJson(accessToken, pathWithQuery) {
  const url = `${EPIC_CONFIG.aud}/${pathWithQuery}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: 'application/fhir+json'
    }
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`FHIR fetch failed (${res.status}) for ${pathWithQuery}: ${text}`);
  }
  return res.json();
}

async function tryFetchFhirJson(accessToken, pathWithQuery) {
  try {
    return await fetchFhirJson(accessToken, pathWithQuery);
  } catch (error) {
    return { resourceType: 'OperationOutcome', error: error.message, request: pathWithQuery };
  }
}

function maskToken(token = '') {
  if (!token) return '';
  if (token.length <= 12) return token;
  return `${token.slice(0, 8)}...${token.slice(-4)}`;
}

function getPatientName(patient) {
  const name = patient?.name?.[0];
  if (!name) return 'Unknown Patient';
  const given = Array.isArray(name.given) ? name.given.join(' ') : '';
  return `${given} ${name.family || ''}`.trim();
}

async function fetchEpicPatientData(tokenResponse) {
  const accessToken = tokenResponse.access_token;
  if (!accessToken) throw new Error('Token response does not include access_token.');

  let patientId = tokenResponse.patient || '';
  if (!patientId) {
    const patientSearch = await tryFetchFhirJson(accessToken, 'Patient?_count=1');
    patientId = patientSearch?.entry?.[0]?.resource?.id || '';
  }
  if (!patientId) throw new Error('No patient ID in token response and no patient found.');

  const [patient, conditions, observations, medications, documents] = await Promise.all([
    fetchFhirJson(accessToken, `Patient/${encodeURIComponent(patientId)}`),
    tryFetchFhirJson(accessToken, `Condition?patient=${encodeURIComponent(patientId)}&_count=20`),
    tryFetchFhirJson(accessToken, `Observation?patient=${encodeURIComponent(patientId)}&_count=20`),
    tryFetchFhirJson(accessToken, `MedicationRequest?patient=${encodeURIComponent(patientId)}&_count=20`),
    tryFetchFhirJson(accessToken, `DocumentReference?patient=${encodeURIComponent(patientId)}&_count=20`)
  ]);

  return {
    fetchedAt: new Date().toISOString(),
    patientId,
    patientName: getPatientName(patient),
    token: {
      tokenType: tokenResponse.token_type,
      expiresIn: tokenResponse.expires_in,
      scope: tokenResponse.scope,
      patient: tokenResponse.patient || '',
      accessTokenPreview: maskToken(tokenResponse.access_token)
    },
    raw: {
      token: tokenResponse,
      patient,
      conditions,
      observations,
      medications,
      documents
    }
  };
}

async function completeEpicOAuth(query) {
  const storedState = sessionStorage.getItem('epic_state');
  if (!query.code) throw new Error('Missing authorization code in callback URL.');
  if (!query.state || query.state !== storedState) throw new Error('State validation failed.');

  const tokenResponse = await exchangeCodeForToken(query.code);
  const epicData = await fetchEpicPatientData(tokenResponse);
  saveEpicSession(epicData);
  clearEpicAuthArtifacts();
  return epicData;
}

async function handleEpicCallbackPage({
  statusElementId = 'callback-status',
  debugElementId = 'debug',
  redirectTo = './index.html#chat'
} = {}) {
  const statusEl = document.getElementById(statusElementId);
  const debugEl = document.getElementById(debugElementId);
  const setStatus = (text) => {
    if (statusEl) statusEl.textContent = text;
  };

  const query = getQueryParams();
  if (query.error) {
    setStatus(`Epic returned an error: ${query.error}`);
    if (debugEl) debugEl.textContent = JSON.stringify(query, null, 2);
    return;
  }

  try {
    setStatus('Validating callback...');
    const session = await completeEpicOAuth(query);
    if (debugEl) debugEl.textContent = JSON.stringify(session.raw, null, 2);
    setStatus('Success. Redirecting to app...');
    setTimeout(() => {
      window.location.replace(redirectTo);
    }, 1200);
  } catch (error) {
    setStatus(error.message);
    if (debugEl) {
      debugEl.textContent = JSON.stringify(
        { query, message: error.message, stack: error.stack },
        null,
        2
      );
    }
  }
}
