# CYZ 工作流新版本：详细技术方案 v0.2

日期：2026-09-18。性质：待执行的工程设计，不是实现或验收报告。

目标：完成教育教学 idea 发现与打磨，将现有 humanizer 与本地 MinerU 优化整合成可安装、可升级、可回滚、可核验的工作流版本并发布到 GitHub。

本方案补充《CYZ教育教学Idea发现与打磨_改造方案_v0.1.md》，保留其全部产品决定。执行方法采用 writing-plans 的分任务组织方式；执行者读取本机 executing-plans 技能逐项实施，不要求用户重新回答已经决定的产品问题。

## 1. 当前基线与源码管理

已核实安装源：

- `C:/Users/W/.agents/skills/cyz-edu-research`
- `C:/Users/W/.codex/skills/cyz-edu-research`
- 同级 `mineru`、`humanizer-zh`、`humanizer`、`clarify-research-idea`。
- cyz 当前 `plugin.json` 版本为 `0.2.1`；本地 MinerU skill 为 `4.0.0-desk-local`。
- 当前改造说明存在，但旧版本号尚未体现全部本地修改，必须以文件哈希而非版本字符串识别基线。

开始时比较两处文件，若不同，逐项调查，不以时间戳自动覆盖。将确认后的 cyz 与本地 MinerU skill 复制到源码仓库，生成逐文件 SHA256 清单并备份两处安装。只在源码仓库开发，验证后再安装。

仓库选择：先寻找明确对应的已存在项目及 Git remote；若没有，默认新建工作目录 `C:/Users/W/Documents/Codex/2026-09-18/wo/work/projects/cyz-edu-research`。如果该路径已有其他内容，另建带日期的目录，不覆盖。工作台源码另建独立仓库。

推荐仓库布局：

```text
skills/cyz-edu-research/    # 完整主 skill，含 references/templates/scripts/agents
skills/mineru/              # 经许可检查后发布的本地 Desk 接入 skill
contracts/workflow-v1.json  # 稳定阶段、状态与成果字段
dependencies.lock.json     # 外部 skill 的来源、版本或 commit、hash、license
tests/                     # 初始化、迁移、缓存、语言检查及场景记录验证
scripts/                   # 打包、验证、安装和回滚
docs/                      # 使用、升级、接入、发布、验收报告
VERSION                    # 默认 0.3.0，若已有该版本则递增，不覆盖已有 tag
CHANGELOG.md
THIRD_PARTY_NOTICES.md
LICENSE
```

安装目录里的 `plugin.json` 声明 `skills: ./skills/`，与它当前所在的单 skill 布局不匹配。发布时不能原样宣称插件可安装：本版必需交付是标准 skill 包和安装脚本；若提供插件外壳，必须按当时官方 schema 另行验证路径与安装，未验证的外壳不放入主发布资产。保持原作者及改编来源归属，不把历史作者误写成本次实现者。

## 2. Idea 状态和持久化契约

保留旧 `entry_mode=discovery|topic|materials` 与 S0–S8。新增字段不改变旧字段含义：

```yaml
workflow_schema: 2
idea_mode: discovery        # discovery | refinement
idea_maturity: broad_interest  # broad_interest | tentative_topic | method_first | positioned_question | study_plan
idea_status: exploring     # not_started | exploring | refining | needs_verification | ready | blocked
idea_revision: 1
idea_workspace: 01-研究起点与问题.md
```

`materials` 不是自动等同 discovery：先查看材料中有没有实际问题或方案。旧项目缺少新字段时仍可读，提示可迁移；不存在关键证据时不得推断 `ready`。

状态规则：

- 无 idea：`not_started → exploring → refining`；有 idea：`not_started → refining`。
- 缺少可补的关键文献：`exploring/refining → needs_verification`；取得证据后返回原步骤。
- 存在现实不可满足条件：进入 `blocked`，记录原因、恢复条件和可替代方案。
- 用户确认问题、定位与初步证据路线，且无影响成立条件的未知：`refining → ready`。
- 新证据动摇已确认问题：`ready → needs_verification/refining`，revision 加一，历史保留，下游标记需复核。
- `ready` 只表示能进入下一阶段，不使 S2–S5 自动 passed，不代表假设已证实。

主记录仍为 `01-研究起点与问题.md`。用稳定 HTML 注释标记可管理区域，例如 `<!-- cyz:idea-canvas:start -->` 和对应 end，正文仍是可读 Markdown。只更新确认属于工具管理的区域；找不到区域或出现多对标记时不猜测替换，创建候选迁移文件并报告。

候选卡字段：candidate_id、具体问题、学段/学科内容/对象、关联 paper_id、可能价值、最接近研究、已有/可获取/需新增材料、替代解释、失败条件、可行性说明、证据范围、推荐/淘汰理由。候选 ID 在不同轮次保持稳定。

当前选题卡额外包含：核心概念、主问题、必要子问题、问题类型、范围排除项、暂定解释、允许主张的边界、关键未知、下一决定。用户陈述单独标来源，不升级成已核验事实。

确认记录包含 decision_id、问题、答案、来源（用户实际回答或测试剧本）、时间、针对的 idea_revision、影响字段。旧 revision 的确认不能自动覆盖新版问题。测试剧本只能用于明确标记的测试项目。

交接区包含：选题摘要、已确认范围、文献与证据位置、未核验项、初步证据路线、不得超出的主张、下一阶段及所需动作。不得复制所有 PDF 正文。

## 3. 指令模块的具体变更

| 文件（相对 skills/cyz-edu-research） | 实现职责 |
| --- | --- |
| SKILL.md | 两条入口、成熟度分流、只加载当前需要的 reference、旧项目恢复和主动打磨入口 |
| references/idea-scout.md | 种子材料盘点、覆盖偏差、问题地图、约 3–5 个候选、淘汰及停止广泛搜索条件 |
| references/idea-refinement.md（新） | 五种成熟度、问题澄清、角色式文献定位、替代解释、反例、资源审查和交接 |
| references/guided-mentor.md | 一轮一个关键问题；先解释再推荐；“不知道”时补材料或给具体例子 |
| references/literature-workflow.md | 探索扫描/关键核查/完整综述分开；引用已有 paper_id 和有效全文缓存 |
| references/project-protocol.md | 新字段、revision、确认记录、兼容迁移与下游复核 |
| references/integrity-gates.md | ready 的实质条件、不得自动跳过文献与研究设计门检 |
| templates/idea-workspace.md（新） | 主记录全部区域与卡片模板 |
| templates/project-status.md | 添加新字段和摘要，不把模板默认值写成已确认 |
| scripts/init_project.py | 用新模板初始化 01 文件，保留 --allow-existing 的不覆盖约定 |
| scripts/migrate_project.py（新） | 预览、备份、幂等迁移；从旧标题保留原文并添加缺失字段/区域 |
| scripts/validate_project.py | 校验枚举、标记成对、链接、revision、ready 记录；只做结构检查，不宣称证明研究价值 |
| 使用说明.md / THIRD_PARTY_NOTICES.md | 两类案例、未核验说明、独立重述 clarify 机制的来源记录 |

不强制课堂困惑开场；不机械凑候选数；不把未检出当原创；不固定两三项贡献；定性研究不强制量化假设；教学设计与效果证据分开；没有现实数据时不得补造。

## 4. 初始化和升级 CLI

执行者需实现并测试以下命令契约。以下 `$python` 指向已确认的 Python 运行时，`$repo` 为源码仓库，`$project` 为隔离测试项目，不指向用户唯一原件。

```powershell
& $python "$repo/skills/cyz-edu-research/scripts/init_project.py" $project --entry-mode topic
& $python "$repo/skills/cyz-edu-research/scripts/migrate_project.py" $project --check
& $python "$repo/skills/cyz-edu-research/scripts/migrate_project.py" $project --apply
& $python "$repo/skills/cyz-edu-research/scripts/validate_project.py" $project
```

迁移 `--check` 不写入，返回 0=已兼容、3=需要迁移、2=结构冲突或参数错误。`--apply` 先备份受影响文件到项目 `.cyz-migrations/<UTC时间>/`，写 manifest（前后 hash、schema、操作），再在同卷临时文件写完校验后替换；重复运行字节不变，返回 0。发现原始内容已变或标记不唯一则返回 2，保留原文件。失败时根据 manifest 回滚工具本轮修改，不删除用户新增内容。

旧项目缺字段在通用 validate 中提示 warning；schema=2 却缺必需字段为 error。ready 但没有有效确认或关键资料指向不存在时为 error。学术判断仍需场景审阅，不能由正则代替。

## 5. humanizer 集成发布要求

沿用中文 `humanizer-zh`、英文 `humanizer` 路由及已有学术适配器。记录被调用 skill 的实际路径、版本/hash、输入基线、输出范围和检查报告。混合语种按段落/章节处理，术语、引文和数学符号锁定。

只提供安装与依赖核验说明或固定来源安装器，不把缺失依赖偷偷替换成 qu-ai-wei。新增依赖安装前查看上游来源、固定 commit 和许可。已安装但 hash 不同的依赖由执行者解释差异，不能无声覆盖用户修改。

验收必须包括：中文和英文分别实际调用；数字、单位、引用、否定、因果与不确定程度保持；人为改动关键数字被脚本拒绝；“相关”被改成“导致”由语义审阅拒绝，即使脚本未检出；基线不被覆盖；最终稿改动后必须重新检查。不能承诺检测器规避或所有 AI 风格消失。

## 6. MinerU 集成发布要求

本机接入线索为 `D:/cyz的资料/03_个人生活/有趣的项目/MinerU/MinerU Desk`，Desk 0.3.1/MinerU 3.4.5 曾通过样本测试，执行时重检实际版本。该路径只在本机配置中使用，发布文档采用用户指定路径、`MINERU_DESK_ROOT` 配置及受支持注册表定位，不嵌入私人目录作为默认。

流程：canonical cache 校验 → 有效则直接读 → 无效时定位和检查本地 Desk → 提交 local/pipeline → 保留任务 ID → 有界轮询 → exporter 获取实际详情 → importer 检查源指纹、完成范围、页码、assets → 原子发布完整缓存。Desk 缺失时显式走已有本地提取；扫描页无 OCR 则报未识别，不能输出假完整全文。绝不自动转云端。

必须回归现有 `convert_pdf_to_md.py`、`export_mineru_task.py`、`mineru_cache.py`，特别是复用任务追溯、UTF-8 PowerShell 返回、Desk cacheKey 和源文件对应关系。不得用 Desk 重序列化的 `_origin.pdf` 哈希替代原始输入哈希。不能用猜测页码填 source_map。

原始 PDF、转换缓存、研究者笔记分开。只发布经过完整校验的缓存；部分页面、缺图片、任务仍在运行、错误源文件和错误 key 均不能当有效全文复用。

依赖清单按“必要的基础 Python 包”和“可选本地提取/截图能力”拆分；从实际 import 与执行测试确定，不向 Desk 随包环境强行安装包。缺可选库时有可理解的诊断与确定降级。

## 7. 测试组织和完成阈值

使用标准库 unittest 运行确定性脚本测试，避免测试基础依赖额外膨胀。测试文件分别为 `tests/test_project_lifecycle.py`、`test_cache_integrity.py`、`test_semantic_lock.py`、`test_release_package.py`。场景演练另放 `tests/scenarios/`，记录输入、真实输出、判定依据，不能把提示词含某关键词当成功。

必需场景用编号 I01–I14 对应 v0.1 的 14 项；增加 H01–H04（中英实际调用、语义变更拒绝、缺依赖、终稿变更重检）、M01–M06（真实本地解析、缓存复用、错误源/页/图拒绝、任务复用追溯、缺 Desk 降级、原件不变）。

至少运行两个真实 Codex 场景：无 idea＋开放全文种子文献；已有 idea＋相近文献。另以明确标记的测试剧本覆盖初学者“不知道”、反例导致改题等分支。所有发表信息由来源核实；样本篇数下限为 3 篇公开可读论文，其中至少 2 篇实际本地 PDF 解析。若来源不足，继续找合规来源，不捏造。

```powershell
& $python -m unittest discover -s "$repo/tests" -p 'test_*.py' -v
& $python "$repo/scripts/verify_release.py" --dist "$repo/dist"
```

`verify_release.py` 必须检查 manifest/hash、相对链接、版本一致性、无个人绝对路径/令牌/真实学生资料、必要许可证、ZIP 解包后的完整性；失败返回非零。安装到两个临时 skill 根，验证依赖解析和新建项目，再有备份地同步用户两个安装根。正式安装前不破坏已可用版本。

## 8. GitHub 与发布工程

默认版本 `0.3.0`（与已存在 tag 冲突则按 SemVer 提升）；记录 source commit、workflow schema、支持的 Desk/Codex 实测版本。必须交付 changelog、安装升级回滚说明、依赖锁定清单、使用案例、测试与限制报告。

打包资产：`cyz-edu-research-<version>.zip`、经许可检查可分发的 `mineru-desk-skill-<version>.zip`、`SHA256SUMS.txt`、`acceptance-report.md`。不打包模型权重、Desk 程序、登录凭据、个人论文或未获许可的第三方 skill。现有 CC-BY-NC-4.0 与历史 MIT 来源归属必须保留，不能把整个工作流改标 MIT。

GitHub 目标按以下顺序解析：现有正确 remote → 用户指定仓库 → 单一已登录账户下新建私有 `cyz-edu-research`。同名仓库存在但来源不明则先核查，禁止覆盖/强推。多账户、无登录或需要公开可见性选择时只请求必要信息。用户已授权上传，不再机械询问“是否上传”；默认不改变已有仓库可见性。

发布前只 stage 明确允许的源码/文档文件，扫描 staged 内容和新提交历史。使用带注释 tag、GitHub Release 及校验和；默认正常版本而非伪装完成的 draft。若安全/许可或验收未过，只能保存本地或明确 prerelease，不能满足正式发布门槛。

发布成功必须通过远端读取确认：仓库 URL、tag、commit、Release URL、资产名称/大小；重新下载 ZIP 核对 SHA256 并执行临时安装测试。只 git push、不建 Release、不验证资产都算未完成。

## 9. 执行工作包

- [ ] W1：基线比对、备份、确定源码根、记录依赖与许可；产物 baseline-manifest.json。
- [ ] W2：实现 idea 模板、入口、成熟度追问与交接；用 I01–I09 验证行为。
- [ ] W3：实现 schema=2 的初始化、迁移、结构检查和恢复；验证 I10–I14 与迁移幂等。
- [ ] W4：把 humanizer/MinerU 既有改造纳入源码并解决发布路径/依赖问题；运行 H/M 全部场景。
- [ ] W5：打包、临时安装、回滚演练、版本与文档审查；创建本地 tag 前检查所有必需门槛。
- [ ] W6：授权目标上传、Release、下载校验、安装复测、同步本地两份 skill；记录远端证据。

每个工作包先补充该变更所需的具体代码步骤和故障测试，再实现，再执行验证；报告真实命令、时间、退出码与文件证据。此文定义工程契约，不假装已经写好全部源码或运行了测试。
