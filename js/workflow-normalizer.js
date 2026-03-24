function toArray(value) {
  return Array.isArray(value) ? value : [];
}

function firstDefined(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return '';
}

function normalizeMedicationItem(item, index) {
  const name = firstDefined(
    item?.medicationCodeableConcept?.text,
    item?.medicationReference?.display,
    item?.name,
    `Medication ${index + 1}`
  );
  return {
    id: firstDefined(item?.id, `med-${index + 1}`),
    name,
    status: firstDefined(item?.status, 'unknown'),
    dosage: firstDefined(item?.dosageInstruction?.[0]?.text, item?.dosage, '')
  };
}

function normalizeConditionItem(item, index) {
  const display = firstDefined(item?.code?.text, item?.name, `Condition ${index + 1}`);
  return {
    id: firstDefined(item?.id, `cond-${index + 1}`),
    display,
    clinicalStatus: firstDefined(item?.clinicalStatus?.coding?.[0]?.code, item?.status, '')
  };
}

function normalizeObservationItem(item, index) {
  const label = firstDefined(item?.code?.text, item?.name, `Observation ${index + 1}`);
  const value = firstDefined(
    item?.valueQuantity?.value ? `${item.valueQuantity.value} ${item.valueQuantity.unit || ''}`.trim() : '',
    item?.valueString,
    item?.value,
    ''
  );
  return {
    id: firstDefined(item?.id, `obs-${index + 1}`),
    label,
    value,
    effectiveAt: firstDefined(item?.effectiveDateTime, item?.issued, item?.datetime, '')
  };
}

function normalizeDocumentItem(item, index) {
  const title = firstDefined(item?.type?.text, item?.description, item?.title, `Document ${index + 1}`);
  return {
    id: firstDefined(item?.id, `doc-${index + 1}`),
    title,
    date: firstDefined(item?.date, item?.created, '')
  };
}

function normalizeAllergyItem(item, index) {
  const display = firstDefined(item?.code?.text, item?.name, `Allergy ${index + 1}`);
  return {
    id: firstDefined(item?.id, `alg-${index + 1}`),
    display,
    criticality: firstDefined(item?.criticality, item?.severity, '')
  };
}

function normalizeAppointmentItem(item, index) {
  return {
    id: firstDefined(item?.id, `appt-${index + 1}`),
    description: firstDefined(item?.description, item?.serviceType?.[0]?.text, `Appointment ${index + 1}`),
    start: firstDefined(item?.start, item?.date, '')
  };
}

function normalizePatientContext(adaptedPayload, { sourceType, sourceId, patientId }) {
  return {
    source_type: sourceType,
    source_id: sourceId,
    patient_id: patientId,
    fetched_at: new Date().toISOString(),
    demographics: adaptedPayload?.demographics || null,
    medications: toArray(adaptedPayload?.medications).map(normalizeMedicationItem),
    conditions: toArray(adaptedPayload?.conditions).map(normalizeConditionItem),
    labs: toArray(adaptedPayload?.observations).map(normalizeObservationItem),
    documents: toArray(adaptedPayload?.documents).map(normalizeDocumentItem),
    allergies: toArray(adaptedPayload?.allergies).map(normalizeAllergyItem),
    appointments: toArray(adaptedPayload?.appointments).map(normalizeAppointmentItem),
    care_plan: toArray(adaptedPayload?.carePlan || [])
  };
}
