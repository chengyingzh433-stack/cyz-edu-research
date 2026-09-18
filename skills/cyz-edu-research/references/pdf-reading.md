# PDF-To-Markdown Canonical Cache Protocol

Use this protocol before reading any PDF paper. The original PDF is authoritative; `paper.md` is the only long-term full-text reading cache. Never modify the PDF or Zotero records.

## 1. Canonical Project Layout

```text
02-文献/转换缓存/
├─ 00-缓存索引.md
└─ <paper-id>/
   ├─ paper.md
   ├─ conversion_manifest.json
   ├─ source_map.json
   ├─ conversion_report.md
   └─ assets/
```

Do not put TXT in this tree or link TXT from project files. Keep interpretation and reading notes separately under `02-文献/核心文献精读/<paper-id>/`.

## 2. Mandatory Cache-First Order

Before extracting PDF text:

1. compute the source PDF SHA-256;
2. locate `02-文献/转换缓存/<paper-id>/`;
3. validate `pdf_sha256`, `conversion_mode`, `dpi`, and `converter_schema` in the manifest;
4. confirm all four files and `assets/` exist, JSON parses, Markdown page headings match the PDF page count, and no TXT is present;
5. print `CACHE_REUSED` and read `paper.md` when valid;
6. reprocess only when the fingerprint or cache integrity fails, or when the user explicitly uses `--force`.

A request for a key figure, formula, table, or page is not permission to re-extract the full PDF. Add only the requested page snapshots with `--render-pages`.

## 3. New PDF: Local MinerU Desk First

The workbench orchestrates the installed `mineru` skill. The bundled converter is the cache adapter and native fallback, not a second cloud/local dispatcher. Before starting Desk, probe without modifying files:

```text
python scripts/convert_pdf_to_md.py <paper.pdf> --project-root <project> --paper-id <paper-id> --image-mode auto --check-cache
```

Exit 0 means reuse the canonical cache even if it predates MinerU; exit 3 means conversion is needed; any other exit is an error to diagnose. Do not reparse valid native caches solely because the preferred backend changed. Explicit user requests to upgrade a cache may use --force after preserving existing reviewed locators.

On a cache miss, read and follow the installed mineru SKILL.md. It automatically locates Desk, validates the installation, checks runtime/models/offline state, submits local Pipeline parsing, and follows tasks to completed/reused. First inspect a small PDF sample as required by that skill; then complete the requested full document. Output Desk artifacts outside the canonical cache (for example project tmp/mineru-desk/) to keep backend output separate from paper.md.

Export a minimal authenticated task record (no connection credentials), using the included helper. It resolves cache-reuse chains to the original runtime version and retains the settings needed to verify the Desk source-binding cache key:

```text
python scripts/export_mineru_task.py --desk-root <installed-Desk-directory> --task-id <completed-ID> --output <project/tmp/task.json>
```

Do not construct fake task records or guess paths. Import the exported record:

```text
python scripts/convert_pdf_to_md.py <paper.pdf> --project-root <project> --paper-id <paper-id> --image-mode auto --mineru-task <task.json>
```

The importer verifies local/full-document status, source path, the Desk 0.3.1 cache key computed from the current source PDF SHA-256, exact options, and recorded runtime settings/version, exact page coverage in `_middle.json`, and block page indexes in `_content_list.json`. It preserves block types, formula text, table HTML, captions, images and bounding boxes; assigns canonical page/block locators; copies images into assets; and updates project state/index using the existing converter. Unknown block schemas, missing assets, partial outputs and mismatched sources fail explicitly, never silently become verified evidence. MinerU reserializes `_origin.pdf`, so it is not used as a byte-identical source. Content-list v2 is not inferred as v1. The importer supports offline local Pipeline; changed Desk cache-key schemas require adapter review. Backend raw outputs remain separate for audit; paper.md remains the only canonical reading cache.

If Desk is unavailable, its model/runtime fails, or its output cannot be adapted, record the concrete reason in the project conversion/audit record and run the native fallback below. Do not auto-upload or download models. A conversion failure does not authorize bypassing installation integrity checks. Native fallback has weaker OCR/table/formula support; disclose its limits. Use --render-pages for page-specific visual verification; imported images are kept even with image-mode none because they carry document content.

### Native fallback or explicit legacy TXT migration

For an explicit native fallback (without --mineru-task), run:

```text
python scripts/convert_pdf_to_md.py <paper.pdf> --project-root <project> --paper-id <paper-id> --image-mode auto
```

For a standalone cache, use `--output-dir`. The converter writes Markdown and JSON directly; it must not create a persistent TXT first.

Modes:

- `none`: page-mapped text only; appropriate for long papers before targeted visual inspection;
- `auto`: text, useful embedded raster images, and selected first/caption/OCR-risk page snapshots;
- `all`: snapshot every page only when explicitly justified.

Keep the same mode and DPI on repeat runs when cache reuse is expected.

## 4. Reuse Existing Paginated TXT

If an earlier extraction produced a TXT with stable PDF page markers, reuse it instead of re-extracting the PDF solely to change formats:

```text
python scripts/convert_pdf_to_md.py <paper.pdf> --project-root <project> --paper-id <paper-id> --source-txt <tmp/pdfs/paper.txt> --image-mode none
```

Supported markers include `===== 第 N 页 =====`, decorated `Page N` markers, and `[Page N]`. The TXT must cover PDF pages 1 through N exactly; otherwise stop instead of creating a misleading full-text cache.

The migration must:

- turn every page marker into `## PDF 第 N 页`;
- add source PDF path, SHA-256, PDF page count, UTC generation time, extraction source, and temporary TXT path;
- create stable text block IDs and a page-level source map;
- state that tables, formulas, two-column order, and images are not guaranteed;
- create an empty `assets/` when no visual assets are yet needed;
- validate all cache artifacts before deleting TXT.

Delete the migrated TXT automatically only when it is under a recognized `tmp/pdfs/` path or an explicitly supplied `--temp-dir`. Do not delete a user-authored TXT outside a trusted temporary root. A non-paginated transcript is source material, not a disposable PDF extraction.

## 5. TXT Is Temporary Only

Any tool that requires TXT must write it below a clear temporary root such as `tmp/pdfs/`. Do not:

- write TXT under `02-文献/`;
- register TXT in `00-项目状态.md`, literature cards, evidence matrices, or cache indexes;
- retain TXT after verified Markdown migration;
- treat TXT as an academic locator or final reading artifact.

Prefer the local MinerU skill plus the bundled cache importer; native fallback also writes Markdown directly without persistent TXT.

## 6. Local Visual Supplement

For a valid text cache, add only required pages:

```text
python scripts/convert_pdf_to_md.py <paper.pdf> --project-root <project> --paper-id <paper-id> --image-mode none --render-pages 1,35-37
```

The command must first print `CACHE_REUSED`, then render missing requested pages into `assets/`, update `source_map.json`, the manifest, and the report, and leave `paper.md` text untouched. Visually inspect representative outputs before interpreting layout-sensitive evidence.

## 7. Artifact Contract

- `paper.md`: YAML provenance, explicit limitations, `## PDF 第 N 页` headings, and stable `S/C/F/R` anchors.
- `conversion_manifest.json`: title, paper ID, PDF path/hash/size/pages, generation time, extraction source, conversion mode, DPI, schema, statistics, and supplemental render pages.
- `source_map.json`: page records, text blocks, extraction method/confidence, figures, OCR risk, and page snapshots.
- `conversion_report.md`: extraction summary plus OCR, table, formula, image, double-column, and verification risks.
- `assets/`: only extracted figures or page snapshots needed by the chosen mode or local verification.

Markdown line numbers are unstable and cannot be the only locator. Use 1-based PDF page numbers and stable block IDs. Never invent printed page numbers.

## 8. Index And Project State

After every project conversion or cache reuse, rebuild `02-文献/转换缓存/00-缓存索引.md` from valid manifests. List title, paper ID, PDF pages, `paper.md` link, and OCR/visual risk.

Update `00-项目状态.md` under `## 可复用全文缓存` with the index link, cache count, and each cached paper. Do not add TXT paths. Cache refresh is a mechanical status update and must not change the research stage or gate.

## 9. Reading Depth

- `灵感探索/批量扫描`: normally use metadata and abstracts. Convert only representative, contradictory, shortlisted, or explicitly requested papers.
- `标准精读`: use the canonical Markdown for navigation, then verify key claims against PDF pages.
- `全文深读`: use Markdown plus targeted figures, tables, formulas, and page snapshots; do not default to all-page rendering.

Before marking a claim verified, confirm the PDF hash, page locator, visual reading order, exact quotation/value, author-versus-workbench attribution, and extraction/OCR uncertainty.
