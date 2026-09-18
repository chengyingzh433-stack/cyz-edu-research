# Integrity And Quality Gates

Use these gates before moving stages and before final output.

## Evidence Labels

| Label | Meaning | Final use |
| --- | --- | --- |
| `已核验` | confirmed against original source, data, or authoritative record | allowed |
| `待核验文献` | abstract, secondary report, incomplete metadata, or missing locator | verify first |
| `研究者推断` | user’s interpretation derived from evidence | allowed only with explicit reasoning |
| `AI建议` | candidate idea, wording, or explanation | not evidence |
| `待补材料` | missing method, sample, data, or procedure | resolve first |
| `不可使用` | fabricated, untraceable, or contradicted | remove |

## Gate S0: Direction Discovery

- scan scope and queries recorded;
- scan depth and access level visible;
- directions supported by identifiable paper IDs;
- method/population/context distributions summarized;
- candidate opportunities not mislabeled as proven gaps;
- recommended direction considers feasibility and ethics.
- about 3–5 candidates are shown only when supported; fewer are allowed and the list is never padded;
- the coverage-based broad-search stop reason is recorded.

## Gate S1: Research Question

- question is empirical and answerable;
- population/context and constructs are clear enough;
- value and literature connection are visible;
- evidence can realistically be collected;
- scope is manageable;
- user confirmed the main RQ.
- the current `idea_revision` has stable candidate/current-topic fields, a user-sourced decision, and traceable handoff references;
- alternatives, closest research, counterevidence, failure conditions, data requirements, feasibility, ethics, and claim boundaries are explicit;
- qualitative or design questions mark quantitative requirements as `not applicable`; satisfaction is not substituted for learning outcomes.

Do not pass S0 or S1 from formatting alone. `needs_verification` and `blocked` cannot pass. `ready` means only that the current idea revision can enter the next research stage; it does not prove novelty, effectiveness, or publishability. Do not enter writing before user confirmation of the current question and claim boundary.

## Gate S2-S4: Literature

- exact search records retained;
- inclusion/exclusion decisions traceable;
- metadata deduplicated;
- evidence access levels declared;
- core claims point to original locations;
- synthesis compares studies rather than lists them;
- gap passed a targeted disconfirmation search or remains `待核验`.

## Gate S5: Design

- every RQ maps to construct/phenomenon, data, collection, analysis, and result form;
- every collected data source has a purpose;
- sampling and grouping match claims;
- tools and procedures are sufficiently specified;
- quality/validity/trustworthiness procedures fit the design;
- ethics and student-data protection are addressed before collection;
- causal language matches design strength.

## Gate S6: Data And Analysis

- data source and transformations are logged;
- exclusions, missingness, attrition, and anomalies are visible;
- method assumptions and nesting are considered;
- results answer RQs in stable order;
- negative, non-significant, or disconfirming evidence is not hidden;
- reported values match source tables, outputs, or coded evidence.

## Gate S7: Writing

- title, abstract, introduction, RQs, method, results, discussion, and conclusion align;
- each literature claim has source support;
- each empirical claim has data support;
- results and discussion remain distinct;
- interpretations identify alternatives and boundaries;
- limitations explain impact, not merely list weaknesses;
- placeholders and unverified content are visible.

### Gate S7-L: Academic Language Pass

Apply by default when the workbench materially drafted or rewrote Chinese or English manuscript prose, or when the user requests humanization. Record `不适用` or `用户跳过` instead of fabricating completion when the pass does not run:

- actual language dependency and reviewed scope recorded (humanizer-zh for Chinese, humanizer for English);
- substantive revision passed before language editing;
- a pre-pass Markdown baseline and SHA-256 were recorded;
- section-specific intensity and frozen text were declared;
- the target text’s source gate (`AI辅助生成/真人原稿/混合稿/不确定`) and action were recorded;
- the deterministic semantic-lock comparison has no unresolved high-risk difference;
- manual comparison confirms population, context, conditions, result direction, uncertainty, causality, limitations, and source meaning did not drift;
- a second language check was run after semantic repairs;
- the polishing report states the reviewed and unreviewed scope;
- no claim is made that AI detection can be defeated or that the entire manuscript is guaranteed free of AI-style wording.

## Gate S8: Finalization

Block “final” or “submission-ready” status when any of these remain:

- fabricated or unverified citation used as support;
- unresolved data/number inconsistency;
- missing method detail that changes interpretation;
- unsupported causal or novelty claim;
- ethics information absent for human/student research when required;
- conclusion exceeds sample, context, or design;
- source locator does not support the stated claim;
- language polishing changed a number, statistic, citation, quotation, RQ, hypothesis, variable, figure/table reference, placeholder, or other frozen anchor without explicit substantive review;
- language polishing weakened uncertainty, strengthened causality, hid negative evidence, or expanded the conclusion boundary;
- a requested final language pass lacks its pre-pass baseline, semantic-regression record, or declared review scope;
- the current Markdown master hash differs from the reviewed post-language-pass hash; any later edit must invalidate the prior pass and trigger a scoped recheck.

Non-blocking issues may be disclosed as limitations or pending format work. Produce [audit-report.md](../templates/audit-report.md) and state what was checked, what remains uncertain, and why.

When a language pass was performed, also complete [academic-humanization-report.md](../templates/academic-humanization-report.md). A clean automated anchor comparison is not evidence of full semantic equivalence; retain manual review.

After the language pass, run S8 as a read-only audit. If S8 requires a manuscript edit, set the language-pass status back to `处理中`, revise the affected passage, rerun semantic and language checks, update hashes, and only then export.

## Cross-Section Alignment Table

Use this compact audit:

| RQ | Literature basis | Data/method | Result | Discussion claim | Conclusion | Status |
| --- | --- | --- | --- | --- | --- | --- |

Any empty cell is an alignment problem. Repair the earliest responsible stage.
