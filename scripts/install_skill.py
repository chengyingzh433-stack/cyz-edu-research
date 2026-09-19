#!/usr/bin/env python3
"""Install, upgrade, or roll back a verified CYZ Skill archive."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path


PACKAGE = "cyz-edu-research"
STATE_DIR = ".cyz-install"
BACKUP_DIR = ".cyz-backups"


def load_verifier():
    path = Path(__file__).with_name("verify_release.py")
    spec = importlib.util.spec_from_file_location("cyz_verify_release", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load verifier: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFY = load_verifier()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_manifest(root: Path) -> list[dict[str, object]]:
    if not root.is_dir():
        return []
    items: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if not path.is_file():
            continue
        if "__pycache__" in relative.parts or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        items.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return items


def state_path(skill_root: Path) -> Path:
    return skill_root / STATE_DIR / f"{PACKAGE}.json"


def read_state(skill_root: Path) -> dict[str, object] | None:
    path = state_path(skill_root)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def write_state(skill_root: Path, value: dict[str, object]) -> None:
    path = state_path(skill_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def backup_install(skill_root: Path, destination: Path) -> Path:
    backup_root = skill_root / BACKUP_DIR / PACKAGE
    backup_root.mkdir(parents=True, exist_ok=True)
    container = Path(tempfile.mkdtemp(prefix="backup-", dir=backup_root))
    snapshot = container / "snapshot"
    shutil.copytree(destination, snapshot)
    previous_state = state_path(skill_root)
    if previous_state.is_file():
        shutil.copy2(previous_state, container / "install-state.json")
    return snapshot


def safe_extract(archive_path: Path, staging_parent: Path) -> Path:
    staging = Path(tempfile.mkdtemp(prefix=".cyz-stage-", dir=staging_parent))
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for item in archive.infolist():
                if item.is_dir():
                    continue
                target = staging / Path(*Path(item.filename).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(item))
        extracted = staging / PACKAGE
        if not extracted.is_dir():
            raise ValueError(f"archive lacks {PACKAGE} root")
        return staging
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def replace_install(destination: Path, extracted: Path) -> None:
    retired = destination.parent / f".{PACKAGE}.retired-{uuid.uuid4().hex}"
    moved_old = False
    try:
        if destination.exists():
            destination.replace(retired)
            moved_old = True
        extracted.replace(destination)
    except Exception:
        if destination.exists() and not moved_old:
            shutil.rmtree(destination, ignore_errors=True)
        if moved_old and retired.exists() and not destination.exists():
            retired.replace(destination)
        raise
    finally:
        if retired.exists():
            shutil.rmtree(retired, ignore_errors=True)


def install_archive(
    archive_path: Path, skill_root: Path, *, allow_conflicts: bool = False
) -> dict[str, str]:
    archive_path = Path(archive_path).resolve()
    skill_root = Path(skill_root).resolve()
    errors = VERIFY.verify_archive(archive_path)
    if errors:
        raise ValueError("archive verification failed: " + "; ".join(errors))
    skill_root.mkdir(parents=True, exist_ok=True)
    destination = skill_root / PACKAGE
    previous_state = read_state(skill_root)
    backup: Path | None = None
    conflicts = False
    if destination.exists():
        backup = backup_install(skill_root, destination)
        current = tree_manifest(destination)
        recorded = previous_state.get("files") if previous_state else None
        conflicts = not isinstance(recorded, list) or current != recorded
        if conflicts and not allow_conflicts:
            return {
                "status": "conflict",
                "destination": str(destination),
                "backup": str(backup),
            }

    staging = safe_extract(archive_path, skill_root)
    try:
        extracted = staging / PACKAGE
        replace_install(destination, extracted)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    version = (destination / "VERSION").read_text(encoding="utf-8").strip()
    current_manifest = tree_manifest(destination)
    write_state(
        skill_root,
        {
            "schemaVersion": 1,
            "package": PACKAGE,
            "version": version,
            "archiveSha256": file_sha256(archive_path),
            "files": current_manifest,
        },
    )
    if backup is None:
        status = "installed"
    elif conflicts:
        status = "upgraded_with_conflicts"
    else:
        status = "upgraded"
    result = {"status": status, "destination": str(destination)}
    if backup is not None:
        result["backup"] = str(backup)
    return result


def rollback_install(skill_root: Path, backup: Path) -> dict[str, str]:
    skill_root = Path(skill_root).resolve()
    backup = Path(backup).resolve()
    allowed_root = (skill_root / BACKUP_DIR / PACKAGE).resolve()
    try:
        backup.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("backup must be inside the managed backup directory") from exc
    if backup.name != "snapshot" or not backup.is_dir():
        raise ValueError(f"invalid backup snapshot: {backup}")
    destination = skill_root / PACKAGE
    staging = Path(tempfile.mkdtemp(prefix=".cyz-rollback-", dir=skill_root))
    try:
        candidate = staging / PACKAGE
        shutil.copytree(backup, candidate)
        replace_install(destination, candidate)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    version_file = destination / "VERSION"
    version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "unknown"
    write_state(
        skill_root,
        {
            "schemaVersion": 1,
            "package": PACKAGE,
            "version": version,
            "archiveSha256": None,
            "files": tree_manifest(destination),
            "restoredFrom": str(backup.relative_to(skill_root).as_posix()),
        },
    )
    return {
        "status": "rolled_back",
        "destination": str(destination),
        "backup": str(backup),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--archive", type=Path, required=True)
    install_parser.add_argument("--skill-root", type=Path, required=True)
    install_parser.add_argument("--allow-conflicts", action="store_true")
    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--skill-root", type=Path, required=True)
    rollback_parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "install":
            result = install_archive(
                args.archive, args.skill_root, allow_conflicts=args.allow_conflicts
            )
        else:
            result = rollback_install(args.skill_root, args.backup)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 3 if result["status"] == "conflict" else 0


if __name__ == "__main__":
    raise SystemExit(main())
