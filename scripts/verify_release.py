#!/usr/bin/env python3
"""Verify CYZ release archives and distribution metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "cyz-edu-research"
ROOT = f"{PACKAGE}/"
MANIFEST_NAME = f"{ROOT}release-manifest.json"
REQUIRED = {
    f"{ROOT}VERSION",
    f"{ROOT}CHANGELOG.md",
    f"{ROOT}LICENSE",
    f"{ROOT}THIRD_PARTY_NOTICES.md",
    f"{ROOT}third_party/qu-ai-wei-LICENSE.txt",
    f"{ROOT}dependencies.lock.json",
    f"{ROOT}plugin.json",
    f"{ROOT}SKILL.md",
    MANIFEST_NAME,
}
FORBIDDEN_SUFFIXES = {
    ".pyc": "forbidden .pyc bytecode",
    ".pyo": "forbidden .pyo bytecode",
    ".pdf": "forbidden PDF",
    ".pt": "forbidden model weight",
    ".pth": "forbidden model weight",
    ".onnx": "forbidden model weight",
    ".safetensors": "forbidden model weight",
    ".ckpt": "forbidden model weight",
    ".gguf": "forbidden model weight",
    ".bin": "forbidden model weight",
}
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".toml",
    ".ini",
    ".cfg",
}
PERSONAL_PATHS = (
    re.compile(r"(?i)\b[a-z]:[\\/]Users[\\/][^\\/\s]+"),
    re.compile(r"(?i)(?:^|[\s'\"(])/(?:Users|home)/[^/\s]+"),
)
TOKEN_PATTERNS = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~-]{20,}\b"),
)
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
DEPENDENCY_USE = re.compile(r"`([a-z][a-z0-9-]+)`\s+[Ss]kill dependency\b")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and not name.startswith(("/", "\\"))
        and not re.match(r"^[A-Za-z]:", name)
        and ".." not in path.parts
        and "\\" not in name
    )


def read_archive(archive_path: Path) -> tuple[dict[str, bytes], list[str]]:
    errors: list[str] = []
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(archive_path) as archive:
            seen: set[str] = set()
            for item in archive.infolist():
                if item.filename in seen:
                    errors.append(f"duplicate archive path: {item.filename}")
                    continue
                seen.add(item.filename)
                if not safe_member_name(item.filename):
                    errors.append(f"unsafe archive path: {item.filename}")
                    continue
                if item.is_dir():
                    continue
                if not item.filename.startswith(ROOT):
                    errors.append(f"archive member outside package root: {item.filename}")
                files[item.filename] = archive.read(item)
    except (OSError, zipfile.BadZipFile) as exc:
        return {}, [f"cannot read archive: {exc}"]
    return files, errors


def verify_manifest(files: dict[str, bytes]) -> tuple[dict[str, object] | None, list[str]]:
    if MANIFEST_NAME not in files:
        return None, [f"missing required file: {MANIFEST_NAME}"]
    try:
        manifest = json.loads(files[MANIFEST_NAME].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"invalid release manifest: {exc}"]
    errors: list[str] = []
    if manifest.get("schemaVersion") != 1 or manifest.get("package") != PACKAGE:
        errors.append("invalid release manifest identity")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        return manifest, errors + ["release manifest files must be a list"]
    expected = set(files) - {MANIFEST_NAME}
    listed: dict[str, dict[str, object]] = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append("invalid release manifest file entry")
            continue
        name = item["path"]
        if name in listed:
            errors.append(f"duplicate manifest path: {name}")
        listed[name] = item
    if set(listed) != expected:
        missing = sorted(expected - set(listed))
        extra = sorted(set(listed) - expected)
        errors.append(f"manifest path mismatch: missing={missing}, extra={extra}")
    for name in sorted(expected & set(listed)):
        data = files[name]
        item = listed[name]
        if item.get("bytes") != len(data):
            errors.append(f"size mismatch: {name}")
        if item.get("sha256") != sha256_bytes(data):
            errors.append(f"hash mismatch: {name}")
    return manifest, errors


def text_files(files: dict[str, bytes]):
    for name, data in files.items():
        if PurePosixPath(name).suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            yield name, data.decode("utf-8")
        except UnicodeDecodeError:
            yield name, ""


def verify_relative_links(files: dict[str, bytes]) -> list[str]:
    errors: list[str] = []
    names = set(files)
    for name, text in text_files(files):
        if not name.endswith(".md") or f"{ROOT}templates/" in name:
            continue
        base = PurePosixPath(name).parent
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split()[0].strip("<>")
            parsed = urllib.parse.urlsplit(target)
            if parsed.scheme or target.startswith(("#", "/")):
                continue
            decoded = urllib.parse.unquote(parsed.path)
            if not decoded:
                continue
            resolved_parts: list[str] = []
            for part in (base / decoded).parts:
                if part == ".":
                    continue
                if part == "..":
                    if resolved_parts:
                        resolved_parts.pop()
                    continue
                resolved_parts.append(part)
            resolved = "/".join(resolved_parts)
            if resolved not in names:
                errors.append(f"broken relative link in {name}: {target}")
    return errors


def verify_dependencies(files: dict[str, bytes]) -> list[str]:
    lock_name = f"{ROOT}dependencies.lock.json"
    skill_name = f"{ROOT}SKILL.md"
    try:
        lock = json.loads(files[lock_name].decode("utf-8"))
        declared = {
            item["name"]
            for item in lock.get("dependencies", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        skill = files[skill_name].decode("utf-8")
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"cannot validate dependencies: {exc}"]
    required = {"humanizer-zh", "humanizer", "mineru"}
    used = set(DEPENDENCY_USE.findall(skill)) | required
    errors = [
        f"undeclared dependency: {name}" for name in sorted(used - declared)
    ]
    if declared - required:
        errors.extend(
            f"unexpected declared dependency: {name}" for name in sorted(declared - required)
        )
    return errors


def verify_archive(archive_path: Path) -> list[str]:
    archive_path = Path(archive_path)
    files, errors = read_archive(archive_path)
    if not files:
        return errors or ["archive is empty"]
    for required in sorted(REQUIRED - set(files)):
        errors.append(f"missing required file: {required.removeprefix(ROOT)}")
    manifest, manifest_errors = verify_manifest(files)
    errors.extend(manifest_errors)

    for name in sorted(files):
        suffix = PurePosixPath(name).suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES:
            errors.append(f"{FORBIDDEN_SUFFIXES[suffix]}: {name}")
        if any(part == "__pycache__" for part in PurePosixPath(name).parts):
            errors.append(f"forbidden Python cache path: {name}")

    for name, text in text_files(files):
        if not text and files[name]:
            errors.append(f"text file is not UTF-8: {name}")
            continue
        if any(pattern.search(text) for pattern in PERSONAL_PATHS):
            errors.append(f"absolute personal path found: {name}")
        if any(pattern.search(text) for pattern in TOKEN_PATTERNS):
            errors.append(f"token-like material found: {name}")

    if manifest is not None:
        try:
            version = files[f"{ROOT}VERSION"].decode("utf-8").strip()
            plugin = json.loads(files[f"{ROOT}plugin.json"].decode("utf-8"))
            versions = {version, str(plugin.get("version")), str(manifest.get("version"))}
            if len(versions) != 1:
                errors.append(
                    "version mismatch: VERSION, plugin.json, and release manifest disagree"
                )
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"cannot validate version: {exc}")

    errors.extend(verify_relative_links(files))
    errors.extend(verify_dependencies(files))
    return errors


def parse_sums(path: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {}, [f"cannot read SHA256SUMS.txt: {exc}"]
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if not match:
            errors.append(f"invalid checksum line: {line!r}")
            continue
        result[match.group(2)] = match.group(1)
    return result, errors


def verify_distribution(dist_dir: Path) -> list[str]:
    dist_dir = Path(dist_dir)
    errors: list[str] = []
    sums, sum_errors = parse_sums(dist_dir / "SHA256SUMS.txt")
    errors.extend(sum_errors)
    archives = sorted(dist_dir.glob(f"{PACKAGE}-*.zip"))
    if len(archives) != 1:
        errors.append(f"expected exactly one workflow ZIP, found {len(archives)}")
    if list(dist_dir.glob("mineru-desk-skill-*.zip")):
        errors.append("MinerU ZIP prohibited: redistribution license unconfirmed")
    if not (dist_dir / "acceptance-report.md").is_file():
        errors.append("missing acceptance-report.md")
    for archive in archives:
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        expected = sums.get(archive.name)
        if expected != actual:
            errors.append(f"distribution hash mismatch: {archive.name}")
        errors.extend(verify_archive(archive))
    if set(sums) != {path.name for path in archives}:
        errors.append("SHA256SUMS.txt entries do not match distribution archives")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    errors = verify_distribution(args.dist)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 2
    print("RELEASE_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
