#!/usr/bin/env python3
"""Compare high-risk academic anchors before and after language revision."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata


PATTERNS: dict[str, re.Pattern[str]] = {
    "units": re.compile(
        r"(?<![A-Za-z0-9_.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
        r"\s*(?:%|‰|mg|kg|g|μg|ug|mL|ml|L|cm|mm|km|m|s|ms|h|Hz|kHz|MHz|"
        r"名|人|例|个|组|班|所|项|次|分|秒|分钟|小时|天|周|月|年)",
        re.IGNORECASE,
    ),
    "numbers": re.compile(
        r"(?<![A-Za-z0-9_.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
        r"(?:[eE][-+]?\d+)?(?:%|‰)?"
    ),
    "statistics": re.compile(
        r"(?<![A-Za-z])(?:p|t|F|r|R\^?2|R²|χ\^?2|χ²|β|OR|CI|M|SD)"
        r"\s*(?:=|<|>|≤|≥)\s*[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:%|‰)?"
    ),
    "doi": re.compile(r"(?i)\b10\.\d{4,9}/[-._;()/:A-Z0-9]+"),
    "urls": re.compile(r"(?i)https?://[^\s<>()\[\]{}，。；；]+"),
    "numeric_citations": re.compile(
        r"\[(?:\d+(?:\s*[-–—,，;；]\s*\d+)*)\]"
    ),
    "author_year_citations": re.compile(
        r"[（(][^（）()\n]{0,120}(?:19|20)\d{2}[a-z]?[^（）()\n]{0,80}[）)]"
    ),
    "figure_table_refs": re.compile(
        r"(?i)(?:图|表|附录|figure|table|appendix)\s*[A-Za-z]?\d+(?:[-–—.]\d+)?"
    ),
    "research_question_refs": re.compile(
        r"(?i)(?:RQ|研究问题)\s*[-：:]?\s*\d+"
    ),
    "placeholders": re.compile(
        r"\[(?:待[^\]\n]+|TODO|TBD|WIP|X{2,}|改写者补注[^\]\n]*)\]"
        r"|\{\{[^{}\n]+\}\}"
    ),
    "quotations": re.compile(
        r"“[^”\n]+”|‘[^’\n]+’|\"[^\"\n]+\"|'[^'\n]+'"
    ),
    "negations": re.compile(
        r"(?:未(?:发现|观察到|达到|显示|支持|通过|证明)?|不能|不可|并非|没有|"
        r"无显著|不显著|\b(?:not|no|never|neither|without)\b)",
        re.IGNORECASE,
    ),
}

BLOCKING_CATEGORIES = tuple(PATTERNS)
CATEGORY_PRIORITY = {name: index for index, name in enumerate(PATTERNS)}
HEADING_PATTERN = re.compile(r"(?m)^#{1,6}\s+.+$")
CANONICAL_DIRECTORY_HASH_ALGORITHM = (
    "relativePath<TAB>fileSha256<TAB>byteLength<LF>, sorted by relativePath, "
    "excluding __pycache__, *.pyc, and *.pyo; SHA-256 of UTF-8 bytes"
)
DEFAULT_DEPENDENCY_LOCK = Path(__file__).resolve().parents[3] / "dependencies.lock.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="Markdown file before language revision")
    parser.add_argument("after", type=Path, help="Markdown file after language revision")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path for a Markdown report; stdout is always used",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of Markdown",
    )
    parser.add_argument(
        "--allow-heading-change",
        action="store_true",
        help="Do not warn when Markdown headings change",
    )
    parser.add_argument(
        "--language",
        choices=("zh", "en"),
        help="Resolve the required language dependency for Chinese or English",
    )
    parser.add_argument(
        "--skills-root",
        type=Path,
        action="append",
        default=[],
        help="Skills directory to search; may be supplied more than once",
    )
    parser.add_argument(
        "--dependency-lock",
        type=Path,
        default=DEFAULT_DEPENDENCY_LOCK,
        help="Dependency lock to enforce (defaults to the repository lock)",
    )
    parser.add_argument(
        "--manual-review",
        type=Path,
        help="Saved JSON manual semantic-regression review tied to both file hashes",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_bytes().decode("utf-8")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_directory_metrics(root: Path) -> dict[str, object]:
    entries: list[tuple[str, str, int]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        if "__pycache__" in relative_path.parts or relative_path.suffix in {
            ".pyc",
            ".pyo",
        }:
            continue
        data = path.read_bytes()
        entries.append(
            (
                relative_path.as_posix(),
                hashlib.sha256(data).hexdigest(),
                len(data),
            )
        )
    entries.sort(key=lambda item: item[0])
    canonical = "".join(
        f"{relative}\t{file_hash}\t{size}\n"
        for relative, file_hash, size in entries
    ).encode("utf-8")
    return {
        "fileCount": len(entries),
        "bytes": sum(item[2] for item in entries),
        "directorySha256": hashlib.sha256(canonical).hexdigest(),
    }


def dependency_failure(message: str) -> ValueError:
    return ValueError(f"{message}; no fallback was used")


def frontmatter(text: str) -> str:
    match = re.match(r"\A(?:\ufeff)?---[ \t]*\r?\n(.*?)\r?\n---", text, re.S)
    return match.group(1) if match else ""


def frontmatter_scalar(text: str, key: str) -> str | None:
    match = re.search(
        rf"(?m)^{re.escape(key)}:\s*([^\r\n]+?)\s*$", frontmatter(text)
    )
    if not match:
        return None
    return match.group(1).strip().strip("\"'")


def metadata_version(text: str) -> str | None:
    block = frontmatter(text)
    match = re.search(
        r"(?m)^metadata:\s*$\r?\n(?:^[ \t]+.*(?:\r?\n|$))*?"
        r"^[ \t]+version:\s*([^\r\n]+?)\s*$",
        block,
    )
    return match.group(1).strip().strip("\"'") if match else None


def load_dependency_record(
    language: str, dependency_lock: Path
) -> tuple[str, dict[str, object]]:
    lock_path = dependency_lock.expanduser().resolve()
    if not lock_path.is_file():
        raise dependency_failure(f"dependency lock does not exist: {lock_path}")
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise dependency_failure(f"dependency lock is unreadable: {exc}") from exc
    if not isinstance(lock, dict) or lock.get("schemaVersion") != 1:
        raise dependency_failure("dependency lock must use schemaVersion 1")
    if lock.get("canonicalDirectoryHashAlgorithm") != CANONICAL_DIRECTORY_HASH_ALGORITHM:
        raise dependency_failure("dependency lock uses an unsupported hash algorithm")
    routing = lock.get("languageRouting")
    if not isinstance(routing, dict) or routing.get(language) not in {
        "humanizer-zh",
        "humanizer",
    }:
        raise dependency_failure(f"dependency lock has no valid route for {language}")
    dependency_name = str(routing[language])
    expected_name = {"zh": "humanizer-zh", "en": "humanizer"}[language]
    if dependency_name != expected_name:
        raise dependency_failure(
            f"dependency lock routes {language} to {dependency_name!r}, expected {expected_name!r}"
        )
    dependencies = lock.get("dependencies")
    if not isinstance(dependencies, list):
        raise dependency_failure("dependency lock lacks dependency records")
    matches = [
        item
        for item in dependencies
        if isinstance(item, dict) and item.get("name") == dependency_name
    ]
    if len(matches) != 1:
        raise dependency_failure(
            f"dependency lock must contain exactly one record for {dependency_name!r}"
        )
    return dependency_name, matches[0]


def verify_dependency_metadata(
    dependency_name: str, dependency_dir: Path, record: dict[str, object]
) -> None:
    skill_path = dependency_dir / "SKILL.md"
    skill_text = skill_path.read_bytes().decode("utf-8")
    if frontmatter_scalar(skill_text, "name") != dependency_name:
        raise dependency_failure(
            f"SKILL.md name does not match locked dependency {dependency_name!r}"
        )

    locked_version = record.get("version")
    version_status = record.get("versionStatus")
    actual_version = metadata_version(skill_text)
    if version_status == "declared":
        if not isinstance(locked_version, str) or actual_version != locked_version:
            raise dependency_failure(
                f"declared version does not match the dependency lock for {dependency_name!r}"
            )
    elif version_status == "unknown":
        if locked_version is not None or actual_version is not None:
            raise dependency_failure(
                f"unknown version status does not match {dependency_name!r} metadata"
            )
    else:
        raise dependency_failure(
            f"dependency lock has invalid version status for {dependency_name!r}"
        )

    upstream = record.get("upstream")
    if record.get("sourceStatus") != "declared-in-README" or not isinstance(
        upstream, str
    ):
        raise dependency_failure(
            f"dependency lock lacks declared README source for {dependency_name!r}"
        )
    readme_path = dependency_dir / "README.md"
    if not readme_path.is_file() or upstream not in readme_path.read_text(encoding="utf-8"):
        raise dependency_failure(
            "upstream source does not match the dependency lock for "
            f"{dependency_name!r}"
        )

    locked_license = record.get("license")
    license_status = record.get("licenseStatus")
    license_path = dependency_dir / "LICENSE"
    if locked_license != "MIT" or not license_path.is_file() or "MIT License" not in license_path.read_text(encoding="utf-8"):
        raise dependency_failure(
            f"license evidence does not match the dependency lock for {dependency_name!r}"
        )
    if license_status == "declared-in-SKILL-and-LICENSE":
        if frontmatter_scalar(skill_text, "license") != locked_license:
            raise dependency_failure(
                f"SKILL.md license does not match the dependency lock for {dependency_name!r}"
            )
    elif license_status != "declared-in-LICENSE":
        raise dependency_failure(
            f"dependency lock has invalid license status for {dependency_name!r}"
        )


def resolve_language_dependency(
    language: str, skills_roots: list[Path], dependency_lock: Path
) -> dict[str, object]:
    dependency_name, record = load_dependency_record(language, dependency_lock)
    installations = record.get("installations")
    if not isinstance(installations, list) or not installations:
        raise dependency_failure(
            f"dependency lock has no approved installations for {dependency_name!r}"
        )
    approved_metrics = [
        {
            "fileCount": item.get("fileCount"),
            "bytes": item.get("bytes"),
            "directorySha256": item.get("directorySha256"),
        }
        for item in installations
        if isinstance(item, dict)
    ]
    searched = []
    for root in skills_roots:
        dependency_dir = root.expanduser().resolve() / dependency_name
        searched.append(str(dependency_dir))
        skill_path = dependency_dir / "SKILL.md"
        if not skill_path.is_file():
            continue
        actual = canonical_directory_metrics(dependency_dir)
        if actual not in approved_metrics:
            raise dependency_failure(
                f"directory hash mismatch for locked dependency {dependency_name!r}"
            )
        verify_dependency_metadata(dependency_name, dependency_dir, record)
        dependency = {
            "language": language,
            "name": dependency_name,
            "path": str(skill_path),
            "skillSha256": hashlib.sha256(skill_path.read_bytes()).hexdigest(),
            "version": record.get("version"),
            "versionStatus": record.get("versionStatus"),
            "upstream": record.get("upstream"),
            "license": record.get("license"),
        }
        dependency.update(actual)
        return dependency
    raise dependency_failure(
        f"required language dependency '{dependency_name}' was not found in: "
        f"{', '.join(searched) or '(no skills roots supplied)'}"
    )


def load_manual_review(
    path: Path, before_sha256: str, after_sha256: str
) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schemaVersion",
        "reviewType",
        "baselineSha256",
        "outputSha256",
        "issue",
        "disposition",
        "reason",
    }
    if not isinstance(payload, dict) or not required <= payload.keys():
        raise ValueError("manual review lacks required fields")
    if payload["schemaVersion"] != 1:
        raise ValueError("manual review schemaVersion must be 1")
    if payload["reviewType"] != "manual-semantic-regression":
        raise ValueError("manual review has an invalid reviewType")
    if payload["baselineSha256"] != before_sha256:
        raise ValueError("manual review baselineSha256 does not match the baseline")
    if payload["outputSha256"] != after_sha256:
        raise ValueError("manual review outputSha256 does not match the output")
    if payload["disposition"] not in {"accepted", "rejected"}:
        raise ValueError("manual review disposition must be accepted or rejected")
    if (
        payload["issue"] == "correlation_to_causation"
        and payload["disposition"] != "rejected"
    ):
        raise ValueError("correlation_to_causation must be rejected")
    if not str(payload["issue"]).strip() or not str(payload["reason"]).strip():
        raise ValueError("manual review issue and reason must be non-empty")
    return payload


def normalize_token(token: str) -> str:
    token = unicodedata.normalize("NFKC", token)
    token = re.sub(r"\s+", " ", token).strip()
    token = token.rstrip(".,;:，。；：")
    return token


def extract(text: str, pattern: re.Pattern[str]) -> Counter[str]:
    return Counter(normalize_token(match.group(0)) for match in pattern.finditer(text))


def counter_delta(
    before: Counter[str], after: Counter[str]
) -> tuple[Counter[str], Counter[str]]:
    return before - after, after - before


def counter_items(counter: Counter[str]) -> list[dict[str, object]]:
    return [
        {"token": token, "count": count}
        for token, count in sorted(counter.items(), key=lambda item: item[0])
    ]


def ordered_anchors(text: str) -> list[str]:
    matches: list[tuple[int, int, int, str]] = []
    for category, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            token = normalize_token(match.group(0))
            matches.append(
                (
                    match.start(),
                    match.end(),
                    CATEGORY_PRIORITY[category],
                    f"{category}:{token}",
                )
            )
    matches.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in matches]


def first_sequence_mismatch(before: list[str], after: list[str]) -> int | None:
    for index, (before_item, after_item) in enumerate(zip(before, after)):
        if before_item != after_item:
            return index
    if len(before) != len(after):
        return min(len(before), len(after))
    return None


def sequence_window(sequence: list[str], index: int | None) -> list[str]:
    if index is None:
        return []
    start = max(0, index - 2)
    end = min(len(sequence), index + 3)
    return sequence[start:end]


def build_result(
    before_path: Path,
    after_path: Path,
    before_text: str,
    after_text: str,
    allow_heading_change: bool,
) -> dict[str, object]:
    categories: dict[str, object] = {}
    blocking_differences = 0

    for name, pattern in PATTERNS.items():
        before_tokens = extract(before_text, pattern)
        after_tokens = extract(after_text, pattern)
        removed, added = counter_delta(before_tokens, after_tokens)
        difference_count = sum(removed.values()) + sum(added.values())
        if name in BLOCKING_CATEGORIES:
            blocking_differences += difference_count
        categories[name] = {
            "before_count": sum(before_tokens.values()),
            "after_count": sum(after_tokens.values()),
            "removed": counter_items(removed),
            "added": counter_items(added),
            "status": "pass" if difference_count == 0 else "fail",
        }

    before_headings = Counter(
        normalize_token(match.group(0)) for match in HEADING_PATTERN.finditer(before_text)
    )
    after_headings = Counter(
        normalize_token(match.group(0)) for match in HEADING_PATTERN.finditer(after_text)
    )
    removed_headings, added_headings = counter_delta(before_headings, after_headings)
    heading_changed = bool(removed_headings or added_headings)

    before_order = ordered_anchors(before_text)
    after_order = ordered_anchors(after_text)
    order_mismatch = first_sequence_mismatch(before_order, after_order)
    if order_mismatch is not None:
        blocking_differences += 1

    return {
        "status": "pass" if blocking_differences == 0 else "fail",
        "before": {
            "path": str(before_path.resolve()),
            "sha256": digest(before_text),
        },
        "after": {
            "path": str(after_path.resolve()),
            "sha256": digest(after_text),
        },
        "blocking_difference_count": blocking_differences,
        "categories": categories,
        "anchor_order": {
            "status": "pass" if order_mismatch is None else "fail",
            "first_mismatch_index": order_mismatch,
            "before_window": sequence_window(before_order, order_mismatch),
            "after_window": sequence_window(after_order, order_mismatch),
        },
        "headings": {
            "status": (
                "ignored"
                if allow_heading_change
                else ("warn" if heading_changed else "pass")
            ),
            "removed": counter_items(removed_headings),
            "added": counter_items(added_headings),
        },
        "limitations": (
            "A passing anchor comparison does not prove semantic equivalence. "
            "Manually review claim direction, certainty, causality, population, "
            "context, conditions, limitations, source meaning, and whether each "
            "number still belongs to the same group, variable, table, and claim."
        ),
    }


def format_items(items: list[dict[str, object]]) -> str:
    if not items:
        return "-"
    values = []
    for item in items:
        token = str(item["token"]).replace("`", "\\`")
        count = int(item["count"])
        values.append(f"`{token}`" if count == 1 else f"`{token}` x{count}")
    return "<br>".join(values)


def to_markdown(result: dict[str, object]) -> str:
    status = str(result["status"]).upper()
    before = result["before"]
    after = result["after"]
    categories = result["categories"]
    lines = [
        "# 语义锁检查报告",
        "",
        f"- 状态：`{status}`",
        f"- 改写前：`{before['path']}`",
        f"- 改写前 SHA-256：`{before['sha256']}`",
        f"- 改写后：`{after['path']}`",
        f"- 改写后 SHA-256：`{after['sha256']}`",
        f"- 阻塞差异数：`{result['blocking_difference_count']}`",
        "",
        "| 类别 | 改写前 | 改写后 | 删除/改变 | 新增 | 状态 |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for name, payload in categories.items():
        lines.append(
            "| "
            + " | ".join(
                (
                    name,
                    str(payload["before_count"]),
                    str(payload["after_count"]),
                    format_items(payload["removed"]),
                    format_items(payload["added"]),
                    str(payload["status"]),
                )
            )
            + " |"
        )

    headings = result["headings"]
    anchor_order = result["anchor_order"]
    lines.extend(
        (
            "",
            "## 锚点顺序",
            "",
            f"- 状态：`{anchor_order['status']}`",
            f"- 首个差异位置：`{anchor_order['first_mismatch_index']}`",
            f"- 改写前窗口：{format_items([{'token': item, 'count': 1} for item in anchor_order['before_window']])}",
            f"- 改写后窗口：{format_items([{'token': item, 'count': 1} for item in anchor_order['after_window']])}",
            "",
            "## 标题结构",
            "",
            f"- 状态：`{headings['status']}`",
            f"- 删除/改变：{format_items(headings['removed'])}",
            f"- 新增：{format_items(headings['added'])}",
            "",
            "## 局限",
            "",
            str(result["limitations"]),
        )
    )
    dependency = result.get("dependency")
    if isinstance(dependency, dict):
        lines.extend(
            (
                "",
                "## 语言依赖",
                "",
                f"- 语言：`{dependency['language']}`",
                f"- Skill：`{dependency['name']}`",
                f"- 实际路径：`{dependency['path']}`",
                f"- SKILL.md SHA-256：`{dependency['skillSha256']}`",
                f"- 目录 SHA-256：`{dependency['directorySha256']}`",
            )
        )
    manual_review = result.get("manual_review")
    if isinstance(manual_review, dict):
        lines.extend(
            (
                "",
                "## 人工语义回归",
                "",
                f"- 问题：`{manual_review['issue']}`",
                f"- 处置：`{manual_review['disposition']}`",
                f"- 理由：{manual_review['reason']}",
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    try:
        before_text = read_text(args.before)
        after_text = read_text(args.after)
    except (OSError, UnicodeError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    result = build_result(
        args.before,
        args.after,
        before_text,
        after_text,
        args.allow_heading_change,
    )
    result["automated_status"] = result["status"]
    try:
        if args.language:
            result["dependency"] = resolve_language_dependency(
                args.language, args.skills_root, args.dependency_lock
            )
        if args.manual_review:
            manual_review = load_manual_review(
                args.manual_review,
                str(result["before"]["sha256"]),
                str(result["after"]["sha256"]),
            )
            result["manual_review"] = manual_review
            if manual_review["disposition"] == "rejected":
                result["status"] = "fail"
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    output = (
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.json
        else to_markdown(result)
    )
    print(output, end="")

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(to_markdown(result), encoding="utf-8")

    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
