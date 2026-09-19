# Academic Humanization And Semantic Regression

Use this module for Chinese or English academic prose whose substantive content is stable. Its purpose is to reduce formulaic AI-style wording and recover a consistent authorial academic voice without changing evidence, methods, results, or claim strength. It does not promise to defeat AI detectors or conceal required AI-use disclosure.

Run it by default before finalization when the workbench materially drafted or rewrote Chinese or English manuscript prose. If the manuscript is outside scope, record `不适用`. If the user explicitly declines the pass, record `用户跳过` and continue with ordinary integrity review; never pretend the pass occurred. For predominantly human-authored prose, diagnose first and preserve passages that already have a coherent authorial voice.

## Required Language Skill Routing

This module is an academic adapter, not a substitute for the language skill. Before editing, resolve and read the actual installed dependency:

- Chinese: sibling `humanizer-zh/SKILL.md`, specifically the syw2039/humanizer-zh distribution. For full revision read its `references/chinese-ai-patterns.md` as directed there.
- English: sibling `humanizer/SKILL.md` (catalog name may be `humanizer:humanizer`).
- Mixed manuscripts: route by paragraph/section; retain embedded English terms in Chinese passages. Do not translate, and do not apply both skills serially to the same paragraph.

Use embedded mode on a WORKING COPY, with language, section purpose, allowed intensity, frozen spans, and the verified source text explicitly supplied. Save only the resulting prose in the manuscript; the workbench records the separate audit. File-mode defaults must never overwrite the sole baseline. If the dependency is missing, report it and pause language rewriting or honor an explicit user skip; never label a generic rewrite as skill execution. Do not invoke qu-ai-wei as a hidden fallback.

Academic constraints govern this integration: preserve quotations, reference punctuation, mathematical ranges, statistics, required headings, and uncertainty even if generic style rules suggest removing them. No added personal stance or anecdotes. Chinese punctuation follows the institution/journal; English prose may use the English skill's style guidance outside frozen spans. Unsupported claims are returned to substantive review, not merely made to sound confident. The existing semantic-lock script and manual review apply to both languages; the script alone does not certify English/Chinese semantic equivalence.

Record language, skill name, resolved SKILL.md path, repository (Chinese: https://github.com/syw2039/humanizer-zh), version when available and SHA-256 of the loaded skill. For mixed work record each scope separately. A dependency update does not retroactively certify earlier text.

The repository-level `dependencies.lock.json` is the local installation evidence for the supported Chinese and English routes. The public release copy removes environment-specific paths while retaining declared versions or explicit unknown status, upstream and license evidence status. Runtime resolution remains strict: `zh` resolves only `humanizer-zh`; `en` resolves only `humanizer`. A missing required dependency is a blocking failure, and `qu-ai-wei` is never a substitute.

## Position In The Workflow

Run this as the final language sub-pass of `S7`, after substantive revision and before `S8` finalization:

```text
S7 substantive draft
-> argument/evidence/method/result alignment
-> freeze a pre-pass Markdown baseline
-> academic humanization
-> deterministic semantic-lock check
-> manual semantic regression
-> second language check
-> S7/S8 integrity gates
-> formatting and export
```

Do not run the final pass while `[待补数据]`, `[待核验引文]`, unresolved number conflicts, unstable RQs, or interpretation-changing method gaps remain. A provisional paragraph may be polished for readability only if it stays visibly provisional.

## Non-Negotiable Semantic Lock

Preserve exactly unless the researcher explicitly authorizes a substantive revision:

- RQs, hypotheses, construct definitions, variable names, coding labels, instrument items, and operational definitions;
- sample sizes, dates, durations, group names, statistics, units, percentages, confidence intervals, effect sizes, and significance values;
- quotations, citation identities, DOI, URLs, source locators, figure/table references, equations, symbols, and reference entries;
- direction and strength of findings, negative or non-significant findings, qualifiers, uncertainty, causal boundaries, limitations, and ethics statements;
- the distinction among author findings, cited findings, researcher inference, AI suggestion, and unresolved material.

Never replace a precise qualifier merely because it looks cautious. Terms such as `可能`, `在本研究样本中`, `相关`, `未发现显著差异`, and `不能据此推断因果` may carry essential epistemic meaning.

## Section-Specific Intensity

| Section | Default intensity | Rules |
| --- | --- | --- |
| Introduction, literature review, discussion, conclusion | moderate | Remove empty scaffolding and repetition; preserve sources, theoretical distinctions, uncertainty, and contribution limits. |
| Abstract | conservative | Preserve purpose, design, sample, method, exact result direction, and conclusion. Prefer compression over stylistic invention. |
| Methods and results | minimal | Improve syntax and local readability only. Do not vary terminology for style. Do not paraphrase statistics, procedures, items, themes, or quotations. |
| Title and headings | conservative | Revise only when wording is inflated, vague, or inconsistent with the study. |
| RQs, hypotheses, instruments, codebooks, quotations, equations, tables, references | frozen | Do not rewrite automatically. Flag a problem and ask for a substantive decision when necessary. |

## Academic Language Profile

Always classify the target as `学术/科技` unless the user identifies another document type. The Chinese checklist below supplements humanizer-zh; use humanizer patterns for English while retaining the same academic locks. Preserve necessary nominalization, passive constructions, terminology, and logical connectors. Do not turn academic prose into chat, publicity copy, or a personal essay.

Apply density and function tests rather than word blacklists. A single standard expression is not evidence of AI-style writing. Revise only when language is repetitive, empty, mechanically balanced, or detachable from the study.

Prioritize these repairs:

1. Remove generic era-setting openings, inflated significance, vague authority, unsupported novelty, and ceremonial conclusions.
2. Replace empty abstract verbs with precise verbs already supported by the sentence; never invent a more concrete action, number, actor, or event.
3. Cut redundant framing, repeated summaries, list previews, mechanical `首先/其次/最后`, and stacked `此外/然而/因此` when they add no logical function.
4. Vary sentence rhythm while keeping logical relations explicit. Split overloaded sentences and merge choppy ones without changing propositions.
5. Repair English-shaped Chinese syntax, repeated subjects, excessive relative clauses, punctuation residue, assistant voice, and Markdown artifacts that do not belong in the target format.
6. Keep one stable term for one construct. Do not rotate synonyms merely to create stylistic variety.
7. Preserve author-provided classroom observations or academically appropriate judgments in the introduction or discussion. Do not manufacture anecdotes, emotion, uncertainty, first-person voice, or an “AI would not write this” sentence.

## Academic Pattern Checklist

Use this checklist diagnostically. Trigger on density, emptiness, and function, not a banned-word list.

| Pattern | Revise when | Preserve when |
| --- | --- | --- |
| Generic era or policy opening | The opening can be moved to another topic without changing meaning. | The policy, event, or time change directly defines the research problem or context. |
| Inflated significance or novelty | `重要意义`, `全新`, `填补空白`, or `深刻影响` lacks a specific evidence-backed object. | The contribution is explicitly derived from literature, design, and results at a bounded strength. |
| Vague authority | `研究表明`, `有学者认为`, or `相关数据显示` has no traceable source. | The source is cited and the wording matches its access level and claim. |
| Abstract universal verbs | `赋能`, `助力`, `推动`, `构建`, `实现`, or `发挥作用` replaces the actual relationship or action. | It is an established technical term or the sentence specifies what changed and how. |
| Mechanical symmetry | Repeated `不仅……而且……`, `首先/其次/最后`, parallel clauses, or exactly three points packages weak content. | The parallel structure represents a real conceptual or procedural distinction. |
| Empty transitions and summaries | `此外`, `然而`, `因此`, `综上所述`, or `值得注意的是` adds no logical relation or new conclusion. | The connector accurately marks contrast, cause, consequence, scope, or synthesis. |
| Synonym rotation | One construct receives several labels merely to avoid repetition. | Different terms denote genuinely different constructs or cited terminology. |
| Redundant bilingual annotation | A familiar term is repeatedly followed by unnecessary English. | First-use terminology, an instrument name, an acronym, or an original construct requires it. |
| Filler and stacked hedging | Several empty qualifiers obscure the proposition. | A qualifier carries uncertainty, sampling, causal, measurement, or transfer limits. |
| Uniform sentence rhythm | Consecutive sentences repeat the same length and grammatical frame without analytical need. | Repetition is necessary for definitions, hypotheses, procedures, or comparable results. |
| Translation-shaped syntax | Long prepositional openings, stacked relative clauses, repeated subjects, or misplaced adverbials impede Chinese reading. | The syntax is required for technical precision and remains readable. |
| Assistant or promotional voice | The manuscript addresses the user, congratulates, advertises, promises, or uses generic positive endings. | Direct address is required by the target genre, such as an instructional appendix. |
| Formatting residue | Chat headings, excessive bold, emoji, raw prompts, URL tracking parameters, or template markers leak into prose. | Markdown structure belongs to the canonical working document or the target format requires it. |
| Formulaic negative definition | `这不是 X，而是 Y` offers an abstract slogan rather than a supported distinction. | It corrects a concrete misconception and immediately states the evidence or boundary. |

For Chinese punctuation, follow the target institution or journal. Normalize accidental half-width punctuation in Chinese prose, but preserve formulas, statistics, code, DOI, URL, English quotations, version numbers, and reference-style requirements.

## Mixed Human And AI Drafts

Do not classify an entire thesis as wholly human or wholly AI from surface style. Work section by section or paragraph by paragraph.

Before editing, record a source gate for the target text: `AI辅助生成`, `真人原稿`, `混合稿`, or `不确定`. For `真人原稿` or `不确定`, run diagnosis only unless the researcher identifies the exact passages to edit. If the passage contains a recognizable personal, interview, classroom, or co-author voice, preserve it by default. This prevents a language pass from erasing the researcher’s voice merely because the prose is formal.

- Preserve passages that already carry a coherent human academic voice.
- Edit only identified problems in mixed passages.
- If authorship or intended voice is uncertain, make a diagnostic report before rewriting.
- When the researcher provides 2-3 authentic academic samples, extract a small style profile: preferred terms, typical sentence length, paragraph openings, punctuation habits, and formality. Ask for confirmation only when applying it would materially change the prose.

## Execution Procedure

### 1. Establish The Baseline

Save or identify the pre-pass Markdown draft. Record its path and SHA-256 in the audit record. Never overwrite the only copy of the substantive draft.

### 2. Inventory Meaning Before Editing

For each target section record:

- controlling claim and RQ relation;
- cited evidence and source locators;
- empirical values and finding direction;
- qualifiers, causal limits, alternatives, and limitations;
- frozen terminology and text spans.

### 3. Run The First Language Pass

Edit prose only. Keep changes local when possible. If a sentence needs new evidence, a new interpretation, or a changed claim, mark it for substantive revision instead of smoothing it.

### 4. Run Deterministic Semantic-Lock Checks

Use `scripts/check_semantic_lock.py BEFORE AFTER` when two Markdown files are available. Treat every reported removal, addition, count change, or anchor-order change as a blocker until reviewed. The script catches high-risk anchors; a pass does not prove semantic equivalence or verify that a number still belongs to the same group, variable, table, or claim.

### 5. Run Manual Semantic Regression

Compare before and after for:

- proposition, subject, population, context, time, condition, direction, magnitude, and certainty;
- correlation versus causation;
- observed result versus explanation;
- author claim versus cited claim;
- limitation and transfer boundary;
- consistency with tables, figures, data outputs, evidence matrix, and source text.

If meaning drifted, restore the last valid wording for that passage and revise more narrowly. Never repair drift from memory.

Save the manual decision with the exact baseline and output SHA-256 values, issue type, disposition, and reason. In particular, changing a correlation statement into a causal statement must be recorded as `issue: correlation_to_causation` with `disposition: rejected`, even when the deterministic anchor check passes. An `accepted` disposition for that issue is invalid and blocks completion. The automated lock is necessary but never sufficient evidence of semantic equivalence.

### 6. Run A Second Language Check

Inspect the corrected text again for formulaic openings, empty transitions, synonym rotation, uniform sentence rhythm, translation-shaped syntax, assistant voice, and unsupported uplift. This second pass checks whether semantic repairs reintroduced awkward or generic wording.

If the second language check changes any text, rerun both the deterministic semantic-lock check and manual semantic regression for every affected passage. The final recorded hash must belong to the version that passed the last semantic check, not an earlier intermediate version.

### 7. Re-run S7 And S8

The language pass is complete only when:

- the deterministic check has no unresolved high-risk differences;
- manual semantic regression passes;
- S7 cross-section alignment still passes;
- S8 has no blocking evidence, data, method, ethics, citation, or claim-boundary issue;
- the final language check has no unresolved high-density AI-style pattern in the reviewed scope.

After the final language check, treat S8 as read-only unless a problem requires revision. Any change to the manuscript invalidates the recorded post-pass SHA-256 and returns the language-pass status to `处理中`. Re-run the semantic-lock comparison and second language check for every affected passage. Before formal export, confirm that the current Markdown master SHA-256 matches the reviewed post-pass hash in the report.

## Reporting

Use [academic-humanization-report.md](../templates/academic-humanization-report.md) at `07-论文草稿/学术语言打磨报告.md` and link its result from `08-审查与修改记录.md`. Keep the report outside the manuscript.

Allowed statuses:

- `不适用`: outside Chinese/English academic prose or no applicable language pass;
- `用户跳过`: user explicitly declined the default final language pass;
- `未开始`: no language pass requested;
- `阻塞`: substantive or evidence issues must be resolved first;
- `处理中`: language or regression checks are incomplete;
- `通过但有说明`: reviewed scope passed, with disclosed residual uncertainty;
- `通过`: reviewed scope passed all checks.

State the reviewed scope. Never report “全篇无 AI 味” unless every section was inspected, and even then describe the result as a bounded editorial assessment rather than a guarantee.

Keep the report frontmatter synchronized. For `passed` or `passed_with_notes`, record `baseline_path`, `baseline_sha256`, `master_path`, `reviewed_sha256`, and `export_sha256`. Use project-relative paths. Immediately before export, recompute the current master hash and write it to `export_sha256`; it must equal `reviewed_sha256`.

The immutable pre-pass baseline, editable post-pass master, and review report must be three separate files. Never point `baseline_path` and `master_path` to the same file, and never use the report itself as either text path. A later change to the master invalidates the old passing report at every project stage, not only at S8.

Mirror the report status in the `academic_language_pass_status` field of `00-项目状态.md`. A final project state must not say `passed` while the report remains `in_progress`, `blocked`, or `not_started`.

## Provenance

Historical provenance: the original academic adapter incorporated concepts from the MIT-licensed `qu-ai-wei` Skill; its notices remain for retained material. The current runtime dependencies are humanizer-zh and humanizer, not qu-ai-wei. Historically adapted concepts include: genre classification, density-based diagnosis, fact-preservation priority, overcorrection protection, Chinese syntax and rhythm repair, and an auditable polishing report. General-audience rules that conflict with academic writing were not carried over unchanged. See `THIRD_PARTY_NOTICES.md` and `third_party/qu-ai-wei-LICENSE.txt`.
