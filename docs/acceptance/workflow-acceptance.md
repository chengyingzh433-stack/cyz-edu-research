# Workflow 0.3.0 Acceptance

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

## Release Boundary

The workflow ZIP may contain only the `cyz-edu-research` Skill and its public metadata. It must not contain MinerU wrappers, Desk binaries, model weights, credentials, personal absolute paths, personal PDFs, raw research material, or generated caches. A MinerU ZIP is prohibited until an explicit redistribution license is established.

GitHub publication and remote-download verification are a separate release milestone; this document does not claim they have passed.
