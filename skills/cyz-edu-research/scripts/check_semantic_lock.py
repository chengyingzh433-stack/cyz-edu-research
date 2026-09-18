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
    "numbers": re.compile(
        r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
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
}

BLOCKING_CATEGORIES = tuple(PATTERNS)
CATEGORY_PRIORITY = {name: index for index, name in enumerate(PATTERNS)}
HEADING_PATTERN = re.compile(r"(?m)^#{1,6}\s+.+$")


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
    return parser.parse_args()


def read_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
