function getBundleEntries(bundle) {
  return Array.isArray(bundle?.entry) ? bundle.entry.map((entry) => entry.resource).filter(Boolean) : [];
}

function adaptFhirPayload(rawPayload) {
  return {
    demographics: rawPayload?.patient || null,
    medications: getBundleEntries(rawPayload?.medications),
    conditions: getBundleEntries(rawPayload?.conditions),
    observations: getBundleEntries(rawPayload?.observations),
    documents: getBundleEntries(rawPayload?.documents),
    allergies: getBundleEntries(rawPayload?.allergies || null),
    appointments: getBundleEntries(rawPayload?.appointments || null)
  };
}

function adaptHl7Payload(rawPayload) {
  const rows = Array.isArray(rawPayload?.segments) ? rawPayload.segments : [];
  return {
    demographics: rawPayload?.patient || null,
    medications: rows.filter((s) => s.type === 'RX'),
    conditions: rows.filter((s) => s.type === 'DG1'),
    observations: rows.filter((s) => s.type === 'OBX'),
    documents: [],
    allergies: rows.filter((s) => s.type === 'AL1'),
    appointments: rows.filter((s) => s.type === 'SCH')
  };
}

function adaptCdaPayload(rawPayload) {
  return {
    demographics: rawPayload?.demographics || null,
    medications: rawPayload?.medications || [],
    conditions: rawPayload?.conditions || [],
    observations: rawPayload?.labs || [],
    documents: rawPayload?.documents || [],
    allergies: rawPayload?.allergies || [],
    appointments: rawPayload?.appointments || []
  };
}

function adaptRestPayload(rawPayload) {
  return {
    demographics: rawPayload?.patient || null,
    medications: rawPayload?.medications || [],
    conditions: rawPayload?.conditions || [],
    observations: rawPayload?.observations || [],
    documents: rawPayload?.documents || [],
    allergies: rawPayload?.allergies || [],
    appointments: rawPayload?.appointments || []
  };
}

function adaptCsvPayload(rawPayload) {
  return {
    demographics: rawPayload?.patient || null,
    medications: rawPayload?.medications || [],
    conditions: rawPayload?.conditions || [],
    observations: rawPayload?.observations || [],
    documents: rawPayload?.documents || [],
    allergies: rawPayload?.allergies || [],
    appointments: rawPayload?.appointments || []
  };
}

function adaptManualPayload(rawPayload) {
  return {
    demographics: rawPayload?.patient || null,
    medications: rawPayload?.medications || [],
    conditions: rawPayload?.conditions || [],
    observations: rawPayload?.observations || [],
    documents: rawPayload?.documents || [],
    allergies: rawPayload?.allergies || [],
    appointments: rawPayload?.appointments || []
  };
}

const ADAPTER_REGISTRY = Object.freeze({
  fhir: adaptFhirPayload,
  hl7: adaptHl7Payload,
  cda: adaptCdaPayload,
  rest: adaptRestPayload,
  csv: adaptCsvPayload,
  manual: adaptManualPayload
});

function adaptSourcePayload(sourceType, rawPayload) {
  const adapter = ADAPTER_REGISTRY[sourceType];
  if (!adapter) {
    throw new Error(`No adapter registered for source type "${sourceType}"`);
  }
  return adapter(rawPayload);
}
