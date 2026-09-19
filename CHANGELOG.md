# Changelog

## 0.3.0 - 2026-09-19

### Added

- Schema 2 research-project lifecycle with deterministic initialization, validation, migration, and rollback.
- Reproducible discovery/refinement scenario contracts and evidence-bounded result validation.
- Chinese/English academic-language routing with semantic-lock and manual-review gates.
- Local MinerU Desk submission, resume, lineage, cache integrity, and explicit native fallback.
- Deterministic release archive, verification, conflict-aware installation, and rollback tooling.

### Changed

- Upgraded the workbench contract from 0.2.1 to 0.3.0.
- Kept local MinerU wrappers, models, personal PDFs, credentials, and generated caches outside the release.

### Compatibility

- Project schema: 2.
- Workflow contract: 1.
- Verified local MinerU runtime: Desk 0.3.1 / MinerU 3.4.5 on CPU.

### Verification

- Passed all 24 workflow scenarios (`I01-I14`, `H01-H04`, `M01-M06`) and all 12 WF gates.
- Passed deterministic package, fresh-install, conflict-backup, and rollback verification.
- GitHub Release and remote-download verification are recorded separately and are not implied by the local checks above.
