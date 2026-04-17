"""ABOUTME: Integration tests for the --intraday flag in daily_strategy CLI.
ABOUTME: Covers fail-loud-when-market-closed and the no-flag legacy path."""

import subprocess
import sys
from pathlib import Path

import pytest


# Repo root resolved from this test file's location (tests/integration/test_*.py → parents[2])
REPO = str(Path(__file__).resolve().parents[2])


def _market_open_now() -> bool:
    """Local helper: is the NYSE regular session open right now?"""
    from assethold.utils.market_hours import is_market_open
    return is_market_open()


@pytest.mark.skipif(
    _market_open_now(),
    reason="--intraday pre-flight only fails loud when market is closed; skip during NYSE regular session",
)
def test_intraday_fails_loud_when_market_closed():
    """--intraday must exit 1 with 'next open' in stderr when invoked outside market hours.

    The pre-flight checks wall-clock NOW (not --date), so this test is meaningful
    only when the test process happens to be running outside the NYSE regular session.
    The skipif guard prevents false failures during weekday market hours.
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "assethold.analysis.daily_strategy",
            "--intraday",
            "--date", "2026-04-19",  # Sunday (report-date override; does not affect pre-flight)
            "--no-write",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stderr={result.stderr}"
    assert "next open" in result.stderr.lower(), f"stderr missing 'next open': {result.stderr}"


def test_no_intraday_flag_does_not_check_market_hours():
    """Without --intraday, a Sunday invocation does NOT trigger the market-hours pre-flight."""
    result = subprocess.run(
        [
            sys.executable, "-m", "assethold.analysis.daily_strategy",
            "--date", "2026-04-19",  # Sunday
            "--no-write",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,  # legacy path may do real fetches
    )
    # The legacy path may fail for unrelated reasons (network, etc.) — assert only that
    # the market-hours pre-flight is NOT triggered.
    assert "next open" not in result.stderr.lower(), (
        f"Legacy path should not check market hours: {result.stderr}"
    )
