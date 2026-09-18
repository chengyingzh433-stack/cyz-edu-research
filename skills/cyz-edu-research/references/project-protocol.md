# Project State And Resume Protocol

## Canonical Record

`00-项目状态.md` is the resume entry. Markdown artifacts are the canonical working record. Exported Word, PDF, and PPT files are derivatives unless the user explicitly designates one as authoritative.

## Required State

Record:

- project title and root;
- entry mode;
- current stage and gate status;
- academic language-pass status when applicable;
- confirmed RQ and scope;
- current evidence boundary;
- completed artifacts;
- unresolved blockers;
- pending verification;
- academic language-pass status, baseline, reviewed scope, and semantic-regression result when used;
- latest decision and rationale;
- next recommended action;
- last updated date.

## Resume

1. Read project state.
2. Check that linked artifacts exist.
3. For a project created by an earlier package version, create missing standard directories with `scripts/init_project.py <project> --allow-existing`; do not replace existing files.
4. Read only artifacts needed for the current gate.
5. Detect contradictions between current files and recorded decisions.
6. Resume from the first incomplete or invalid gate.
7. Do not repeat completed work solely because a new conversation began.

## Updates

After meaningful work, update:

- status and stage;
- files created or revised;
- evidence status changes;
- decision log;
- next action;
- blockers.

For academic humanization, preserve the pre-pass draft, record both file hashes, complete `07-论文草稿/学术语言打磨报告.md`, and link its result from `08-审查与修改记录.md`. Never overwrite the only substantively approved draft.

Never mark a gate complete merely because a file exists. Confirm the artifact meets the gate’s substantive criteria.

## Project Discovery Safety

Search only within the user-provided project or current workspace. Do not scan unrelated drives. If multiple project-state files are present, ask which project to open.

## File Preservation

Do not overwrite original papers, datasets, proposals, or drafts. Create project notes and working versions. Record source paths in the project inventory.

Generated PDF reading caches belong under `02-文献/转换缓存/<paper-id>/`. They are reproducible derivatives identified by the source PDF hash, not canonical evidence or researcher-authored notes. Keep full reading notes separately under `02-文献/核心文献精读/<paper-id>/` so cache regeneration cannot erase interpretation or decisions.

Maintain `02-文献/转换缓存/00-缓存索引.md` and the `## 可复用全文缓存` section in project state from cache manifests. Markdown is the only long-term full-text cache; never index temporary TXT.
