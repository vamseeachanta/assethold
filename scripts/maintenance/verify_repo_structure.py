#!/usr/bin/env python3
"""Verify assethold's Phase 1 repository-structure contract.

The checker is intentionally conservative: it validates the current tracked
repository shape plus non-ignored working-tree paths without moving or deleting
anything. It also rejects deletion/relocation of classified generated evidence
so generated-looking artifacts cannot disappear silently during structure work.
"""

from __future__ import annotations

import argparse
import dataclasses
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

import yaml

PLACEHOLDER_VALUES = {"", "tbd", "todo", "none", "n/a", "na", "unknown"}
VALID_EXCEPTION_CATEGORIES = {
    "durable-evidence",
    "temporary-durable-exception",
    "authorized-generated-artifact",
}


@dataclasses.dataclass(frozen=True)
class RepoStructureViolation:
    """Stable repo-structure violation emitted by the checker."""

    code: str
    root: str
    path: str


@dataclasses.dataclass(frozen=True)
class WorktreeStatusEntry:
    """Parsed `git status --short` path with its two-character status code."""

    status: str
    path: str
    original_path: str | None = None


@dataclasses.dataclass(frozen=True)
class RepoStructureContract:
    """Loaded machine-readable repo-structure policy."""

    allowed_roots: frozenset[str]
    ignored_roots: frozenset[str]
    generated_artifact_roots: frozenset[str]
    temporary_exceptions: dict[str, dict]


def root_for(path: str) -> str:
    """Return the first repository path component without stripping leading dots."""

    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.strip()
    return normalized.split("/", 1)[0] if normalized else ""


def load_contract(path: Path) -> RepoStructureContract:
    """Load `config/repo_structure.yml` into a normalized contract object."""

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RepoStructureContract(
        allowed_roots=frozenset(data.get("allowed_roots", [])),
        ignored_roots=frozenset(data.get("ignored_roots", [])),
        generated_artifact_roots=frozenset(data.get("generated_artifact_roots", [])),
        temporary_exceptions=dict(data.get("temporary_exceptions", {})),
    )


def _is_placeholder(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in PLACEHOLDER_VALUES or text.startswith("todo") or text.startswith("tbd")


def _exception_metadata_valid(root: str, metadata: dict) -> bool:
    required_fields = ("category", "owner", "review_date", "justification")
    if any(_is_placeholder(metadata.get(field)) for field in required_fields):
        return False
    if metadata.get("category") not in VALID_EXCEPTION_CATEGORIES:
        return False
    follow_up = str(metadata.get("follow_up", "")).strip()
    permanent = str(metadata.get("permanent_justification", "")).strip()
    if _is_placeholder(follow_up) and _is_placeholder(permanent):
        return False
    if follow_up and not follow_up.startswith("https://github.com/"):
        return False
    allowed_paths = metadata.get("allowed_paths", [])
    if not isinstance(allowed_paths, list) or not allowed_paths:
        return False
    return all(root_for(path) == root for path in allowed_paths)


def validate_exception_metadata(contract: RepoStructureContract) -> list[RepoStructureViolation]:
    """Validate all generated-artifact temporary-exception metadata."""

    violations: list[RepoStructureViolation] = []
    for root, metadata in sorted(contract.temporary_exceptions.items()):
        if root not in contract.generated_artifact_roots:
            violations.append(RepoStructureViolation("invalid-exception-root", root, root))
            continue
        if not isinstance(metadata, dict) or not _exception_metadata_valid(root, metadata):
            violations.append(RepoStructureViolation("invalid-exception-metadata", root, root))
    return violations


def validate_paths(paths: Iterable[str], contract: RepoStructureContract) -> list[RepoStructureViolation]:
    """Validate repository paths against the loaded contract."""

    violations = validate_exception_metadata(contract)
    classified_paths_by_root = {
        root: set(metadata.get("allowed_paths", []))
        for root, metadata in contract.temporary_exceptions.items()
        if isinstance(metadata, dict)
    }

    for raw_path in sorted(set(paths)):
        path = raw_path.replace("\\", "/")
        root = root_for(path)
        if not root or root in contract.ignored_roots:
            continue
        if root in contract.generated_artifact_roots:
            if root not in contract.temporary_exceptions:
                violations.append(
                    RepoStructureViolation("generated-root-missing-exception", root, path)
                )
                continue
            if path not in classified_paths_by_root.get(root, set()):
                violations.append(
                    RepoStructureViolation("generated-path-not-classified", root, path)
                )
                continue
        if root not in contract.allowed_roots and root not in contract.generated_artifact_roots:
            violations.append(RepoStructureViolation("unknown-root", root, path))
    return sorted(set(violations), key=lambda item: (item.code, item.root, item.path))


def validate_worktree_status_entries(
    entries: Iterable[WorktreeStatusEntry], contract: RepoStructureContract
) -> list[RepoStructureViolation]:
    """Validate worktree status entries, preserving destructive status codes."""

    violations: list[RepoStructureViolation] = []
    for entry in entries:
        roots = [root_for(entry.path)]
        if entry.original_path:
            roots.append(root_for(entry.original_path))
        status = entry.status.strip()
        if ("D" in entry.status or status.startswith("R")) and any(
            root in contract.generated_artifact_roots for root in roots
        ):
            root = next(root for root in roots if root in contract.generated_artifact_roots)
            path = (
                f"{entry.original_path} -> {entry.path}"
                if entry.original_path
                else entry.path
            )
            violations.append(
                RepoStructureViolation("generated-artifact-deletion-or-relocation", root, path)
            )
    return sorted(set(violations), key=lambda item: (item.code, item.root, item.path))


def _split_status_path(payload: str, *, is_rename: bool) -> tuple[str | None, str]:
    """Split a short-status payload into optional old path and current path."""

    if not is_rename or " -> " not in payload:
        return None, _unquote_path(payload)
    old_path, new_path = payload.split(" -> ", 1)
    return _unquote_path(old_path), _unquote_path(new_path)


def _unquote_path(path: str) -> str:
    """Parse Git's quoted path form while leaving unquoted paths unchanged."""

    path = path.strip()
    if path.startswith('"'):
        return shlex.split(path)[0]
    return path


def parse_git_status_entries(output: str) -> list[WorktreeStatusEntry]:
    """Parse `git status --short --untracked-files=all` output."""

    entries: list[WorktreeStatusEntry] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        payload = line[3:] if len(line) > 3 else ""
        old_path, path = _split_status_path(payload, is_rename=status.startswith("R"))
        entries.append(WorktreeStatusEntry(status=status, path=path, original_path=old_path))
    return entries


def parse_git_status_paths(output: str) -> list[str]:
    """Return current paths from short-status output."""

    return [entry.path for entry in parse_git_status_entries(output)]


def _git(repo_root: Path, args: Sequence[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=repo_root, text=True)


def git_tracked_paths(repo_root: Path) -> list[str]:
    """Return tracked repository paths."""

    return _git(repo_root, ["ls-files"]).splitlines()


def git_worktree_status_entries(repo_root: Path) -> list[WorktreeStatusEntry]:
    """Return tracked and untracked non-ignored worktree status entries."""

    output = _git(repo_root, ["status", "--short", "--untracked-files=all"])
    return parse_git_status_entries(output)


def _print_violations(violations: Sequence[RepoStructureViolation]) -> None:
    if not violations:
        print("repo-structure: OK")
        return
    print("repo-structure: violations found")
    for violation in violations:
        print(f"{violation.code}\t{violation.root}\t{violation.path}")


def _default_config_path(repo_root: Path) -> Path:
    return repo_root / "config" / "repo_structure.yml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to repo_structure.yml (default: config/repo_structure.yml)",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Validate an explicit path instead of the default git path set; repeatable.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path.cwd()
    config_path = args.config or _default_config_path(repo_root)
    contract = load_contract(config_path)

    if args.path:
        paths = list(args.path)
        status_entries: list[WorktreeStatusEntry] = []
    else:
        status_entries = git_worktree_status_entries(repo_root)
        paths = git_tracked_paths(repo_root) + [entry.path for entry in status_entries]

    violations = validate_paths(paths, contract)
    violations.extend(validate_worktree_status_entries(status_entries, contract))
    violations = sorted(set(violations), key=lambda item: (item.code, item.root, item.path))
    _print_violations(violations)
    return 1 if violations else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
