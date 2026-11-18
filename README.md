# Portfolio impact aggregation with the Common Framework and CIDS

A worked example of rolling up diverse, bottom-up impact metrics from a multi-asset portfolio into portfolio-level headline indicators, using Common Approach's **Common Framework (v1.0)**, and exporting the results as **Common Impact Data Standard (CIDS v3.2)** JSON-LD.

> **All data is fictional.** The six portfolio organizations, their figures, and the portfolio itself were invented to exercise the method. One conversion factor (F2) is a labelled placeholder. This is an independent learning project and is not affiliated with or endorsed by Common Approach.

**Live dashboard:** https://ozturk-zehra.github.io/impact-portfolio-common-approach/

---

## The problem this demonstrates

Impact investors receive metrics from investees in different units, periods and levels of evidence. Some metrics describe the same activity twice, some come from an intermediary fund that also reports its own totals, some are forecasts, and some are ratios with no counts behind them. Adding them up naively overstates impact.

The Common Framework's answer is a documented, reproducible process modelled on financial reporting principles. This repository implements that process end to end on a small fictional portfolio:

| Holding (fictional) | Asset class | Reports |
|---|---|---|
| Cedar Solar Co-op | Private debt | MWh generated **and** tCO2e avoided for the same arrays, plus a 2026 forecast |
| Harbourview Housing Society | Community bond | Households housed (March fiscal year-end), a rent ratio, temporary construction jobs |
| Riverbend Retrofit Social Enterprise | Private debt | Quarterly homes retrofitted (Q4 missing), energy saved per home, **with a unit error** |
| Northern Table Social Enterprise | Private equity | FT/PT jobs, weekly food-box recipients, events, one-time hampers |
| Greenway Community Loan Fund | Fund LP interest | A fund-level jobs total **and** investee-level detail that **includes Northern Table** |
| Lakeshore Learning Collective | Community bond | Training completers, % employed, training hours, participant characteristics |

## Results (fictional, 2025)

| Headline indicator | Portfolio total | Investor share* | Prior year | Target |
|---|---:|---:|---:|---:|
| tCO2e of greenhouse gas emissions avoided | 1,837.1 | 212.1 | 1,350 | 1,700 |
| MWh of clean energy generated or saved | 5,482.5 | 627.0 | 4,900 | 5,800 |
| People living in affordable housing | 816 | 68.0 | 700 | 850 |
| Jobs created or sustained | 404 | 50.5 | 380 | 450 |
| People who gained employment after training | 150 | 18.8 | 140 | 160 |
| People with recurring access to nutritious food | 1,150 | 143.8 | 1,000 | 1,200 |

\*Investor share = outcome × (investment outstanding ÷ enterprise value). This is an allocation convention for analysis (Common Framework 4.3). It is not evidence that the investor caused or contributed to the outcome.

QA record: 10 checks pass, 3 warnings logged for follow-up, 0 failures.

## How each Common Framework step is implemented

| Step | What the pipeline does | Where to look |
|---|---|---|
| **1. Group metrics by theme** | Links all 22 reported metrics to four themes with written inclusion criteria and confidence ratings, or logs an exclusion reason. A completeness check confirms nothing is unaccounted for. | `data/reference/themes.csv`, `metric_mapping.csv` |
| **2. Harmonize units** | Applies all four harmonization types without overwriting source values: direct equivalence, fixed-value conversion (kWh → MWh), derived-value transformation (quarters × savings per home; completers × % employed), and proxy-value transformation (households → people; MWh → tCO2e). People counts are rounded down. Ratios without counts are kept as context. | `src/pipeline.py` `step2_harmonize`, `conversion_factors.csv` |
| **3. Develop headline indicators** | Six headline indicators with explicit boundaries (time window, ongoing vs temporary jobs, recurring vs one-time food support, outcome vs activity level) and external references recorded as exact, partial or conceptual. | `headline_indicators.csv`, `outputs/exclusions.csv` |
| **4. Aggregate and validate** | Runs a **trial aggregation** first. It flags H1 and H2 at more than 250× the prior year, traced to a kWh/MWh unit error that is fixed through a documented correction. It then finalizes with a fund-layer exclusion, a cross-holding overlap deduction (−23 jobs), reasonableness checks against the prior year, and an independent recomputation from the audit trail. | `trial_aggregation_review.csv`, `corrections.csv`, `overlaps.csv` |
| **5. Document aggregation policies** | An aggregation policy manual, a methodology log, an audit trail for every headline value, and a QA record. | `docs/aggregation_policy.md`, `docs/methodology_log.md`, `outputs/audit_trail.csv`, `outputs/qa_checks.csv` |

Double-counting traps the data is built to catch:

- **Same activity, two units.** Cedar's MWh is reported in H2 only. It is not converted to tCO2e because Cedar already reports tCO2e for the same arrays (Common Framework 2.3.2).
- **Fund-of-funds layering.** Greenway's fund-level total (410 jobs) is excluded in favour of its investee-level detail (404). The 6-job gap is logged as a reconciliation warning.
- **Cross-holdings.** Greenway's investee list includes Northern Table, which is also a direct holding, so 23 jobs are deducted.
- **Activity vs outcome.** Lakeshore's training hours are excluded because the outcome metric (people employed) describes the same program.

## CIDS export

`outputs/cids_portfolio.jsonld` represents each portfolio organization's data and the portfolio's headline indicators using CIDS classes from the Basic and Essential tiers (`Organization`, `Theme`, `Code`, `Outcome`, `Indicator`, `IndicatorReport`, `Target`, `Stakeholder`, `StakeholderOutcome`, `ImpactReport`), plus `ImpactRisk` subclasses from the Full tier. Values follow the ISO/IEC 21972 measurement pattern (`i72:value` → `i72:Measure` → `i72:numerical_value`), and evidence levels are recorded as `dqv:hasQualityAnnotation`.

`src/validate_cids.py` checks link integrity and that each class uses only the properties listed for it in the CIDS v3.2.1 class reference. It is a consistency check, not an official alignment test. See `docs/cids_mapping.md` for the field-by-field mapping.

## Run it

```bash
pip install -r requirements.txt
python src/pipeline.py          # writes outputs/ and docs/data.js
python src/validate_cids.py     # structural check of the JSON-LD
python tests/test_pipeline.py   # or: python -m pytest -q
```

Open `docs/index.html` in a browser to view the dashboard locally. `outputs/portfolio_aggregation_workbook.xlsx` contains every table and loads directly into Power BI or Excel.

## Repository layout

```
data/raw/            Investee reports and holdings, exactly as "received"
data/reference/      Analyst work: themes, mapping, factors, corrections, overlaps, policy
src/pipeline.py      Common Framework steps 1-5
src/cids_export.py   CIDS v3.2 JSON-LD export
src/validate_cids.py Structural validator for the export
outputs/             Results, audit trail, QA record, workbook, JSON-LD
docs/                Dashboard (GitHub Pages), aggregation policy, CIDS mapping, methodology log
tests/               Checks for the key methodological rules
```

## Limitations

- The portfolio is small, so most headline indicators rest on one to three metrics. The Common Framework suggests three to five metrics per headline in small portfolios.
- F2 (grid emission factor) is a placeholder. A real application would use the provincial factor for the reporting year from Canada's National Inventory Report.
- Instance URIs use a placeholder base. Common Approach publishes a recommended URI format in its implementation guidance.
- Theme assignments were coded by one analyst. The Common Framework recommends a second coder and an inter-coder reliability check for real portfolios.

## Sources

- Common Approach to Impact Measurement (2026). *The Common Framework: Aggregating diverse impact data, Version 1.0.* CC BY-SA 4.0.
- Common Approach to Impact Measurement (2025). *Common Impact Data Standard, Revision 3.2.1.* https://ontology.commonapproach.org/cids/3.2.1. CC BY-SA 4.0.
- Statistics Canada, 2021 Census of Population (average household size).

## License

Code: MIT. Text describing the Common Framework and CIDS paraphrases material licensed CC BY-SA 4.0 by Common Approach to Impact Measurement.
