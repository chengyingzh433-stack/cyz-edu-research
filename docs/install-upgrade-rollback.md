# Install, Upgrade, and Roll Back

## Prerequisites

- Python 3.11 or later.
- The release ZIP and its matching entry in `SHA256SUMS.txt`.
- Separately installed `humanizer-zh` and `humanizer` when their features are needed. Workflow 0.3.1 includes the user's MinerU Desk entry Skill; no separate global mineru Skill installation is needed.

MinerU Desk, model weights, personal PDFs, and generated caches are not part of this release. Read the embedded references/mineru/SKILL.md before PDF parsing; if Desk is missing, follow its preparation instructions instead of immediately using native conversion.

## Verify

From the source checkout, verify all release assets before installation:

```powershell
py -3.11 scripts/verify_release.py --dist dist
```

Verification checks the ZIP manifest and hashes, version agreement, required licenses and notices, relative links, dependency declarations, and forbidden private or binary material.

## Fresh Install or Upgrade

Install into a chosen Skill root:

```powershell
py -3.11 scripts/install_skill.py install --archive dist/cyz-edu-research-0.3.0.zip --skill-root C:/path/to/skills
```

The destination is `<skill-root>/cyz-edu-research`. Existing installations are backed up before replacement. If installed files differ from the previous installation record, the command reports a conflict and leaves the installation unchanged. Review the backup and local edits before deciding whether to rerun with `--allow-conflicts`.

## Roll Back

The installer prints the exact backup path used for an upgrade. Restore it explicitly:

```powershell
py -3.11 scripts/install_skill.py rollback --skill-root C:/path/to/skills --backup C:/path/to/skills/.cyz-backups/cyz-edu-research/<backup>/snapshot
```

Rollback replaces only the managed `cyz-edu-research` installation and records the restored tree hash. It does not alter sibling Skills or research projects.

## Post-Install Check

Create and validate a disposable project before using the installation with real work:

```powershell
py -3.11 C:/path/to/skills/cyz-edu-research/scripts/init_project.py C:/temp/cyz-check --entry-mode discovery
py -3.11 C:/path/to/skills/cyz-edu-research/scripts/validate_project.py C:/temp/cyz-check
```

## 0.3.0 documentation and language-check notes

The installer and verifier are in the source archive, not the Skill ZIP. The original packaged guide incorrectly uses `--mode`; use `--entry-mode` as shown above.

For a beginner walkthrough and agent setup, see [agent-install.md](https://github.com/chengyingzh433-stack/cyz-edu-research/blob/main/docs/agent-install.md). Version 0.3.0 language checks require an explicit `--dependency-lock` pointing to the supplemental verified lock described there. The packaged minimal lock omits required validation fields, and the script's default path does not match a standalone Skill installation.
