const WORKFLOW_CACHE_TTL_MS = 5 * 60 * 1000;

function makeWorkflowCacheKey(patientId, sourceId) {
  return `workflow_context:${sourceId}:${patientId}`;
}

function getWorkflowCache(patientId, sourceId) {
  const key = makeWorkflowCacheKey(patientId, sourceId);
  const raw = sessionStorage.getItem(key);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw);
    const age = Date.now() - parsed.cachedAt;
    if (age > WORKFLOW_CACHE_TTL_MS) {
      sessionStorage.removeItem(key);
      return null;
    }
    return parsed;
  } catch {
    sessionStorage.removeItem(key);
    return null;
  }
}

function setWorkflowCache(patientId, sourceId, payload) {
  const key = makeWorkflowCacheKey(patientId, sourceId);
  const value = {
    cachedAt: Date.now(),
    patientId,
    sourceId,
    payload
  };
  sessionStorage.setItem(key, JSON.stringify(value));
  return value;
}
