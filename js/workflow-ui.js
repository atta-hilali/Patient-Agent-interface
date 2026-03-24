function renderWorkflowSnapshot(snapshot) {
  const statusEl = document.getElementById('workflow-status');
  const ctxEl = document.getElementById('workflow-context-debug');
  const promptEl = document.getElementById('workflow-prompt-debug');

  if (statusEl) {
    if (snapshot?.error) {
      statusEl.textContent = `Workflow error: ${snapshot.error}`;
    } else if (snapshot) {
      statusEl.textContent = `Workflow ready · source=${snapshot.sourceType} · cache=${snapshot.cacheHit ? 'hit' : 'miss'}`;
    } else {
      statusEl.textContent = 'Workflow not initialized yet.';
    }
  }

  if (ctxEl) {
    ctxEl.textContent = snapshot?.context
      ? JSON.stringify(snapshot.context, null, 2)
      : 'No normalized context yet.';
  }

  if (promptEl) {
    promptEl.textContent = snapshot?.prompt || 'No system prompt yet.';
  }
}

function initWorkflowUi() {
  const existing = loadLatestWorkflowSnapshot();
  if (existing) {
    renderWorkflowSnapshot(existing);
  } else {
    const epicSession = loadEpicSession?.();
    if (epicSession) {
      const snapshot = syncWorkflowFromEpicSession(epicSession);
      renderWorkflowSnapshot(snapshot);
    } else {
      renderWorkflowSnapshot(null);
    }
  }

  document.addEventListener('workflow:updated', (event) => {
    renderWorkflowSnapshot(event.detail);
  });
}
