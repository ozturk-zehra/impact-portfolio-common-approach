# Aggregation policy (Common Framework Step 5)

Portfolio: Maple Ridge Impact Portfolio (fictional) · Reporting period: 1 January to 31 December 2025 · Methodology version 1.0

This document records the rules applied in `src/pipeline.py`. It follows the structure of Common Framework Step 5: evidence base, coding rules, exclusion rules, aggregation logic, a methodology log, and the QA process.

## 5.1 Evidence base

| Item | File |
|---|---|
| Theme definitions and inclusion criteria | `data/reference/themes.csv` |
| Metric-to-theme and metric-to-headline links, with confidence | `data/reference/metric_mapping.csv` |
| Conversion factors and sources | `data/reference/conversion_factors.csv` |
| Headline indicator definitions, boundaries, external alignment | `data/reference/headline_indicators.csv` |
| Data corrections confirmed with investees | `data/reference/corrections.csv` |
| Overlap deductions | `data/reference/overlaps.csv` |
| Time boundary and thresholds | `data/reference/reporting_policy.json` |

## 5.2.1 Coding and linkage rules

1. A metric links to a theme when it meets that theme's written inclusion criterion. Otherwise it is left unassigned and excluded as `IMMATERIAL`.
2. A metric may feed more than one headline only when each headline measures a different construct in a different unit. The rule is applied once: Riverbend's energy saved feeds H2 (MWh) and H1 (tCO2e). This is allowed because Riverbend does not report tCO2e itself.
3. Each link has a confidence rating (High, Medium, Low). Low is used where a placeholder proxy is involved.
4. When a portfolio organization supplies its own theme link, it is kept unless it conflicts with an inclusion criterion. Any override is recorded in `analyst_note`. (No overrides were needed this cycle.)

## 5.2.2 Exclusion rules

| Code | Rule | Example |
|---|---|---|
| `OUT_OF_WINDOW` | Forecasts and periods ending outside the reporting window are excluded | Cedar 2026 forecast |
| `NON_CONVERTIBLE` | No defensible path to a common unit | Events hosted with no attendance data |
| `RATIO_NO_COUNTS` | Ratios without a numerator and denominator are kept as context only | Rent as % of market |
| `BOUNDARY` | Falls outside a headline boundary | Temporary construction jobs; one-time food hampers |
| `FUND_LAYER` | Intermediary fund totals are excluded when investee-level data exists | Greenway fund total |
| `ACTIVITY_DUPLICATE` | The outcome-level metric is kept and the activity-level duplicate excluded | Training hours |
| `INPUT_TO_DERIVED` | Used only as an input to a derived value | Quarterly homes retrofitted |
| `CONTEXTUAL` | Stakeholder characteristics, reported as context | % participants self-identifying as Indigenous |
| `IMMATERIAL` | Does not measure any portfolio theme | Co-op member-owners |

## 5.2.3 Aggregation logic

**Harmonization.** Use direct equivalence first, then fixed-value conversions, then derived-value transformations from reported inputs, and only then proxy values. Source values are never overwritten. Every harmonized row records its type, formula and factor.

**Rounding.** People counts are rounded down to whole people. Other units are rounded to one decimal place.

**Time boundary.** Include actual results for the calendar year, or the most recent 12-month period ending within it (for example, a fiscal year ending 31 March 2025). Partial periods are not annualized. Missing quarters are logged as a coverage warning.

**Combining.** Harmonized values within a headline are summed, then documented overlap deductions are subtracted. No weighting is applied to headline totals.

**Secondary indicator.** Investor share = net contribution × (investment outstanding ÷ enterprise value or equivalent basis, recorded per holding). It is always labelled as an allocation convention and never replaces the headline total.

**Ambiguous cases.** When a metric fits several headlines, it goes to the one whose construct and unit match most closely. Anything involving a new proxy or an override of an investee's own mapping goes to a second reviewer.

## 5.3 Methodology log

See `docs/methodology_log.md`.

## 5.4 Internal QA process

The checks run automatically and are written to `outputs/qa_checks.csv`:

- **Completeness:** every metric is linked or excluded
- **Inclusion/exclusion integrity:** no excluded metric appears in a total; no fund-level totals alongside investee data
- **Double counting:** documented overlap deductions are applied
- **Internal consistency:** one common unit per headline
- **Boundaries:** only in-window actuals are aggregated
- **Assumptions:** conservative rounding is applied
- **Reconciliation:** fund total compared with investee-level detail
- **Coverage:** quarterly reporters submitted all quarters
- **Conversion logic:** proxy sources documented; placeholders flagged
- **Trial aggregation:** anomalies traced and resolved before finalizing
- **External reasonableness:** results within ±50% of the prior year
- **Peer replication:** totals recomputed independently from the audit trail
