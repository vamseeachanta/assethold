"""Tests for scripts/ci/leak_scan.py (fictional inputs only)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "leak_scan.py"
_spec = importlib.util.spec_from_file_location("leak_scan", _SCRIPT)
leak_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(leak_scan)

SURNAME = "ach" + "anta"


def test_owner_email_is_flagged():
    data = ("contact: someone." + SURNAME + "@example.com\n").encode()
    assert leak_scan.content_findings("a.md", data, []) == ["a.md: owner email address"]


def test_noreply_address_is_allowed():
    data = ("12345+someone" + SURNAME + "@users.noreply.github.com").encode()
    assert leak_scan.content_findings("a.md", data, []) == []


def test_unrelated_email_is_allowed():
    assert leak_scan.content_findings("a.md", b"info@example.com", []) == []


def test_extra_pattern_is_flagged_case_insensitively():
    findings = leak_scan.content_findings("b.py", b"repo = 'Fictional-Private-Repo'", [b"fictional-private-repo"])
    assert findings == ["b.py: matches private pattern #1"]


def test_extra_patterns_come_from_environment(monkeypatch):
    monkeypatch.setenv(leak_scan.EXTRA_PATTERNS_ENV, "AlphaRepo\n\n  BETA-123  \n")
    assert leak_scan.load_extra_patterns() == [b"alpharepo", b"beta-123"]


@pytest.mark.parametrize(
    "path",
    [
        "data/sandsig-cre-listings/email/x.md",
        "reports/daily-strategy/2030-01-01.md",
        "config/daily_strategy.yaml",
        "tests/modules/stocks/data/clients/client9/2030.csv",
        "docs/business/x.pdf",
        "docs/domain/realestate/x/someone_conversations.md",
        "docs/x/WhatsApp Chat with Someone.txt",
        "data/private/fidelity/2030.csv",
    ],
)
def test_private_paths_are_flagged(path):
    assert leak_scan.path_findings([path]) == [f"{path}: path is reserved for private storage"]


def test_example_config_path_is_allowed():
    assert leak_scan.path_findings(["config/daily_strategy.example.yaml"]) == []


def test_scan_end_to_end_on_a_temporary_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "ok.md").write_text("nothing private here\n")
    (tmp_path / "bad.md").write_text("mail someone." + SURNAME + "@example.com\n")
    subprocess.run(["git", "add", "ok.md", "bad.md"], cwd=tmp_path, check=True)
    assert leak_scan.scan(tmp_path) == ["bad.md: owner email address"]


# Frozen inventory of the 525 files removed on 2026-11-15. Restoring any of them
# must fail the scan. A fixed list (not a git diff against HEAD) so that later,
# unrelated deletions do not change what this test checks.
INVENTORY = Path(__file__).resolve().parent / "data" / "removed_paths_2026-11-15.txt"


def _inventory() -> list[str]:
    lines = INVENTORY.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line and not line.startswith("#")]


def test_inventory_is_complete():
    assert len(_inventory()) == 525


def test_every_removed_path_is_blocked_by_path_rules():
    unprotected = [p for p in _inventory() if not leak_scan.path_findings([p])]
    assert unprotected == []


def test_scanner_scans_its_own_source(tmp_path, monkeypatch):
    """A private literal planted in the scanner's own file must be reported.

    The scanner is loaded from a copy inside a temporary repository, so a
    reintroduced "skip my own file" rule would hide the planted literal and
    fail this test.
    """
    literal = "fictional-private-" + "literal-7q"
    target = tmp_path / "scripts" / "ci" / "leak_scan.py"
    target.parent.mkdir(parents=True)
    planted = "\n# " + literal + "\n"
    target.write_bytes(_SCRIPT.read_bytes() + planted.encode())
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "scripts/ci/leak_scan.py"], cwd=tmp_path, check=True)

    spec = importlib.util.spec_from_file_location("leak_scan_copy", target)
    copy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copy)

    monkeypatch.setenv(copy.EXTRA_PATTERNS_ENV, literal)
    assert copy.scan(tmp_path) == ["scripts/ci/leak_scan.py: matches private pattern #1"]


def test_real_scanner_source_is_clean():
    data = _SCRIPT.read_bytes()
    assert leak_scan.content_findings("scripts/ci/leak_scan.py", data, []) == []
