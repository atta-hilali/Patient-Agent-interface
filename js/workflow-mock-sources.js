const EHR_SOURCE_TYPE_MAP = Object.freeze({
  epic: 'fhir',
  cerner: 'fhir',
  veradigm: 'rest',
  athena: 'cda'
});

function getSourceTypeFromEhrId(ehrId) {
  return EHR_SOURCE_TYPE_MAP[ehrId] || 'manual';
}

function buildMockRawPayload(sourceType) {
  if (sourceType === 'hl7') {
    return {
      patient: { id: 'hl7-001', name: [{ given: ['Avery'], family: 'Mills' }] },
      segments: [
        { type: 'DG1', id: 'dg1-1', name: 'Hypertension', status: 'active' },
        { type: 'OBX', id: 'obx-1', name: 'HbA1c', value: '7.0', datetime: new Date().toISOString() },
        { type: 'RX', id: 'rx-1', name: 'Lisinopril 10mg', dosage: 'daily', status: 'active' }
      ]
    };
  }

  if (sourceType === 'cda') {
    return {
      demographics: { id: 'cda-001', display: 'Jordan Lee' },
      medications: [{ id: 'med-1', name: 'Metformin 1000mg', status: 'active', dosage: 'BID' }],
      conditions: [{ id: 'cond-1', name: 'Type 2 diabetes', status: 'active' }],
      labs: [{ id: 'lab-1', name: 'HbA1c', value: '7.2', datetime: new Date().toISOString() }],
      documents: [{ id: 'doc-1', title: 'CCD Summary', date: new Date().toISOString() }]
    };
  }

  if (sourceType === 'rest' || sourceType === 'csv' || sourceType === 'manual') {
    return {
      patient: { id: `${sourceType}-001`, display: 'Taylor Parker' },
      medications: [{ id: 'med-1', name: 'Atorvastatin 20mg', status: 'active', dosage: 'nightly' }],
      conditions: [{ id: 'cond-1', name: 'Hyperlipidemia', status: 'active' }],
      observations: [{ id: 'obs-1', name: 'LDL', value: '110 mg/dL', datetime: new Date().toISOString() }],
      documents: [{ id: 'doc-1', title: 'Imported Clinic Note', date: new Date().toISOString() }]
    };
  }

  return {
    patient: { id: 'fhir-mock-001', name: [{ given: ['Sam'], family: 'Reed' }] },
    medications: { entry: [] },
    conditions: { entry: [] },
    observations: { entry: [] },
    documents: { entry: [] }
  };
}

function seedMockWorkflowForSource(sourceType, sourceId) {
  if (typeof runWorkflowPipeline !== 'function') return null;

  const rawPayload = buildMockRawPayload(sourceType);
  const patientId =
    rawPayload?.patient?.id ||
    rawPayload?.demographics?.id ||
    `${sourceType}-mock-patient`;

  return runWorkflowPipeline({
    sourceType,
    sourceId: sourceId || `${sourceType}-mock`,
    patientId,
    rawPayload
  });
}
