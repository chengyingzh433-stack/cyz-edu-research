# Workflow 0.3.0 Release Evidence

## Candidate

- Version: `0.3.0`
- Release commit: `7ed5f72c350236c08a55738a0495c4395942b855`
- Archive: `cyz-edu-research-0.3.0.zip`
- Local archive SHA-256: `a87e7c2a40779529d37c241af06b544d1409fda856b7220f9b82f1a5632294cc`
- Manifested payload files: 40, plus the release manifest itself
- MinerU ZIP: not produced because redistribution permission for the local wrapper was not established

## Local verification

- Full deterministic suite: 96/96 passed.
- Idea fixture replay: I01-I14 passed in one run.
- Language suite: 13/13 passed; real bounded Chinese and English passes both resolved the required dependency and passed automated plus manual semantic regression.
- MinerU/cache suite: 18/18 passed; M01-M02 also retain redacted live Desk evidence.
- Fresh package checks: two isolated roots matched across all 40 manifested payload files with payload tree SHA-256 `ca60ca3dfd38889431965d2d4da7396aa776308ccd1cbdcb64f39b0b116940b1`; including `release-manifest.json`, each installed tree contains 41 controlled files. Both roots initialized and validated a project.
- Upgrade safety: local edits produce a conflict and backup; explicit conflict upgrade plus rollback restores the exact pre-upgrade tree.

## Live idea-session boundary

The two idea conversations were run sequentially by the current primary Codex agent with scripted acceptance-user turns because the user prohibited subagents and additional delegated agents. They demonstrate candidate behavior in this execution, but they are not independent-model replications and do not substitute for user research.

## Remote release

- Repository: [chengyingzh433-stack/cyz-edu-research](https://github.com/chengyingzh433-stack/cyz-edu-research), private, default branch `main`.
- Annotated tag: `0.3.0`; tag object `09837a21e706139a9cb58de094f9e549dfc9d18f`; target commit `7ed5f72c350236c08a55738a0495c4395942b855`.
- Release: [cyz-edu-research 0.3.0](https://github.com/chengyingzh433-stack/cyz-edu-research/releases/tag/0.3.0), normal release (`draft=false`, `prerelease=false`), published `2026-09-19T00:51:44Z`.
- Assets: `cyz-edu-research-0.3.0.zip` (129,802 bytes), `SHA256SUMS.txt` (93 bytes), `acceptance-report.md` (442 bytes).
- Remote ZIP SHA-256: `a87e7c2a40779529d37c241af06b544d1409fda856b7220f9b82f1a5632294cc`, identical to the local release asset.
- Remote re-download: `verify_release.py` passed; two fresh installs were identical, matched every packaged manifest entry, and produced installed tree SHA-256 `d2b154ee6e319b7d77bc0bffbeced7a9cd1dea9c0d9570e21d69de9336fa4409` across 41 files.
- A project initialized from the remote-downloaded installation validated with zero warnings.

## Local synchronization

Both existing Skill roots were byte-identical at version 0.2.1 before synchronization (31 files; tree SHA-256 `ed612888766e4445993f3988a3c17405568fcea67a33480332d30d019b2d6ef8`). The installer detected the absence of an earlier 0.3.0 install record as a conflict, created backups, and upgraded only after the explicit conflict override. Both roots now contain version 0.3.0, 41 controlled files, and tree SHA-256 `d2b154ee6e319b7d77bc0bffbeced7a9cd1dea9c0d9570e21d69de9336fa4409`.

The redacted backup identifiers and complete installed-file manifest are stored in [local-install-manifest.json](local-install-manifest.json). No `.pyc`, personal PDF, model weight, credential, or absolute user path is recorded in the published evidence.
