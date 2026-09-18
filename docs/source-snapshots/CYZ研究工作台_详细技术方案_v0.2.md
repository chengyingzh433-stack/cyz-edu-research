# CYZ 研究工作台：详细技术方案 v0.2

日期：2026-09-18。状态：实施契约，尚未开发或证明接入成功。

补充《CYZ研究工作台_PRD与技术方案_v0.1.md》。本次用户已授权在新版工作流发布后开始工作台并完成验收，因此旧 PRD 的“等待后续启动通知”被该顺序授权替代。第三方模型独立执行仍是后续版本，不因“全流程验收”扩大到该功能。

## 1. 交付范围与架构决策

首版以 Windows x64、本机单用户、项目文件夹为边界。Electron 主进程管理应用服务，React/TypeScript 展示界面，Node.js 负责本地服务，SQLite 记录执行数据。采用 pnpm workspace、锁文件、Vitest 服务测试、Playwright Electron 交互测试与 Windows 打包。安装版本在执行时核实并固定，不直接使用浮动 latest。SQLite 驱动选择支持目标 Electron ABI 的 better-sqlite3，打包时重建并做真实启动测试。

项目内保存研究内容；Codex、MinerU 程序和认证由各自运行时管理。工作台不自建模型循环。前端对话由 Codex App Server 执行，外部 Codex 通过工作台 loopback HTTP API 和配套 CLI 访问同一应用服务。

必须能从 UI 对话完成 idea 模块及后续 S0–S8 研究流程。全阶段均能展示成果、研究决定和门检；首版专用交互重点仍是文献、证据矩阵与草稿。S5/S6 不另造统计软件或实验管理系统，通过 Codex、文件和成果视图完成任务。不得用“这些阶段只是展示”回避验收中的真实对话执行。

## 2. 源码目录与职责

新仓库默认 `C:/Users/W/Documents/Codex/2026-09-18/wo/work/projects/cyz-research-workbench`，已有正确仓库则复用并记录绝对路径。以下路径均相对该源码根：

```text
apps/desktop/src/main/       lifecycle.ts ipc.ts windows.ts
apps/desktop/src/preload/    bridge.ts
apps/desktop/src/renderer/   App.tsx features/{projects,stages,chat,ideas,materials,evidence,editor,history}
packages/contracts/src/     domain.ts events.ts api.ts engine.ts
packages/project-service/src/ project.ts imports.ts artifacts.ts decisions.ts leases.ts recovery.ts
packages/project-service/src/db/ migrations/ repositories.ts
packages/codex-adapter/src/  transport.ts client.ts normalize.ts requests.ts capabilities.ts
packages/codex-adapter/generated/  # 由已验证本机 CLI 生成的协议类型
packages/workflow-adapter/src/ markdown.ts gates.ts dependencies.ts snapshots.ts
packages/mineru-adapter/src/ cli.ts tasks.ts cache.ts
packages/local-api/src/     server.ts auth.ts routes.ts path-policy.ts
packages/bridge-cli/src/    index.ts
tests/{unit,integration,e2e,live}/
fixtures/                  # 仅可分发的测试数据
docs/{architecture,acceptance,release}/
scripts/                   doctor.mjs verify-package.mjs collect-evidence.mjs
```

渲染层不直接访问文件系统、SQLite、shell 或凭据。Electron 主进程和 HTTP 路由调用同一项目服务，不复制业务规则。workflow-adapter 读取已发布 cyz 的 contracts/workflow-v1.json 及 Markdown，不能在前端再发明学术通过标准。

## 3. 项目内目录与数据权威

保持 cyz 原有文件布局，新增：

```text
.cyz/project.json          # schemaVersion/projectId/workflowVersion/createdAt
.cyz/state.sqlite          # 数据库，WAL；应用负责打开关闭
.cyz/versions/<sha256>     # 不可变成果内容，去重
.cyz/runs/<runId>/         # 本次执行的工作副本、候选输出与恢复清单
.cyz/exports/              # 脱敏后的可读事件、决定和任务导出
.cyz/backup/               # 迁移/恢复备份
02-文献/原件/<sourceId>/   # 导入副本，保留原名，另存 SHA256
```

研究正文以 Markdown 为权威；原件指纹为来源依据；SQLite 是任务、租约、事件和版本发布事务的权威。阶段学术状态以 cyz Markdown 的经核查内容为准，数据库为索引：应用更新通过单一事务日志同步，外部修改造成 hash 不一致时进入 reconciliation，不以数据库旧值覆盖文件。

移动同一项目目录不改变 projectId；同时打开同 ID 不同路径时只允许一个写实例。用户需要分叉副本时显式创建新 ID，并记录 parentProjectId。不要仅根据目录名识别项目。

## 4. 数据表与约束

采用 UUID 标识业务对象，UTC ISO 时间，序列号使用 64-bit 整数；JSON 编码必须有 schemaVersion，未知版本只读并提示升级。所有外键启用，迁移前备份，事务失败回滚。

| 表 | 必需字段与关键约束 |
| --- | --- |
| projects | id PK, schema_version, root_realpath, workflow_version, revision |
| stages | project_id+stage_id PK, gate_status, source_hash, checked_revision, reason |
| tasks | id PK, project_id, stage_id, objective, status, executor_id, run_id, thread_id, turn_id, input_fingerprint, created_at, updated_at |
| events | project_id+seq PK, event_id UNIQUE, task_id nullable, type, schema_version, payload_json, created_at |
| sources | id PK, project_id, original_name, imported_relpath, sha256, provenance_json; UNIQUE(project_id,sha256) |
| artifacts | id PK, project_id, relpath, type, current_version_id, quality_status, stale_reason; UNIQUE(project_id,relpath) |
| artifact_versions | id PK, artifact_id, sha256, base_version_id nullable, producer_task_id nullable, state, origin, created_at |
| dependencies | downstream_artifact_id+upstream_id+upstream_version PK, upstream_kind |
| decisions | id PK, task_id, kind, status, target_revision, question_json, answer_json nullable, runtime_request_id nullable, expires_at nullable |
| leases | project_id PK, owner_id, epoch, expires_at, heartbeat_at |
| checkpoints | task_id PK, completed_steps_json, pending_steps_json, external_task_ids_json, reconciliation_state |
| request_dedup | project_id+actor_id+idempotency_key PK, method_path, body_sha256, status_code, response_json |
| publish_ops | id PK, artifact_id, old_hash, new_hash, phase, version_id, temp_relpath |
| usage | task_id+provider_event_key PK, source, input_tokens nullable, output_tokens nullable, cached_read_tokens nullable, cached_write_tokens nullable, cost nullable, currency nullable |

不把“unknown”储为数字 0。用量记录保存来源与计数语义（delta/cumulative），累计事件覆盖对应快照，不能重复相加。

## 5. 状态机与事件契约

任务状态：`queued → running → waiting_user/running → completed`；可进入 `stopping → interrupted` 或 `failed`。连接未知进入 `reconciling`，不能直接变 completed 或自动重试。恢复历史任务保留 attempt，创建新的 runId，避免抹去失败经过。

阶段质量状态沿用 cyz 的 pending/in_progress/blocked/passed，另以 artifact.quality_status 保存 unverified/verified/needs_review。任务 completed 不改变学术门检。S8 导出必须验证当前正文 hash 与语言审阅报告匹配。

标准事件结构：

```json
{"schemaVersion":1,"eventId":"UUID","projectId":"UUID","seq":21,"taskId":"UUID","type":"artifact.candidate.created","occurredAt":"2026-09-18T00:00:00Z","payload":{"artifactId":"UUID","versionId":"UUID","baseVersionId":null}}
```

事件类型最少支持 task.status.changed、message.delta、message.completed、tool.status.changed、decision.requested、decision.resolved、artifact.candidate.created、artifact.published、artifact.conflict、artifact.stale、source.imported、cache.reused、lease.changed、usage.updated、recovery.required。

seq 在项目数据库事务内分配，业务写入和持久事件同事务提交。UI 按 eventId 去重并持久化已处理 seq；SSE 通过 Last-Event-ID=seq 重放。缺少历史时先请求 snapshot 返回 snapshotSeq，再订阅之后事件，不能仅凭内存恢复进度。

高频文字 delta 可按 100ms 批处理落库；最终消息必须持久完整文本。崩溃后允许标记尾部流式文字未完整，不能把残缺消息标为完成。工具消息只展示运行时公开返回内容，不采集私有思维链。

## 6. Codex 接入及预验证

本次本机只读检查版本为 `codex-cli 0.153.4`，app-server 帮助标为 experimental，支持 stdio 与协议类型生成。该事实不代表本产品已接入，也不是任意未来版本兼容保证。

执行者首先在小型隔离项目运行：

```powershell
codex --version
codex app-server generate-ts --out packages/codex-adapter/generated
codex app-server generate-json-schema --help
codex app-server --stdio
```

生成 schema/type 并记录 CLI 版本、生成命令和 hash；所有运行时请求使用该版本类型验证，不凭本文拼造未知参数。完成初始化后验证 thread/start、thread/resume、turn/start、turn/interrupt 的实际支持，以及该版本公开事件、审批和用户输入请求。协议细节以本机生成类型和官方文档为准。[官方 App Server 文档](https://learn.chatgpt.com/docs/app-server)

Node 隐藏启动可执行入口，优先查明真正的 exe/cmd；若通过 PowerShell 调用，则用固定参数数组或编码脚本传入，不把用户消息拼成 shell 命令。stdout 仅作协议帧，stderr 限长脱敏。启动超时 30 秒、一般 RPC 30 秒；研究 turn 不设置 30 秒总时限，按事件状态跟踪。

维护 requestId→pending promise 与 runtimeRequestId→decision 映射。未知 server request 不自动批准；记录并提示不支持。文本消息、工具事件、最终结果分开归一化。登录沿用 Codex 支持的本机机制；认证失效时请求用户登录，不读取/复制 token 到项目。

UI 关闭默认隐藏到托盘并保持当前任务；无运行任务时可退出。显式“退出应用”若有任务必须显示“后台继续”与“停止并退出”。停止超时 15 秒后保持 stopping/reconciling 并提供受管进程诊断，不伪报已停止，不批量结束系统 Python/Electron。

主进程崩溃时先查询记录的 thread/turn 与实际 runtime 能力。stdio 连接恢复不能假定旧子进程仍可接回；若支持恢复读取则核实，否则将状态标为未知，展示已确认成果并等待用户继续，绝不盲目再次 turn/start。

重复失败自动重试最多 2 次，只对已证明未提交的幂等调用重试。模型请求结果未知时不自动重试。同一无进展错误连续 3 次产生诊断并等待处理，费用额度不是自动停止条件。

## 7. 执行隔离、版本与发布事务

不能仅靠提示词声称 AI 不会覆盖人工稿。首版采用每 run 独立工作副本：把本次所需 cyz 文档、源材料引用/副本和已确认成果复制到 `.cyz/runs/<runId>/workspace`，记录每个输入的 base hash。任务 cwd 指向该副本，Codex 的写入限于 run 工作副本；正式成果由项目服务发布。

共享 skill/模型只读；不使用硬链接连接可变稿件，避免副本改动影响主文件。不盲目复制整个项目或用户历史。大 PDF 可复用只读路径，但必须验证当前沙箱确实允许只读访问而不能改写；不能验证则复制。实现时对 Windows 实际 sandbox 做越界写入负例；无法实现所需限制时不得静默降成 unrestricted 并宣称达标，应调整隔离策略或明确阻塞此门槛。

Codex 通过 bridge CLI 提交候选，或应用扫描工作副本差异生成候选。新成果 baseVersion=null；已存在成果必须携带正确 baseVersion。通过检查且无人工冲突的普通成果可自动发布；涉及尚未回答的研究决定不能自动通过 gate。人工编辑保存同样走版本服务。

发布采用可恢复事务：

1. 校验路径、租约 epoch、baseVersion、输入依赖和当前文件 hash。
2. 将候选内容存入不可变 versions/hash，写入 publish_ops=prepared。
3. 在目标同目录写临时文件并同步磁盘；再次核对目标 hash；替换目标，标记 file_replaced。
4. 数据库事务更新当前版本、依赖、事件，标记 committed；最后清理临时文件。
5. 任一阶段崩溃后按目标 hash=old/new/other 重放提交、保留候选或进入冲突，不猜测最后成功状态。

应用内写入串行化；外部非协议编辑无法绝对锁死，监听与 hash 再核查发现冲突。若系统允许文件共享竞态，外部版本另存并显示冲突，保证可恢复内容，不把协作租约宣传为 OS 级隔离。

上游变化按依赖图传播 needs_review，检测环并拒绝循环依赖。无需自动重新生成下游。回滚是把旧内容发布为新版本，保留历史。

## 8. 本机 HTTP API 与 Codex 工具桥

仅监听 `127.0.0.1` 动态端口。令牌由主进程生成，保存在应用用户数据目录、限制当前用户访问；不放项目、渲染页、日志或命令行参数。CLI 通过受保护的连接文件读取。请求验证 Authorization、Host 和 Origin；浏览器跨源默认拒绝。UI 通过 preload 白名单 IPC，不直接持有 HTTP token。

版本前缀 `/v1`，JSON 最大 1 MiB，材料通过受控导入路径处理而非大 JSON。所有业务写请求携带 Idempotency-Key；同 actor/key 相同请求返回原结果，内容不同返回 409。error 格式 `{code,message,requestId,retryable,details}`，details 不泄漏凭据。

| 接口 | 请求关键字段 | 结果/语义 |
| --- | --- | --- |
| GET /health | 无 | 应用/协议版本，不泄漏项目隐私 |
| GET /v1/projects | 认证 | 已登记项目列表，不扫描磁盘 |
| GET /v1/projects/:id/snapshot | 认证 | 阶段、任务、成果、pending decisions、snapshotSeq |
| GET /v1/projects/:id/events | Last-Event-ID | SSE，项目范围顺序重放 |
| POST /v1/projects/:id/leases | ownerId | epoch、expiresAt；冲突 409 |
| POST /v1/projects/:id/leases/renew | ownerId,epoch | 续期；旧 epoch 409 |
| DELETE /v1/projects/:id/leases/current | ownerId,epoch | 仅释放自己的执行权 |
| POST /v1/projects/:id/tasks | goal,stageId,inputArtifactIds,ownerId,epoch | 新 taskId；不会隐式启动第二执行方 |
| PATCH /v1/tasks/:id/status | expectedRevision,status,ownerId,epoch | 检查允许状态转换 |
| POST /v1/tasks/:id/events | producerEventId,type,payload,ownerId,epoch | 去重并分配 seq，事件类型白名单 |
| POST /v1/tasks/:id/artifacts/candidates | relpath,content,baseVersionId,dependencies,ownerId,epoch | 新候选，冲突保留双方 |
| POST /v1/artifacts/:id/publish | candidateVersionId,expectedVersionId,ownerId,epoch | 原子发布；hash 冲突 409 |
| POST /v1/tasks/:id/decisions | question,options,recommendation,targetRevision | pending 决定卡 |
| GET /v1/decisions/:id | 认证 | pending/answered/expired；未答不阻塞请求连接 |
| POST /v1/decisions/:id/answer | answer,targetRevision | 仅 UI 用户身份可答；重复同答幂等，旧版 409 |
| POST /v1/tasks/:id/checkpoint | completed,pending,externalTaskIds | 只保存已核实进度 |

认证失败 401，未授权项目 403，资源不存在 404，状态/版本冲突 409，路径或结构错误 422，不支持的契约版本 426。HTTP 连接令牌只证明访问本机服务；每个 agent capability 还限定 projectId、runId、角色和租约，不能由外部 agent 冒充 UI 回答用户确认。

lease 默认 60 秒，每 15 秒续期。过期后不得直接抢占：核实原执行是否仍在运行，必要时先停止或由用户明确交接，成功接管后 epoch 递增，旧写入一律拒绝。只约束遵循接口的执行方，外部直接改文件仍按冲突处理。

配套 CLI 命令族 `cyz-workbench status|claim|renew|release|task|event|artifact|decision|checkpoint`，参数解析后调用同一 API。产出 skill 接入说明和一份可运行外部 Codex 场景。正常接管不能要求用户每次手工粘贴 token。

路径只接受规范相对路径；拒绝绝对路径、`..`、UNC、设备路径、NTFS ADS、保留名称和非法字符。对已存在父目录 realpath 后验证仍在项目根内，junction/symlink 越界拒绝；不存在的目标逐层检查并在写前重验。不得只用字符串 startsWith。

## 9. 界面、IPC 与材料处理

三栏：左侧阶段与资料入口，中间进度/成果/编辑器，右侧对话与决定卡。idea 卡至少显示候选、当前问题、依据、材料需求、风险与下一决定。用户不了解术语时由对话解释，不堆原始 JSON。

preload 只暴露 `projects.* / tasks.* / decisions.* / artifacts.* / events.subscribe / dialogs.*` 的有限方法，全部运行时 schema 校验。禁 nodeIntegration、启用 contextIsolation 和 sandbox，限制导航/新窗口。Markdown 禁脚本与原始危险 HTML，外链经确认用系统浏览器，PDF 通过受控本地协议读取；预览不能获取 token 或执行系统命令。[Electron 安全资料](https://www.electronjs.org/docs/latest/tutorial/security)

材料导入：dialog 选择 → 流式 SHA256 → source 去重 → 同名不同内容新 sourceId → 复制到临时文件并核对 → 原子登记。取消或崩溃只留下可清理临时文件，不登记半个 source。原始外部文件 hash 前后相同。

矩阵以现有 Markdown 为源，表格展示和编辑优先只管理明确列；未知列、脚注、单元格换行无法无损解析时切换源码编辑，不能静默丢内容。PDF 定位用页码和 source_map 的 block ID；没有定位时明确未知。

进度仅展示已知计数，不根据耗时拟造百分比。100 篇材料列表应虚拟化；2,000 个本地事件回放后交互仍可用。性能测试机器、样本、启动/查询时间必须记录，不把远端模型延迟算成本地 UI 性能。

## 10. MinerU、缓存与 humanizer

MinerU-adapter 不再实现另一套启动/认证逻辑，调用已发布的本地 skill 约定、Codex.ps1 和 cyz exporter/importer。提交前登记 request/task 关联；响应丢失先查任务，不重复提交。Desk 输出从实际返回值读取。只取消自己关联的任务。

本地解析缓存以源 SHA256、转换器 schema、有效参数与实际运行版本判断；研究成果复用键包含输入版本、目标、workflow/skill hash、模型可用标识及关键上下文。复用结果须通过完整性检查，复用事件和模型 cache usage 分开。

语言润色必须实际通过已发布 humanizer 适配器，基线、语义检查和报告进入 artifact 版本体系。语言处理后的新文本不会继承旧正文的审阅 hash。

工作台不保证 Codex 服务端 prompt cache 命中或折扣；只显示真实报告信息。未来 provider 能力设计见下一节。[OpenAI 缓存说明](https://developers.openai.com/api/docs/guides/prompt-caching)

## 11. 未来独立 API 执行器契约

第一版只实现 CodexEngine 与不联网的 FakeEngine。共同接口：

```typescript
type Usage = { input: number|null; output: number|null; cachedRead: number|null; cachedWrite: number|null; cost: number|null; source: string };
interface ResearchEngine {
  capabilities(): Promise<{ resume: boolean; approvals: boolean; usage: boolean; promptCache: 'reported'|'unsupported'|'unknown' }>;
  start(request: { projectId: string; taskId: string; runId: string; cwd: string; prompt: string }): Promise<{ sessionId: string }>;
  resume(request: { sessionId: string; taskId: string; prompt: string }): Promise<void>;
  stop(request: { sessionId: string; taskId: string }): Promise<void>;
  answer(request: { requestId: string; targetRevision: number; answer: unknown }): Promise<void>;
  subscribe(listener: (event: { type: string; taskId: string; payload: unknown }) => void): () => void;
}
```

新增 provider 不得绕开 ProjectService 或版本发布。未来 OpenAI-compatible 与 Anthropic 分开适配 endpoint、messages、tool calls、cache 参数和 usage；稳定前缀和工具顺序靠前，动态资料增量加入，不默认发送全项目。Anthropic 的 cache_control 与读取/写入用量依能力支持，未知中转不假定透传。[Anthropic 缓存说明](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

首期验收 FakeEngine 与 CodexEngine 共享事件/项目模型，以及 UI 对 unsupported/unknown 的诚实呈现；不要求真实付费 provider，不把此预案写成已支持第三方 API。

## 12. 验收层次和全流程研究样例

自动化分四层：纯状态/路径/幂等/恢复算法；临时 SQLite+文件集成；FakeEngine 驱动的真实 Electron UI；真实 Codex+本地 MinerU live。前三层不能替代第四层。

全流程研究样例采用公开可核验资料的“小型教育教学文献分析/教学设计研究”。S6 处理实际取得的文献编码表和比较结果，S8 交付带范围限制的示范稿与 PDF；不需要也不允许伪造学生课堂实验。若用户提供真实教学数据，再追加相应设计，但不把等待未提供数据作为无限停滞理由。

至少 3 篇开放全文，其中 2 篇以上 PDF 实际通过本机 MinerU。保留检索日期、来源 URL、access level、原件 hash、页码/块定位。研究样例是软件验收示范，不宣称完成系统综述或可直接投稿。需要关键选择的 live 场景请求真实用户回答；离线回归允许预设测试剧本，报告明确标记 simulated，不冒充用户。

强制证据矩阵见 Goal 文件 WB01–WB20、E01–E06。每条包含 actual result、passed/failed/blocked、时间、命令或操作、截图/日志/文件、commit 与版本，不能只写“检查通过”。

## 13. 实施工作包及验证命令

执行者建立下列 package scripts；命令是应交付的运行接口，不代表当前已有项目：

```powershell
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm test:unit
pnpm test:integration
pnpm test:e2e
pnpm test:live
pnpm build
pnpm package:win
pnpm verify:package
```

所有必需 tests 返回 0，无未说明 skipped。`test:live` 需要真实运行时，不满足时非零并输出 blocked，不用 mock 替代后退出成功。可选测试单独分组，不能把未通过必需测试改标 optional。

- [ ] B1 接入验证：协议生成、登录复用、消息、问题/审批、停止、恢复；产物 codex-compatibility.md 和脱敏 live 记录；失败先修适配。
- [ ] B2 数据服务：表迁移、导入、版本发布、恢复日志、租约、事件序列、幂等与路径测试。
- [ ] B3 UI：三栏、项目选择、全阶段、idea 卡、对话、资料/矩阵/编辑器；先给真实可交互预览并收集现有用户反馈，不为等待纯美术偏好阻塞已授权功能开发。
- [ ] B4 工具桥：HTTP/CLI/外部 Codex 接管、认证与越界负例、恢复与状态同步。
- [ ] B5 研究集成：发布版 cyz、本地 MinerU、语言处理、质量门检与引用定位；跑完整文献小流程。
- [ ] B6 韧性：编辑冲突、重复事件、结果未知、停机、断线、迁移备份、失效依赖；故障注入。
- [ ] B7 全流程 live：无 idea、有 idea 两入口；S0–S8 示例及成品核查。
- [ ] B8 Windows 分发：生成 portable ZIP 和可用启动入口，在非开发目录解包运行，验证 SQLite 原生模块、中文路径、项目打开/保存；如交付安装器则另外测试安装与卸载不删除项目。

包默认版本 0.1.0，实测支持范围至少记录当前 Windows、Codex、Desk 和 cyz 版本。未取得代码签名证书时明确未签名，不承诺消除 SmartScreen 提示，不代用户购买证书。

## 14. 最终交付与发布边界

必需交付工作台源码、锁文件、架构/接口文档、安装使用说明、portable ZIP、SHA256、完整验收报告、真实样例项目与已知限制。源码和二进制可以上传到用户 GitHub 独立工作台仓库；同样遵守 Goal 文件发布策略，不带真实私密研究材料。

发布版引用确定的 cyz tag，不复制并另改一套 workflow。运行时发现不支持的 workflow schema 时只读提示，不破坏项目。日志脱敏但保留诊断代码；公开报告不含原生认证、学生数据或私有路径。

此方案的技术选择可在接入试验发现不兼容时局部调整，须记录理由与验收等价性；不能用降级功能、删测试、模拟结果或更改用户目标来换取“全部完成”。
