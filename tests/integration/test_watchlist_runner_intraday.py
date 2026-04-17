"""ABOUTME: Integration tests for the --intraday flag in watchlist_runner CLI.
ABOUTME: Subprocess-level verification that --intraday fail-loud honors NYSE open state (#39)."""

import subprocess
import sys
from pathlib import Path

import pytest


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
    """`python -m assethold.signals.watchlist_runner --intraday` exits 1 with
    `next open` in stderr when the NYSE regular session is closed.

    Mirrors the Phase 1 pattern from `test_daily_strategy_intraday.py`. The
    pre-flight checks wall-clock NOW; the skipif guard prevents false failures
    during weekday market hours.
    """
    result = subprocess.run(
        [sys.executable, "-m", "assethold.signals.watchlist_runner", "--intraday"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1, (
        f"Expected exit 1, got {result.returncode}. stderr={result.stderr}"
    )
    assert "next open" in result.stderr.lower(), (
        f"stderr missing 'next open': {result.stderr}"
    )
    # v2.1 disambiguation message: pre-flight is wall-clock, not --lookback-days.
    assert "lookback" in result.stderr.lower() or "wall-clock" in result.stderr.lower(), (
        f"stderr missing pre-flight disambiguation: {result.stderr}"
    )


@pytest.mark.slow
def test_no_intraday_flag_does_not_check_market_hours():
    """Without --intraday or --no-intraday, and with config.settings.market_hours_aware
    not overriding to true, the market-hours pre-flight does NOT fire.

    Asserts only that 'next open' is absent from stderr — does not assert exit 0,
    because the default path may still fail for unrelated reasons (network, etc.).
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "assethold.signals.watchlist_runner",
            "--no-intraday",  # explicit False to override any config drift
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert "next open" not in result.stderr.lower(), (
        f"Default path should not trigger market-hours pre-flight: {result.stderr}"
    )


def test_help_lists_all_flags():
    """`--help` output includes every documented CLI flag."""
    result = subprocess.run(
        [sys.executable, "-m", "assethold.signals.watchlist_runner", "--help"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"--help returned {result.returncode}: {result.stderr}"
    combined = result.stdout
    for flag in ("--intraday", "--no-intraday", "--lookback-days", "--render-charts", "--charts-dir"):
        assert flag in combined, f"--help missing {flag}: {combined}"
