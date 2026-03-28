const CSV_FIELD_SPECS = Object.freeze([
  { key: 'patientId', label: 'Patient ID' },
  { key: 'patientName', label: 'Patient Name' },
  { key: 'birthDate', label: 'Birth Date' },
  { key: 'gender', label: 'Gender' },
  { key: 'medicationName', label: 'Medication Name' },
  { key: 'medicationStatus', label: 'Medication Status' },
  { key: 'medicationDosage', label: 'Medication Dosage' },
  { key: 'conditionName', label: 'Condition Name' },
  { key: 'conditionStatus', label: 'Condition Status' },
  { key: 'labName', label: 'Lab Name' },
  { key: 'labValue', label: 'Lab Value' },
  { key: 'labUnit', label: 'Lab Unit' },
  { key: 'allergySubstance', label: 'Allergy Substance' },
  { key: 'allergyReaction', label: 'Allergy Reaction' },
  { key: 'appointmentDescription', label: 'Appointment Description' },
  { key: 'appointmentStart', label: 'Appointment Start' },
  { key: 'documentTitle', label: 'Document Title' },
  { key: 'carePlanTitle', label: 'Care Plan Title' }
]);

const CSV_DEFAULT_SAMPLE = `patient_id,patient_name,birth_date,gender,medication,medication_status,medication_dosage,condition,lab_name,lab_value,lab_unit,allergy,appointment,appointment_start
P-1001,Sarah Connor,1980-05-12,female,Metformin,active,1000mg BID,Type 2 diabetes,HbA1c,7.1,%,Penicillin,Endocrinology follow-up,2026-04-12
P-1001,Sarah Connor,1980-05-12,female,Lisinopril,active,10mg daily,Hypertension,LDL,110,mg/dL,,Nutrition counseling,2026-04-20`;

function parseCsvLine(line) {
  const values = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      const nextChar = line[i + 1];
      if (inQuotes && nextChar === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === ',' && !inQuotes) {
      values.push(current.trim());
      current = '';
      continue;
    }

    current += char;
  }
  values.push(current.trim());
  return values;
}

function parseCsvText(csvText) {
  const lines = csvText
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length < 2) {
    throw new Error('CSV must include header row and at least one data row.');
  }

  const headers = parseCsvLine(lines[0]);
  const rows = lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] || '';
    });
    return row;
  });

  return { headers, rows };
}

function guessColumn(fieldKey, headers) {
  const lowerHeaders = headers.map((header) => header.toLowerCase());
  const aliases = {
    patientId: ['patient_id', 'patientid', 'pid', 'mrn'],
    patientName: ['patient_name', 'name', 'full_name'],
    birthDate: ['birth_date', 'dob'],
    gender: ['gender', 'sex'],
    medicationName: ['medication', 'medication_name', 'med_name'],
    medicationStatus: ['medication_status', 'med_status'],
    medicationDosage: ['medication_dosage', 'dosage'],
    conditionName: ['condition', 'condition_name', 'diagnosis'],
    conditionStatus: ['condition_status', 'diag_status'],
    labName: ['lab_name', 'test_name', 'observation'],
    labValue: ['lab_value', 'value', 'result'],
    labUnit: ['lab_unit', 'unit'],
    allergySubstance: ['allergy', 'allergy_substance'],
    allergyReaction: ['allergy_reaction', 'reaction'],
    appointmentDescription: ['appointment', 'appointment_description'],
    appointmentStart: ['appointment_start', 'appointment_date', 'start'],
    documentTitle: ['document_title', 'document'],
    carePlanTitle: ['care_plan_title', 'care_plan']
  };

  const candidates = aliases[fieldKey] || [];
  for (const alias of candidates) {
    const idx = lowerHeaders.indexOf(alias);
    if (idx >= 0) return headers[idx];
  }
  return '';
}

function getBackendBaseUrl() {
  return (window.EPIC_CONFIG?.backendBaseUrl || '').replace(/\/+$/, '');
}

async function postCsvToBackend({ csvText, mapping }) {
  const base = getBackendBaseUrl();
  if (!base) throw new Error('Missing backendBaseUrl in EPIC_CONFIG.');

  const payload = {
    sourceId: 'csv-upload',
    patientId: '',
    csvText,
    mapping,
    consentAccepted: true
  };

  const response = await fetch(`${base}/workflow/ingest/csv`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(body?.detail || text || `CSV ingest failed (${response.status}).`);
  }
  return body;
}

function initCsvMappingUi() {
  const screen = document.getElementById('screen-csv-map');
  if (!screen) return;

  const backBtn = document.getElementById('csv-back-btn');
  const fileInput = document.getElementById('csv-file-input');
  const loadSampleBtn = document.getElementById('csv-load-sample-btn');
  const importBtn = document.getElementById('csv-import-btn');
  const fileNameEl = document.getElementById('csv-file-name');
  const previewWrap = document.getElementById('csv-preview-wrap');
  const previewTable = document.getElementById('csv-preview-table');
  const mappingGrid = document.getElementById('csv-mapping-grid');
  const statusEl = document.getElementById('csv-status');

  let currentCsvText = '';
  let currentHeaders = [];

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function renderPreview(headers, rows) {
    if (!previewWrap || !previewTable) return;
    const previewRows = rows.slice(0, 5);
    const headerHtml = headers.map((header) => `<th>${header}</th>`).join('');
    const rowHtml = previewRows
      .map((row) => `<tr>${headers.map((header) => `<td>${row[header] || ''}</td>`).join('')}</tr>`)
      .join('');
    previewTable.innerHTML = `<thead><tr>${headerHtml}</tr></thead><tbody>${rowHtml}</tbody>`;
    previewWrap.style.display = '';
  }

  function renderMappings(headers) {
    if (!mappingGrid) return;
    mappingGrid.innerHTML = '';
    CSV_FIELD_SPECS.forEach((field) => {
      const wrap = document.createElement('div');
      wrap.className = 'csv-map-item';
      const label = document.createElement('label');
      label.textContent = field.label;
      const select = document.createElement('select');
      select.id = `csv-map-${field.key}`;
      const blankOption = document.createElement('option');
      blankOption.value = '';
      blankOption.textContent = '-- Not mapped --';
      select.appendChild(blankOption);
      headers.forEach((header) => {
        const option = document.createElement('option');
        option.value = header;
        option.textContent = header;
        select.appendChild(option);
      });
      select.value = guessColumn(field.key, headers);
      wrap.appendChild(label);
      wrap.appendChild(select);
      mappingGrid.appendChild(wrap);
    });
  }

  function collectMapping() {
    const mapping = {};
    CSV_FIELD_SPECS.forEach((field) => {
      const select = document.getElementById(`csv-map-${field.key}`);
      if (select?.value) mapping[field.key] = select.value;
    });
    return mapping;
  }

  function applyCsv(csvText, displayName) {
    try {
      const parsed = parseCsvText(csvText);
      currentCsvText = csvText;
      currentHeaders = parsed.headers;
      renderPreview(parsed.headers, parsed.rows);
      renderMappings(parsed.headers);
      if (fileNameEl) fileNameEl.textContent = `${displayName} · ${parsed.rows.length} row(s)`;
      if (importBtn) importBtn.disabled = false;
      setStatus('CSV loaded. Review mappings and import.');
    } catch (error) {
      currentCsvText = '';
      currentHeaders = [];
      if (importBtn) importBtn.disabled = true;
      setStatus(error.message || 'Unable to parse CSV.');
    }
  }

  fileInput?.addEventListener('change', async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    const text = await file.text();
    applyCsv(text, file.name);
    fileInput.value = '';
  });

  loadSampleBtn?.addEventListener('click', () => {
    applyCsv(CSV_DEFAULT_SAMPLE, 'sample.csv');
  });

  importBtn?.addEventListener('click', async () => {
    if (!currentCsvText || currentHeaders.length === 0) return;
    importBtn.disabled = true;
    setStatus('Importing CSV through backend workflow...');
    try {
      const snapshot = await postCsvToBackend({
        csvText: currentCsvText,
        mapping: collectMapping()
      });
      sessionStorage.setItem('workflow_latest_snapshot', JSON.stringify(snapshot));
      sessionStorage.setItem('workflow_selected_source_type', 'csv');
      sessionStorage.setItem('workflow_selected_source_id', 'csv-upload');
      document.dispatchEvent(new CustomEvent('workflow:updated', { detail: snapshot }));
      setStatus('CSV imported successfully. Opening chat.');
      goTo('screen-chat');
    } catch (error) {
      setStatus(error.message || 'CSV import failed.');
    } finally {
      importBtn.disabled = false;
    }
  });

  backBtn?.addEventListener('click', () => goTo('screen-ehr'));

  document.addEventListener('screen:change', (event) => {
    if (event.detail.id !== 'screen-csv-map') return;
    setStatus('Upload a CSV file or load a sample to start mapping.');
  });
}
