# Workflow 场景映射

本表把 24 个强制场景固定映射到原始需求与 WF 验收项。fixture 的 `passCriteria` 使用结构化 predicate、oracle 和证据路径；关键词出现本身不能判定通过。

| 场景 | 原始要求 | WF | 执行模式 |
| --- | --- | --- | --- |
| I01 | 原场景 1：仅“高中物理教学” | WF01 | scripted |
| I02 | 原场景 2：模糊领域＋一批论文 | WF01 | live |
| I03 | 原场景 3：仅“AI 辅助实验教学” | WF02、WF03 | live |
| I04 | 原场景 4：完整方案要求打磨 | WF02、WF03 | scripted |
| I05 | 原场景 5：初学者回答“不知道” | WF03 | scripted |
| I06 | 原场景 6：混合材料路径 | WF03 | scripted |
| I07 | 原场景 7：与既有论文高度相似 | WF03 | scripted |
| I08 | 原场景 8：仅摘要或无法联网 | WF04 | scripted |
| I09 | 原场景 9：定性、教材或教学设计研究 | WF04 | scripted |
| I10 | 原场景 10：暂停后继续 | WF05 | deterministic |
| I11 | 原场景 11：新证据否定原选择 | WF05、WF06 | deterministic |
| I12 | 原场景 12：简报完成但后续阶段未完成 | WF05、WF06 | deterministic |
| I13 | 原场景 13：旧项目升级与新项目初始化 | WF05 | deterministic |
| I14 | 原场景 14：双安装一致与旧流程回归 | WF12 | deterministic |
| H01 | 中英文实际依赖调用 | WF07 | live |
| H02 | 数字、单位、引文、否定与因果强化拒绝 | WF07 | scripted |
| H03 | 缺依赖清晰失败且不替代 | WF08 | deterministic |
| H04 | 正文修改使旧审阅失效 | WF08 | deterministic |
| M01 | 两篇真实本地 PDF 与页级抽查 | WF09 | live |
| M02 | 同源同参数缓存复用 | WF10 | live |
| M03 | 错源、缺页、缺图、错 key、未完成拒绝 | WF10 | deterministic |
| M04 | 复用任务 lineage | WF10 | deterministic |
| M05 | 缺 Desk、无 OCR、离线与中断恢复 | WF11 | scripted |
| M06 | 原 PDF hash 不变 | WF09 | deterministic |

## 判定规则

- `deterministic`：脚本或文件状态可重复验证，必须保存命令结果和结构化证据。
- `scripted`：允许明确标记的测试剧本，不能冒充用户真实回答或真实研究结论。
- `live`：必须保存真实运行时输入输出、时间、版本和人工审阅依据。
- 每个场景必须记录 actual result、passed/failed/blocked、执行时间、commit、环境、退出码或界面状态及证据路径。
- I01–I14 与原 14 个场景保持一对一编号；H/M 场景补充语言与 MinerU 集成边界。

## Schema 与判定 DSL

- 每个 fixture 都由 `scenario-contract.schema.json` 验证。仓库内 `tests/scenarios/schema_validator.py` 只实现并声明本仓库需要的 JSON Schema 关键词子集，并不声称完整实现 Draft 2020-12。校验器会先递归检查 schema 本身；未知断言关键词、未知类型、外部 `$ref` 和未声明字段一律失败，因此不会把未实现的规则静默当作通过。
- `criteriaDslVersion` 当前固定为 `1`。每条通过条件和禁止行为都有稳定 ID、人工可读 oracle、结构化 `condition` 和已声明的证据路径。
- condition 仅允许点分字段路径，以及 `eq`、`not_eq`、`gte`、`lte`、`exists`、`unchanged` 运算符。解释器使用封闭分支，不执行 `eval`、表达式字符串或动态代码。
- `eq`、`not_eq` 与 `unchanged` 按 JSON 类型比较；布尔值不会与数值 `0` 或 `1` 混同。`unchanged` 的观测值固定为 `{"before": ..., "after": ...}`。
- 场景运行结果遵循 `result-contract.schema.json`：包含版本、场景 ID、记录时间、状态、原始 `observations` 与来源证据。判据直接读取这些观测值，不允许用 `*Passed`、`*Valid`、`*Unchanged` 一类汇总布尔值自证成功。
- 所有证据路径必须是当前场景目录下的 POSIX 相对路径：`results/<scenario-id>/...`。绝对路径、盘符、UNC、反斜杠、任何纯点号路径段（`.`、`..`、`...` 等）、跨场景路径和未在顶层声明的 criterion 证据都会被拒绝。
- 复现命令：`py -3.11 -m unittest tests.test_workflow_contract -v`。
