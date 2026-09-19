# Install, Upgrade, and Roll Back

## Prerequisites

- Python 3.11 or later.
- The release ZIP and its matching entry in `SHA256SUMS.txt`.
- Separately installed `humanizer-zh`, `humanizer`, and local `mineru` dependencies when their features are needed.

MinerU Desk, its wrapper Skill, model weights, personal PDFs, and generated caches are not part of this release.

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
py -3.11 C:/path/to/skills/cyz-edu-research/scripts/init_project.py C:/temp/cyz-check --mode discovery
py -3.11 C:/path/to/skills/cyz-edu-research/scripts/validate_project.py C:/temp/cyz-check
```
