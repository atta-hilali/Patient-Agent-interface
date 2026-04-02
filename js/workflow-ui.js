function renderWorkflowSnapshot(snapshot) {
  const statusEl = document.getElementById('workflow-status');
  const ctxEl = document.getElementById('workflow-context-debug');
  const promptEl = document.getElementById('workflow-prompt-debug');
  const updateChip = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = text;
  };

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

  if (snapshot?.context) {
    const ctx = snapshot.context;
    updateChip('chip-meds', `<span class="ctx-chip-dot" style="background:var(--green)"></span>${(ctx.medications || []).length} meds`);
    updateChip('chip-conditions', `<span class="ctx-chip-dot" style="background:#1D4ED8"></span>${(ctx.conditions || []).length} conditions`);
    updateChip('chip-labs', `<span class="ctx-chip-dot" style="background:#7C3AED"></span>${(ctx.labs || []).length} labs`);
    updateChip('chip-docs', `<span class="ctx-chip-dot" style="background:var(--teal)"></span>${(ctx.documents || []).length} documents`);
    updateChip('chip-allergy', `<span class="ctx-chip-dot" style="background:var(--red)"></span>${(ctx.allergies || []).length} allergies`);
    updateChip('chip-appointments', `<span class="ctx-chip-dot" style="background:var(--amber)"></span>${(ctx.appointments || []).length} appointments`);
    const header = document.getElementById('chat-header-status');
    if (header) {
      const source = snapshot.sourceType || ctx.sourceType || 'unknown';
      const patient = snapshot.patientId || ctx.patientId || 'n/a';
      header.innerHTML = `<div class="online-dot"></div>Workflow ready · ${source} · patient ${patient}`;
    }
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
