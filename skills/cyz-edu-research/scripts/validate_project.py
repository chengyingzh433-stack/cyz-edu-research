#!/usr/bin/env python3
"""Validate the minimum structure of a CYZ education-research project."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


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
ALLOWED_ENTRY_MODE = {"discovery", "topic", "materials"}
ALLOWED_IDEA_MODE = {"discovery", "refinement"}
ALLOWED_IDEA_MATURITY = {
    "broad_interest",
    "tentative_topic",
    "method_first",
    "positioned_question",
    "study_plan",
}
ALLOWED_IDEA_STATUS = {
    "not_started",
    "exploring",
    "refining",
    "needs_verification",
    "ready",
    "blocked",
}
ALLOWED_GATE_STATUS = {"pending", "in_progress", "passed", "failed", "blocked"}
SCHEMA2_REQUIRED_FIELDS = (
    "entry_mode",
    "workflow_schema",
    "idea_mode",
    "idea_maturity",
    "idea_status",
    "idea_revision",
    "idea_workspace",
    "current_decision",
    "current_evidence",
    "handoff_path",
    "current_stage",
    "gate_status",
)
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


def clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def parse_frontmatter(text: str) -> tuple[dict[str, str], set[str], list[str]]:
    if text.startswith("\ufeff"):
        text = text[1:]
    match = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not match:
        return {}, set(), []
    values: dict[str, str] = {}
    duplicates: set[str] = set()
    malformed: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        field = re.match(
            r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line
        )
        if not field:
            malformed.append(stripped)
            continue
        key, raw_value = field.groups()
        if key in values:
            duplicates.add(key)
        values[key] = clean_scalar(raw_value)
    return values, duplicates, malformed


def frontmatter_value(text: str, key: str) -> str | None:
    values, _, _ = parse_frontmatter(text)
    return values.get(key)


def parse_managed_records(
    text: str, kind: str
) -> list[tuple[dict[str, str], set[str]]]:
    pattern = re.compile(
        rf"(?ms)<!-- cyz:{re.escape(kind)}-record:start -->\s*(.*?)\s*"
        rf"<!-- cyz:{re.escape(kind)}-record:end -->"
    )
    records = []
    for block in pattern.findall(text):
        record: dict[str, str] = {}
        duplicates: set[str] = set()
        for key, value in re.findall(
            r"(?m)^\s*-\s*([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", block
        ):
            if key in record:
                duplicates.add(key)
            record[key] = clean_scalar(value)
        records.append((record, duplicates))
    return records


def complete_record(record: dict[str, str], required: set[str]) -> bool:
    if not required <= record.keys():
        return False
    def is_placeholder(value: str) -> bool:
        if "###" in value or value == "YYYY-MM-DD":
            return True
        return bool(
            re.fullmatch(
                r"待(?:填写|确认|核验|记录|补充|生成|核对)(?:[（(].*[）)])?",
                value,
            )
        )

    return all(record[key] and not is_placeholder(record[key]) for key in required)


def resolve_project_link(root: Path, value: str) -> tuple[Path | None, str]:
    path_text, _, anchor = value.partition("#")
    if not path_text or re.match(r"^[a-z][a-z0-9+.-]*://", path_text, re.I):
        return None, anchor
    candidate = (root / path_text).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, anchor
    return candidate, anchor


def anchor_exists(path: Path, anchor: str) -> bool:
    if not anchor:
        return True
    wanted = anchor.strip().lower()
    for heading in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", path.read_text(encoding="utf-8")):
        normalized = re.sub(r"\s+", "-", heading.strip().lower())
        if normalized == wanted:
            return True
    return False


def source_locator_exists(root: Path, value: str) -> bool:
    if re.match(r"^https?://", value, re.I):
        if any(character.isspace() for character in value):
            return False
        try:
            parsed = urlsplit(value)
            parsed.port
        except ValueError:
            return False
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)
    path, anchor = resolve_project_link(root, value)
    return bool(
        path is not None
        and path.is_file()
        and anchor
        and anchor_exists(path, anchor)
    )


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
        state_values, duplicate_state_keys, malformed_state_lines = parse_frontmatter(text)
        for key in sorted(duplicate_state_keys):
            errors.append(f"duplicate frontmatter key: {key}")
        for line in malformed_state_lines:
            errors.append(f"malformed frontmatter line: {line}")
        if state_values.get("cyz_edu_research_project") != "true":
            errors.append("project marker missing from 00-项目状态.md")
        stage = frontmatter_value(text, "current_stage")
        gate = frontmatter_value(text, "gate_status")
        workflow_schema = frontmatter_value(text, "workflow_schema")
        entry_mode = frontmatter_value(text, "entry_mode")
        idea_mode = frontmatter_value(text, "idea_mode")
        idea_maturity = frontmatter_value(text, "idea_maturity")
        idea_status = frontmatter_value(text, "idea_status")
        state_language_status = frontmatter_value(text, "academic_language_pass_status")
        if stage not in ALLOWED_STAGES:
            errors.append(f"invalid current_stage: {stage!r}")
        if gate not in ALLOWED_GATE_STATUS:
            errors.append(f"invalid gate_status: {gate!r}")
        if workflow_schema is None:
            warnings.append("legacy project lacks workflow_schema; migration is available")
        elif workflow_schema != "2":
            errors.append(f"invalid workflow_schema: {workflow_schema!r}")
        else:
            values = {key: frontmatter_value(text, key) for key in SCHEMA2_REQUIRED_FIELDS}
            for key, value in values.items():
                if value is None:
                    errors.append(f"schema 2 lacks required field: {key}")

            if entry_mode not in ALLOWED_ENTRY_MODE:
                errors.append(f"invalid entry_mode: {entry_mode!r}")
            if idea_mode not in ALLOWED_IDEA_MODE:
                errors.append(f"invalid idea_mode: {idea_mode!r}")
            if idea_maturity not in ALLOWED_IDEA_MATURITY:
                errors.append(f"invalid idea_maturity: {idea_maturity!r}")
            if idea_status not in ALLOWED_IDEA_STATUS:
                errors.append(f"invalid idea_status: {idea_status!r}")

            revision = frontmatter_value(text, "idea_revision")
            if revision is not None and (not revision.isdigit() or int(revision) < 1):
                errors.append(f"invalid idea_revision: {revision!r}")

            idea_path_value = frontmatter_value(text, "idea_workspace")
            idea_canvas_text: str | None = None
            idea_path, _ = resolve_project_link(root, idea_path_value or "")
            if idea_path is None or not idea_path.is_file():
                errors.append(f"idea_workspace does not exist: {idea_path_value!r}")
            else:
                idea_text = idea_path.read_text(encoding="utf-8")
                start_count = idea_text.count("<!-- cyz:idea-canvas:start -->")
                end_count = idea_text.count("<!-- cyz:idea-canvas:end -->")
                if start_count != 1 or end_count != 1:
                    errors.append("idea-canvas markers must occur exactly once")
                elif idea_text.index("<!-- cyz:idea-canvas:start -->") > idea_text.index(
                    "<!-- cyz:idea-canvas:end -->"
                ):
                    errors.append("idea-canvas markers are out of order")
                else:
                    start_marker = "<!-- cyz:idea-canvas:start -->"
                    end_marker = "<!-- cyz:idea-canvas:end -->"
                    start_index = idea_text.index(start_marker) + len(start_marker)
                    end_index = idea_text.index(end_marker)
                    idea_canvas_text = idea_text[start_index:end_index]
                handoff_section = re.search(
                    r"(?ms)^### 交接区\s*$\n(.*?)(?=^###\s|<!-- cyz:idea-canvas:end -->)",
                    idea_text,
                )
                if handoff_section:
                    for destination in re.findall(
                        r"\[[^\]]+\]\(([^)]+)\)", handoff_section.group(1)
                    ):
                        if re.match(r"^[a-z][a-z0-9+.-]*://", destination, re.I):
                            continue
                        if destination.startswith("#"):
                            linked_path, linked_anchor = idea_path, destination[1:]
                        else:
                            linked_path, linked_anchor = resolve_project_link(
                                root, destination
                            )
                        if (
                            linked_path is None
                            or not linked_path.is_file()
                            or not anchor_exists(linked_path, linked_anchor)
                        ):
                            errors.append(
                                f"handoff link does not exist: {destination!r}"
                            )

            handoff_value = frontmatter_value(text, "handoff_path")
            handoff_path, handoff_anchor = resolve_project_link(root, handoff_value or "")
            if (
                handoff_path is None
                or not handoff_path.is_file()
                or not anchor_exists(handoff_path, handoff_anchor)
            ):
                errors.append(f"handoff_path does not exist: {handoff_value!r}")

            if idea_status == "ready":
                current_decision = frontmatter_value(text, "current_decision")
                current_evidence = frontmatter_value(text, "current_evidence")
                if not current_decision:
                    errors.append("ready idea lacks current_decision")
                elif idea_path is not None and idea_path.is_file():
                    decision_required = {
                        "decision_id",
                        "idea_revision",
                        "question",
                        "answer",
                        "source",
                        "decided_at",
                        "affects",
                    }
                    decisions = parse_managed_records(idea_canvas_text or "", "decision")
                    for _, duplicate_fields in decisions:
                        for key in sorted(duplicate_fields):
                            errors.append(f"duplicate decision record field: {key}")
                    if not any(
                        complete_record(record, decision_required)
                        and not duplicate_fields
                        and record["decision_id"] == current_decision
                        and record["idea_revision"] == revision
                        for record, duplicate_fields in decisions
                    ):
                        errors.append(
                            "current_decision does not reference a decision record "
                            f"for idea_revision {revision}"
                        )
                if not current_evidence:
                    errors.append("ready idea lacks current_evidence")
                elif idea_path is not None and idea_path.is_file():
                    evidence_required = {
                        "evidence_id",
                        "idea_revision",
                        "claim_id",
                        "source_type",
                        "source_locator",
                        "access_level",
                        "verification_status",
                        "recorded_at",
                    }
                    evidence_records = parse_managed_records(
                        idea_canvas_text or "", "evidence"
                    )
                    for _, duplicate_fields in evidence_records:
                        for key in sorted(duplicate_fields):
                            errors.append(f"duplicate evidence record field: {key}")
                    if not any(
                        complete_record(record, evidence_required)
                        and not duplicate_fields
                        and record["evidence_id"] == current_evidence
                        and record["idea_revision"] == revision
                        and source_locator_exists(root, record["source_locator"])
                        for record, duplicate_fields in evidence_records
                    ):
                        errors.append(
                            "current_evidence does not reference an evidence record "
                            f"for idea_revision {revision}"
                        )
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

            resolved_language_paths: dict[str, Path] = {}
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
                resolved_language_paths[key] = candidate
                if candidate == language_report.resolve():
                    errors.append(f"language report {key} must be separate from the report")
                if not candidate.is_file():
                    errors.append(f"language report {key} does not exist: {value}")
                elif expected_hash and SHA256_RE.fullmatch(expected_hash):
                    actual_hash = sha256_file(candidate)
                    if actual_hash.lower() != expected_hash.lower():
                        errors.append(
                            f"language report {key} hash differs from current file"
                        )

            if (
                resolved_language_paths.get("baseline_path")
                == resolved_language_paths.get("master_path")
                and "baseline_path" in resolved_language_paths
            ):
                errors.append("language report baseline_path and master_path must be different")

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
    print("NOTE 仅完成结构校验；学术价值仍需人工评审。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
