import json
import os

import pytest

from evaluation.run_calibration import HERE, build_report, calibration_metrics


def test_perfect_agreement():
    m = calibration_metrics([10, 5, 2], [10, 5, 2])
    assert m == {"mean_absolute_error": 0.0, "correlation": pytest.approx(1.0), "pass_fail_agreement": 1.0}


def test_disagreement_is_measured():
    m = calibration_metrics([10, 2], [4, 9])      # judge fails the good report and passes the bad one
    assert m["mean_absolute_error"] == 6.5 and m["pass_fail_agreement"] == 0.0


def test_every_case_builds_and_removes_sections():
    with open(os.path.join(HERE, "base_report.md"), encoding="utf-8") as f:
        base = f.read()
    with open(os.path.join(HERE, "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)
    for case in cases:
        report = build_report(base, case)
        for section in case.get("remove_sections", []):
            assert f"## {section}" not in report
