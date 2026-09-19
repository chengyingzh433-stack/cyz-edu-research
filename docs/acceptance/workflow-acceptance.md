# Workflow 0.3.0 Acceptance

## Current result

Post-release documentation audit (2026-09-19): the counts below describe the original test runs. A fresh-install language-dependency check was subsequently found to require an explicit supplemental lock; the packaged minimal lock and default lookup path are insufficient. See [the agent guide](https://github.com/chengyingzh433-stack/cyz-edu-research/blob/main/docs/agent-install.md#4-语言依赖与-030-兼容处理). The published ZIP is unchanged; this limitation must accompany the historical pass counts.

- WF01-WF12: **12/12 passed** on 2026-09-19.
- Scenario fixtures: **24/24 passed** (`I01-I14`, `H01-H04`, `M01-M06`).
- Deterministic unit suite: **96/96 passed** at candidate commit `132c213ec83b9ab46616504296fc5d43c35a80c6`, then **96/96 passed** again after verified local synchronization.
- Release package gates REL01-REL02: **passed**.
- REL03: **passed**; the private GitHub Release, annotated tag, remote re-download, fresh install, and two-root local synchronization were verified.

The detailed machine-readable record is in [evidence-index.json](evidence-index.json). Two idea sessions were executed by the current primary agent with scripted user turns, sequentially and without subagents; they are not represented as independent human-user studies or independent model replications.

## Deterministic Gates

- Unit and scenario-harness tests must all pass without required skips.
- The release archive must reproduce byte-for-byte from identical source inputs and source commit.
- `verify_release.py` must accept the complete distribution and reject version, license, privacy, dependency, link, and hash violations.
- Fresh installation into two temporary Skill roots must initialize and validate a schema 2 project.
- Upgrade must detect local edits, create a recoverable backup, and avoid silent overwrite.
- Rollback must restore the exact pre-upgrade file hashes.

## Runtime Gates

- Real local MinerU evidence is stored only as redacted scenario evidence.
- At least two authorized PDFs must complete local parsing, cache validation, and representative page-level visual review without changing source hashes.
- Identical input and options must demonstrate reuse; interrupted polling must resume an existing task rather than submit a duplicate.

Observed local runtime: MinerU Desk 0.3.1, MinerU 3.4.5, CPU, local Pipeline, offline mode. Two authorized PDFs completed 15-page and 17-page conversions, and 12 representative pages were visually inspected across text, figures, tables, chart content, and formulas where applicable. Original PDF hashes were unchanged.

## Release Boundary

The workflow ZIP may contain only the `cyz-edu-research` Skill and its public metadata. It must not contain MinerU wrappers, Desk binaries, model weights, credentials, personal absolute paths, personal PDFs, raw research material, or generated caches. A MinerU ZIP is prohibited until an explicit redistribution license is established.

GitHub publication and remote-download verification were a separate milestone from the candidate-package gates. REL03 now records that milestone as passed; its URLs, hashes, installed-file manifest, and local backup identifiers are retained under `docs/release/`.
