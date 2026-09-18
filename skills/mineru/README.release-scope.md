# MinerU Release Scope

MinerU is a local dependency of this workflow, not a vendored release component.

The installed `mineru` wrapper Skill declares version `4.0.0-desk-local`, but the inspected installations contain no `LICENSE` or `NOTICE` that establishes redistribution permission. Therefore this repository must not copy, package, or publish the wrapper files, and must not build a MinerU Skill ZIP. The observed installation paths, cache-excluded directory hash, file count, byte count, declared version, and unknown license/source status are recorded in `dependencies.lock.json` as local-environment evidence only.

## Local installation

1. Install MinerU Desk independently on the user's machine.
2. Install the local `mineru` wrapper Skill independently under an available skills root, such as `.codex/skills/mineru` or `.agents/skills/mineru`.
3. Verify the local Desk with its own doctor/self-test commands before use.
4. Recompute the canonical directory hash described in `dependencies.lock.json`; transient `__pycache__`, `*.pyc`, and `*.pyo` files are excluded.
5. Use `export_mineru_task.py` only with an existing local task ID, then import through `convert_pdf_to_md.py --mineru-task`. The workflow never auto-uploads a source document.

The currently observed runtime is MinerU Desk `0.3.1` with MinerU `3.4.5` on CPU. These runtime observations do not establish redistribution rights and do not replace live acceptance with authorized PDFs.
