# MinerU Release Scope

MinerU Desk is a local dependency. Since 0.3.1, the user-authored Desk entry Skill and its local interface reference are embedded in the workflow under references/mineru with the author's explicit authorization on 2026-09-22. No separate global mineru Skill installation is required.

The original installed directory declares version `4.0.0-desk-local` but has no blanket `LICENSE` or `NOTICE`. The two-file authorization must not be extended to its historical cloud scripts, program, models, or data; do not build a ZIP of the entire original wrapper. The original directory metrics in dependencies.lock.json remain historical local-environment evidence, not permission to redistribute all its files.

## Local installation

1. Install MinerU Desk independently on the user's machine.
2. Read the embedded references/mineru/SKILL.md; do not require another global Skill registration.
3. Verify the local Desk with its own doctor/self-test commands before use.
4. Recompute the canonical directory hash described in `dependencies.lock.json`; transient `__pycache__`, `*.pyc`, and `*.pyo` files are excluded.
5. Use `export_mineru_task.py` only with an existing local task ID, then import through `convert_pdf_to_md.py --mineru-task`. The workflow never auto-uploads a source document.

The currently observed runtime is MinerU Desk `0.3.1` with MinerU `3.4.5` on CPU. These runtime observations do not establish redistribution rights and do not replace live acceptance with authorized PDFs.
