#!/usr/bin/env python3
"""Build a deterministic, privacy-safe CYZ Skill release archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable


PACKAGE = "cyz-edu-research"
MANIFEST_NAME = f"{PACKAGE}/release-manifest.json"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repository_commit(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def public_dependency_lock(lock_path: Path) -> bytes:
    """Remove machine-specific installation evidence from the public lock."""
    source = json.loads(lock_path.read_text(encoding="utf-8"))
    dependencies = []
    for item in source.get("dependencies", []):
        dependencies.append(
            {
                key: item.get(key)
                for key in (
                    "name",
                    "version",
                    "versionStatus",
                    "versionEvidence",
                    "upstream",
                    "sourceStatus",
                    "license",
                    "licenseStatus",
                )
            }
            | {"installedSeparately": True}
        )
    public = {
        "schemaVersion": source.get("schemaVersion", 1),
        "languageRouting": source.get("languageRouting", {}),
        "dependencies": dependencies,
        "releasePolicy": {
            "environmentSpecificPathsExcluded": True,
            "dependenciesBundled": False,
            "mineruRedistributionAllowed": False,
        },
    }
    return (json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def iter_source_files(source: Path) -> Iterable[Path]:
    for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        relative = path.relative_to(source)
        if not path.is_file():
            continue
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        yield path


def collect_package_files(repo_root: Path, version: str) -> dict[str, bytes]:
    source = repo_root / "skills" / PACKAGE
    if not source.is_dir():
        raise ValueError(f"missing Skill source: {source}")
    files: dict[str, bytes] = {}
    for path in iter_source_files(source):
        relative = path.relative_to(source).as_posix()
        files[f"{PACKAGE}/{relative}"] = path.read_bytes()

    overlays = {
        "VERSION": repo_root / "VERSION",
        "CHANGELOG.md": repo_root / "CHANGELOG.md",
        "THIRD_PARTY_NOTICES.md": repo_root / "THIRD_PARTY_NOTICES.md",
        "docs/install-upgrade-rollback.md": repo_root / "docs" / "install-upgrade-rollback.md",
        "docs/acceptance/workflow-acceptance.md": (
            repo_root / "docs" / "acceptance" / "workflow-acceptance.md"
        ),
    }
    for relative, source_path in overlays.items():
        if not source_path.is_file():
            raise ValueError(f"missing release input: {source_path}")
        files[f"{PACKAGE}/{relative}"] = source_path.read_bytes()
    files[f"{PACKAGE}/dependencies.lock.json"] = public_dependency_lock(
        repo_root / "dependencies.lock.json"
    )

    plugin = json.loads(files[f"{PACKAGE}/plugin.json"].decode("utf-8"))
    if plugin.get("version") != version:
        raise ValueError(
            f"version mismatch: VERSION={version}, plugin.json={plugin.get('version')}"
        )
    return files


def release_manifest(
    files: dict[str, bytes], version: str, source_commit: str
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "package": PACKAGE,
        "version": version,
        "sourceCommit": source_commit,
        "manifestExcludes": [MANIFEST_NAME],
        "files": [
            {
                "path": name,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
            for name, data in sorted(files.items())
        ],
    }


def write_deterministic_zip(destination: Path, files: dict[str, bytes]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def build_release(
    repo_root: Path, dist_dir: Path, *, source_commit: str | None = None
) -> dict[str, str]:
    repo_root = repo_root.resolve()
    dist_dir = dist_dir.resolve()
    version = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
    if not SEMVER.fullmatch(version):
        raise ValueError(f"invalid VERSION: {version!r}")
    commit = source_commit or repository_commit(repo_root)
    files = collect_package_files(repo_root, version)
    manifest = release_manifest(files, version, commit)
    files[MANIFEST_NAME] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    archive = dist_dir / f"{PACKAGE}-{version}.zip"
    write_deterministic_zip(archive, files)
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()

    sums = dist_dir / "SHA256SUMS.txt"
    sums.write_text(f"{archive_hash}  {archive.name}\n", encoding="utf-8", newline="\n")
    report = dist_dir / "acceptance-report.md"
    report.write_text(
        f"# CYZ Education Research {version} Release Acceptance\n\n"
        f"- Version: `{version}`\n"
        f"- Source commit: `{commit}`\n"
        f"- Archive: `{archive.name}`\n"
        f"- SHA-256: `{archive_hash}`\n"
        f"- Manifested payload files: {len(manifest['files'])}\n"
        "- MinerU wrapper ZIP: not produced (redistribution license unconfirmed)\n"
        "- Required next gate: run `scripts/verify_release.py --dist dist` and the full test suite.\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "archive": str(archive),
        "checksums": str(sums),
        "report": str(report),
        "version": version,
        "sha256": archive_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--dist", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    dist = args.dist.resolve() if args.dist else repo_root / "dist"
    try:
        result = build_release(repo_root, dist)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR {exc}")
        return 2
    print(f"BUILT {result['archive']}")
    print(f"SHA256 {result['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
