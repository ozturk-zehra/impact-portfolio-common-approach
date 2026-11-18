"""
Lightweight structural validator for the CIDS JSON-LD export.

Checks
  1. Every node has an @id and @type.
  2. Every referenced @id resolves to a node in the graph (link integrity).
  3. Each CIDS class only uses properties documented for that class in the
     Common Impact Data Standard v3.2.1 class reference.
  4. Minimum fields used by this project for Basic/Essential tier classes are present.

This is not an official Common Approach validator. It checks consistency with
the published class reference, not formal OWL conformance.

    python src/validate_cids.py outputs/cids_portfolio.jsonld
"""

from __future__ import annotations

import json
import sys

# Properties per class, transcribed from the CIDS v3.2.1 class reference (Section 4.1).
ALLOWED = {
    "cids:Organization": {"cids:hasName", "org:hasLegalName", "cids:hasDescription", "cids:hasOutcome",
                          "cids:hasIndicator", "cids:hasProgram", "cids:hasStakeholder", "cids:hasCharacteristic",
                          "cids:hasContact", "cids:hasWebAddress", "cids:hasPurpose", "cids:hasAddress", "org:hasID"},
    "cids:Theme": {"cids:hasCode", "cids:hasName", "cids:hasDescription", "cids:relatesTo"},
    "cids:Code": {"cids:definedBy", "cids:hasSpecification", "cids:hasIdentifier", "cids:hasName",
                  "cids:hasDescription", "schema:codeValue", "i72:value"},
    "cids:Outcome": {"cids:hasCode", "cids:hasStakeholderOutcome", "cids:forTheme", "cids:hasIndicator",
                     "cids:canEnable", "cids:canProduce", "i72:located_in", "oep:partOf", "cids:hasName",
                     "cids:hasDescription", "cids:hasImpactReport", "cids:forOrganization"},
    "cids:Indicator": {"cids:definedBy", "cids:forOutcome", "cids:forOrganization", "cids:usesOutput",
                       "cids:hasBaseline", "cids:hasThreshold", "cids:hasTarget", "cids:unitDescription",
                       "cids:describesPopulation", "i72:unit_of_measure", "prov:wasGeneratedBy", "dcat:dataset",
                       "cids:hasIndicatorReport", "cids:hasAccess", "cids:hasCode", "cids:hasIdentifier",
                       "cids:hasName", "cids:hasDescription", "cids:hasCounterfactual", "cids:hasHowMuch"},
    "cids:IndicatorReport": {"cids:forOrganization", "cids:forIndicator", "i72:value", "i72:unit_of_measure",
                             "cids:forTarget", "prov:wasGeneratedBy", "dcat:dataset", "prov:startedAtTime",
                             "prov:endedAtTime", "dqv:hasQualityAnnotation", "dqv:conformsTo",
                             "dqv:hasQualityMeasurement", "cids:forStakeholder", "cids:hasAccess", "cids:hasName",
                             "cids:hasComment"},
    "cids:Target": {"cids:hasName", "i72:value", "i72:unit_of_measure", "prov:startedAtTime", "prov:endedAtTime",
                    "cids:hasComment", "cids:forIndicatorReport"},
    "cids:Stakeholder": {"cids:hasName", "cids:hasDescription", "cids:hasCatchmentArea", "cids:hasCharacteristic",
                         "cids:performs", "i72:located_in", "oep:partOf", "cids:forOrganization"},
    "cids:StakeholderOutcome": {"cids:hasName", "cids:hasDescription", "cids:hasCode", "cids:forStakeholder",
                                "cids:forOutcome", "cids:fromPerspectiveOf", "cids:hasImportance",
                                "cids:isUnderserved", "cids:intendedImpact", "cids:hasIndicator",
                                "cids:hasImpactReport"},
    "cids:ImpactReport": {"cids:forOrganization", "prov:startedAtTime", "prov:endedAtTime", "cids:forOutcome",
                          "cids:hasName", "cids:hasReportedImpact", "cids:hasImpactScale", "cids:hasImpactDepth",
                          "cids:hasImpactDuration", "cids:hasExpectation", "cids:hasImpactRisk", "cids:hasComment"},
    "cids:ImpactRisk": {"cids:forImpactReport", "cids:hasLikelihood", "cids:hasConsequence", "cids:hasMitigation",
                        "cids:hasIdentifier", "cids:hasDescription"},
}

# Minimum fields this project populates (based on the Basic/Essential tier tables).
REQUIRED = {
    "cids:Organization": {"cids:hasName", "org:hasLegalName", "cids:hasIndicator"},
    "cids:Theme": {"cids:hasName", "cids:hasDescription"},
    "cids:Outcome": {"cids:hasName", "cids:hasDescription", "cids:forOrganization", "cids:forTheme", "cids:hasIndicator"},
    "cids:Indicator": {"cids:hasName", "cids:hasDescription", "cids:forOrganization", "cids:hasIndicatorReport"},
    "cids:IndicatorReport": {"cids:hasName", "i72:value", "prov:startedAtTime", "prov:endedAtTime", "cids:forIndicator"},
    "cids:Target": {"cids:hasName", "i72:value", "prov:startedAtTime", "prov:endedAtTime"},
    "cids:StakeholderOutcome": {"cids:forStakeholder", "cids:forOutcome", "cids:hasImportance", "cids:isUnderserved"},
    "cids:ImpactReport": {"cids:forOrganization", "cids:forOutcome", "prov:startedAtTime", "prov:endedAtTime"},
    "cids:ImpactRisk": {"cids:forImpactReport", "cids:hasDescription"},
}

RISK_SUBCLASSES = {"cids:AlignmentRisk", "cids:DropOffRisk", "cids:EfficiencyRisk", "cids:EnduranceRisk",
                   "cids:EvidenceRisk", "cids:ExecutionRisk", "cids:ExternalRisk",
                   "cids:StakeholderParticipationRisk", "cids:UnexpectedImpactRisk"}


def _refs(value):
    if isinstance(value, dict):
        if set(value) == {"@id"}:
            yield value["@id"]
        else:
            for v in value.values():
                yield from _refs(v)
    elif isinstance(value, list):
        for v in value:
            yield from _refs(v)


def validate(doc: dict) -> list[str]:
    errors = []
    nodes = doc.get("@graph", [])
    ids = {n.get("@id") for n in nodes}
    for n in nodes:
        nid, types = n.get("@id"), n.get("@type")
        if not nid or not types:
            errors.append(f"Node missing @id or @type: {n}")
            continue
        types = types if isinstance(types, list) else [types]
        for t in types:
            if t in RISK_SUBCLASSES:
                continue
            if t not in ALLOWED:
                errors.append(f"{nid}: unexpected class {t}")
                continue
            props = {k for k in n if not k.startswith("@")}
            for p in props - ALLOWED[t]:
                errors.append(f"{nid}: property {p} is not documented for {t}")
            for p in REQUIRED.get(t, set()) - props:
                errors.append(f"{nid}: missing {p} for {t}")
        for k, v in n.items():
            if k.startswith("@") or k == "cids:hasSpecification":
                continue  # hasSpecification points to an external URI
            for ref in _refs(v):
                if ref.startswith("https://example.org/") and ref not in ids:
                    errors.append(f"{nid}: {k} points to missing node {ref}")
    return errors


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "outputs/cids_portfolio.jsonld"
    doc = json.load(open(path))
    errs = validate(doc)
    counts = {}
    for n in doc["@graph"]:
        for t in (n["@type"] if isinstance(n["@type"], list) else [n["@type"]]):
            counts[t] = counts.get(t, 0) + 1
    print("Nodes by class:", dict(sorted(counts.items())))
    if errs:
        print(f"{len(errs)} problem(s):")
        print("\n".join(errs))
        sys.exit(1)
    print("CIDS structural validation passed.")
