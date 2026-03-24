let selectedEhr = null;
const ehrNames = {
  epic: 'Epic MyChart',
  cerner: 'Cerner HealtheLife',
  veradigm: 'Veradigm',
  athena: 'athenahealth'
};

function selectEhr(id) {
  if (!ehrNames[id]) return;

  if (selectedEhr) {
    document.getElementById(`opt-${selectedEhr}`)?.classList.remove('selected');
  }

  selectedEhr = id;
  document.getElementById(`opt-${id}`)?.classList.add('selected');
  const sourceType = typeof getSourceTypeFromEhrId === 'function' ? getSourceTypeFromEhrId(id) : 'manual';
  sessionStorage.setItem('workflow_selected_source_type', sourceType);
  sessionStorage.setItem('workflow_selected_source_id', id);

  const btn = document.getElementById('ehr-continue-btn');
  if (btn) {
    btn.textContent = `Continue with ${ehrNames[id]}`;
    btn.classList.add('ready');
  }

  document.getElementById('redirect-info')?.classList.remove('show');
}

function filterEhr(query) {
  const q = query.toLowerCase().trim();
  Object.keys(ehrNames).forEach((id) => {
    const option = document.getElementById(`opt-${id}`);
    if (option) {
      option.style.display = !q || ehrNames[id].toLowerCase().includes(q) ? '' : 'none';
    }
  });
}

async function doRedirect() {
  if (!selectedEhr) return;

  const info = document.getElementById('redirect-info');
  const text = document.getElementById('redirect-text');
  info?.classList.add('show');
  if (text) text.textContent = `Preparing ${ehrNames[selectedEhr]} login...`;

  if (selectedEhr === 'epic') {
    try {
      await startEpicLogin();
    } catch (error) {
      if (text) text.textContent = error.message;
    }
    return;
  }

  if (typeof seedMockWorkflowForSource === 'function') {
    const sourceType = typeof getSourceTypeFromEhrId === 'function' ? getSourceTypeFromEhrId(selectedEhr) : 'manual';
    seedMockWorkflowForSource(sourceType, selectedEhr);
  }

  setTimeout(() => {
    if (text) text.textContent = `Redirecting to ${ehrNames[selectedEhr]}...`;
  }, 900);

  setTimeout(() => {
    goTo('screen-login');
  }, 2000);
}

function initEhrFlow() {
  document.getElementById('ehr-back-btn')?.addEventListener('click', () => {
    goTo('screen-welcome');
  });

  document.getElementById('ehr-search-input')?.addEventListener('input', (event) => {
    filterEhr(event.target.value);
  });

  document.querySelectorAll('.ehr-option[data-ehr-id]').forEach((option) => {
    option.addEventListener('click', () => {
      selectEhr(option.dataset.ehrId);
    });
  });

  document.getElementById('ehr-continue-btn')?.addEventListener('click', doRedirect);

  document.addEventListener('screen:change', (event) => {
    if (event.detail.id !== 'screen-ehr') return;
    document.getElementById('redirect-info')?.classList.remove('show');
    if (!selectedEhr) selectEhr('epic');
  });
}
