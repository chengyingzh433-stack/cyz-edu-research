#!/usr/bin/env python3
"""Check or atomically migrate a legacy CYZ project to project schema 2."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import NoReturn


MANAGED_FILES = ("00-项目状态.md", "01-研究起点与问题.md")
CANVAS_START = b"<!-- cyz:idea-canvas:start -->"
CANVAS_END = b"<!-- cyz:idea-canvas:end -->"
FAULT_POINTS = (
    "before-backup",
    "after-backup",
    "before-replace",
    "after-first-replace",
    "user-edit-before-second-replace",
)
SIMULATED_USER_EDIT = b"\n<!-- cyz:test-hook:user-edit -->\n"

SCHEMA2_DEFAULTS = (
    ("entry_mode", '"materials"'),
    ("workflow_schema", "2"),
    ("idea_mode", '"discovery"'),
    ("idea_maturity", '"broad_interest"'),
    ("idea_status", '"not_started"'),
    ("idea_revision", "1"),
    ("idea_workspace", '"01-研究起点与问题.md"'),
    ("current_decision", '""'),
    ("current_evidence", '""'),
    ("handoff_path", '"01-研究起点与问题.md#交接区"'),
)


class MigrationError(RuntimeError):
    """A safe migration precondition or execution step failed."""


class StructuralConflict(MigrationError):
    """A project no longer matches the structure or bytes that were inspected."""


class InjectedFailure(MigrationError):
    """A documented recovery-test failure was requested on the command line."""

    def __init__(self, point: str):
        super().__init__(f"simulated failure at {point}")
        self.point = point


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="Report migration status")
    action.add_argument("--apply", action="store_true", help="Apply a schema-2 migration")
    parser.add_argument(
        "--simulate-failure",
        choices=FAULT_POINTS,
        metavar="POINT",
        help=(
            "Recovery/concurrency tests only: inject before-backup, after-backup, "
            "before-replace, after-first-replace, or a user edit before the "
            "second replace"
        ),
    )
    args = parser.parse_args()
    if args.simulate_failure and not args.apply:
        parser.error("--simulate-failure requires --apply")
    return args


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_utf8(data: bytes, relative: str) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MigrationError(f"{relative} is not valid UTF-8: {exc}") from exc


def frontmatter_fields(data: bytes) -> tuple[dict[str, str], set[str]]:
    text = decode_utf8(data, MANAGED_FILES[0])
    match = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not match:
        raise MigrationError("00-项目状态.md lacks valid frontmatter")
    values: dict[str, str] = {}
    duplicates: set[str] = set()
    for line in match.group(1).splitlines():
        field = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if not field:
            continue
        key, value = field.groups()
        if key in values:
            duplicates.add(key)
        values[key] = value.strip().strip("\"'")
    return values, duplicates


def read_snapshot(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        raise MigrationError(f"project directory does not exist: {root}")
    snapshot: dict[str, bytes] = {}
    for relative in MANAGED_FILES:
        path = root / relative
        if not path.is_file():
            raise MigrationError(f"missing managed file: {relative}")
        snapshot[relative] = path.read_bytes()
    return snapshot


def inspect_snapshot(snapshot: dict[str, bytes]) -> str:
    state, duplicates = frontmatter_fields(snapshot[MANAGED_FILES[0]])
    if "workflow_schema" in duplicates:
        raise MigrationError("duplicate workflow_schema frontmatter field")

    idea = snapshot[MANAGED_FILES[1]]
    start_count = idea.count(CANVAS_START)
    end_count = idea.count(CANVAS_END)
    markers_valid = (
        start_count == 1
        and end_count == 1
        and idea.index(CANVAS_START) < idea.index(CANVAS_END)
    )
    if (start_count, end_count) not in {(0, 0), (1, 1)} or (
        start_count == 1 and not markers_valid
    ):
        raise MigrationError(
            "duplicate, unmatched, or out-of-order managed markers in "
            "01-研究起点与问题.md"
        )

    schema = state.get("workflow_schema")
    if schema == "2":
        if not markers_valid:
            raise MigrationError("schema 2 project lacks one valid idea-canvas marker pair")
        return "compatible"
    if schema is not None:
        raise MigrationError(f"unsupported workflow_schema: {schema!r}")
    return "migratable"


def add_schema2_frontmatter(data: bytes) -> bytes:
    match = re.match(
        rb"(?:\xef\xbb\xbf)?---[ \t]*(\r?\n)(.*?)(\r?\n)---(?=\r?\n|\Z)",
        data,
        re.S,
    )
    if not match:
        raise MigrationError("00-项目状态.md lacks valid byte-level frontmatter")
    existing, _ = frontmatter_fields(data)
    newline = match.group(1)
    additions = newline.join(
        f"{key}: {value}".encode("utf-8")
        for key, value in SCHEMA2_DEFAULTS
        if key not in existing
    )
    if not additions:
        return data
    insertion = newline + additions
    return data[: match.end(2)] + insertion + data[match.end(2) :]


def wrap_legacy_idea(data: bytes) -> bytes:
    if data.count(CANVAS_START) == 1 and data.count(CANVAS_END) == 1:
        return data
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    prefix = newline.join(
        (
            CANVAS_START,
            "## Idea 工作区".encode("utf-8"),
            b"",
            "- 入口：`materials`".encode("utf-8"),
            "- 模式：`discovery`".encode("utf-8"),
            "- 成熟度：`broad_interest`".encode("utf-8"),
            "- 状态：`not_started`".encode("utf-8"),
            "- 修订：`1`".encode("utf-8"),
            b"",
            "### 已迁移旧版记录".encode("utf-8"),
            b"",
            b"<!-- cyz:legacy-record:start -->",
        )
    ) + newline
    suffix = newline.join(
        (
            b"<!-- cyz:legacy-record:end -->",
            b"",
            "### 交接区".encode("utf-8"),
            b"",
            "- 待核对旧版记录后生成交接记录。".encode("utf-8"),
            CANVAS_END,
            b"",
        )
    )
    separator = b"" if data.endswith((b"\n", b"\r")) else newline
    return prefix + data + separator + suffix


def build_candidates(snapshot: dict[str, bytes]) -> dict[str, bytes]:
    return {
        MANAGED_FILES[0]: add_schema2_frontmatter(snapshot[MANAGED_FILES[0]]),
        MANAGED_FILES[1]: wrap_legacy_idea(snapshot[MANAGED_FILES[1]]),
    }


def unique_migration_dir(root: Path) -> Path:
    migrations = root / ".cyz-migrations"
    migrations.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = migrations / stamp
    destination.mkdir()
    return destination


def write_temp(path: Path, data: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.cyz-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = write_temp(path, payload)
    os.replace(temporary, path)


def fail_if_requested(requested: str | None, point: str) -> None:
    if requested == point:
        raise InjectedFailure(point)


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    validate_script = Path(__file__).with_name("validate_project.py")
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(validate_script), str(root)],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=environment,
    )


def require_valid_project(root: Path, error_type: type[MigrationError]) -> None:
    result = run_validator(root)
    if result.returncode != 0:
        details = (result.stdout + result.stderr).strip()
        raise error_type(f"project validation failed:\n{details}")


def validate_candidates(root: Path, candidates: dict[str, bytes]) -> None:
    with tempfile.TemporaryDirectory(prefix=".cyz-candidate-", dir=root.parent) as temp:
        candidate_root = Path(temp) / "project"
        shutil.copytree(
            root,
            candidate_root,
            ignore=shutil.ignore_patterns(".cyz-migrations"),
        )
        for relative, data in candidates.items():
            (candidate_root / relative).write_bytes(data)
        require_valid_project(candidate_root, MigrationError)


def restore_changed(
    root: Path,
    snapshot: dict[str, bytes],
    changed_paths: list[str],
) -> tuple[list[str], list[dict[str, str]]]:
    restored: list[str] = []
    failures: list[dict[str, str]] = []
    for relative in reversed(changed_paths):
        destination = root / relative
        temporary: Path | None = None
        try:
            temporary = write_temp(destination, snapshot[relative])
            os.replace(temporary, destination)
            restored.append(relative)
        except BaseException as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            failures.append(
                {
                    "path": relative,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
    return restored, failures


def apply_migration(
    root: Path,
    snapshot: dict[str, bytes],
    fault_point: str | None,
) -> int:
    candidates = build_candidates(snapshot)
    migration_dir = unique_migration_dir(root)
    manifest_path = migration_dir / "manifest.json"
    files = [
        {
            "path": relative,
            "before_sha256": sha256(snapshot[relative]),
            "after_sha256": sha256(candidates[relative]),
            "backup_path": f"backups/{relative}",
        }
        for relative in MANAGED_FILES
    ]
    manifest: dict[str, object] = {
        "migration": "legacy-to-schema-2",
        "target": "schema-2",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "phase": "planned",
        "last_completed_phase": "planned",
        "files": files,
        "changed_paths": [],
    }
    changed_paths: list[str] = []
    staged: dict[str, Path] = {}
    write_manifest(manifest_path, manifest)

    try:
        fail_if_requested(fault_point, "before-backup")

        for relative in MANAGED_FILES:
            backup = migration_dir / "backups" / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(snapshot[relative])
        manifest["phase"] = "backups_complete"
        manifest["last_completed_phase"] = "backups_complete"
        write_manifest(manifest_path, manifest)

        fail_if_requested(fault_point, "after-backup")

        validate_candidates(root, candidates)
        manifest["phase"] = "candidate_validated"
        manifest["last_completed_phase"] = "candidate_validated"
        write_manifest(manifest_path, manifest)

        for relative in MANAGED_FILES:
            staged[relative] = write_temp(root / relative, candidates[relative])

        fail_if_requested(fault_point, "before-replace")

        manifest["phase"] = "replacing"
        write_manifest(manifest_path, manifest)
        for index, relative in enumerate(MANAGED_FILES):
            if index == 1 and fault_point == "user-edit-before-second-replace":
                destination = root / relative
                destination.write_bytes(destination.read_bytes() + SIMULATED_USER_EDIT)
            if sha256((root / relative).read_bytes()) != sha256(snapshot[relative]):
                raise StructuralConflict(
                    f"managed file changed during migration: {relative}"
                )
            os.replace(staged.pop(relative), root / relative)
            changed_paths.append(relative)
            manifest["changed_paths"] = list(changed_paths)
            write_manifest(manifest_path, manifest)
            if index == 0:
                fail_if_requested(fault_point, "after-first-replace")

        manifest["phase"] = "complete"
        manifest["last_completed_phase"] = "complete"
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        write_manifest(manifest_path, manifest)
        print(f"MIGRATED {root}")
        print(f"MANIFEST {manifest_path}")
        return 0
    except BaseException as exc:
        # Reconcile against candidate bytes as well as the in-memory journal. This
        # closes the tiny interruption window between os.replace returning and the
        # changed-path journal being updated, without treating unrelated user edits
        # as migration changes.
        for relative in MANAGED_FILES:
            try:
                current = (root / relative).read_bytes()
            except OSError:
                continue
            if (
                current == candidates[relative]
                and current != snapshot[relative]
                and relative not in changed_paths
            ):
                changed_paths.append(relative)
        restored: list[str] = []
        restore_failures: list[dict[str, str]] = []
        if changed_paths:
            restored, restore_failures = restore_changed(root, snapshot, changed_paths)
        point = exc.point if isinstance(exc, InjectedFailure) else manifest["phase"]
        manifest["phase"] = "rollback_failed" if restore_failures else "failed"
        manifest["changed_paths"] = list(changed_paths)
        manifest["restored_paths"] = restored
        manifest["restore_failures"] = restore_failures
        manifest["failure"] = {
            "point": point,
            "message": str(exc),
            "kind": (
                "structural_conflict"
                if isinstance(exc, StructuralConflict)
                else "injected_failure"
                if isinstance(exc, InjectedFailure)
                else "migration_error"
            ),
        }
        manifest["failed_at"] = datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        try:
            write_manifest(manifest_path, manifest)
        except OSError as manifest_exc:
            print(f"ERROR could not update migration manifest: {manifest_exc}", file=sys.stderr)
        print(f"ERROR migration failed: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, StructuralConflict) else 1
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def structural_error(message: str) -> NoReturn:
    print(f"ERROR {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    args = parse_args()
    root = args.project_dir.expanduser().resolve()
    try:
        snapshot = read_snapshot(root)
        status = inspect_snapshot(snapshot)
    except (MigrationError, OSError) as exc:
        structural_error(str(exc))

    if status == "compatible":
        try:
            require_valid_project(root, StructuralConflict)
        except (MigrationError, OSError) as exc:
            structural_error(str(exc))
        print(f"COMPATIBLE schema 2: {root}")
        return 0
    if args.check:
        print(f"MIGRATABLE legacy project: {root}")
        return 3
    return apply_migration(root, snapshot, args.simulate_failure)


if __name__ == "__main__":
    raise SystemExit(main())
