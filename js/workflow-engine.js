function saveLatestWorkflowSnapshot(snapshot) {
  sessionStorage.setItem('workflow_latest_snapshot', JSON.stringify(snapshot));
}

function loadLatestWorkflowSnapshot() {
  const raw = sessionStorage.getItem('workflow_latest_snapshot');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function emitWorkflowUpdated(detail) {
  document.dispatchEvent(new CustomEvent('workflow:updated', { detail }));
}

function runWorkflowPipeline({ sourceType, sourceId, patientId, rawPayload }) {
  if (!sourceType || !sourceId || !patientId) {
    throw new Error('Workflow pipeline requires sourceType, sourceId, and patientId.');
  }

  const cached = getWorkflowCache(patientId, sourceId);
  let context;
  let cacheHit = false;

  if (cached?.payload?.context) {
    context = cached.payload.context;
    cacheHit = true;
  } else {
    const adapted = adaptSourcePayload(sourceType, rawPayload);
    context = normalizePatientContext(adapted, { sourceType, sourceId, patientId });
    setWorkflowCache(patientId, sourceId, { context });
  }

  const prompt = buildSystemPromptFromContext(context);
  const snapshot = {
    updatedAt: new Date().toISOString(),
    sourceType,
    sourceId,
    patientId,
    cacheHit,
    context,
    prompt
  };

  saveLatestWorkflowSnapshot(snapshot);
  emitWorkflowUpdated(snapshot);
  return snapshot;
}

function syncWorkflowFromEpicSession(epicSession) {
  if (!epicSession?.raw || !epicSession?.patientId) return null;

  try {
    return runWorkflowPipeline({
      sourceType: 'fhir',
      sourceId: 'epic-smart',
      patientId: epicSession.patientId,
      rawPayload: epicSession.raw
    });
  } catch (error) {
    emitWorkflowUpdated({
      updatedAt: new Date().toISOString(),
      sourceType: 'fhir',
      sourceId: 'epic-smart',
      patientId: epicSession.patientId,
      error: error.message
    });
    return null;
  }
}
