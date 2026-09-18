#!/usr/bin/env python3
"""Build or reuse the canonical Markdown reading cache for a PDF paper."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any
import uuid


SCHEMA_VERSION = 2
MIN_TEXT_CHARS = 40
CAPTION_RE = re.compile(
    r"(?im)^\s*(?:图|表)\s*[0-9一二三四五六七八九十]+|"
    r"^\s*(?:fig(?:ure)?|table)\s*\.?\s*\d+"
)
PAGE_MARKER_RE = re.compile(
    r"(?im)^(?:"
    r"\s*=+\s*第\s*(\d+)\s*页\s*=+\s*|"
    r"\s*=+\s*(?:PDF\s*)?Page\s*(\d+)\s*=+\s*|"
    r"\s*-{3,}\s*(?:PDF\s*)?Page\s*(\d+)\s*-{3,}\s*|"
    r"\s*\[(?:PDF\s*)?Page\s*(\d+)\]\s*"
    r")$"
)
REQUIRED_CACHE_FILES = (
    "paper.md",
    "conversion_manifest.json",
    "source_map.json",
    "conversion_report.md",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Source PDF; it is never modified")
    destination = parser.add_argument_group("cache destination")
    destination.add_argument("--output-dir", type=Path)
    destination.add_argument("--project-root", type=Path)
    destination.add_argument("--paper-id")
    parser.add_argument("--title", help="Display title; defaults to PDF metadata or filename")
    parser.add_argument("--check-cache", action="store_true", help="Read-only cache probe; exit 3 means conversion needed")
    parser.add_argument("--mineru-task", type=Path, help="Completed local Desk task JSON exported through Codex.ps1")
    parser.add_argument(
        "--source-txt",
        type=Path,
        help="Existing page-marked TXT to migrate without re-extracting PDF text",
    )
    parser.add_argument(
        "--temp-dir",
        action="append",
        default=[],
        type=Path,
        help="Additional trusted temporary root; repeat when needed",
    )
    parser.add_argument(
        "--image-mode",
        choices=("none", "auto", "all"),
        default="auto",
        help="PDF extraction visuals: none, selected risk pages, or every page",
    )
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument(
        "--render-pages",
        default="",
        help="Add only these PDF page snapshots to a valid cache, e.g. 1,8-10",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even when the cache fingerprint is valid",
    )
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    result: list[str] = []
    for line in lines:
        if not line:
            if result and result[-1]:
                result.append("")
            continue
        if line.startswith(("#", ">")):
            line = "\\" + line
        result.append(line)
    return "\n".join(result).strip()


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def safe_paper_id(stem: str, digest: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "-", stem).strip(" .-")
    cleaned = re.sub(r"\s+", "-", cleaned)
    if not cleaned:
        cleaned = "paper"
    return f"{cleaned[:72]}-{digest[:8]}"


def get_pdf_info(pdf_path: Path) -> tuple[int, str | None]:
    try:
        import fitz  # type: ignore
    except ImportError:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(pdf_path)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise RuntimeError("PDF is password protected")
        title = getattr(reader.metadata, "title", None) if reader.metadata else None
        return len(reader.pages), str(title).strip() if title else None
    document = fitz.open(pdf_path)
    try:
        if document.needs_pass and not document.authenticate(""):
            raise RuntimeError("PDF is password protected")
        title = (document.metadata or {}).get("title")
        return document.page_count, str(title).strip() if title else None
    finally:
        document.close()


def resolve_destination(
    args: argparse.Namespace, pdf_path: Path, digest: str
) -> tuple[Path, Path | None, str]:
    project_root = args.project_root.expanduser().resolve() if args.project_root else None
    paper_id = args.paper_id or safe_paper_id(pdf_path.stem, digest)
    if project_root:
        canonical = project_root / "02-文献" / "转换缓存" / paper_id
        if args.output_dir and args.output_dir.expanduser().resolve() != canonical:
            raise ValueError("--output-dir must equal the canonical project cache path")
        return canonical, project_root, paper_id
    if not args.output_dir:
        raise ValueError("provide --project-root or --output-dir")
    output_dir = args.output_dir.expanduser().resolve()
    if output_dir.parent.name == "转换缓存" and output_dir.parent.parent.name == "02-文献":
        project_root = output_dir.parent.parent.parent
        paper_id = output_dir.name
    return output_dir, project_root, paper_id


def parse_page_spec(spec: str, page_count: int) -> list[int]:
    if not spec.strip():
        return []
    pages: set[int] = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"invalid page range: {token}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(token))
    invalid = sorted(page for page in pages if page < 1 or page > page_count)
    if invalid:
        raise ValueError(f"page(s) outside 1-{page_count}: {invalid}")
    return sorted(pages)


def mineru_task_binding(task: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise ValueError("MinerU task record must be a JSON object")
    options = task.get("options")
    settings = task.get("runtimeSettings")
    if not isinstance(options, dict) or not isinstance(settings, dict):
        raise ValueError("MinerU task record lacks options or runtime settings")
    option_fields = ("provider", "backend", "method", "language", "formula", "table", "pages")
    setting_fields = ("modelSource", "offline", "modelRoot")
    if any(key not in options for key in option_fields):
        raise ValueError("MinerU task record lacks conversion options")
    if any(key not in settings for key in setting_fields):
        raise ValueError("MinerU task record lacks runtime settings")
    if options["provider"] != "local" or options["backend"] != "pipeline":
        raise ValueError("MinerU cache requires the local Pipeline provider")
    if options["pages"] is not None:
        raise ValueError("MinerU cache requires a full-document task")
    if settings["offline"] is not True:
        raise ValueError("MinerU cache requires offline runtime settings")
    source_hash = task.get("source_sha256")
    cache_key = task.get("key")
    runtime_version = task.get("runtime_version")
    if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        raise ValueError("MinerU task record lacks an original source hash")
    if not isinstance(cache_key, str) or not cache_key:
        raise ValueError("MinerU task record lacks a Desk cache key")
    if not isinstance(runtime_version, str) or not runtime_version:
        raise ValueError("MinerU task record lacks a runtime version")
    return {
        "source_sha256": source_hash,
        "desk_cache_key": cache_key,
        "options": {key: options[key] for key in option_fields},
        "runtime_version": runtime_version,
        "runtime_settings": {key: settings[key] for key in setting_fields},
    }


def cache_fingerprint(
    digest: str,
    image_mode: str,
    dpi: int,
    *,
    mineru_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fingerprint = {
        "pdf_sha256": digest,
        "conversion_mode": image_mode,
        "dpi": dpi,
        "converter_schema": SCHEMA_VERSION,
    }
    if mineru_binding is not None:
        fingerprint["mineru_request"] = mineru_binding
    return fingerprint


def validate_cache(output_dir: Path, fingerprint: dict[str, Any]) -> tuple[bool, str]:
    for filename in REQUIRED_CACHE_FILES:
        path = output_dir / filename
        if not path.is_file() or path.stat().st_size == 0:
            return False, f"missing or empty {filename}"
    if not (output_dir / "assets").is_dir():
        return False, "missing assets directory"
    if any(output_dir.glob("*.txt")):
        return False, "TXT is not permitted in a canonical cache directory"
    try:
        manifest = load_json(output_dir / "conversion_manifest.json")
        source_map = load_json(output_dir / "source_map.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        return False, f"invalid cache metadata: {exc}"
    for key, expected in fingerprint.items():
        if manifest.get(key) != expected:
            return False, f"fingerprint mismatch: {key}"
    if source_map.get("pdf_sha256") != fingerprint.get("pdf_sha256"):
        return False, "source map original PDF hash does not match fingerprint"
    page_count = manifest.get("page_count")
    pages = source_map.get("pages")
    if not isinstance(page_count, int) or page_count < 1 or not isinstance(pages, list) or len(pages) != page_count:
        return False, "page count does not match source map"
    try:
        markdown = (output_dir / "paper.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return False, f"invalid cache Markdown: {exc}"
    headings = re.findall(r"(?m)^## PDF 第 (\d+) 页$", markdown)
    if headings != [str(n) for n in range(1, page_count + 1)]:
        return False, "Markdown page headings do not match PDF page count"
    if any(not isinstance(page, dict) for page in pages):
        return False, "source map page metadata is invalid"
    if [page.get("pdf_page") for page in pages] != list(range(1, page_count + 1)):
        return False, "source map page sequence is invalid"
    for page in pages:
        figures = page.get("figures", [])
        renders = page.get("page_renders", [])
        if not isinstance(figures, list) or not isinstance(renders, list):
            return False, "cache asset metadata must use lists"
        for item in figures + renders:
            if not isinstance(item, dict) or not isinstance(item.get("asset"), str) or not item["asset"]:
                return False, "cache asset metadata is invalid"
            asset = (output_dir / item["asset"]).resolve()
            if not asset.is_relative_to(output_dir.resolve()) or not asset.is_file() or asset.stat().st_size == 0:
                return False, "missing or unsafe cache asset"
    if manifest.get("extraction_source") == "mineru_desk_local":
        binding = fingerprint.get("mineru_request")
        if not isinstance(binding, dict):
            return False, "MinerU cache lacks a pinned mineru_request fingerprint"
        manifest_mineru = manifest.get("mineru")
        source_mineru = source_map.get("mineru")
        if not isinstance(manifest_mineru, dict) or manifest_mineru != source_mineru:
            return False, "MinerU lineage metadata is missing or inconsistent"
        status = manifest_mineru.get("task_status")
        task_id = manifest_mineru.get("task_id")
        base_task_id = manifest_mineru.get("base_task_id")
        lineage = manifest_mineru.get("lineage_task_ids")
        if (
            status not in {"completed", "reused"}
            or manifest_mineru.get("source_sha256") != fingerprint.get("pdf_sha256")
            or not isinstance(task_id, str)
            or not isinstance(base_task_id, str)
            or not isinstance(lineage, list)
            or not lineage
            or lineage[0] != task_id
            or lineage[-1] != base_task_id
            or len(lineage) != len(set(lineage))
        ):
            return False, "MinerU task lineage is invalid"
        required = {
            "desk_cache_key": binding.get("desk_cache_key"),
            "options": binding.get("options"),
            "runtime_version": binding.get("runtime_version"),
            "runtime_settings": binding.get("runtime_settings"),
            "source_verification": "original_input_sha256",
        }
        if any(manifest_mineru.get(key) != value for key, value in required.items()):
            return False, "MinerU provenance does not match mineru_request"
        options = manifest_mineru.get("options")
        settings = manifest_mineru.get("runtime_settings")
        if (
            not isinstance(options, dict)
            or options.get("provider") != "local"
            or options.get("backend") != "pipeline"
            or options.get("pages") is not None
            or not isinstance(settings, dict)
            or settings.get("offline") is not True
        ):
            return False, "MinerU provenance is not full-document local/offline Pipeline"
        if status == "completed" and lineage != [task_id]:
            return False, "completed MinerU cache has invalid lineage"
        if status == "reused" and (
            len(lineage) < 2
            or manifest_mineru.get("reused_from_task_id") != lineage[1]
        ):
            return False, "reused MinerU cache lacks source lineage"
    elif "mineru_request" in fingerprint:
        return False, "fingerprint requests MinerU but cache provenance is not MinerU"
    return True, "valid"


def cache_first_probe(
    output_dir: Path,
    fingerprint: dict[str, Any],
    discover_on_miss=None,
) -> tuple[bool, str]:
    valid, reason = validate_cache(output_dir, fingerprint)
    if not valid and discover_on_miss is not None:
        discover_on_miss()
    return valid, reason


def local_fallback_policy(
    *, ocr_available: bool, unrecognized_pages: list[int]
) -> dict[str, Any]:
    return {
        "mode": "local_native",
        "ocr_available": ocr_available,
        "unrecognized_pages": sorted(set(unrecognized_pages)),
        "auto_upload": False,
        "notice": (
            "Local native fallback only; never auto-upload. "
            "Unrecognized pages remain explicit and require local review."
        ),
    }


def publish_cache_atomically(
    prepared_dir: Path,
    destination: Path,
    fingerprint: dict[str, Any],
    *,
    cleanup_backup=shutil.rmtree,
) -> str | None:
    prepared = prepared_dir.resolve()
    target = destination.resolve()
    valid, reason = validate_cache(prepared, fingerprint)
    if not valid:
        raise ValueError(f"prepared cache failed validation: {reason}")
    if prepared.parent != target.parent:
        raise ValueError("atomic cache publication requires a sibling staging directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_name(f".{target.name}.previous-{uuid.uuid4().hex}")
    had_target = target.exists()
    if had_target:
        target.replace(backup)
    try:
        prepared.replace(target)
    except Exception:
        if had_target and backup.exists() and not target.exists():
            backup.replace(target)
        raise
    else:
        if backup.exists():
            try:
                cleanup_backup(backup)
            except Exception as exc:
                # Publication has committed. Retaining the recoverable old cache is safer
                # than reporting failure after the canonical path already changed.
                return f"backup cleanup failed after commit: {exc}"
    return None


def update_cache_atomically(
    destination: Path,
    fingerprint: dict[str, Any],
    update_callback,
) -> str | None:
    """Apply a supplemental cache update in a sibling copy, then publish it."""
    target = destination.resolve()
    valid, reason = validate_cache(target, fingerprint)
    if not valid:
        raise ValueError(f"existing cache failed validation: {reason}")
    staging = target.with_name(f".{target.name}.staging-{uuid.uuid4().hex}")
    try:
        shutil.copytree(target, staging)
        update_callback(staging)
        return publish_cache_atomically(staging, target, fingerprint)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise


def markdown_header(
    pdf_path: Path,
    digest: str,
    page_count: int,
    title: str,
    generated_at: str,
    extraction_source: str,
    source_txt: Path | None,
    warning: str,
) -> list[str]:
    lines = [
        "---",
        f"source_pdf: {yaml_string(pdf_path.as_posix())}",
        f"pdf_sha256: {yaml_string(digest)}",
        f"pdf_pages: {page_count}",
        f"generated_at_utc: {yaml_string(generated_at)}",
        f"extraction_source: {yaml_string(extraction_source)}",
    ]
    if source_txt:
        lines.append(f"temporary_text_source: {yaml_string(source_txt.as_posix())}")
    lines.extend(
        [
            "locator_rule: PDF页码 + 稳定块ID；不得仅用Markdown行号",
            "generated_cache: true",
            "---",
            "",
            f"# {title}",
            "",
            f"> {warning}",
            "",
        ]
    )
    return lines


def read_text_file(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot decode TXT as UTF-8 or GB18030: {path}")


def parse_paginated_txt(path: Path, pdf_page_count: int) -> tuple[list[tuple[int, str]], str]:
    text, encoding = read_text_file(path)
    matches = list(PAGE_MARKER_RE.finditer(text))
    if not matches:
        raise ValueError("TXT has no supported PDF page markers")
    pages: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        page_number = int(next(group for group in match.groups() if group is not None))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages.append((page_number, text[match.end() : end].strip()))
    numbers = [number for number, _ in pages]
    expected = list(range(1, pdf_page_count + 1))
    if numbers != expected:
        raise ValueError(
            "TXT page markers do not cover the PDF exactly: "
            f"found {len(numbers)} markers ending at {numbers[-1]}, expected {pdf_page_count}"
        )
    return pages, encoding


def build_from_paginated_txt(
    pdf_path: Path,
    source_txt: Path,
    digest: str,
    page_count: int,
    title: str,
    generated_at: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    pages, encoding = parse_paginated_txt(source_txt, page_count)
    warning = (
        "本缓存复用了已有分页 TXT，未重新抽取整份 PDF。它不保证表格、公式、双栏阅读顺序或图片完整；"
        "精读这些内容时必须回到原 PDF，并只补充相关页面快照或局部解析。"
    )
    markdown = markdown_header(
        pdf_path,
        digest,
        page_count,
        title,
        generated_at,
        "legacy_paginated_txt",
        source_txt,
        warning,
    )
    source_map: dict[str, Any] = {
        "source_pdf": str(pdf_path),
        "pdf_sha256": digest,
        "generated_at_utc": generated_at,
        "extraction_source": "legacy_paginated_txt",
        "temporary_text_source": str(source_txt),
        "temporary_text_encoding": encoding,
        "page_numbering": "PDF page numbers are 1-based; printed page numbers are not inferred",
        "pages": [],
    }
    ocr_pages: list[int] = []
    block_count = 0
    for page_number, raw_text in pages:
        text = normalize_text(raw_text)
        compact_chars = len(re.sub(r"\s+", "", text))
        needs_ocr = compact_chars < MIN_TEXT_CHARS
        if needs_ocr:
            ocr_pages.append(page_number)
        markdown.extend([f"## PDF 第 {page_number} 页", ""])
        blocks: list[dict[str, Any]] = []
        if text:
            block_count += 1
            anchor = f"S{block_count:04d}"
            markdown.extend([f'<a id="{anchor}"></a>', text, ""])
            blocks.append(
                {
                    "id": anchor,
                    "type": "page_text",
                    "extraction": "legacy_paginated_txt",
                    "confidence": "text_only_requires_visual_check",
                }
            )
        else:
            markdown.extend(["> [分页 TXT 中本页无文字；需查看原 PDF。]", ""])
        source_map["pages"].append(
            {
                "pdf_page": page_number,
                "printed_page": None,
                "text_characters": compact_chars,
                "needs_ocr": needs_ocr,
                "blocks": blocks,
                "figures": [],
                "page_renders": [],
            }
        )
    stats = {
        "page_count": page_count,
        "text_blocks": block_count,
        "captions": 0,
        "embedded_images": 0,
        "rendered_pages": 0,
        "ocr_pages": ocr_pages,
        "visual_risk": "高：分页 TXT 不保证图表、公式、双栏顺序和图片完整",
        "engine": "legacy-paginated-txt-migration",
    }
    return "\n".join(markdown).rstrip() + "\n", source_map, stats


def extract_with_pymupdf(
    pdf_path: Path,
    output_dir: Path,
    image_mode: str,
    dpi: int,
    digest: str,
    page_count: int,
    title: str,
    generated_at: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    import fitz  # type: ignore

    document = fitz.open(pdf_path)
    if document.needs_pass and not document.authenticate(""):
        raise RuntimeError("PDF is password protected")
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    prefix = digest[:12]
    warning = (
        "本文件是模型快速阅读缓存。表格、公式、双栏顺序和图片可能不完整；引用、数字及关键结论必须回到原 PDF 页面核验。"
    )
    markdown = markdown_header(
        pdf_path,
        digest,
        page_count,
        title,
        generated_at,
        "pymupdf_native_pdf",
        None,
        warning,
    )
    source_map: dict[str, Any] = {
        "source_pdf": str(pdf_path),
        "pdf_sha256": digest,
        "generated_at_utc": generated_at,
        "extraction_source": "pymupdf_native_pdf",
        "page_numbering": "PDF page numbers are 1-based; printed page numbers are not inferred",
        "pages": [],
    }
    text_counter = caption_counter = figure_counter = render_counter = 0
    extracted_images = rendered_pages = 0
    ocr_pages: list[int] = []
    for page_index in range(document.page_count):
        page_number = page_index + 1
        page = document.load_page(page_index)
        raw_blocks = page.get_text("blocks", sort=True)
        page_text = "\n".join(
            str(block[4]) for block in raw_blocks if len(block) > 6 and block[6] == 0
        )
        compact_chars = len(re.sub(r"\s+", "", page_text))
        needs_ocr = compact_chars < MIN_TEXT_CHARS
        if needs_ocr:
            ocr_pages.append(page_number)
        markdown.extend([f"## PDF 第 {page_number} 页", ""])
        page_record: dict[str, Any] = {
            "pdf_page": page_number,
            "printed_page": None,
            "text_characters": compact_chars,
            "needs_ocr": needs_ocr,
            "blocks": [],
            "figures": [],
            "page_renders": [],
        }
        for block in raw_blocks:
            if len(block) <= 6 or block[6] != 0:
                continue
            text = normalize_text(str(block[4]))
            if not text:
                continue
            if CAPTION_RE.search(text):
                caption_counter += 1
                anchor, kind = f"C{caption_counter:04d}", "caption"
            else:
                text_counter += 1
                anchor, kind = f"S{text_counter:04d}", "body_text"
            markdown.extend([f'<a id="{anchor}"></a>', text, ""])
            page_record["blocks"].append(
                {
                    "id": anchor,
                    "type": kind,
                    "bbox": [round(float(value), 2) for value in block[:4]],
                    "extraction": "native_text",
                    "confidence": "needs_visual_check" if needs_ocr else "machine_extracted",
                }
            )
        if not page_record["blocks"]:
            markdown.extend(["> [本页未提取到可靠文字，需 OCR 或查看原 PDF。]", ""])
        seen_xrefs: set[int] = set()
        if image_mode != "none":
            for image_info in page.get_images(full=True):
                xref = int(image_info[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    image_data = document.extract_image(xref)
                except Exception:
                    continue
                width = int(image_data.get("width", 0))
                height = int(image_data.get("height", 0))
                if width < 120 or height < 80:
                    continue
                figure_counter += 1
                figure_id = f"F{figure_counter:04d}"
                extension = str(image_data.get("ext", "png"))
                filename = f"{prefix}-p{page_number:04d}-{figure_id}.{extension}"
                (assets_dir / filename).write_bytes(image_data["image"])
                relative = f"assets/{filename}"
                markdown.extend(
                    [f'<a id="{figure_id}"></a>', f"![PDF 第 {page_number} 页图片 {figure_id}]({relative})", ""]
                )
                page_record["figures"].append(
                    {
                        "id": figure_id,
                        "asset": relative,
                        "xref": xref,
                        "width": width,
                        "height": height,
                        "extraction": "embedded_raster",
                        "confidence": "requires_caption_and_page_check",
                    }
                )
                extracted_images += 1
        should_render = image_mode == "all" or (
            image_mode == "auto"
            and (page_number == 1 or needs_ocr or bool(CAPTION_RE.search(page_text)))
        )
        if should_render:
            render_counter += 1
            render_id = f"R{render_counter:04d}"
            filename = f"{prefix}-p{page_number:04d}-{render_id}.png"
            pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), alpha=False)
            pixmap.save(assets_dir / filename)
            relative = f"assets/{filename}"
            markdown.extend([f'<a id="{render_id}"></a>', f"[查看 PDF 第 {page_number} 页快照]({relative})", ""])
            page_record["page_renders"].append(
                {
                    "id": render_id,
                    "asset": relative,
                    "dpi": dpi,
                    "reason": "ocr_risk" if needs_ocr else "first_page" if page_number == 1 else "caption_detected",
                }
            )
            rendered_pages += 1
        source_map["pages"].append(page_record)
    document.close()
    stats = {
        "page_count": page_count,
        "text_blocks": text_counter,
        "captions": caption_counter,
        "embedded_images": extracted_images,
        "rendered_pages": rendered_pages,
        "ocr_pages": ocr_pages,
        "visual_risk": "中：已保留部分图片/页面，但复杂表格、公式和双栏顺序仍需核验" if image_mode != "none" else "高：仅转换正文，图表、公式、双栏顺序和图片需回原 PDF",
        "engine": "PyMuPDF",
    }
    return "\n".join(markdown).rstrip() + "\n", source_map, stats


def extract_with_pypdf(
    pdf_path: Path,
    digest: str,
    page_count: int,
    title: str,
    generated_at: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(pdf_path)
    markdown = markdown_header(
        pdf_path,
        digest,
        page_count,
        title,
        generated_at,
        "pypdf_text_fallback",
        None,
        "当前环境仅完成文本降级抽取；表格、公式、双栏顺序和图片不保证完整，必须回到原 PDF 核验。",
    )
    source_map: dict[str, Any] = {
        "source_pdf": str(pdf_path),
        "pdf_sha256": digest,
        "generated_at_utc": generated_at,
        "extraction_source": "pypdf_text_fallback",
        "page_numbering": "PDF page numbers are 1-based; printed page numbers are not inferred",
        "pages": [],
    }
    ocr_pages: list[int] = []
    block_count = 0
    for index, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        compact_chars = len(re.sub(r"\s+", "", text))
        needs_ocr = compact_chars < MIN_TEXT_CHARS
        if needs_ocr:
            ocr_pages.append(index)
        markdown.extend([f"## PDF 第 {index} 页", ""])
        blocks: list[dict[str, Any]] = []
        if text:
            block_count += 1
            anchor = f"S{block_count:04d}"
            markdown.extend([f'<a id="{anchor}"></a>', text, ""])
            blocks.append(
                {
                    "id": anchor,
                    "type": "page_text",
                    "extraction": "pypdf_fallback",
                    "confidence": "requires_visual_check",
                }
            )
        else:
            markdown.extend(["> [本页未提取到文字，需 OCR。]", ""])
        source_map["pages"].append(
            {
                "pdf_page": index,
                "printed_page": None,
                "text_characters": compact_chars,
                "needs_ocr": needs_ocr,
                "blocks": blocks,
                "figures": [],
                "page_renders": [],
            }
        )
    stats = {
        "page_count": page_count,
        "text_blocks": block_count,
        "captions": 0,
        "embedded_images": 0,
        "rendered_pages": 0,
        "ocr_pages": ocr_pages,
        "visual_risk": "高：降级文本抽取不保证图表、公式、双栏顺序和图片完整",
        "engine": "pypdf-text-only-fallback",
    }
    return "\n".join(markdown).rstrip() + "\n", source_map, stats


def render_selected_pages(
    pdf_path: Path,
    output_dir: Path,
    digest: str,
    dpi: int,
    source_map: dict[str, Any],
    pages: list[int],
) -> list[int]:
    if not pages:
        return []
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for local page snapshots") from exc
    page_records = {int(item["pdf_page"]): item for item in source_map.get("pages", [])}
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf_path)
    added: list[int] = []
    try:
        for page_number in pages:
            record = page_records[page_number]
            renders = record.setdefault("page_renders", [])
            filename = f"{digest[:12]}-p{page_number:04d}-manual-dpi{dpi}.png"
            relative = f"assets/{filename}"
            if any(item.get("asset") == relative for item in renders) and (assets_dir / filename).is_file():
                continue
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0), alpha=False)
            pixmap.save(assets_dir / filename)
            renders.append(
                {
                    "id": f"RM{page_number:04d}",
                    "asset": relative,
                    "dpi": dpi,
                    "reason": "manual_local_verification",
                }
            )
            added.append(page_number)
    finally:
        document.close()
    return added


def build_report(manifest: dict[str, Any]) -> str:
    stats = manifest["stats"]
    ocr_pages = stats.get("ocr_pages", [])
    ocr_text = "、".join(str(page) for page in ocr_pages) if ocr_pages else "无"
    source_txt = manifest.get("temporary_text_source")
    txt_line = f"- 临时 TXT 来源：`{source_txt}`（成功迁移后可已清理）\n" if source_txt else ""
    return f"""# PDF 转换报告

- 题名：{manifest['title']}
- 原 PDF：`{manifest['source_pdf']}`
- PDF SHA-256：`{manifest['pdf_sha256']}`
- PDF 页数：{manifest['page_count']}
- 生成时间：`{manifest['generated_at_utc']}`
- 提取来源：`{manifest['extraction_source']}`
{txt_line}- 转换模式：`{manifest['conversion_mode']}`
- DPI：{manifest['dpi']}
- 正文文本块：{stats.get('text_blocks', 0)}
- 识别到的题注块：{stats.get('captions', 0)}
- 抽取的嵌入图片：{stats.get('embedded_images', 0)}
- 页面快照：{stats.get('rendered_pages', 0)}
- 疑似需要 OCR 的 PDF 页：{ocr_text}
- 图表/公式/版式风险：{stats.get('visual_risk', '待核验')}

## 使用边界

1. `paper.md` 是唯一长期全文阅读缓存，原 PDF 是权威原件。
2. 缓存不保证表格、公式、双栏阅读顺序和图片完整。
3. 引文、数值、统计符号、公式、图表与关键结论必须按 PDF 页码回查。
4. 只有精读图表、公式或关键页面时，才补充相应页面快照或局部解析。
5. “需要 OCR”表示原生文字过少，不代表页面为空；未核验前不得猜测。
6. Markdown 行号不是学术定位；使用 PDF 页码和 `S/C/F/R` 块 ID。
"""


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def recognized_temp_txt(path: Path, extra_roots: list[Path]) -> bool:
    resolved = path.resolve()
    if any(is_relative_to(resolved, root.expanduser().resolve()) for root in extra_roots):
        return True
    lowered = [part.lower() for part in resolved.parts]
    return any(lowered[index : index + 2] == ["tmp", "pdfs"] for index in range(len(lowered) - 1))


def cleanup_temporary_txt(path: Path | None, extra_roots: list[Path]) -> str | None:
    if path is None or not path.exists():
        return None
    if not recognized_temp_txt(path, extra_roots):
        return f"TXT_NOT_DELETED_OUTSIDE_TEMP {path}"
    path.unlink()
    return f"TEMP_TXT_DELETED {path}"


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def refresh_project_cache_records(project_root: Path) -> int:
    cache_root = project_root / "02-文献" / "转换缓存"
    cache_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for manifest_path in sorted(cache_root.glob("*/conversion_manifest.json")):
        try:
            manifest = load_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        fingerprint = {
            key: manifest.get(key)
            for key in ("pdf_sha256", "conversion_mode", "dpi", "converter_schema")
        }
        if "mineru_request" in manifest:
            fingerprint["mineru_request"] = manifest["mineru_request"]
        valid, _ = validate_cache(manifest_path.parent, fingerprint)
        if not valid:
            continue
        stats = manifest.get("stats", {})
        records.append(
            {
                "title": manifest.get("title", manifest_path.parent.name),
                "paper_id": manifest.get("paper_id", manifest_path.parent.name),
                "pages": manifest.get("page_count", "?"),
                "link": f"./{manifest_path.parent.name}/paper.md",
                "risk": (
                    f"OCR风险 {len(stats.get('ocr_pages', []))} 页；"
                    f"{stats.get('visual_risk', '图表风险待核验')}"
                ),
            }
        )
    generated = now_utc()
    index_lines = [
        "# Markdown 全文缓存索引",
        "",
        f"> 更新时间：`{generated}`。`paper.md` 是唯一长期全文阅读缓存；原 PDF 仍是权威原件。",
        "",
        "| 题名 | Paper ID | PDF 页数 | 缓存 | OCR/图表风险 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for record in records:
        index_lines.append(
            "| {title} | `{paper_id}` | {pages} | [paper.md]({link}) | {risk} |".format(
                **{key: markdown_cell(value) for key, value in record.items()}
            )
        )
    if not records:
        index_lines.append("| 暂无 | - | - | - | - |")
    atomic_text(cache_root / "00-缓存索引.md", "\n".join(index_lines) + "\n")

    state_path = project_root / "00-项目状态.md"
    if state_path.is_file():
        state = state_path.read_text(encoding="utf-8")
        state = re.sub(r"(?m)^last_updated:\s*[^\n]+", f'last_updated: "{datetime.now().date().isoformat()}"', state)
        section_lines = [
            "## 可复用全文缓存",
            "",
            "- 索引：[Markdown 全文缓存索引](02-文献/转换缓存/00-缓存索引.md)",
            f"- 已有可复用缓存：{len(records)} 篇",
        ]
        section_lines.extend(
            f"- `{record['paper_id']}`：{record['title']}（{record['pages']} 页）"
            for record in records
        )
        section = "\n".join(section_lines) + "\n\n"
        pattern = re.compile(r"(?ms)^## 可复用全文缓存\s*\n.*?(?=^## |\Z)")
        if pattern.search(state):
            state = pattern.sub(section, state)
        else:
            marker = "## 文件索引"
            state = state.replace(marker, section + marker) if marker in state else state.rstrip() + "\n\n" + section
        atomic_text(state_path, state)
    return len(records)


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf.expanduser().resolve()
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        print(f"ERROR input PDF does not exist: {pdf_path}", file=sys.stderr)
        return 2
    if not 72 <= args.dpi <= 300:
        print("ERROR --dpi must be between 72 and 300", file=sys.stderr)
        return 2
    try:
        digest = sha256_file(pdf_path)
        page_count, metadata_title = get_pdf_info(pdf_path)
        output_dir, project_root, paper_id = resolve_destination(args, pdf_path, digest)
        render_pages = parse_page_spec(args.render_pages, page_count)
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    if args.mineru_task and args.source_txt:
        print("ERROR choose either --mineru-task or --source-txt", file=sys.stderr)
        return 2
    source_txt = args.source_txt.expanduser().resolve() if args.source_txt else None
    mineru_binding = None
    if args.mineru_task is not None:
        try:
            mineru_task_record = load_json(args.mineru_task)
            mineru_binding = mineru_task_binding(mineru_task_record)
            if mineru_binding["source_sha256"] != digest:
                raise ValueError("MinerU task original source hash does not match input PDF")
            if Path(mineru_task_record.get("source", "")).expanduser().resolve() != pdf_path:
                raise ValueError("MinerU task source path does not match input PDF")
        except Exception as exc:
            print(f"ERROR invalid MinerU task record: {exc}", file=sys.stderr)
            return 2
    fingerprint = cache_fingerprint(
        digest, args.image_mode, args.dpi, mineru_binding=mineru_binding
    )
    valid, reason = cache_first_probe(output_dir, fingerprint)
    if args.check_cache:
        print(f"CACHE_REUSED {output_dir}" if valid else f"CACHE_MISS {reason}")
        return 0 if valid else 3
    if valid and not args.force:
        added: list[int] = []
        if render_pages:
            def apply_render_update(staging: Path) -> None:
                nonlocal added
                manifest = load_json(staging / "conversion_manifest.json")
                source_map = load_json(staging / "source_map.json")
                added = render_selected_pages(
                    pdf_path, staging, digest, args.dpi, source_map, render_pages
                )
                if not added:
                    return
                stats = manifest.setdefault("stats", {})
                stats["rendered_pages"] = sum(
                    len(page.get("page_renders", []))
                    for page in source_map.get("pages", [])
                )
                manual = set(manifest.get("supplemental_render_pages", []))
                manual.update(added)
                manifest["supplemental_render_pages"] = sorted(manual)
                atomic_json(staging / "source_map.json", source_map)
                atomic_json(staging / "conversion_manifest.json", manifest)
                atomic_text(staging / "conversion_report.md", build_report(manifest))

            try:
                update_cache_atomically(output_dir, fingerprint, apply_render_update)
            except Exception as exc:
                print(f"ERROR supplemental render failed: {exc}", file=sys.stderr)
                return 1
        cleanup_message = cleanup_temporary_txt(source_txt, args.temp_dir)
        if project_root:
            refresh_project_cache_records(project_root)
        print(f"CACHE_REUSED {output_dir}")
        if added:
            print("LOCAL_PAGES_RENDERED " + ",".join(str(page) for page in added))
        if cleanup_message:
            print(cleanup_message)
        return 0

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    prepared_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    (prepared_dir / "assets").mkdir(parents=True, exist_ok=True)
    generated_at = now_utc()
    title = args.title or metadata_title or pdf_path.stem
    if not title or title.lower() in {"untitled", "microsoft word"}:
        title = pdf_path.stem
    try:
        if args.mineru_task is not None:
            # Embeddable Python may omit the script directory from sys.path.
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from mineru_cache import import_task
            markdown, source_map, stats = import_task(
                args.mineru_task,
                pdf_path,
                prepared_dir,
                digest,
                page_count,
                title,
                generated_at,
            )
            extraction_source = "mineru_desk_local"
        elif source_txt is not None:
            if not source_txt.is_file():
                raise FileNotFoundError(f"source TXT does not exist: {source_txt}")
            markdown, source_map, stats = build_from_paginated_txt(
                pdf_path, source_txt, digest, page_count, title, generated_at
            )
            extraction_source = "legacy_paginated_txt"
        else:
            try:
                import fitz  # noqa: F401
            except ImportError:
                markdown, source_map, stats = extract_with_pypdf(
                    pdf_path, digest, page_count, title, generated_at
                )
                extraction_source = "pypdf_text_fallback"
            else:
                markdown, source_map, stats = extract_with_pymupdf(
                    pdf_path,
                    prepared_dir,
                    args.image_mode,
                    args.dpi,
                    digest,
                    page_count,
                    title,
                    generated_at,
                )
                extraction_source = "pymupdf_native_pdf"
    except Exception as exc:
        shutil.rmtree(prepared_dir, ignore_errors=True)
        print(f"ERROR conversion failed: {exc}", file=sys.stderr)
        return 1

    try:
        manifest: dict[str, Any] = {
            **fingerprint,
            "paper_id": paper_id,
            "title": title,
            "source_pdf": str(pdf_path),
            "source_size_bytes": pdf_path.stat().st_size,
            "page_count": page_count,
            "generated_at_utc": generated_at,
            "extraction_source": extraction_source,
            "stats": stats,
            "supplemental_render_pages": [],
            "network_policy": "local_only_no_auto_upload",
        }
        if source_txt:
            manifest["temporary_text_source"] = str(source_txt)
        if extraction_source == "mineru_desk_local":
            manifest["mineru"] = source_map["mineru"]
        else:
            manifest["local_fallback"] = local_fallback_policy(
                ocr_available=False,
                unrecognized_pages=list(stats.get("ocr_pages", [])),
            )
        atomic_text(prepared_dir / "paper.md", markdown)
        atomic_json(prepared_dir / "source_map.json", source_map)
        atomic_json(prepared_dir / "conversion_manifest.json", manifest)
        atomic_text(prepared_dir / "conversion_report.md", build_report(manifest))

        added = render_selected_pages(
            pdf_path, prepared_dir, digest, args.dpi, source_map, render_pages
        )
        if added:
            stats["rendered_pages"] = sum(
                len(page.get("page_renders", []))
                for page in source_map.get("pages", [])
            )
            manifest["supplemental_render_pages"] = added
            atomic_json(prepared_dir / "source_map.json", source_map)
            atomic_json(prepared_dir / "conversion_manifest.json", manifest)
            atomic_text(prepared_dir / "conversion_report.md", build_report(manifest))

        if sha256_file(pdf_path) != digest:
            raise ValueError("original PDF changed during conversion")
        publish_cache_atomically(prepared_dir, output_dir, fingerprint)
    except Exception as exc:
        shutil.rmtree(prepared_dir, ignore_errors=True)
        print(f"ERROR generated cache failed validation: {exc}", file=sys.stderr)
        return 1
    cleanup_message = cleanup_temporary_txt(source_txt, args.temp_dir)
    cache_count = refresh_project_cache_records(project_root) if project_root else None
    print(f"CONVERTED {pdf_path}")
    print(f"OUTPUT {output_dir}")
    print(
        "SUMMARY "
        f"pages={page_count} blocks={stats['text_blocks']} "
        f"images={stats['embedded_images']} renders={stats['rendered_pages']} "
        f"ocr_pages={len(stats['ocr_pages'])} source={extraction_source}"
    )
    if added:
        print("LOCAL_PAGES_RENDERED " + ",".join(str(page) for page in added))
    if extraction_source != "mineru_desk_local":
        print("LOCAL_FALLBACK local-only; never auto-upload")
    if cleanup_message:
        print(cleanup_message)
    if cache_count is not None:
        print(f"PROJECT_CACHE_INDEX_UPDATED count={cache_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
