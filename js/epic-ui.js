function countBundleEntries(bundle) {
  return Array.isArray(bundle?.entry) ? bundle.entry.length : 0;
}

function updateText(id, text) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = text;
}

function appendEpicWelcomeMessage(session) {
  const messages = document.getElementById('messages');
  if (!messages) return;
  if (messages.querySelector('[data-epic-welcome="true"]')) return;

  const group = document.createElement('div');
  group.className = 'msg-group agent';
  group.setAttribute('data-epic-welcome', 'true');
  group.innerHTML = `
    <div class="msg-sender">Veldooc</div>
    <div class="bubble agent">
      Epic connection is active for <strong>${session.patientName || 'your patient'}</strong>.
      OAuth succeeded, token was issued, and FHIR data was fetched successfully.
    </div>
    <div class="msg-source"><span class="msg-source-icon">⊙</span> OAuth2 · SMART on FHIR · Epic Sandbox</div>
  `;
  messages.appendChild(group);
  messages.scrollTop = messages.scrollHeight;
}

function renderEpicSession(session) {
  if (!session || !session.raw) return;

  const patient = session.raw.patient || {};
  const conditions = session.raw.conditions || {};
  const observations = session.raw.observations || {};
  const medications = session.raw.medications || {};
  const documents = session.raw.documents || {};

  updateText('chat-header-status', `<div class="online-dot"></div>Connected · ${session.patientName || 'Epic patient loaded'}`);
  updateText('chip-meds', `<span class="ctx-chip-dot" style="background:var(--green)"></span>${countBundleEntries(medications)} meds`);
  updateText('chip-conditions', `<span class="ctx-chip-dot" style="background:#1D4ED8"></span>${countBundleEntries(conditions)} conditions`);
  updateText('chip-labs', `<span class="ctx-chip-dot" style="background:#7C3AED"></span>${countBundleEntries(observations)} labs`);
  updateText('chip-docs', `<span class="ctx-chip-dot" style="background:var(--teal)"></span>${countBundleEntries(documents)} documents`);
  updateText('chip-allergy', `<span class="ctx-chip-dot" style="background:var(--red)"></span>Allergy data`);
  updateText('chip-appointments', `<span class="ctx-chip-dot" style="background:var(--amber)"></span>patient ${session.patientId || 'n/a'}`);

  const debugEl = document.getElementById('epic-debug');
  if (debugEl) debugEl.textContent = JSON.stringify(session.raw, null, 2);
  const panel = document.getElementById('epic-debug-panel');
  if (panel) panel.open = true;

  appendEpicWelcomeMessage(session);
}

function initEpicUi() {
  const existing = loadEpicSession();
  if (existing) renderEpicSession(existing);

  document.addEventListener('epic:session-updated', (event) => {
    renderEpicSession(event.detail);
  });
}
