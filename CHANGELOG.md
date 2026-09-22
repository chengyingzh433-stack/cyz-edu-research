# Changelog

## 0.3.1 - Unreleased

- Embed the user's own MinerU Desk Skill entry and local API reference; a separate global mineru Skill registration is no longer needed.
- Prepare Desk before conversion: discover an existing installation, obtain a verified compatible installer if absent, then diagnose models/runtime and inspect a sample.
- Stop silent native conversion on a cache miss, including --force. Last-resort extraction requires --fallback-reason, recorded in the manifest and report.
- Keep valid caches, explicit legacy TXT migration, local-only processing and the Desk task importer.
- Published workbench 0.1.0-preview.1 still bundles workflow 0.3.0 until separately rebuilt and verified.

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
- Published the private GitHub Release `0.3.0`; the remote-downloaded archive matched SHA-256, installed cleanly in two fresh roots, and was then synchronized to both verified local Skill roots with backups.
