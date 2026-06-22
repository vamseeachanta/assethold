#!/usr/bin/env python3
# ABOUTME: Single-source PR-gate test selector — maps changed files -> pytest targets.
# ABOUTME: Auto-discovers modules from the filesystem so new modules never drift.

"""Select pytest targets for the PR gate from a list of changed files.

Ports the modular per-domain CI pattern from worldenergydata#526/#530 to
assethold. The module list is the filesystem: a module is "mapped" iff
``tests/modules/<module>/`` exists (mirrored by ``src/assethold/modules/<module>/``).
Adding a module needs no CI edit — and the drift-guard test
(``tests/ci/test_select_test_targets.py``) fails if any ``tests/modules/<module>``
stops being selected.

Decision tree (first match wins):
  * a **core** path changed (engine, common, base_configs, packaging, conftest,
    the workflow itself, this selector) -> ``scope=full`` (whole tree).
  * otherwise collect the modules touched under ``src/assethold/modules/<m>/`` or
    ``tests/modules/<m>/``, plus any top-level test dir touched directly
    (tests/options, tests/net_lease, ...) and unit changes -> ``scope=modules``.
  * if nothing test-relevant changed (docs / reports / notebooks only)
    -> ``scope=skip`` — still runs the cheap always-on cross-cutting set so the
    required PR-gate check passes fast, never the full tree.

The always-on set always runs, so the target list is never empty.

Usage::

    python3 scripts/ci/select_test_targets.py --files-from changed.txt
    git diff --name-only BASE...HEAD | python3 scripts/ci/select_test_targets.py -
    python3 scripts/ci/select_test_targets.py --emit-matrix --files-from changed.txt

Emits ``scope=`` / ``xdist_targets=`` / ``seq_targets=`` lines, or (with
``--emit-matrix``) ``scope=`` / ``matrix=<json>`` lines (GitHub Actions
``$GITHUB_OUTPUT`` format).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Always-on cross-cutting set: smoke, the contracts suite, the repo-structure
# contract, and the unit tree's loose top-level files. Runs for every PR so the
# target list is never empty. (Kept to dirs/files that exist at select time.)
ALWAYS_XDIST = [
    "tests/test_smoke.py",
    "tests/contracts",
    "tests/repo_structure",
    "tests/unit",
]

# Changing any of these can affect every module -> run the whole tree.
CORE_EXACT = {
    "src/assethold/engine.py",
    "src/assethold/__main__.py",
    "src/assethold/__init__.py",
    "pyproject.toml",
    "uv.lock",
    "pytest.ini",
    "tests/conftest.py",
    ".github/workflows/ci.yml",
}
CORE_PREFIXES = (
    "src/assethold/base_configs/",
    "src/assethold/common/",
    "src/assethold/utils/",
    "scripts/ci/",  # the selector itself / its tests -> fail safe to full
)

# Exact non-module paths that should run a specific contract suite.
CONTRACT_ROUTES = {
    "config/repo_structure.yml": "tests/repo_structure",
    "docs/standards/repo-structure.md": "tests/repo_structure",
}

# Top-level test dirs that map 1:1 to a source area but live outside
# tests/modules (e.g. tests/options <-> src/assethold/options). A change under
# either side routes to the matching tests dir.
TOPLEVEL_TEST_DIRS = ("net_lease", "options", "portfolio")

_MODULE_RE = re.compile(r"^(?:src/assethold/modules|tests/modules)/([^/]+)/")
_TOPLEVEL_SRC_RE = re.compile(r"^src/assethold/([^/]+)/")
_UNIT_RE = re.compile(r"^tests/unit/")
_INTEGRATION_RE = re.compile(r"^tests/integration/")


def _is_core(path: str) -> bool:
    return path in CORE_EXACT or path.startswith(CORE_PREFIXES)


def _has_tests(directory: Path) -> bool:
    """True if ``directory`` contains at least one pytest file.

    Keeps non-test support dirs (fixtures/, helpers/, mocks/, output/, …) out of
    the domain matrix so they don't become empty shards. Note: a dir that *has*
    test files but is excluded by ``--ignore`` still becomes a shard — the CI
    step treats pytest's "no tests collected" (exit 5) as a pass, so such shards
    are harmless.
    """
    for pattern in ("test_*.py", "*_test.py"):
        if next(directory.rglob(pattern), None) is not None:
            return True
    return False


def select(changed: list[str], root: Path) -> dict:
    """Return {scope, xdist, seq} for the given changed files."""
    if any(_is_core(p) for p in changed):
        full = _full_tree(root)
        return {
            "scope": "full",
            "xdist": full,
            "seq": ["tests/integration"],
        }

    modules: set[str] = set()
    toplevel: set[str] = set()
    contracts: set[str] = set()
    unit = False
    integration = False
    relevant = False

    for p in changed:
        if p in CONTRACT_ROUTES:
            contracts.add(CONTRACT_ROUTES[p])
            relevant = True
            continue
        m = _MODULE_RE.match(p)
        if m:
            modules.add(m.group(1))
            relevant = True
            continue
        if _UNIT_RE.match(p):
            unit = True
            relevant = True
            continue
        if _INTEGRATION_RE.match(p):
            integration = True
            relevant = True
            continue
        ms = _TOPLEVEL_SRC_RE.match(p)
        if ms and ms.group(1) in TOPLEVEL_TEST_DIRS:
            toplevel.add(ms.group(1))
            relevant = True
            continue
        # tests/<toplevel>/... changed directly
        for name in TOPLEVEL_TEST_DIRS:
            if p.startswith(f"tests/{name}/"):
                toplevel.add(name)
                relevant = True
                break
        # anything else (reports/, notebooks/, *.md, docs/ non-contract,
        # scripts/ non-ci) is not test-relevant.

    xdist = list(ALWAYS_XDIST)
    for mod in sorted(modules):
        xdist.append(f"tests/modules/{mod}")
    for name in sorted(toplevel):
        xdist.append(f"tests/{name}")
    xdist.extend(sorted(contracts))
    seq = ["tests/integration"] if integration else []

    # keep only dirs/files that exist, dedupe, preserve order
    xdist = _existing_unique(xdist, root)
    seq = _existing_unique(seq, root)
    return {"scope": "modules" if relevant else "skip", "xdist": xdist, "seq": seq}


def _existing_unique(targets: list[str], root: Path) -> list[str]:
    seen, out = set(), []
    for t in targets:
        if t not in seen and (root / t).exists():
            seen.add(t)
            out.append(t)
    return out


def _full_tree(root: Path) -> list[str]:
    tests = root / "tests"
    out = []
    for child in sorted(tests.iterdir()):
        if child.is_dir() and child.name not in {
            "integration",
            "fixtures",
            "__pycache__",
        }:
            out.append(f"tests/{child.name}")
        elif (
            child.is_file() and child.name.startswith("test_") and child.suffix == ".py"
        ):
            out.append(f"tests/{child.name}")
    return out


def to_matrix(changed: list[str], root: Path) -> dict:
    """Build a GitHub-Actions matrix of per-domain shards from changed files.

    Each shard is ``{"name", "targets", "mode"}`` where ``mode`` is ``xdist``
    (parallel, ``-n auto``) or ``seq`` (sequential, for integration).

    Unlike :func:`select` (one big target list), this fans the work out so every
    domain runs as its own CI job — faster wall-clock and per-domain pass/fail
    isolation (a red domain no longer blocks green siblings).

    * ``scope=full`` -> one shard per ``tests/modules/<domain>`` plus one per
      other top-level ``tests/<dir>`` (that has tests) plus a ``_root`` shard for
      top-level test files plus a seq shard for integration.
    * ``scope=modules`` -> the always-on shard + one shard per touched module +
      one per touched top-level dir / routed contract; seq shard if integration.
    * ``scope=skip`` -> just the always-on shard (never empty).
    """
    result = select(changed, root)
    scope = result["scope"]
    shards: list[dict] = []

    if scope == "full":
        mods = root / "tests" / "modules"
        if mods.is_dir():
            for child in sorted(mods.iterdir()):
                if (
                    child.is_dir()
                    and child.name != "__pycache__"
                    and _has_tests(child)
                ):
                    shards.append(
                        {
                            "name": f"modules-{child.name}",
                            "targets": f"tests/modules/{child.name}",
                            "mode": "xdist",
                        }
                    )
        tests = root / "tests"
        root_files: list[str] = []
        for child in sorted(tests.iterdir()):
            if (
                child.is_dir()
                and child.name
                not in {
                    "modules",
                    "integration",
                    "fixtures",
                    "__pycache__",
                }
                and _has_tests(child)
            ):
                shards.append(
                    {
                        "name": child.name,
                        "targets": f"tests/{child.name}",
                        "mode": "xdist",
                    }
                )
            elif (
                child.is_file()
                and child.name.startswith("test_")
                and child.suffix == ".py"
            ):
                root_files.append(f"tests/{child.name}")
        if root_files:
            shards.append(
                {"name": "_root", "targets": " ".join(root_files), "mode": "xdist"}
            )
        if (root / "tests/integration").is_dir():
            shards.append(
                {"name": "integration", "targets": "tests/integration", "mode": "seq"}
            )
    else:
        # modules / skip: the always-on shard guarantees a non-empty matrix.
        always = _existing_unique(list(ALWAYS_XDIST), root)
        if always:
            shards.append(
                {"name": "_always", "targets": " ".join(always), "mode": "xdist"}
            )
        for tgt in result["xdist"]:
            if tgt in ALWAYS_XDIST:
                continue  # already in the always-on shard
            name = tgt.replace("tests/modules/", "modules-").replace("tests/", "")
            shards.append({"name": name, "targets": tgt, "mode": "xdist"})
        for tgt in result["seq"]:
            name = tgt.replace("tests/", "")
            shards.append({"name": name, "targets": tgt, "mode": "seq"})

    return {"scope": scope, "include": shards}


def _read_changed(args) -> list[str]:
    if args.files_from == "-":
        text = sys.stdin.read()
    elif args.files_from:
        text = Path(args.files_from).read_text(encoding="utf-8")
    else:
        return list(args.files)
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="*", help="changed file paths")
    ap.add_argument(
        "--files-from", help="read changed paths from FILE (or - for stdin)"
    )
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument(
        "--emit-matrix",
        action="store_true",
        help="emit a per-domain GitHub Actions matrix (matrix=<json>) instead "
        "of the flat xdist/seq target lists",
    )
    a = ap.parse_args(argv)
    changed = _read_changed(a)
    if a.emit_matrix:
        matrix = to_matrix(changed, Path(a.root))
        print(f"scope={matrix['scope']}")
        print(f"matrix={json.dumps({'include': matrix['include']})}")
        return 0
    result = select(changed, Path(a.root))
    print(f"scope={result['scope']}")
    print(f"xdist_targets={' '.join(result['xdist'])}")
    print(f"seq_targets={' '.join(result['seq'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
