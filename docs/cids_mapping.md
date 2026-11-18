# CIDS mapping

How each piece of portfolio data is represented in `outputs/cids_portfolio.jsonld`, using the Common Impact Data Standard v3.2.1. Property names come from the CIDS class reference.

| Source data | CIDS class | Key properties used | Tier |
|---|---|---|---|
| Holding (`portfolio_holdings.csv`) | `cids:Organization` | `hasName`, `org:hasLegalName`, `hasDescription`, `hasOutcome`, `hasIndicator` | Basic |
| Theme (`themes.csv`) | `cids:Theme` | `hasName`, `hasDescription`, `hasCode` | Basic |
| SDG reference for a theme | `cids:Code` | `hasName`, `hasSpecification`, `hasDescription` (alignment degree) | Basic |
| Organization × theme | `cids:Outcome` | `hasName`, `hasDescription`, `forOrganization`, `forTheme`, `hasIndicator`, `hasStakeholderOutcome`, `hasImpactReport` | Basic / Essential |
| Each reported metric | `cids:Indicator` | `hasName`, `hasDescription`, `unitDescription` (unit exactly as reported), `forOrganization`, `definedBy`, `forOutcome`, `hasIndicatorReport` | Basic |
| Each reported value | `cids:IndicatorReport` | `hasName`, `i72:value` → `i72:Measure`, `prov:startedAtTime`, `prov:endedAtTime`, `forIndicator`, `forOrganization`, `hasComment`, `dqv:hasQualityAnnotation` (evidence level) | Basic |
| Stakeholder (`stakeholders.csv`) | `cids:Stakeholder` | `hasName`, `hasDescription` | Essential |
| Outcome × stakeholder | `cids:StakeholderOutcome` | `forStakeholder`, `forOutcome`, `hasImportance`, `isUnderserved`, `hasIndicator`, `hasImpactReport` | Essential |
| Organization × theme report | `cids:ImpactReport` | `forOrganization`, `forOutcome`, `prov:startedAtTime`, `prov:endedAtTime`, `hasReportedImpact`, `hasImpactRisk` | Essential |
| Risk notes | `cids:ImpactRisk` + subclass (`EvidenceRisk`, `StakeholderParticipationRisk`, `DropOffRisk`) | `forImpactReport`, `hasLikelihood`, `hasConsequence`, `hasMitigation`, `hasDescription` | Full |
| Headline indicator | `cids:Indicator` (defined by the portfolio aggregator) | `definedBy`, `forOrganization`, `hasTarget`, `hasIndicatorReport` | Basic / Essential |
| Headline total | `cids:IndicatorReport` | `i72:value`, `forTarget`, `hasComment` (method and audit trail pointer) | Basic / Essential |
| Headline target | `cids:Target` | `hasName`, `i72:value`, `prov:startedAtTime`, `prov:endedAtTime`, `forIndicatorReport` | Essential |

## Design choices

- **Bottom-up data is exported as reported.** Excluded metrics still appear as `Indicator` and `IndicatorReport` nodes because they are the investee's data. Exclusion is the aggregator's decision, and it lives in the audit trail, not in the investee's record.
- **Two layers.** Portfolio organizations define their own indicators (`definedBy` the organization). Headline indicators are defined by the aggregator. This mirrors the Common Framework's split between bottom-up metrics and headline indicators.
- **Units.** The investee's original unit string goes in `cids:unitDescription`, the property CIDS v3.2 added for capturing a user's original input. The measure also carries `i72:unit_of_measure`.
- **Importance perspective.** `fromPerspectiveOf` expects a linked stakeholder or organization. Because the assessors here are not modelled as nodes, the perspective is recorded in the `StakeholderOutcome` description instead.

## Not yet represented

`Program`, `Service`, `Activity`, `Input`, `Output`, `ImpactScale`, `ImpactDepth`, `ImpactDuration`, `Counterfactual`, `CharacteristicReport` (for Lakeshore's participant self-identification), and Common Approach's recommended URI format.
