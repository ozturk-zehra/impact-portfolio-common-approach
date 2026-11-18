"""
Export portfolio data as Common Impact Data Standard (CIDS) v3.2 JSON-LD.

Classes used (Basic and Essential tiers, plus ImpactRisk from the Full tier):
  cids:Organization, cids:Theme, cids:Code, cids:Outcome, cids:Indicator,
  cids:IndicatorReport, cids:Target, cids:Stakeholder, cids:StakeholderOutcome,
  cids:ImpactReport, cids:ImpactRisk subclasses (cids:EvidenceRisk, etc.)

Values use the ISO/IEC 21972 measurement pattern that CIDS imports:
  i72:value -> i72:Measure -> i72:numerical_value (string)

Notes
- Instance URIs use a placeholder base (https://example.org/...). Common Approach
  publishes a recommended URI format in its implementation guidance; a production
  export should follow it.
- This is an illustrative export for learning purposes. It has not been validated
  by Common Approach and does not claim CIDS alignment certification.
"""

from __future__ import annotations

import pandas as pd

BASE = "https://example.org/maple-ridge/"

CONTEXT = {
    "cids": "https://ontology.commonapproach.org/cids#",
    "i72": "http://ontology.eil.utoronto.ca/ISO21972/iso21972#",
    "org": "http://ontology.eil.utoronto.ca/tove/organization#",
    "prov": "http://www.w3.org/ns/prov#",
    "dqv": "http://www.w3.org/ns/dqv#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "prov:startedAtTime": {"@type": "xsd:dateTime"},
    "prov:endedAtTime": {"@type": "xsd:dateTime"},
}

SDG_URLS = {
    "T1": [("SDG 7", "https://sdgs.un.org/goals/goal7"), ("SDG 13", "https://sdgs.un.org/goals/goal13")],
    "T2": [("SDG target 11.1", "https://sdgs.un.org/goals/goal11")],
    "T3": [("SDG target 8.5", "https://sdgs.un.org/goals/goal8")],
    "T4": [("SDG target 2.1", "https://sdgs.un.org/goals/goal2")],
}

# Illustrative impact risks (Impact Management Norms risk types, as subclassed in CIDS)
RISKS = [
    ("RRS", "T1", "cids:EvidenceRisk", "medium", "moderate",
     "Energy savings are modelled from pre/post audits, not metered, and Q4 data is missing.",
     "Request metered utility data for a sample of homes and the Q4 report."),
    ("NTS", "T4", "cids:StakeholderParticipationRisk", "low", "moderate",
     "Program design could drift from community priorities if feedback loops weaken.",
     "Continue quarterly community advisory circle and report importance ratings."),
    ("LLC", "T3", "cids:DropOffRisk", "medium", "moderate",
     "Employment outcomes may not persist beyond the six-month follow-up.",
     "Add a 12-month follow-up survey."),
]


def uri(kind, key):
    return f"{BASE}{kind}/{key}"


def measure(value, unit):
    return {
        "@type": "i72:Measure",
        "i72:numerical_value": f"{value:g}" if isinstance(value, (int, float)) else str(value),
        "i72:unit_of_measure": {"@type": "i72:Unit_of_measure", "rdfs:label": unit},
    }


def dt(ts):
    return pd.Timestamp(ts).strftime("%Y-%m-%dT00:00:00")


def build_cids_graph(d, harmonized: pd.DataFrame, results: pd.DataFrame) -> dict:
    g = []
    pol = d["policy"]
    start, end = dt(pol["reporting_period_start"]), dt(pol["reporting_period_end"])
    themes = d["themes"].set_index("theme_id")
    stake = d["stakeholders"].set_index("stakeholder_id")
    reports = d["reports"].set_index("report_id")
    mapping = d["mapping"].drop_duplicates("report_id").set_index("report_id")

    # --- Themes and Codes -------------------------------------------------
    for tid, t in themes.iterrows():
        codes = []
        for name, url in SDG_URLS.get(tid, []):
            cid = uri("code", name.replace(" ", "-").replace(".", "-"))
            g.append({"@id": cid, "@type": "cids:Code", "cids:hasName": name,
                      "cids:hasSpecification": {"@id": url},
                      "cids:hasDescription": f"Alignment: {t.alignment_degree.lower()} (Common Framework 3.4.2)"})
            codes.append({"@id": cid})
        g.append({"@id": uri("theme", tid), "@type": "cids:Theme", "cids:hasName": t.theme,
                  "cids:hasDescription": t.description, "cids:hasCode": codes})

    # --- Stakeholders -----------------------------------------------------
    for sid, s in stake.iterrows():
        g.append({"@id": uri("stakeholder", sid), "@type": "cids:Stakeholder",
                  "cids:hasName": s.stakeholder, "cids:hasDescription": s.description})

    # --- Portfolio organizations: Outcomes, Indicators, IndicatorReports ---
    for _, org in d["holdings"].iterrows():
        hid = org.holding_id
        org_reports = reports[reports.holding_id == hid]
        outcome_ids, indicator_ids = set(), []

        for rid, r in org_reports.iterrows():
            m = mapping.loc[rid]
            ind_id, rep_id = uri("indicator", rid), uri("indicatorReport", rid)
            indicator_ids.append({"@id": ind_id})
            ind = {"@id": ind_id, "@type": "cids:Indicator", "cids:hasName": r.metric_as_reported,
                   "cids:hasDescription": r.investee_note, "cids:unitDescription": r.unit_as_reported,
                   "cids:forOrganization": {"@id": uri("organization", hid)},
                   "cids:definedBy": {"@id": uri("organization", hid)},
                   "cids:hasIndicatorReport": [{"@id": rep_id}]}
            if m.theme_id:
                oid = uri("outcome", f"{hid}-{m.theme_id}")
                outcome_ids.add(oid)
                ind["cids:forOutcome"] = [{"@id": oid}]
            g.append(ind)
            g.append({"@id": rep_id, "@type": "cids:IndicatorReport",
                      "cids:hasName": f"{r.metric_as_reported} ({r.period_start:%Y-%m-%d} to {r.period_end:%Y-%m-%d})",
                      "cids:forIndicator": {"@id": ind_id},
                      "cids:forOrganization": {"@id": uri("organization", hid)},
                      "i72:value": measure(float(r.value), r.unit_as_reported),
                      "prov:startedAtTime": dt(r.period_start), "prov:endedAtTime": dt(r.period_end),
                      "cids:hasComment": f"{r.report_type}; reporting layer: {r.reporting_layer}",
                      "dqv:hasQualityAnnotation": {"@type": "dqv:QualityAnnotation", "rdfs:comment": r.evidence_level}})

        # Outcomes, StakeholderOutcomes, ImpactReports (one per organization x theme)
        org_map = d["mapping"][d["mapping"].report_id.isin(org_reports.index) & (d["mapping"].theme_id != "")]
        for tid in sorted(org_map.theme_id.unique()):
            oid = uri("outcome", f"{hid}-{tid}")
            inds = [{"@id": uri("indicator", x)} for x in org_map[org_map.theme_id == tid].report_id.unique()]
            sids = sorted(set(org_map[org_map.theme_id == tid].stakeholder_id) - {""})
            so_ids, ir_id = [], uri("impactReport", f"{hid}-{tid}")
            for sid in sids:
                s = stake.loc[sid]
                so_id = uri("stakeholderOutcome", f"{hid}-{tid}-{sid}")
                so_ids.append({"@id": so_id})
                g.append({"@id": so_id, "@type": "cids:StakeholderOutcome",
                          "cids:hasName": f"{themes.loc[tid].theme}: {s.stakeholder}",
                          "cids:hasDescription": f"Importance assessed by: {s.from_perspective_of}",
                          "cids:forStakeholder": {"@id": uri("stakeholder", sid)},
                          "cids:forOutcome": {"@id": oid},
                          "cids:hasImportance": s.importance,
                          "cids:isUnderserved": str(s.is_underserved).lower() == "true",
                          "cids:hasIndicator": inds,
                          "cids:hasImpactReport": [{"@id": ir_id}]})
            risk_ids = []
            for (rh, rt, rtype, like, cons, desc, mitig) in RISKS:
                if rh == hid and rt == tid:
                    rk = uri("impactRisk", f"{hid}-{tid}")
                    risk_ids.append({"@id": rk})
                    g.append({"@id": rk, "@type": ["cids:ImpactRisk", rtype], "cids:hasDescription": desc,
                              "cids:hasLikelihood": like, "cids:hasConsequence": cons,
                              "cids:hasMitigation": mitig, "cids:forImpactReport": {"@id": ir_id}})
            ir = {"@id": ir_id, "@type": "cids:ImpactReport",
                  "cids:hasName": f"{org.organization}: {themes.loc[tid].theme} impact report 2025",
                  "cids:forOrganization": {"@id": uri("organization", hid)},
                  "cids:forOutcome": {"@id": oid},
                  "prov:startedAtTime": start, "prov:endedAtTime": end,
                  "cids:hasReportedImpact": "positive"}
            if risk_ids:
                ir["cids:hasImpactRisk"] = risk_ids
            g.append(ir)
            g.append({"@id": oid, "@type": "cids:Outcome",
                      "cids:hasName": f"{themes.loc[tid].theme} - {org.organization}",
                      "cids:hasDescription": themes.loc[tid].description,
                      "cids:forOrganization": {"@id": uri("organization", hid)},
                      "cids:forTheme": [{"@id": uri("theme", tid)}],
                      "cids:hasIndicator": inds,
                      "cids:hasStakeholderOutcome": so_ids,
                      "cids:hasImpactReport": [{"@id": ir_id}]})

        g.append({"@id": uri("organization", hid), "@type": "cids:Organization",
                  "cids:hasName": org.organization, "org:hasLegalName": org.legal_name,
                  "cids:hasDescription": f"{org.organization_type}; {org.sector}; {org.province}",
                  "cids:hasOutcome": [{"@id": o} for o in sorted(outcome_ids)],
                  "cids:hasIndicator": indicator_ids})

    # --- Portfolio-level headline indicators (the aggregator's view) ---------
    agg = uri("organization", "portfolio")
    hl_ids = []
    for _, h in results.iterrows():
        ind_id, rep_id, tgt_id = uri("indicator", h.headline_id), uri("indicatorReport", h.headline_id), uri("target", h.headline_id)
        hl_ids.append({"@id": ind_id})
        g.append({"@id": tgt_id, "@type": "cids:Target", "cids:hasName": f"2025 target: {h.headline_indicator}",
                  "i72:value": measure(float(h.target_value), h.common_unit),
                  "prov:startedAtTime": start, "prov:endedAtTime": end,
                  "cids:forIndicatorReport": [{"@id": rep_id}]})
        g.append({"@id": ind_id, "@type": "cids:Indicator", "cids:hasName": h.headline_indicator,
                  "cids:hasDescription": f"{h.description} Boundaries: {h.boundaries}",
                  "cids:unitDescription": h.common_unit,
                  "cids:definedBy": {"@id": agg}, "cids:forOrganization": {"@id": agg},
                  "cids:hasTarget": {"@id": tgt_id},
                  "cids:hasIndicatorReport": [{"@id": rep_id}]})
        g.append({"@id": rep_id, "@type": "cids:IndicatorReport",
                  "cids:hasName": f"{h.headline_indicator} - portfolio total 2025",
                  "cids:forIndicator": {"@id": ind_id}, "cids:forOrganization": {"@id": agg},
                  "cids:forTarget": {"@id": tgt_id},
                  "i72:value": measure(float(h.portfolio_total), h.common_unit),
                  "prov:startedAtTime": start, "prov:endedAtTime": end,
                  "cids:hasComment": (f"Aggregated with the Common Framework v1.0 from {int(h.n_metrics)} metrics across "
                                      f"{int(h.n_organizations)} organizations; overlap deduction {h.overlap_deduction:g}. "
                                      f"See outputs/audit_trail.csv."),
                  "dqv:hasQualityAnnotation": {"@type": "dqv:QualityAnnotation",
                                                "rdfs:comment": "Internal QA record: outputs/qa_checks.csv"}})
    g.append({"@id": agg, "@type": "cids:Organization", "cids:hasName": pol["portfolio_name"],
              "org:hasLegalName": pol["portfolio_name"],
              "cids:hasDescription": "Fictional portfolio aggregator used for this demonstration.",
              "cids:hasIndicator": hl_ids})

    return {"@context": CONTEXT, "@graph": g}
