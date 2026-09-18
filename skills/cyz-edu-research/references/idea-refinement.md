# Evidence-Bounded Idea Refinement

Use for any existing idea: a concern, keyword, direction, title, tentative question, or complete plan. Start from its present maturity and skip broad discovery. Use targeted literature checks only for uncertainties that could change the idea.

## Maturity Route

| Maturity | Next action |
| --- | --- |
| `broad_interest` | Offer a few substantively different problem framings and identify the first consequential boundary. |
| `tentative_topic` | Separate topic/title from an answerable question; specify scope, constructs or phenomenon, and evidence need. |
| `provisional_question` | Check closest research, alternatives, feasibility, ethics, and claim boundary. |
| `structured_plan` | Audit unsupported assumptions, counterevidence, failure conditions, data requirements, and design–claim fit. |

Do not enter writing before user confirmation of the current question and claim boundary. A polished title or complete format is not evidence that the idea is ready.

## Refinement Loop

1. Preserve the user's original wording and classify maturity without upgrading its evidence status.
2. State the current bottleneck and complete any safe comparison or targeted check first.
3. Compare alternatives, including a null or simpler explanation when relevant.
4. Record counterevidence, failure conditions, data requirements, feasibility, ethics, and claim boundary.
5. Recommend a next choice, then use the guided mentor for exactly one consequential question per turn.
6. After a substantive change, increment `idea_revision`; retain the prior candidate, decision history, and reason.
7. Recheck any downstream record tied to an older revision.

For a near-duplicate study, compare task, population, context, mechanism, data, and intended claim. Require a substantive change, narrower justified claim, or reject the candidate. A title-only revision is not substantive. Preserve the decision history and the closest-study locator.

## Material And Claim Boundaries

Classify every required source as `existing | obtainable | new collection`. Make collection burden, access, consent, and ethics visible. Never describe planned data as existing data.

Qualitative, textbook, design, action-research, quantitative, and mixed-method questions need different evidence routes. Mark requirements that do not apply as `not applicable`; do not force a quantitative hypothesis onto a qualitative question. Satisfaction may be process evidence but cannot substitute for learning outcomes.

## Canonical Records

Use the matching marked regions in `01-研究起点与问题.md` and keep identifiers stable.

- Candidate card: `candidate_id`, `idea_revision`, `specific_problem`, `scope`, `paper_ids`, `evidence_locators`, `possible_value`, `closest_research`, `materials_existing`, `materials_acquirable`, `materials_new_required`, `alternatives`, `counterevidence`, `failure_conditions`, `feasibility`, `claim_limits`, `recommendation_reason`.
- Current topic: `topic_id`, `idea_revision`, `core_concepts`, `main_question`, `subquestions`, `question_type`, `scope`, `exclusions`, `provisional_explanation`, `alternatives`, `evidence_locators`, `claim_limits`, `key_unknowns`, `next_decision`.
- Decision record: `decision_id`, `idea_revision`, `question`, `answer`, `source`, `decided_at`, `affects`. An AI recommendation keeps `source: AI_suggestion`; only the user's answer uses `source: user_statement`.
- Handoff: `handoff_id`, `idea_revision`, `topic_id_ref`, `decision_id_ref`, `evidence_ids`, `summary`, `confirmed_scope`, `evidence_locators`, `unverified_items`, `evidence_route`, `claim_limits`, `next_stage`, `required_actions`.

## Exit And Handoff

Set `idea_status: needs_verification` when a decisive claim lacks full-text or other suitable evidence, and `blocked` when work cannot proceed without a named resource or decision. Set `ready` only when the current revision has a user-sourced decision, traceable evidence, feasible data route, alternatives and counterevidence reviewed, explicit claim limits, and no unresolved issue that could overturn the question. Ready means ready for the next research stage, not proven, publishable, or ready for manuscript drafting.
