from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any


NS = {"cda": "urn:hl7-org:v3"}

DEFAULT_XPATH_MAP = {
    "patientId": ".//cda:recordTarget/cda:patientRole/cda:id",
    "patientName": ".//cda:recordTarget/cda:patientRole/cda:patient/cda:name",
    "birthDate": ".//cda:recordTarget/cda:patientRole/cda:patient/cda:birthTime",
    "gender": ".//cda:recordTarget/cda:patientRole/cda:patient/cda:administrativeGenderCode",
    "medications": ".//cda:section[cda:code[@code='10160-0']]//cda:entry",
    "conditions": ".//cda:section[cda:code[@code='11450-4']]//cda:entry",
    "allergies": ".//cda:section[cda:code[@code='48765-2']]//cda:entry",
    "labs": ".//cda:section[cda:code[@code='30954-2']]//cda:entry",
    "appointments": ".//cda:section[cda:code[@code='46240-8']]//cda:entry",
    "documents": ".//cda:section[cda:code[@code='55107-7']]//cda:entry",
    "carePlan": ".//cda:section[cda:code[@code='18776-5']]//cda:entry",
}

SECTION_LOINC_CODES = {
    "medications": "10160-0",
    "conditions": "11450-4",
    "allergies": "48765-2",
    "labs": "30954-2",
    "appointments": "46240-8",
    "documents": "55107-7",
    "carePlan": "18776-5",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_match(root: ET.Element, xpath_expr: str) -> ET.Element | None:
    try:
        return root.find(xpath_expr, namespaces=NS)
    except Exception:  # noqa: BLE001
        return None


def _all_matches(root: ET.Element, xpath_expr: str) -> list[ET.Element]:
    try:
        return root.findall(xpath_expr, namespaces=NS)
    except Exception:  # noqa: BLE001
        return []


def _entries_from_section_code(root: ET.Element, loinc_code: str) -> list[ET.Element]:
    entries: list[ET.Element] = []
    sections = root.findall(".//cda:section", namespaces=NS)
    for section in sections:
        code_node = section.find("cda:code", namespaces=NS)
        code_value = _attr(code_node, "code")
        if code_value != loinc_code:
            continue
        entries.extend(section.findall(".//cda:entry", namespaces=NS))
    return entries


def _attr(element: ET.Element | None, key: str) -> str:
    if element is None:
        return ""
    return element.attrib.get(key, "")


def _element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    parts = [part.strip() for part in element.itertext() if part and part.strip()]
    return " ".join(parts).strip()


def _entry_id(entry: ET.Element, fallback: str) -> str:
    node = entry.find(".//cda:id", namespaces=NS)
    return _attr(node, "extension") or _attr(node, "root") or fallback


def _entry_name(entry: ET.Element, fallback: str) -> str:
    code = entry.find(".//cda:code", namespaces=NS)
    if code is not None:
        name = _attr(code, "displayName") or _attr(code, "code")
        if name:
            return name
    text_node = entry.find(".//cda:text", namespaces=NS)
    text = _element_text(text_node)
    if text:
        return text
    return fallback


def _patient_name(node: ET.Element | None) -> str:
    if node is None:
        return "Unknown Patient"
    given = _element_text(node.find("cda:given", namespaces=NS))
    family = _element_text(node.find("cda:family", namespaces=NS))
    merged = f"{given} {family}".strip()
    return merged or _element_text(node) or "Unknown Patient"


def parse_cda_xml(cda_xml: str, *, xpath_map: dict[str, str] | None = None) -> dict[str, Any]:
    if not cda_xml.strip():
        raise ValueError("CDA XML payload is empty.")

    try:
        root = ET.fromstring(cda_xml)
    except ET.ParseError as exc:
        raise ValueError(f"CDA XML is invalid: {exc}") from exc

    xpaths = dict(DEFAULT_XPATH_MAP)
    if xpath_map:
        xpaths.update({key: value for key, value in xpath_map.items() if value})
    overridden = set(xpath_map.keys()) if xpath_map else set()

    patient_id_node = _first_match(root, xpaths["patientId"])
    patient_name_node = _first_match(root, xpaths["patientName"])
    birth_node = _first_match(root, xpaths["birthDate"])
    gender_node = _first_match(root, xpaths["gender"])

    patient = {
        "id": _attr(patient_id_node, "extension") or _attr(patient_id_node, "root") or "cda-patient",
        "name": _patient_name(patient_name_node),
        "birthDate": _attr(birth_node, "value") or _element_text(birth_node),
        "gender": _attr(gender_node, "code") or _attr(gender_node, "displayName") or _element_text(gender_node),
    }

    def entries_for_key(xpath_key: str) -> list[ET.Element]:
        if xpath_key in overridden:
            return _all_matches(root, xpaths[xpath_key])
        loinc = SECTION_LOINC_CODES.get(xpath_key)
        if not loinc:
            return _all_matches(root, xpaths[xpath_key])
        return _entries_from_section_code(root, loinc)

    def entries_to_items(xpath_key: str, *, id_prefix: str, field_name: str) -> list[dict[str, Any]]:
        entries = entries_for_key(xpath_key)
        output: list[dict[str, Any]] = []
        for idx, entry in enumerate(entries, start=1):
            output.append(
                {
                    "id": _entry_id(entry, f"{id_prefix}-{idx}"),
                    field_name: _entry_name(entry, f"{field_name.title()} {idx}"),
                }
            )
        return output

    lab_entries = entries_for_key("labs")
    labs = entries_to_items("labs", id_prefix="lab", field_name="name")
    for idx, item in enumerate(labs, start=1):
        entry = lab_entries[idx - 1]
        value_node = entry.find(".//cda:value", namespaces=NS)
        item["value"] = _attr(value_node, "value") or _element_text(value_node)
        item["unit"] = _attr(value_node, "unit")
        item["effectiveDate"] = _attr(entry.find(".//cda:effectiveTime", namespaces=NS), "value")

    medications = entries_to_items("medications", id_prefix="med", field_name="name")
    conditions = entries_to_items("conditions", id_prefix="cond", field_name="name")
    allergies = entries_to_items("allergies", id_prefix="alg", field_name="substance")
    appointments = entries_to_items("appointments", id_prefix="appt", field_name="description")
    documents = entries_to_items("documents", id_prefix="doc", field_name="title")
    care_plan = entries_to_items("carePlan", id_prefix="cp", field_name="title")

    return {
        "patient": patient,
        "medications": medications,
        "conditions": conditions,
        "observations": labs,
        "allergies": allergies,
        "appointments": appointments,
        "documents": documents,
        "carePlan": care_plan,
        "xpathMapApplied": xpaths,
        "parsedAt": _now_iso(),
    }
