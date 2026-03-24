function buildSystemPromptFromContext(context) {
  if (!context) return '';

  const header = [
    'You are Veldooc assistant.',
    'Use grounded answers only from provided PatientContext.',
    'If data is missing, say so explicitly.'
  ].join(' ');

  const counts = [
    `medications=${context.medications.length}`,
    `conditions=${context.conditions.length}`,
    `labs=${context.labs.length}`,
    `allergies=${context.allergies.length}`,
    `appointments=${context.appointments.length}`,
    `documents=${context.documents.length}`
  ].join(', ');

  const provenance = `source_type=${context.source_type}; source_id=${context.source_id}; fetched_at=${context.fetched_at}`;

  return [
    header,
    `PatientContext summary: ${counts}.`,
    `Provenance: ${provenance}.`,
    'Safety rules: never fabricate medications/allergies/labs; flag conflicts; recommend clinician follow-up for urgent findings.',
    'Citation rule: cite item ids when available from context arrays.'
  ].join('\n');
}
