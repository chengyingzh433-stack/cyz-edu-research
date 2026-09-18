# Idea Scout: Literature-Based Direction Discovery

Use when the user has no research idea. The goal is a reliable map of directions, not a literature review and not a stack of detailed paper summaries.

## Minimum Intake

Collect only boundaries that change the search:

- broad field, such as high-school physics teaching, science education, or teacher education;
- accessible stage, participants, or setting, if known;
- Chinese/English balance;
- time or feasibility constraints;
- excluded topics or methods, if any.

If the user truly has no boundary, start with a broad physics-education or education scan and clearly label the scope chosen by the workbench.

## Scan Sequence

1. Prefer recent reviews and broad field maps to learn terminology.
2. Search Chinese and English sources with recorded queries and dates.
3. Deduplicate by DOI, database ID, or normalized title.
4. Screen title and abstract for education relevance.
5. For each retained candidate, extract the compact fields below.
6. Cluster by educational problem, theory, method, population, context, and outcome/theme.
7. Verify a small number of representative and contradictory papers against full text when accessible.
8. Produce candidate directions, not premature detailed proposals. Reuse supplied seed papers and valid caches before supplementary searching.

## Compact Paper Scan

Use [three-way-scan.md](../templates/three-way-scan.md).

- `WHY`: problem, tension, or bottleneck and why it matters.
- `HOW`: design, sample/context, data source, method, and analysis route.
- `WHAT`: finding direction, claimed contribution, limitation, or unresolved issue.

Add education-specific fields:

- direction and RQ type;
- stage, subject, participants, and setting;
- theory or core constructs;
- variables, outcomes, or qualitative themes;
- evidence access: metadata, abstract, partial full text, or verified full text;
- relevance and feasibility for the user.

Do not infer unreported methods or results. Abstract-level evidence cannot support full method-quality judgments.

## Cross-Paper Outputs

Produce:

1. common `WHY` problems;
2. divergent `HOW` methods and evidence paths;
3. strongest or most repeated `WHAT` findings;
4. contradictions and conditional differences;
5. method, population, context, theory, and time distributions;
6. underrepresented areas marked as candidate opportunities, not proven gaps;
7. representative, contradictory, and priority-reading papers;
8. about 3–5 candidate directions scored on value, evidence base, feasibility, ethics, and fit with accessible settings, but only when evidence supports that many.

## Candidate Direction Card

Use exactly the canonical fields carried into refinement:

- Candidate card: `candidate_id`, `idea_revision`, `specific_problem`, `scope`, `paper_ids`, `evidence_locators`, `possible_value`, `closest_research`, `materials_existing`, `materials_acquirable`, `materials_new_required`, `alternatives`, `counterevidence`, `failure_conditions`, `feasibility`, `claim_limits`, `recommendation_reason`.

Put scan-wide depth, coverage, terminology, and next-search notes in the direction scan package rather than inventing extra candidate fields. Within the canonical card, use `claim_limits` for material uncertainty, `alternatives` for promising competing questions, `feasibility` for prerequisites and collection burden, and `failure_conditions` for primary risks.

Present about 3–5 cards when supported. Do not pad the list to reach 3–5: show fewer and state the evidence shortage. Use the guided mentor to recommend one main direction and at most two backups.

Stop broad discovery when coverage includes the main terminology and plausible direction families, seed-material bias has been checked, a representative and a contradictory source have been sought where available, and another search round no longer changes the candidate set or known uncertainties. Also stop when the user confirms a direction. Record the stop reason, then switch to targeted search and [idea-refinement.md](idea-refinement.md).
