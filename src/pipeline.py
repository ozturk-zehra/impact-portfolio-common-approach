"""
Portfolio impact aggregation pipeline.

Applies the five steps of Common Approach's Common Framework (v1.0) to a
fictional multi-asset impact portfolio, then exports the results as
Common Impact Data Standard (CIDS v3.2) JSON-LD.

    Step 1  Group metrics by theme
    Step 2  Harmonize units (direct, fixed-value, derived-value, proxy-value)
    Step 3  Develop headline indicators (with boundaries and exclusions)
    Step 4  Aggregate and validate (trial aggregation, then final)
    Step 5  Document aggregation policies (audit trail, QA record, log)

All data in this repository is fictional. Run from the repo root:

    python src/pipeline.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from cids_export import build_cids_graph

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "reference"
OUT = ROOT / "outputs"
DASH = ROOT / "docs"

PEOPLE_UNITS = {"people"}


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load():
    d = {
        "holdings": pd.read_csv(RAW / "portfolio_holdings.csv"),
        "reports": pd.read_csv(RAW / "investee_reports.csv", parse_dates=["period_start", "period_end"]),
        "themes": pd.read_csv(REF / "themes.csv"),
        "headlines": pd.read_csv(REF / "headline_indicators.csv"),
        "factors": pd.read_csv(REF / "conversion_factors.csv"),
        "stakeholders": pd.read_csv(REF / "stakeholders.csv"),
        "mapping": pd.read_csv(REF / "metric_mapping.csv", dtype=str).fillna(""),
        "corrections": pd.read_csv(REF / "corrections.csv"),
        "overlaps": pd.read_csv(REF / "overlaps.csv"),
        "policy": json.loads((REF / "reporting_policy.json").read_text()),
    }
    return d


# ---------------------------------------------------------------------------
# Step 1: group metrics by theme (link every reported metric or log exclusion)
# ---------------------------------------------------------------------------
def step1_link(d):
    rep, mp = d["reports"], d["mapping"]
    linked = mp.merge(rep, on="report_id", how="left", validate="many_to_one")
    unmapped = sorted(set(rep.report_id) - set(mp.report_id))
    return linked, unmapped


# ---------------------------------------------------------------------------
# Step 2: harmonize units. Original values are never overwritten.
# ---------------------------------------------------------------------------
def _value_lookup(reports, corrections, apply_corrections):
    vals = reports.set_index("report_id")["value"].astype(float).to_dict()
    if apply_corrections:
        for _, c in corrections.iterrows():
            vals[c.report_id] = float(c.corrected_value)
    return vals


def step2_harmonize(linked, d, apply_corrections=True):
    vals = _value_lookup(d["reports"], d["corrections"], apply_corrections)
    factors = d["factors"].set_index("factor_id")
    hl_units = d["headlines"].set_index("headline_id")["common_unit"].to_dict()
    corrected_ids = set(d["corrections"].report_id) if apply_corrections else set()

    rows = []
    for _, r in linked.iterrows():
        out = r.to_dict()
        out["value_used"] = vals[r.report_id]
        out["correction_applied"] = r.report_id in corrected_ids
        out["common_unit"] = hl_units.get(r.headline_id, "")
        out["common_value"] = None
        out["formula"] = ""

        if r.headline_id and not r.exclusion_code:
            v = vals[r.report_id]
            formula = []
            # derived-value transformations combine two or more reported data points
            if r.derivation == "sum_x_rate":
                inputs = r.derive_inputs.split("|")
                base = sum(vals[i] for i in inputs)
                v = base * vals[r.report_id]
                formula.append(f"({' + '.join(inputs)}) x {r.report_id} = {base:g} x {vals[r.report_id]:g}")
            elif r.derivation == "count_x_pct":
                count = vals[r.derive_inputs]
                v = count * vals[r.report_id] / 100
                formula.append(f"{r.derive_inputs} x {r.report_id}% = {count:g} x {vals[r.report_id]:g}%")
            else:
                formula.append(f"{r.report_id} = {v:g}")
            if r.report_id in corrected_ids or (r.derive_inputs and set(r.derive_inputs.split("|")) & corrected_ids):
                formula.append("[uses corrected value; see corrections.csv]")
            # fixed-value or proxy-value factor
            if r.factor_id:
                f = factors.loc[r.factor_id]
                v = v * float(f.value)
                formula.append(f"x {f.value:g} ({r.factor_id}: {f.from_unit} to {f.to_unit})")
            # conservative rounding: whole people rounded down
            if out["common_unit"] in PEOPLE_UNITS:
                v = math.floor(v)
                formula.append("rounded down to whole people")
            else:
                v = round(v, 1)
            out["common_value"] = v
            out["formula"] = " ".join(formula)
        rows.append(out)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Step 3: headline indicators, boundaries and exclusions
# ---------------------------------------------------------------------------
def step3_boundaries(h, d):
    pol = d["policy"]
    start, end = pd.Timestamp(pol["reporting_period_start"]), pd.Timestamp(pol["reporting_period_end"])
    h = h.copy()
    h["in_window"] = (h.period_end >= start) & (h.period_end <= end) & (h.report_type == "actual")
    h["included"] = (h.headline_id != "") & (h.exclusion_code == "") & h.in_window
    exclusions = h[h.exclusion_code != ""][
        ["report_id", "holding_id", "metric_as_reported", "value", "unit_as_reported", "theme_id",
         "exclusion_code", "exclusion_rationale"]
    ].drop_duplicates("report_id")
    return h, exclusions


# ---------------------------------------------------------------------------
# Step 4: aggregate and validate
# ---------------------------------------------------------------------------
def aggregate(h, d, apply_overlaps=True):
    inc = h[h.included]
    tot = inc.groupby("headline_id")["common_value"].sum()
    ded = d["overlaps"].groupby("headline_id")["deduction"].sum() if apply_overlaps else pd.Series(dtype=float)
    res = d["headlines"].set_index("headline_id").copy()
    res["gross_total"] = tot.reindex(res.index).fillna(0)
    res["overlap_deduction"] = ded.reindex(res.index).fillna(0)
    res["portfolio_total"] = res.gross_total - res.overlap_deduction
    res["n_metrics"] = inc.groupby("headline_id").size().reindex(res.index).fillna(0).astype(int)
    res["n_organizations"] = inc.groupby("headline_id")["holding_id"].nunique().reindex(res.index).fillna(0).astype(int)
    res["change_vs_prior"] = (res.portfolio_total / res.prior_year_value - 1).round(3)
    res["pct_of_target"] = (res.portfolio_total / res.target_value).round(3)
    return res.reset_index()


def trial_aggregation(linked, d):
    """Trial run on uncorrected inputs, like a trial balance (Common Framework 4.1)."""
    h = step2_harmonize(linked, d, apply_corrections=False)
    h, _ = step3_boundaries(h, d)
    res = aggregate(h, d)
    thr = d["policy"]["trial_anomaly_ratio"]
    ratio = res.portfolio_total / res.prior_year_value
    res["trial_ratio_to_prior"] = ratio.round(2)
    res["trial_flag"] = ["ANOMALY: investigate before finalizing" if (x > thr or x < 1 / thr) else "ok" for x in ratio]
    return res[["headline_id", "headline_indicator", "common_unit", "portfolio_total", "prior_year_value",
                "trial_ratio_to_prior", "trial_flag"]]


def investor_share(h, d):
    """Secondary indicator (Common Framework 4.3): outcome x (outstanding / enterprise value).
    An allocation convention only. It is not evidence that the investor caused the outcome."""
    inc = h[h.included].merge(d["holdings"], on="holding_id")
    inc["ownership_share"] = inc.investment_outstanding_cad / inc.enterprise_value_cad
    # apply overlap deductions to the report they belong to before allocating
    ded = d["overlaps"].set_index(["headline_id", "report_id"])["deduction"]
    inc["net_value"] = [cv - ded.get((hid, rid), 0) for cv, hid, rid in zip(inc.common_value, inc.headline_id, inc.report_id)]
    inc["investor_share_value"] = (inc.net_value * inc.ownership_share).round(1)
    by_org = inc[["headline_id", "holding_id", "organization", "net_value", "ownership_share", "investor_share_value"]]
    by_hl = by_org.groupby("headline_id")["investor_share_value"].sum().round(1)
    return by_org, by_hl


def audit_trail(h, d, calc_date, version):
    inc = h[h.included].merge(d["holdings"][["holding_id", "organization"]], on="holding_id")
    ded = d["overlaps"].set_index(["headline_id", "report_id"])["deduction"]
    inc["overlap_deduction"] = [ded.get((a, b), 0) for a, b in zip(inc.headline_id, inc.report_id)]
    inc["net_contribution"] = inc.common_value - inc.overlap_deduction
    inc["calculated_on"] = calc_date
    inc["methodology_version"] = version
    cols = ["headline_id", "report_id", "organization", "metric_as_reported", "value", "unit_as_reported",
            "value_used", "correction_applied", "harmonization_type", "factor_id", "formula", "common_value",
            "common_unit", "overlap_deduction", "net_contribution", "evidence_level", "confidence",
            "pathway_stage", "calculated_on", "methodology_version"]
    return inc[cols].sort_values(["headline_id", "report_id"])


def qa_checks(h, d, results, trail, unmapped, trial):
    pol = d["policy"]
    checks = []

    def add(area, check, status, detail):
        checks.append({"area": area, "check": check, "status": status, "detail": detail})

    add("Completeness", "Every reported metric is linked to a headline or logged as excluded",
        "pass" if not unmapped else "fail", f"Unmapped: {unmapped}" if unmapped else f"{d['reports'].shape[0]} of {d['reports'].shape[0]} metrics accounted for")

    excluded_ids = set(h[h.exclusion_code != ""].report_id)
    leaked = excluded_ids & set(trail.report_id)
    add("Inclusion/exclusion integrity", "Excluded metrics do not appear in any total",
        "pass" if not leaked else "fail", "No leakage" if not leaked else f"Leaked: {sorted(leaked)}")

    fund_rows = set(h[(h.reporting_layer == "fund total") & h.included].report_id)
    add("Inclusion/exclusion integrity", "Fund-level totals are not counted alongside investee-level data",
        "pass" if not fund_rows else "fail", "Investee layer used for the intermediary fund" if not fund_rows else str(fund_rows))

    applied = all(((trail.headline_id == o.headline_id) & (trail.report_id == o.report_id) &
                   (trail.overlap_deduction == o.deduction)).any() for _, o in d["overlaps"].iterrows())
    add("Double counting", "Documented overlap deductions are applied", "pass" if applied else "fail",
        "; ".join(f"{o.adjustment_id}: -{o.deduction} {o.headline_id}" for _, o in d["overlaps"].iterrows()))

    mixed = trail.groupby("headline_id")["common_unit"].nunique()
    add("Internal consistency", "Each headline uses a single common unit", "pass" if (mixed <= 1).all() else "fail",
        "No mixed units")

    start, end = pd.Timestamp(pol["reporting_period_start"]), pd.Timestamp(pol["reporting_period_end"])
    out_win = h[h.included & ~h.period_end.between(start, end)]
    add("Boundaries", "Only data within the reporting window is aggregated", "pass" if out_win.empty else "fail",
        f"Window {pol['reporting_period_start']} to {pol['reporting_period_end']}")

    people = trail[trail.common_unit == "people"]
    add("Assumptions", "People counts are whole numbers (conservative rounding)",
        "pass" if (people.common_value % 1 == 0).all() else "fail", "Rounded down")

    rec = d["reports"].set_index("report_id")
    diff = rec.loc["R017", "value"] - rec.loc["R018", "value"]
    add("Reconciliation", "Intermediary fund total reconciles to investee-level detail",
        "warn" if diff else "pass", f"Fund total exceeds investee detail by {diff:g} jobs. Request explanation (possible mid-year exits).")

    rrs_q = h[(h.holding_id == "RRS") & h.metric_as_reported.str.startswith("Homes retrofitted")]
    add("Coverage", "Quarterly reporters have complete coverage of the period",
        "warn" if len(rrs_q) < 4 else "pass", f"Riverbend submitted {len(rrs_q)} of 4 quarters. Not annualized. H1/H2 understate full-year results.")

    illus = d["factors"][d["factors"].source.str.contains("ILLUSTRATIVE")]
    used = set(trail.factor_id.dropna()) - {""}
    illus_used = sorted(set(illus.factor_id) & used)
    add("Conversion logic", "Proxy factors are sourced and documented",
        "warn" if illus_used else "pass", f"Placeholder factor(s) in use: {illus_used}. Replace before external use." if illus_used else "All sourced")

    flagged = trial[trial.trial_flag != "ok"]
    corrected = set(d["corrections"].report_id)
    thr_a = pol["trial_anomaly_ratio"]
    unresolved = []
    for hl in flagged.headline_id:
        contributors = set(trail[trail.headline_id == hl].report_id)
        final_ratio = float(results.set_index("headline_id").loc[hl, "portfolio_total"] /
                            results.set_index("headline_id").loc[hl, "prior_year_value"])
        if not (contributors & corrected) or not (1 / thr_a <= final_ratio <= thr_a):
            unresolved.append(hl)
    add("Trial aggregation", "Anomalies from the trial run are resolved before finalizing",
        "pass" if not unresolved else "fail",
        f"Trial flagged {', '.join(flagged.headline_id) or 'none'}; traced to and resolved by documented correction(s) "
        f"{', '.join(sorted(corrected))}" if not unresolved else f"Unresolved: {unresolved}")

    thr = pol["reasonableness_threshold"]
    outside = results[(results.change_vs_prior.abs() > thr)]
    add("External reasonableness", f"Results within +/-{int(thr*100)}% of prior year",
        "pass" if outside.empty else "warn",
        "All within range" if outside.empty else f"Review: {', '.join(outside.headline_id)}")

    # peer replication: recompute independently from the audit trail
    rep = trail.groupby("headline_id")["net_contribution"].sum().round(1)
    official = results.set_index("headline_id")["portfolio_total"].round(1)
    ok = (rep.reindex(official.index).fillna(0) == official).all()
    add("Peer replication", "Totals recomputed independently from the audit trail match", "pass" if ok else "fail",
        "Independent groupby matches final totals")

    return pd.DataFrame(checks)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
def export_workbook(path, sheets):
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
            ws = xw.sheets[name[:31]]
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
            ws.freeze_panes = "A2"


def main():
    OUT.mkdir(exist_ok=True)
    d = load()
    pol = d["policy"]

    linked, unmapped = step1_link(d)
    trial = trial_aggregation(linked, d)                      # Step 4.1 trial run
    h = step2_harmonize(linked, d, apply_corrections=True)    # Step 2
    h, exclusions = step3_boundaries(h, d)                    # Step 3
    results = aggregate(h, d)                                 # Step 4.2
    by_org, inv_hl = investor_share(h, d)                     # Step 4.3 (secondary)
    results["investor_share_total"] = results.headline_id.map(inv_hl).fillna(0)
    trail = audit_trail(h, d, pol["calculated_on"], pol["methodology_version"])
    qa = qa_checks(h, d, results, trail, unmapped, trial)    # Step 5.4

    harmonized = h.drop(columns=["derive_inputs"])
    files = {
        "harmonized_metrics.csv": harmonized,
        "exclusions.csv": exclusions,
        "trial_aggregation_review.csv": trial,
        "headline_results.csv": results,
        "audit_trail.csv": trail,
        "investor_share_by_organization.csv": by_org,
        "qa_checks.csv": qa,
    }
    for name, df in files.items():
        df.to_csv(OUT / name, index=False)

    export_workbook(OUT / "portfolio_aggregation_workbook.xlsx", {
        "Headline results": results,
        "Audit trail": trail,
        "Exclusions": exclusions,
        "QA checks": qa,
        "Trial aggregation": trial,
        "Investor share": by_org,
        "Harmonized metrics": harmonized,
        "Raw reports": d["reports"],
        "Holdings": d["holdings"],
        "Themes": d["themes"],
        "Conversion factors": d["factors"],
        "Overlaps": d["overlaps"],
        "Corrections": d["corrections"],
    })

    graph = build_cids_graph(d, h, results)
    (OUT / "cids_portfolio.jsonld").write_text(json.dumps(graph, indent=2))

    # dashboard data
    dash = {
        "portfolio": pol["portfolio_name"],
        "period": f"{pol['reporting_period_start']} to {pol['reporting_period_end']}",
        "calculated_on": pol["calculated_on"],
        "themes": d["themes"].to_dict("records"),
        "headlines": json.loads(results.to_json(orient="records")),
        "contributions": json.loads(trail.to_json(orient="records")),
        "investor_share": json.loads(by_org.to_json(orient="records")),
        "exclusions": json.loads(exclusions.to_json(orient="records")),
        "qa": qa.to_dict("records"),
        "trial": json.loads(trial.to_json(orient="records")),
        "holdings": d["holdings"].to_dict("records"),
    }
    DASH.mkdir(exist_ok=True)
    (DASH / "data.js").write_text("window.PORTFOLIO_DATA = " + json.dumps(dash, indent=1) + ";\n")

    # console summary
    print(f"\n{pol['portfolio_name']}  |  {dash['period']}\n")
    print(results[["headline_id", "headline_indicator", "portfolio_total", "common_unit",
                   "investor_share_total", "prior_year_value", "target_value"]].to_string(index=False))
    print("\nQA:", qa.status.value_counts().to_dict())
    print(f"Outputs written to {OUT.relative_to(ROOT)}/ and {DASH.relative_to(ROOT)}/data.js")
    return results, qa


if __name__ == "__main__":
    main()
