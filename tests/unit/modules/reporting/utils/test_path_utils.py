"""Unit tests for reporting path utilities."""

from pathlib import Path

import pytest

from assethold.modules.reporting.utils.path_utils import relative_path_from_report

pytestmark = pytest.mark.unit


def test_relative_path_fallback_uses_common_prefix_root(tmp_path):
    """Fallback path calculation works when direct relative_to is impossible."""
    report_file = tmp_path / "reports" / "monthly" / "analysis.html"
    data_file = tmp_path / "data" / "processed" / "measurements.csv"

    assert (
        relative_path_from_report(Path(data_file), Path(report_file))
        == "../../data/processed/measurements.csv"
    )
