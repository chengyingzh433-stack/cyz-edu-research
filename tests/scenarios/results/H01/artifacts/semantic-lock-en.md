# 语义锁检查报告

- 状态：`PASS`
- 改写前：`baseline-en.md`
- 改写前 SHA-256：`2b73b5d176b334e60a09d0fcd1e848824b4e97daf5f09bfa128c2a40b1dd4d25`
- 改写后：`revised-en.md`
- 改写后 SHA-256：`10840e7099d10d009f7e3b7a716fdcf9da775cc8648ed65cf1e4d4c236f0d93d`
- 阻塞差异数：`0`

| 类别 | 改写前 | 改写后 | 删除/改变 | 新增 | 状态 |
| --- | ---: | ---: | --- | --- | --- |
| units | 2 | 2 | - | - | pass |
| numbers | 5 | 5 | - | - | pass |
| statistics | 2 | 2 | - | - | pass |
| doi | 0 | 0 | - | - | pass |
| urls | 0 | 0 | - | - | pass |
| numeric_citations | 0 | 0 | - | - | pass |
| author_year_citations | 0 | 0 | - | - | pass |
| figure_table_refs | 0 | 0 | - | - | pass |
| research_question_refs | 0 | 0 | - | - | pass |
| placeholders | 0 | 0 | - | - | pass |
| quotations | 0 | 0 | - | - | pass |
| negations | 1 | 1 | - | - | pass |

## 锚点顺序

- 状态：`pass`
- 首个差异位置：`None`
- 改写前窗口：-
- 改写后窗口：-

## 标题结构

- 状态：`pass`
- 删除/改变：-
- 新增：-

## 局限

A passing anchor comparison does not prove semantic equivalence. Manually review claim direction, certainty, causality, population, context, conditions, limitations, source meaning, and whether each number still belongs to the same group, variable, table, and claim.

## 语言依赖

- 语言：`en`
- Skill：`humanizer`
- 实际路径：`<skills-root>/humanizer/SKILL.md`（已在本机解析，公开证据脱敏）
- SKILL.md SHA-256：`70938f3cce25970e1ded5fdd194b755c03f1e4e4fa76820958ce78f86b677b1a`
- 目录 SHA-256：`ca43b838a44ad4819f3fd60f10c2ed2ef9b6ced517929be2dcca9dbc41a9e892`

## 人工语义回归

- 问题：`bounded_academic_language_revision`
- 处置：`accepted`
- 理由：The sample, duration, correlation direction, statistics, causal limit, and transfer boundary are unchanged; only generic framing, promotional wording, and repetition were removed.
