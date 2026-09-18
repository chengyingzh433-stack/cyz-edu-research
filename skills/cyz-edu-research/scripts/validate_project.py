#!/usr/bin/env python3
"""Validate the minimum structure of a CYZ education-research project."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


REQUIRED_FILES = (
    "00-项目状态.md",
    "01-研究起点与问题.md",
    "02-文献/00-检索记录.md",
    "02-文献/01-筛选记录.md",
    "02-文献/转换缓存/00-缓存索引.md",
    "03-文献证据矩阵.md",
    "04-综述与研究缺口.md",
    "05-研究方案.md",
    "06-数据与分析.md",
    "07-论文草稿/学术语言打磨报告.md",
    "08-审查与修改记录.md",
)

REQUIRED_DIRS = (
    "02-文献/文献卡",
    "02-文献/转换缓存",
    "02-文献/核心文献精读",
    "07-论文草稿",
    "09-正式输出",
)

ALLOWED_STAGES = {f"S{i}" for i in range(9)}
ALLOWED_GATE_STATUS = {"pending", "in_progress", "blocked", "passed"}
ALLOWED_LANGUAGE_PASS_STATUS = {
    "not_applicable",
    "user_skipped",
    "not_started",
    "blocked",
    "in_progress",
    "passed_with_notes",
    "passed",
}
FINAL_LANGUAGE_PASS_STATUS = {
    "not_applicable",
    "user_skipped",
    "passed_with_notes",
    "passed",
}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
CACHE_REQUIRED = (
    "paper.md",
    "conversion_manifest.json",
    "source_map.json",
    "conversion_report.md",
)


def frontmatter_value(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*[\"']?([^\"'\n]+)", text)
    return match.group(1).strip() if match else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    args = parser.parse_args()
    root = args.project_dir.expanduser().resolve()

    errors: list[str] = []
    warnings: list[str] = []
    stage: str | None = None
    gate: str | None = None
    state_language_status: str | None = None

    if not root.is_dir():
        print(f"ERROR project directory does not exist: {root}", file=sys.stderr)
        return 2

    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file():
            errors.append(f"missing file: {relative}")
        elif path.stat().st_size == 0:
            errors.append(f"empty file: {relative}")

    for relative in REQUIRED_DIRS:
        if not (root / relative).is_dir():
            errors.append(f"missing directory: {relative}")

    cache_root = root / "02-文献" / "转换缓存"
    if cache_root.is_dir():
        forbidden_txt = list(cache_root.rglob("*.txt"))
        for path in forbidden_txt:
            errors.append(f"TXT is forbidden in canonical cache: {path.relative_to(root)}")
        for cache_dir in sorted(path for path in cache_root.iterdir() if path.is_dir()):
            for filename in CACHE_REQUIRED:
                path = cache_dir / filename
                if not path.is_file() or path.stat().st_size == 0:
                    errors.append(f"invalid cache {cache_dir.name}: missing or empty {filename}")
            if not (cache_dir / "assets").is_dir():
                errors.append(f"invalid cache {cache_dir.name}: missing assets directory")
            manifest_path = cache_dir / "conversion_manifest.json"
            source_map_path = cache_dir / "source_map.json"
            paper_path = cache_dir / "paper.md"
            if manifest_path.is_file() and source_map_path.is_file() and paper_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"invalid cache {cache_dir.name}: malformed JSON ({exc})")
                    continue
                for field in ("pdf_sha256", "conversion_mode", "dpi", "converter_schema"):
                    if field not in manifest:
                        errors.append(f"invalid cache {cache_dir.name}: manifest lacks {field}")
                page_count = manifest.get("page_count")
                pages = source_map.get("pages")
                headings = re.findall(
                    r"(?m)^## PDF 第 (\d+) 页$",
                    paper_path.read_text(encoding="utf-8"),
                )
                if not isinstance(page_count, int) or not isinstance(pages, list):
                    errors.append(f"invalid cache {cache_dir.name}: invalid page metadata")
                elif len(pages) != page_count or len(headings) != page_count:
                    errors.append(f"invalid cache {cache_dir.name}: page counts disagree")

    state_path = root / "00-项目状态.md"
    if state_path.is_file():
        text = state_path.read_text(encoding="utf-8")
        if "cyz_edu_research_project: true" not in text:
            errors.append("project marker missing from 00-项目状态.md")
        stage = frontmatter_value(text, "current_stage")
        gate = frontmatter_value(text, "gate_status")
        state_language_status = frontmatter_value(text, "academic_language_pass_status")
        if stage not in ALLOWED_STAGES:
            errors.append(f"invalid current_stage: {stage!r}")
        if gate not in ALLOWED_GATE_STATUS:
            errors.append(f"invalid gate_status: {gate!r}")
        if state_language_status is None:
            warnings.append(
                "state lacks academic_language_pass_status; add it when the language pass is used"
            )
        elif state_language_status not in ALLOWED_LANGUAGE_PASS_STATUS:
            errors.append(
                "invalid academic_language_pass_status: "
                f"{state_language_status!r}"
            )
        for heading in ("## 当前阶段", "## 待核验与阻塞项", "## 下一步"):
            if heading not in text:
                errors.append(f"state heading missing: {heading}")
        if "## 学术语言打磨" not in text:
            warnings.append(
                "state lacks academic-language-pass status; run init_project.py "
                "with --allow-existing and add the status section when resuming"
            )

    language_report = root / "07-论文草稿" / "学术语言打磨报告.md"
    if language_report.is_file():
        report_text = language_report.read_text(encoding="utf-8")
        if "cyz_academic_humanization_report: true" not in report_text:
            errors.append("language report marker missing")
        for heading in ("## 基本信息", "## 语义锁检查", "## 人工语义回归", "## 最终结论"):
            if heading not in report_text:
                errors.append(f"language report heading missing: {heading}")
        language_status = frontmatter_value(report_text, "status")
        if language_status not in ALLOWED_LANGUAGE_PASS_STATUS:
            errors.append(f"invalid academic-language-pass status: {language_status!r}")

        if stage == "S8" and gate == "passed":
            if language_status not in FINAL_LANGUAGE_PASS_STATUS:
                errors.append(
                    "S8 cannot pass while academic-language-pass status is "
                    f"{language_status!r}"
                )
            if state_language_status not in FINAL_LANGUAGE_PASS_STATUS:
                errors.append(
                    "S8 cannot pass while project-state academic language status is "
                    f"{state_language_status!r}"
                )
            if (
                state_language_status is not None
                and state_language_status != language_status
            ):
                errors.append(
                    "project state language-pass status does not match report status"
                )
            if language_status in {"passed", "passed_with_notes"}:
                baseline_path_value = frontmatter_value(report_text, "baseline_path")
                master_path_value = frontmatter_value(report_text, "master_path")
                baseline_hash = frontmatter_value(report_text, "baseline_sha256")
                reviewed_hash = frontmatter_value(report_text, "reviewed_sha256")
                export_hash = frontmatter_value(report_text, "export_sha256")

                for key, value in (
                    ("baseline_sha256", baseline_hash),
                    ("reviewed_sha256", reviewed_hash),
                    ("export_sha256", export_hash),
                ):
                    if value is None or not SHA256_RE.fullmatch(value):
                        errors.append(f"final language report has invalid {key}")

                if reviewed_hash and export_hash and reviewed_hash.lower() != export_hash.lower():
                    errors.append(
                        "current export hash differs from reviewed post-language-pass hash"
                    )

                for key, value, expected_hash in (
                    ("baseline_path", baseline_path_value, baseline_hash),
                    ("master_path", master_path_value, reviewed_hash),
                ):
                    if not value:
                        errors.append(f"final language report lacks {key}")
                        continue
                    candidate = (root / value).resolve()
                    try:
                        candidate.relative_to(root)
                    except ValueError:
                        errors.append(f"language report {key} escapes project root: {value}")
                        continue
                    if not candidate.is_file():
                        errors.append(f"language report {key} does not exist: {value}")
                    elif expected_hash and SHA256_RE.fullmatch(expected_hash):
                        actual_hash = sha256_file(candidate)
                        if actual_hash.lower() != expected_hash.lower():
                            errors.append(
                                f"language report {key} hash differs from current file"
                            )

    matrix = root / "03-文献证据矩阵.md"
    if matrix.is_file():
        matrix_text = matrix.read_text(encoding="utf-8")
        if "证据状态" not in matrix_text or "原文位置" not in matrix_text:
            warnings.append("evidence matrix lacks evidence-status or source-locator columns")

    for item in errors:
        print(f"ERROR {item}")
    for item in warnings:
        print(f"WARN {item}")

    if errors:
        print(f"FAIL {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1

    print(f"PASS {root} ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
