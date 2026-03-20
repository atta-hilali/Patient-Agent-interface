function initLoadingFlow() {
  const fhirItems = document.getElementById('fhir-items');
  if (!fhirItems) return;

  const initialMarkup = fhirItems.innerHTML;
  let loadingRun = 0;

  function resetLoadingRows() {
    fhirItems.innerHTML = initialMarkup;
  }

  function playLoadingSequence() {
    loadingRun += 1;
    const runId = loadingRun;

    setTimeout(() => {
      if (runId !== loadingRun) return;

      const rows = fhirItems.querySelectorAll('.fhir-row.loading');
      rows.forEach((row, i) => {
        setTimeout(() => {
          if (runId !== loadingRun) return;
          row.classList.remove('loading');
          row.classList.add('done');
          const status = row.querySelector('.fhir-row-status');
          const name = row.querySelector('.fhir-row-name')?.textContent || '';
          if (status) status.textContent = name === 'Appointments' ? '2 loaded ✓' : '1 loaded ✓';
          row.querySelector('.fhir-row-spinner')?.remove();
        }, i * 600);
      });

      setTimeout(() => {
        if (runId !== loadingRun) return;
        goTo('screen-chat');
      }, 2400);
    }, 800);
  }

  document.addEventListener('screen:change', (event) => {
    if (event.detail.id !== 'screen-loading') return;
    resetLoadingRows();
    playLoadingSequence();
  });
}
