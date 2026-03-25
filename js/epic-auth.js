const STATE_KEY = 'epic_state';
const CODE_VERIFIER_KEY = 'epic_code_verifier';
const AUTH_TRANSPORT_KEY = 'epic_auth_transport';

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
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
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
  localStorage.removeItem(STATE_KEY);
  localStorage.removeItem(CODE_VERIFIER_KEY);
  localStorage.removeItem(AUTH_TRANSPORT_KEY);
}

function getAuthMode() {
  return EPIC_CONFIG?.authMode || 'browser';
}

function getBackendBaseUrl() {
  return (EPIC_CONFIG?.backendBaseUrl || '').replace(/\/+$/, '');
}

async function fetchJsonWithTimeout(url, options = {}, timeoutMs = 6000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    const text = await res.text();
    let json = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = null;
    }
    if (!res.ok) {
      const detail = json?.detail || text || `HTTP ${res.status}`;
      throw new Error(detail);
    }
    return json;
  } finally {
    clearTimeout(id);
  }
}

async function startEpicLoginViaBackend() {
  const base = getBackendBaseUrl();
  if (!base) throw new Error('EPIC_CONFIG.backendBaseUrl is missing.');
  const response = await fetchJsonWithTimeout(`${base}/auth/epic/start?format=json`, {
    method: 'GET',
    credentials: 'omit'
  });
  const authorizeUrl = response?.authorize_url;
  if (!authorizeUrl) throw new Error('Backend did not return authorize_url.');
  localStorage.setItem(AUTH_TRANSPORT_KEY, 'backend');
  window.location.href = authorizeUrl;
}

async function startEpicLoginBrowser() {
  if (!EPIC_CONFIG || !EPIC_CONFIG.clientId || EPIC_CONFIG.clientId.includes('YOUR_NON_PRD')) {
    throw new Error('Set EPIC_CONFIG.clientId with your Epic Non-Production Client ID first.');
  }

  const state = randomString(32);
  const codeVerifier = randomString(64);
  const codeChallenge = await sha256Base64Url(codeVerifier);

  localStorage.setItem(STATE_KEY, state);
  localStorage.setItem(CODE_VERIFIER_KEY, codeVerifier);
  localStorage.setItem(AUTH_TRANSPORT_KEY, 'browser');

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

async function startEpicLogin() {
  const mode = getAuthMode();
  if (mode === 'backend') {
    await startEpicLoginViaBackend();
    return;
  }

  if (mode === 'hybrid') {
    try {
      await startEpicLoginViaBackend();
      return;
    } catch {
      // Fallback to known working browser path.
    }
  }

  await startEpicLoginBrowser();
}

async function exchangeCodeForToken(code) {
  const codeVerifier = localStorage.getItem(CODE_VERIFIER_KEY);
  if (!codeVerifier) throw new Error('Missing code_verifier in localStorage.');

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

  const [patient, conditions, observations, medications, documents, allergies, appointments] =
    await Promise.all([
      fetchFhirJson(accessToken, `Patient/${encodeURIComponent(patientId)}`),
      tryFetchFhirJson(accessToken, `Condition?patient=${encodeURIComponent(patientId)}&_count=20`),
      tryFetchFhirJson(accessToken, `Observation?patient=${encodeURIComponent(patientId)}&_count=20`),
      tryFetchFhirJson(accessToken, `MedicationRequest?patient=${encodeURIComponent(patientId)}&_count=20`),
      tryFetchFhirJson(accessToken, `DocumentReference?patient=${encodeURIComponent(patientId)}&_count=20`),
      tryFetchFhirJson(accessToken, `AllergyIntolerance?patient=${encodeURIComponent(patientId)}&_count=20`),
      tryFetchFhirJson(accessToken, `Appointment?patient=${encodeURIComponent(patientId)}&_count=20`)
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
      documents,
      allergies,
      appointments
    }
  };
}

async function completeEpicOAuthViaBackend(query) {
  const base = getBackendBaseUrl();
  if (!base) throw new Error('EPIC_CONFIG.backendBaseUrl is missing.');

  const url =
    `${base}/auth/epic/callback?` +
    `code=${encodeURIComponent(query.code || '')}&` +
    `state=${encodeURIComponent(query.state || '')}`;

  const payload = await fetchJsonWithTimeout(url, { method: 'GET', credentials: 'omit' }, 18000);
  if (!payload?.session) throw new Error('Backend callback response is missing session data.');

  saveEpicSession(payload.session);
  if (payload.workflow) {
    sessionStorage.setItem('workflow_latest_snapshot', JSON.stringify(payload.workflow));
    document.dispatchEvent(new CustomEvent('workflow:updated', { detail: payload.workflow }));
  }
  clearEpicAuthArtifacts();
  return payload.session;
}

async function completeEpicOAuthBrowser(query) {
  const storedState = localStorage.getItem(STATE_KEY);
  if (!query.code) throw new Error('Missing authorization code in callback URL.');
  if (!query.state || query.state !== storedState) {
    // If state mismatch but we are configured for backend, fall back to backend flow
    if (getAuthMode() === 'backend') {
      return completeEpicOAuthViaBackend(query);
    }
    throw new Error('State validation failed.');
  }

  const tokenResponse = await exchangeCodeForToken(query.code);
  const epicData = await fetchEpicPatientData(tokenResponse);
  saveEpicSession(epicData);
  clearEpicAuthArtifacts();
  return epicData;
}

async function completeEpicOAuth(query) {
  const mode = getAuthMode();
  const transport = localStorage.getItem(AUTH_TRANSPORT_KEY);
  const looksSignedState = typeof query.state === 'string' && query.state.includes('.') && query.state.length > 40;

  if (transport === 'backend' || looksSignedState || mode === 'backend') {
    return completeEpicOAuthViaBackend(query);
  }

  if (transport === 'browser' || mode === 'browser') {
    return completeEpicOAuthBrowser(query);
  }

  // Hybrid fallback behavior: try backend first, then browser if backend not used.
  try {
    return await completeEpicOAuthViaBackend(query);
  } catch {
    return completeEpicOAuthBrowser(query);
  }
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
    if (debugEl) debugEl.textContent = JSON.stringify(session.raw || session, null, 2);
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
