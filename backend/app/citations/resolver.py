# app/citations/resolver.py
from dataclasses import dataclass
from app.models import PatientContext

@dataclass
class ResolvedCitation:
    id:            str
    resource_type: str
    display:       str
    fhir_id:       str
    field:         str
    value:         str
    verified_by:   str

def resolve_citations(
    raw: list[dict],
    ctx: PatientContext,
) -> list[ResolvedCitation]:
    resolved = []
    for c in raw:
        cid   = c.get('id','')
        rtype = c.get('resource_type','')
        item, field, value = _lookup(cid, rtype, ctx)
        if item:
            resolved.append(ResolvedCitation(
                id=cid, resource_type=rtype,
                display=value, fhir_id=str(id(item)),
                field=field, value=value,
                verified_by='clinician' if item.source == 'ehr' else 'patient_reported'
                if hasattr(item,'source') else 'clinician',
            ))
    return resolved

def _lookup(cid: str, rtype: str, ctx: PatientContext):
    try: idx = int(cid.split('-')[1]) - 1
    except: return None,'',''
    mapping = {
        'MedicationRequest': (ctx.medications,  lambda m: f'{m.name} {m.dose}'),
        'Condition':         (ctx.conditions,   lambda c: c.name),
        'DiagnosticReport':  (ctx.labs,         lambda l: f'{l.value} {l.unit}'),
        'Appointment':       (ctx.appointments, lambda a: f'{a.specialty} {a.date}'),
        'CarePlan':          (ctx.care_plan,    lambda p: p.instruction),
        'AllergyIntolerance':(ctx.allergies,    lambda a: a.substance),
    }
    if rtype not in mapping: return None,'',''
    items, getter = mapping[rtype]
    if idx >= len(items): return None,'',''
    item = items[idx]
    return item, rtype, getter(item)
