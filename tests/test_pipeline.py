"""Run with:  python -m pytest -q   (or)   python tests/test_pipeline.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pipeline  # noqa: E402
from validate_cids import validate  # noqa: E402

RESULTS, QA = pipeline.main()
TOTALS = RESULTS.set_index("headline_id")["portfolio_total"]


def test_no_failed_qa_checks():
    assert (QA.status != "fail").all(), QA[QA.status == "fail"]


def test_fund_layer_not_double_counted():
    # GCL investee-level 404 jobs minus 23 overlapping NTS jobs, plus NTS 14 FT + 9 PT
    assert TOTALS["H4"] == 404 - 23 + 14 + 9


def test_mwh_not_converted_when_tco2e_reported():
    trail = pipeline.pd.read_csv(ROOT / "outputs" / "audit_trail.csv")
    h1 = trail[trail.headline_id == "H1"]
    assert "R001" not in set(h1.report_id), "Cedar MWh must not be converted into tCO2e (it reports tCO2e itself)"


def test_correction_resolves_trial_anomaly():
    trial = pipeline.pd.read_csv(ROOT / "outputs" / "trial_aggregation_review.csv").set_index("headline_id")
    assert trial.loc["H2", "trial_flag"].startswith("ANOMALY")
    assert abs(TOTALS["H2"] - (4200 + 135 * 9.5)) < 0.01


def test_people_rounded_down():
    assert TOTALS["H3"] == 816  # 340 households x 2.4 = 816
    assert TOTALS["H5"] == 150  # 260 x 58% = 150.8 -> 150


def test_cids_export_valid():
    doc = json.loads((ROOT / "outputs" / "cids_portfolio.jsonld").read_text())
    assert validate(doc) == []


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("passed:", name)
