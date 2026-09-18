# Literature Search, Reading, Synthesis, And Gap Workflow

## 1. Start From A Question Or Scan Boundary

Before targeted searching, define the concepts, population, context, and question boundary. In no-idea discovery, use the broader boundary from `idea-scout` and do not pretend a final RQ already exists.

Choose one search purpose and reuse earlier records rather than restarting:

- `discovery scan`: map terminology and direction families before an idea exists;
- `targeted idea check`: test the closest research, counterevidence, and uncertainty that could change a candidate;
- `formal review`: execute the reproducible search, screening, appraisal, and synthesis needed for a confirmed RQ.

When seed papers or prior records exist, inventory, deduplicate, and reuse their paper IDs, access labels, caches, and extracted fields first. Supplement only the missing coverage. Record the stop condition before searching.

## 2. Search Matrix

For each concept list:

- Chinese and English terms;
- synonyms and translations;
- broader and narrower terms;
- related theoretical or methodological terms;
- spelling variants and acronyms;
- terms to exclude only when exclusion is justified.

Build Boolean combinations with `AND`, `OR`, and careful `NOT`. Record database/source, exact query, fields, filters, date, hit count, and access limits.

For physics education and education studies, prioritize a balanced set as available:

- Chinese: CNKI and relevant core or field journals;
- international: Web of Science, Google Scholar discovery, OpenAlex, Crossref, Semantic Scholar, ERIC or publisher indexes when accessible;
- STEM/technology: IEEE only when the topic genuinely involves educational technology or engineering education;
- citation chaining from representative papers.

Do not force a fixed number of databases. Use enough independent coverage for the claim being made.

## 3. Deduplication And Screening

Deduplicate by DOI or database ID, then normalized title, year, and authors. Keep a trace of merged versions.

Use two passes:

1. title/abstract relevance;
2. full-text relevance and quality for included core evidence.

Record exclusion reasons. Common reasons: wrong population, non-education focus, wrong outcome, wrong study type, insufficient evidence, inaccessible full text when method/result verification is required, duplicate, or outside justified date/language scope.

## 4. Evidence Access Levels

Label every paper:

- `M`: metadata only;
- `A`: abstract read;
- `P`: partial full text;
- `F`: full text inspected;
- `V`: key claims verified with source locators.

Never let `M` or `A` evidence silently support a detailed methods critique or precise result claim.

## 5. Reading Levels

### Rapid Scan

Use [rapid-scan.md](../templates/rapid-scan.md). Capture only what can be supported by the access level. Discovery mode normally ends here for most papers. Do not convert every PDF in a broad discovery set; build Markdown caches only for representative, contradictory, shortlisted, or explicitly requested papers.

### Standard Education-Research Reading

For a PDF, first build or reuse the cache defined in [pdf-reading.md](pdf-reading.md): valid cache first, otherwise local MinerU Desk through the mineru skill, then explicit native fallback if unavailable. Read `paper.md` for speed, but verify key claims against the original page. Then use [literature-card.md](../templates/literature-card.md). Explain the paper to a beginner, then extract professional fields and source locations.

Distinguish:

- authors’ stated purpose, findings, interpretation, and limitations;
- workbench appraisal;
- relevance or suggestions for the current project.

### Full Deep Reading

Apply the figure-aware cache and verification process in [pdf-reading.md](pdf-reading.md), or an equivalent HTML source map. Preserve figures, tables, definitions, method detail, and stable anchors. Use only for core theory, critical evidence, measurement, or method replication.

## 6. Education-Research Quality Appraisal

Do not use one hierarchy to rank all designs. First identify the study’s purpose and design, then assess fit.

Across designs check:

- setting, recruitment, sample, attrition, ethics, and consent;
- whether the method can answer the RQ;
- transparency of data collection and analysis;
- alternative explanations and negative evidence;
- claim strength versus design and context.

For quantitative or quasi-experimental studies check:

- baseline comparability, confounding, clustering, missing data, implementation fidelity;
- instrument validity and reliability in the present sample/context;
- analysis assumptions, effect size, uncertainty, and multiplicity where relevant.

For qualitative studies check:

- sampling rationale, researcher position, data sufficiency, interview/observation transparency;
- named and traceable analysis process;
- coding or theme development, disconfirming cases, triangulation, audit trail, and supporting quotations.

For mixed methods check each component plus integration: why methods were combined, where integration occurred, and whether the joint interpretation follows from both strands.

For action research check cycles, practitioner role, evidence across cycles, change mechanism, reflexivity, local utility, and limits on generalization.

Use quality as a multidimensional profile, not a prestige score. Do not equate citation count, journal impact, author institution, or a single design label with truth.

## 7. Evidence Matrix

Use [evidence-matrix.md](../templates/evidence-matrix.md). Include paper ID, topic, RQ, theory, context, sample, design, data, analysis, finding, limitations, quality profile, access level, project relevance, evidence status, and locator.

The matrix is the bridge between reading and writing. Update it after each standard or full reading.

## 8. Cross-Paper Synthesis

Synthesize by theme or explanatory function, not author-by-author sequence.

For each theme:

1. state the provisional claim;
2. identify converging evidence;
3. identify contradictions or conditional differences;
4. compare population, context, theory, instruments, intervention, duration, and methods;
5. weigh evidence by fit and quality profile;
6. state what remains uncertain;
7. connect the uncertainty to the current RQ or design.

Maintain a tension inventory for paper pairs that address the same construct but differ in findings. Do not claim all contradictions were checked; state the candidate-pair scope.

## 9. Research Gap Validation

A defensible gap answers:

1. what prior studies establish;
2. where explanation, observation, or applicability is stuck;
3. the specific theoretical, methodological, population, context, temporal, mechanism, or integration opening;
4. why entering there improves knowledge or practice.

After proposing a candidate gap, run a targeted verification search designed to disconfirm it. Record queries and contrary evidence. Mark the gap as `待核验` until this pass is complete.

Avoid “few studies exist” as the sole argument. Scarcity matters only when the missing evidence blocks an important explanation or decision.

For idea refinement, return the closest studies, contrary findings, unresolved conditions, evidence access limits, and implications for the candidate's alternatives, data requirements, failure conditions, and claim boundary. Do not turn a targeted check into a whole-discipline rescan.
