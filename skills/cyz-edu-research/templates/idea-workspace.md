# 研究起点与问题

<!-- cyz:idea-canvas:start -->
## Idea 工作区

- 入口：`{{ENTRY_MODE}}`
- 模式：`{{IDEA_MODE}}`
- 成熟度：`{{IDEA_MATURITY}}`
- 状态：`{{IDEA_STATUS}}`
- 修订：`1`

### 原始想法或材料

- 材料状态：`{{MATERIAL_STATUS}}`
- 用户原话：`待填写`
- 来源：`user_statement`

### 候选卡模板

<!-- cyz:candidate-template:start -->
- candidate_id: C-###
- idea_revision: 1
- specific_problem: 待填写
- scope: 学段/学科内容/对象/情境
- paper_ids: []
- evidence_locators: []
- possible_value: 待核验
- closest_research: 待核验
- materials_existing: []
- materials_acquirable: []
- materials_new_required: []
- alternatives: []
- failure_conditions: []
- feasibility: 待核对
- claim_limits: 待核验
- recommendation_reason: 待记录
<!-- cyz:candidate-template:end -->

> 复制模板生成候选卡；保持 candidate_id 稳定，不得把 AI 建议写成已核验证据。

### 当前选题卡模板

<!-- cyz:current-topic-template:start -->
- topic_id: T-###
- idea_revision: 1
- core_concepts: []
- main_question: 待确认
- subquestions: []
- question_type: 待确认
- scope: 待确认
- exclusions: []
- provisional_explanation: 待核验
- alternatives: []
- evidence_locators: []
- claim_limits: 待核验
- key_unknowns: []
- next_decision: 待确认
<!-- cyz:current-topic-template:end -->

### 决策记录模板

<!-- cyz:decision-template:start -->
- decision_id: D-###
- idea_revision: 1
- question: 待记录
- answer: 待记录
- source: user_statement
- decided_at: YYYY-MM-DD
- affects: []
<!-- cyz:decision-template:end -->

> 真实记录使用 `cyz:decision-record:start/end` 标记；模板本身不是当前决策。

### 证据路线

- [文献检索记录](02-文献/00-检索记录.md)
- [文献证据矩阵](03-文献证据矩阵.md)

<!-- cyz:evidence-template:start -->
- evidence_id: E-###
- idea_revision: 1
- claim_id: C-###
- source_type: literature_record
- source_locator: 02-文献/00-检索记录.md#record-id
- access_level: metadata
- verification_status: pending_verification
- recorded_at: YYYY-MM-DD
<!-- cyz:evidence-template:end -->

> 真实记录使用 `cyz:evidence-record:start/end` 标记，source_locator 必须是可定位来源。

### 交接区

<!-- cyz:handoff-template:start -->
- handoff_id: H-###
- idea_revision: 1
- topic_id_ref: T-###
- decision_id_ref: D-###
- evidence_ids: []
- summary: 待确认
- confirmed_scope: 待确认
- evidence_locators: []
- unverified_items: []
- evidence_route: 待确认
- claim_limits: 待核验
- next_stage: S1
- required_actions: []
<!-- cyz:handoff-template:end -->
<!-- cyz:idea-canvas:end -->
