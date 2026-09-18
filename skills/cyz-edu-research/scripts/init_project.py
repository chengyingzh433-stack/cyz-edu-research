#!/usr/bin/env python3
"""Create a resumable CYZ education-research Markdown project."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys


DIRECTORIES = (
    "02-文献/文献卡",
    "02-文献/转换缓存",
    "02-文献/核心文献精读",
    "07-论文草稿",
    "09-正式输出",
)

TEMPLATE_MAP = {
    "project-status.md": "00-项目状态.md",
    "idea-workspace.md": "01-研究起点与问题.md",
    "evidence-matrix.md": "03-文献证据矩阵.md",
    "research-design.md": "05-研究方案.md",
    "audit-report.md": "08-审查与修改记录.md",
    "academic-humanization-report.md": "07-论文草稿/学术语言打磨报告.md",
}

SIMPLE_FILES = {
    "02-文献/00-检索记录.md": "# 文献检索记录\n\n| 日期 | 数据库/来源 | 检索式 | 筛选条件 | 命中数 | 备注 |\n| --- | --- | --- | --- | --- | --- |\n",
    "02-文献/01-筛选记录.md": "# 文献筛选记录\n\n| 文献 ID | 题名 | 访问级别 | 决定 | 理由 |\n| --- | --- | --- | --- | --- |\n",
    "02-文献/转换缓存/00-缓存索引.md": "# Markdown 全文缓存索引\n\n> `paper.md` 是唯一长期全文阅读缓存；原 PDF 是权威原件。\n\n| 题名 | Paper ID | PDF 页数 | 缓存 | OCR/图表风险 |\n| --- | --- | ---: | --- | --- |\n| 暂无 | - | - | - | - |\n",
    "04-综述与研究缺口.md": "# 综述与研究缺口\n\n## 已有共识\n\n## 分歧与条件\n\n## 证据和方法边界\n\n## 候选缺口\n\n## 定向复核记录\n",
    "06-数据与分析.md": "# 数据与分析\n\n## 数据清单与来源\n\n## 数据字典\n\n## 清理与排除记录\n\n## 分析计划\n\n## 结果\n\n## 待核验\n",
}

ENTRY_STAGE = {
    "discovery": ("S0", "S0 领域扫描与灵感发现"),
    "topic": ("S1", "S1 实践问题与研究问题"),
    "materials": ("S0", "材料盘点与阶段识别"),
}

IDEA_DEFAULTS = {
    "discovery": {
        "idea_mode": "discovery",
        "idea_maturity": "broad_interest",
        "idea_status": "exploring",
        "material_status": "待补充",
    },
    "topic": {
        "idea_mode": "refinement",
        "idea_maturity": "tentative_topic",
        "idea_status": "refining",
        "material_status": "待补充",
    },
    "materials": {
        "idea_mode": "discovery",
        "idea_maturity": "broad_interest",
        "idea_status": "not_started",
        "material_status": "待核对（不预判已有/可获取/需新增）",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path, help="Project directory to create")
    parser.add_argument("--title", default=None, help="Human-readable project title")
    parser.add_argument(
        "--entry-mode",
        choices=("discovery", "topic", "materials"),
        default="discovery",
    )
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="Add missing project files to an existing directory without overwriting files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_dir.expanduser().resolve()
    title = args.title or root.name
    current_stage, stage_label = ENTRY_STAGE[args.entry_mode]
    idea_defaults = IDEA_DEFAULTS[args.entry_mode]

    if root.exists() and any(root.iterdir()) and not args.allow_existing:
        print(
            f"Refusing to initialize non-empty directory without --allow-existing: {root}",
            file=sys.stderr,
        )
        return 2

    root.mkdir(parents=True, exist_ok=True)
    for relative in DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)

    templates = Path(__file__).resolve().parents[1] / "templates"
    created: list[Path] = []
    skipped: list[Path] = []

    for source_name, destination_name in TEMPLATE_MAP.items():
        source = templates / source_name
        destination = root / destination_name
        if destination.exists():
            skipped.append(destination)
            continue
        text = source.read_text(encoding="utf-8")
        text = text.replace("{{PROJECT_TITLE}}", title)
        text = text.replace("{{ENTRY_MODE}}", args.entry_mode)
        text = text.replace("{{CURRENT_STAGE}}", current_stage)
        text = text.replace("{{STAGE_LABEL}}", stage_label)
        text = text.replace("{{DATE}}", date.today().isoformat())
        text = text.replace("{{IDEA_MODE}}", idea_defaults["idea_mode"])
        text = text.replace("{{IDEA_MATURITY}}", idea_defaults["idea_maturity"])
        text = text.replace("{{IDEA_STATUS}}", idea_defaults["idea_status"])
        text = text.replace("{{MATERIAL_STATUS}}", idea_defaults["material_status"])
        destination.write_text(text, encoding="utf-8")
        created.append(destination)

    for destination_name, content in SIMPLE_FILES.items():
        destination = root / destination_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            skipped.append(destination)
            continue
        destination.write_text(content, encoding="utf-8")
        created.append(destination)

    print(f"Project initialized: {root}")
    for path in created:
        print(f"CREATED {path.relative_to(root)}")
    for path in skipped:
        print(f"SKIPPED {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
