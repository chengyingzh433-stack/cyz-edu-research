# 语义锁检查报告

- 状态：`PASS`
- 改写前：`baseline-zh.md`
- 改写前 SHA-256：`0115feb60e2b83ba59826ed1150de15e1957b9e3748d2c0ed967527ceef717fd`
- 改写后：`revised-zh.md`
- 改写后 SHA-256：`205ba726c9da0e320b5329477fc285f34c9b9583422ea004a31d0395f50cc58f`
- 阻塞差异数：`0`

| 类别 | 改写前 | 改写后 | 删除/改变 | 新增 | 状态 |
| --- | ---: | ---: | --- | --- | --- |
| units | 2 | 2 | - | - | pass |
| numbers | 4 | 4 | - | - | pass |
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

- 语言：`zh`
- Skill：`humanizer-zh`
- 实际路径：`<skills-root>/humanizer-zh/SKILL.md`（已在本机解析，公开证据脱敏）
- SKILL.md SHA-256：`171758fed76b0c5f70ff5e2284bf2bd951749ff097ddd05f33e94597f52434f5`
- 目录 SHA-256：`4fd457ac06688f55d8cd6921dde5ae3b105f371696a4673d956a038c435b3f9f`

## 人工语义回归

- 问题：`bounded_academic_language_revision`
- 处置：`accepted`
- 理由：数字、样本、时间、相关方向、显著性、因果限制和外推边界均保持不变；仅删除空泛背景、重复升华和助手式连接语。
