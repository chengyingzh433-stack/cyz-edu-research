import base64
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "cyz-edu-research" / "scripts"
LOCK = ROOT / "dependencies.lock.json"
RELEASE_SCOPE = ROOT / "skills" / "mineru" / "README.release-scope.md"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MINERU_CACHE = load_module("task7_mineru_cache", SCRIPTS / "mineru_cache.py")
EXPORT_TASK = load_module("task7_export_mineru_task", SCRIPTS / "export_mineru_task.py")
CONVERT = load_module("task7_convert_pdf_to_md", SCRIPTS / "convert_pdf_to_md.py")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def desk_key(source_hash: str, task: dict[str, object]) -> str:
    options = task["options"]
    settings = task["runtimeSettings"]
    payload = {
        "digest": source_hash,
        "conversion": {key: value for key, value in options.items() if key != "force"},
        "version": task["runtime_version"],
        "server": "",
        "vlmUrl": "",
        **{
            key: settings[key]
            for key in ("modelSource", "offline", "modelRoot")
        },
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_cache_fixture(
    root: Path, source_hash: str, *, task_status: str = "completed"
) -> dict[str, object]:
    root.mkdir(parents=True)
    assets = root / "assets"
    assets.mkdir()
    (assets / "figure.png").write_bytes(b"figure")
    (root / "paper.md").write_text(
        "# Fixture\n\n## PDF 第 1 页\n\n第一页\n\n## PDF 第 2 页\n\n第二页\n",
        encoding="utf-8",
    )
    binding = {
        "source_sha256": source_hash,
        "desk_cache_key": "desk-key",
        "options": {
            "provider": "local",
            "backend": "pipeline",
            "cloudMode": "extract",
            "method": "auto",
            "language": "ch",
            "formula": True,
            "table": True,
            "imageAnalysis": False,
            "effort": "medium",
            "formats": ["md", "json"],
            "timeout": 3600,
            "extraArgs": [],
            "env": {},
            "pages": None,
        },
        "runtime_version": "mineru-cli.py, version 3.4.5",
        "runtime_settings": {
            "modelSource": "local",
            "offline": True,
            "modelRoot": "models",
        },
    }
    source_map = {
        "source_pdf": "fixture.pdf",
        "pdf_sha256": source_hash,
        "pages": [
            {
                "pdf_page": 1,
                "figures": [{"asset": "assets/figure.png"}],
                "page_renders": [],
            },
            {"pdf_page": 2, "figures": [], "page_renders": []},
        ],
        "mineru": {
            "task_id": "task-1",
            "task_status": task_status,
            "source_sha256": source_hash,
            "desk_cache_key": "desk-key",
            "source_verification": "original_input_sha256",
            "options": binding["options"],
            "runtime_version": binding["runtime_version"],
            "runtime_settings": binding["runtime_settings"],
            "base_task_id": "task-1",
            "lineage_task_ids": ["task-1"],
        },
    }
    manifest = {
        "pdf_sha256": source_hash,
        "conversion_mode": "auto",
        "dpi": 150,
        "converter_schema": CONVERT.SCHEMA_VERSION,
        "mineru_request": binding,
        "page_count": 2,
        "extraction_source": "mineru_desk_local",
        "mineru": source_map["mineru"],
        "stats": {"ocr_pages": []},
    }
    (root / "source_map.json").write_text(
        json.dumps(source_map, ensure_ascii=False), encoding="utf-8"
    )
    (root / "conversion_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    (root / "conversion_report.md").write_text("# Report\n", encoding="utf-8")
    return CONVERT.cache_fingerprint(
        source_hash, "auto", 150, mineru_binding=binding
    )


class CacheIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.temp_root = Path(self.temporary.name)
        self.fixture_number = 0

    def copied_desk_fixture(
        self, *, status: str = "completed", provider: str = "local"
    ) -> tuple[Path, Path, Path, dict[str, object]]:
        self.fixture_number += 1
        fixture_root = self.temp_root / f"desk-fixture-{self.fixture_number}"
        seed = fixture_root / "seed"
        raw_seed = seed / "raw"
        images = raw_seed / "images"
        images.mkdir(parents=True)
        (raw_seed / "document.md").write_text("raw markdown\n", encoding="utf-8")
        (raw_seed / "document_content_list.json").write_text(
            json.dumps(
                [
                    {"type": "text", "page_idx": 0, "text": "第一页正文。" * 10},
                    {
                        "type": "image",
                        "page_idx": 1,
                        "text": "第二页图示。" * 10,
                        "img_path": "images/figure.png",
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (raw_seed / "document_middle.json").write_text(
            json.dumps(
                {
                    "_version_name": "3.4.5",
                    "_backend": "pipeline",
                    "pdf_info": [{"page_idx": 0}, {"page_idx": 1}],
                }
            ),
            encoding="utf-8",
        )
        (images / "figure.png").write_bytes(b"synthetic-image")
        (raw_seed / "document_origin.pdf").write_bytes(b"not-the-original-pdf")
        case = fixture_root / "case"
        shutil.copytree(seed, case)
        source = fixture_root / "input.pdf"
        source.write_bytes(b"%PDF-1.7\nsynthetic authorized fixture\n")
        source_hash = sha256(source)
        raw = case / "raw"
        task: dict[str, object] = {
            "id": "task-1",
            "status": status,
            "source": str(source),
            "source_sha256": source_hash,
            "options": {
                "provider": provider,
                "backend": "pipeline",
                "cloudMode": "extract",
                "method": "auto",
                "language": "ch",
                "formula": True,
                "table": True,
                "imageAnalysis": False,
                "effort": "medium",
                "formats": ["md", "json"],
                "timeout": 3600,
                "pages": "",
                "force": False,
                "extraArgs": [],
                "env": {},
            },
            "markdown": str(raw / "document.md"),
            "outputDir": str(raw),
            "runtime_version": "mineru-cli.py, version 3.4.5",
            "runtimeSettings": {
                "modelSource": "local",
                "offline": True,
                "modelRoot": "models",
            },
            "base_task_id": "task-1",
            "lineage_task_ids": ["task-1"],
        }
        task["key"] = desk_key(source_hash, task)
        task_json = fixture_root / "task.json"
        task_json.write_text(
            json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return source, task_json, fixture_root / "cache", task

    def import_fixture(
        self, source: Path, task_json: Path, output: Path
    ) -> tuple[str, dict[str, object], dict[str, object]]:
        return MINERU_CACHE.import_task(
            task_json,
            source,
            output,
            sha256(source),
            2,
            "Synthetic fixture",
            "2026-09-19T00:00:00+00:00",
        )

    def test_m01_completed_local_export_uses_original_hash_and_keeps_source_unchanged(self):
        source, task_json, output, _ = self.copied_desk_fixture()
        before = sha256(source)

        markdown, source_map, stats = self.import_fixture(source, task_json, output)

        self.assertEqual(before, sha256(source))
        self.assertEqual(2, stats["page_count"])
        self.assertEqual([1, 2], [page["pdf_page"] for page in source_map["pages"]])
        self.assertEqual(before, source_map["pdf_sha256"])
        self.assertEqual(
            "original_input_sha256", source_map["mineru"]["source_verification"]
        )
        self.assertNotIn("origin.pdf", json.dumps(source_map, ensure_ascii=False))
        self.assertIn("## PDF 第 2 页", markdown)

    def test_m01_empty_real_shaped_blocks_are_preserved_as_visual_uncertainty(self):
        source, task_json, output, _ = self.copied_desk_fixture()
        task = json.loads(task_json.read_text(encoding="utf-8"))
        markdown_path = Path(task["markdown"])
        content_path = markdown_path.parent / f"{markdown_path.stem}_content_list.json"
        content = json.loads(content_path.read_text(encoding="utf-8"))
        content.extend(
            [
                {"type": "header", "page_idx": 0, "bbox": [1, 2, 3, 4]},
                {"type": "text", "page_idx": 1, "bbox": [5, 6, 7, 8]},
            ]
        )
        content_path.write_text(json.dumps(content), encoding="utf-8")

        markdown, source_map, _ = self.import_fixture(source, task_json, output)

        empty_blocks = [
            block
            for page in source_map["pages"]
            for block in page["blocks"]
            if block.get("empty_content") is True
        ]
        self.assertEqual(["header", "text"], [block["type"] for block in empty_blocks])
        self.assertTrue(
            all(
                block["confidence"] == "missing_content_requires_visual_check"
                for block in empty_blocks
            )
        )
        self.assertEqual(2, markdown.count("MinerU 返回空内容块"))

    def test_m01_real_shaped_chart_block_keeps_image_caption_and_footnote(self):
        source, task_json, output, _ = self.copied_desk_fixture()
        task = json.loads(task_json.read_text(encoding="utf-8"))
        markdown_path = Path(task["markdown"])
        content_path = markdown_path.parent / f"{markdown_path.stem}_content_list.json"
        content = json.loads(content_path.read_text(encoding="utf-8"))
        content.append(
            {
                "type": "chart",
                "page_idx": 0,
                "bbox": [1, 2, 3, 4],
                "content": "Chart content",
                "chart_caption": ["Chart caption"],
                "chart_footnote": ["Chart footnote"],
                "img_path": "images/figure.png",
            }
        )
        content_path.write_text(json.dumps(content), encoding="utf-8")

        markdown, source_map, stats = self.import_fixture(source, task_json, output)

        self.assertIn("Chart content", markdown)
        self.assertIn("Chart caption", markdown)
        self.assertIn("Chart footnote", markdown)
        self.assertEqual(2, stats["embedded_images"])
        self.assertEqual("chart", source_map["pages"][0]["blocks"][-1]["type"])

    def test_m02_cache_first_reuses_valid_cache_without_desk_discovery(self):
        source_hash = hashlib.sha256(b"source").hexdigest()
        seed = self.temp_root / "cache-seed"
        fingerprint = write_cache_fixture(seed, source_hash)
        cache = self.temp_root / "cache-case"
        shutil.copytree(seed, cache)
        discovery_calls = []

        valid, reason = CONVERT.cache_first_probe(
            cache, fingerprint, lambda: discovery_calls.append("desk")
        )

        self.assertTrue(valid, reason)
        self.assertEqual([], discovery_calls)
        self.assertEqual(
            ["task-1"],
            json.loads((cache / "conversion_manifest.json").read_text(encoding="utf-8"))[
                "mineru"
            ]["lineage_task_ids"],
        )

    def test_m02_existing_cache_rejects_changed_mineru_binding_and_invalid_state(self):
        source_hash = hashlib.sha256(b"source").hexdigest()
        seed = self.temp_root / "bound-cache-seed"
        fingerprint = write_cache_fixture(seed, source_hash)

        binding_mutations = {
            "language": lambda value: value["mineru_request"]["options"].__setitem__(
                "language", "en"
            ),
            "formula": lambda value: value["mineru_request"]["options"].__setitem__(
                "formula", False
            ),
            "table": lambda value: value["mineru_request"]["options"].__setitem__(
                "table", False
            ),
            "runtime_version": lambda value: value["mineru_request"].__setitem__(
                "runtime_version", "mineru-cli.py, version 9.9.9"
            ),
            "runtime_settings": lambda value: value["mineru_request"][
                "runtime_settings"
            ].__setitem__("modelRoot", "other-models"),
        }
        for name, mutate_binding in binding_mutations.items():
            with self.subTest(binding=name):
                changed_binding = json.loads(json.dumps(fingerprint))
                mutate_binding(changed_binding)
                valid, reason = CONVERT.validate_cache(seed, changed_binding)
                self.assertFalse(valid)
                self.assertIn("mineru_request", reason)

        mutations = {
            "running": lambda manifest, source_map: (
                manifest["mineru"].__setitem__("task_status", "running"),
                source_map["mineru"].__setitem__("task_status", "running"),
            ),
            "cloud": lambda manifest, source_map: (
                manifest["mineru"]["options"].__setitem__("provider", "cloud"),
                source_map["mineru"]["options"].__setitem__("provider", "cloud"),
            ),
            "missing_lineage": lambda manifest, source_map: (
                manifest["mineru"].pop("lineage_task_ids"),
                source_map["mineru"].pop("lineage_task_ids"),
            ),
            "source_map_hash": lambda manifest, source_map: source_map.__setitem__(
                "pdf_sha256", "0" * 64
            ),
            "runtime": lambda manifest, source_map: (
                manifest["mineru"].__setitem__(
                    "runtime_version", "mineru-cli.py, version 9.9.9"
                ),
                source_map["mineru"].__setitem__(
                    "runtime_version", "mineru-cli.py, version 9.9.9"
                ),
            ),
            "missing_source_verification": lambda manifest, source_map: (
                manifest["mineru"].pop("source_verification"),
                source_map["mineru"].pop("source_verification"),
            ),
            "wrong_key": lambda manifest, source_map: (
                manifest["mineru"].__setitem__("desk_cache_key", "wrong"),
                source_map["mineru"].__setitem__("desk_cache_key", "wrong"),
            ),
            "partial_pages": lambda manifest, source_map: (
                manifest["mineru"]["options"].__setitem__("pages", []),
                source_map["mineru"]["options"].__setitem__("pages", []),
            ),
            "online": lambda manifest, source_map: (
                manifest["mineru"]["runtime_settings"].__setitem__("offline", False),
                source_map["mineru"]["runtime_settings"].__setitem__("offline", False),
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                case = self.temp_root / f"bound-cache-{name}"
                shutil.copytree(seed, case)
                manifest_path = case / "conversion_manifest.json"
                source_map_path = case / "source_map.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
                mutate(manifest, source_map)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                source_map_path.write_text(json.dumps(source_map), encoding="utf-8")
                valid, reason = CONVERT.validate_cache(case, fingerprint)
                self.assertFalse(valid, name)
                self.assertNotEqual("valid", reason)

        malformed = self.temp_root / "bound-cache-malformed-assets"
        shutil.copytree(seed, malformed)
        source_map_path = malformed / "source_map.json"
        source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
        source_map["pages"][0]["figures"] = {"asset": "assets/figure.png"}
        source_map_path.write_text(json.dumps(source_map), encoding="utf-8")
        valid, reason = CONVERT.validate_cache(malformed, fingerprint)
        self.assertFalse(valid)
        self.assertIn("asset metadata", reason)

    def test_m02_cli_check_cache_reuses_intrinsically_valid_mineru_cache(self):
        source = self.temp_root / "probe.pdf"
        source.write_bytes(b"source")
        output = self.temp_root / "probe-cache"
        write_cache_fixture(output, sha256(source))
        stdout = io.StringIO()
        argv = [
            str(CONVERT.__file__),
            str(source),
            "--output-dir", str(output),
            "--check-cache",
        ]
        with (
            mock.patch("sys.argv", argv),
            mock.patch.object(CONVERT, "get_pdf_info", return_value=(2, "Fixture")),
            mock.patch.object(
                CONVERT,
                "mineru_task_binding",
                side_effect=AssertionError("Desk/task discovery must not run"),
            ) as discovery,
            mock.patch("sys.stdout", stdout),
        ):
            result = CONVERT.main()

        self.assertEqual(0, result, stdout.getvalue())
        self.assertIn("CACHE_REUSED", stdout.getvalue())
        discovery.assert_not_called()

    def test_m03_rejects_wrong_source_key_partial_pages_missing_assets_running_and_cloud(self):
        variants = {
            "wrong_source_hash": lambda task, raw: task.__setitem__(
                "source_sha256", "0" * 64
            ),
            "wrong_cache_key": lambda task, raw: task.__setitem__("key", "0" * 64),
            "partial_pages": lambda task, raw: (raw / "document_middle.json").write_text(
                json.dumps(
                    {
                        "_version_name": "3.4.5",
                        "_backend": "pipeline",
                        "pdf_info": [{"page_idx": 0}],
                    }
                ),
                encoding="utf-8",
            ),
            "missing_asset": lambda task, raw: (
                raw / "images" / "figure.png"
            ).unlink(),
            "running": lambda task, raw: task.__setitem__("status", "running"),
            "cloud": lambda task, raw: task["options"].__setitem__(
                "provider", "cloud"
            ),
        }
        messages = set()
        for name, mutate in variants.items():
            with self.subTest(variant=name):
                source, task_json, output, task = self.copied_desk_fixture()
                raw = Path(task["outputDir"])
                mutate(task, raw)
                task_json.write_text(json.dumps(task), encoding="utf-8")
                with self.assertRaises(ValueError) as raised:
                    self.import_fixture(source, task_json, output)
                messages.add(str(raised.exception))
        self.assertEqual(len(variants), len(messages))

        source, task_json, output, task = self.copied_desk_fixture()
        task["options"]["pages"] = []
        task_json.write_text(json.dumps(task), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "full-document"):
            self.import_fixture(source, task_json, output)

    def test_m03_full_document_pages_accepts_null_or_empty_string_only(self):
        source, task_json, output, task = self.copied_desk_fixture()
        task["options"]["pages"] = ""
        task["key"] = desk_key(sha256(source), task)
        task_json.write_text(json.dumps(task), encoding="utf-8")

        _, source_map, _ = self.import_fixture(source, task_json, output)

        self.assertIsNone(source_map["mineru"]["options"]["pages"])
        binding = CONVERT.mineru_task_binding(task)
        self.assertIsNone(binding["options"]["pages"])

        for invalid in ([], 0, False, "1"):
            with self.subTest(import_pages=repr(invalid)):
                source, task_json, output, task = self.copied_desk_fixture()
                task["options"]["pages"] = invalid
                task["key"] = desk_key(sha256(source), task)
                task_json.write_text(json.dumps(task), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "full-document"):
                    self.import_fixture(source, task_json, output)

        invalid_options = {
            "cloudMode": ("upload", "cloudMode"),
            "env": ({"TOKEN": "secret"}, "env"),
            "extraArgs": (["--unsafe"], "extraArgs"),
            "formats": ("markdown", "formats"),
            "imageAnalysis": ("yes", "imageAnalysis"),
            "effort": ("", "effort"),
            "timeout": (False, "timeout"),
        }
        for field, (invalid, message) in invalid_options.items():
            with self.subTest(import_field=field):
                source, task_json, output, task = self.copied_desk_fixture()
                task["options"][field] = invalid
                task["key"] = desk_key(sha256(source), task)
                task_json.write_text(json.dumps(task), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    self.import_fixture(source, task_json, output)

        source, _, _, task = self.copied_desk_fixture(status="reused")
        base = dict(task, id="base-1", status="completed")
        base["options"] = dict(task["options"], pages="")
        base["log"] = "mineru-cli.py, version 3.4.5\n"
        middle = dict(task, id="reuse-1", status="reused", reusedFrom="base-1")
        middle["options"] = dict(task["options"], pages=None)
        head = dict(task, id="reuse-2", status="reused", reusedFrom="reuse-1")
        head["options"] = dict(task["options"], pages="")
        tasks = {item["id"]: item for item in (head, middle, base)}

        exported = EXPORT_TASK.export(
            self.temp_root, "reuse-2", fetch_task=lambda identifier: tasks[identifier]
        )

        self.assertEqual("", exported["options"]["pages"])
        self.assertEqual(
            {
                "provider", "backend", "cloudMode", "method", "language",
                "formula", "table", "imageAnalysis", "effort", "formats",
                "timeout", "pages", "force", "extraArgs", "env",
            },
            set(exported["options"]),
        )
        exported_path = self.temp_root / "real-shape-export.json"
        exported_path.write_text(json.dumps(exported), encoding="utf-8")
        _, exported_source_map, _ = MINERU_CACHE.import_task(
            exported_path,
            source,
            self.temp_root / "real-shape-import",
            sha256(source),
            2,
            "Synthetic fixture",
            "2026-09-19T00:00:00+00:00",
        )
        self.assertIsNone(exported_source_map["mineru"]["options"]["pages"])
        self.assertIsNone(CONVERT.mineru_task_binding(exported)["options"]["pages"])
        for invalid in ([], 0, False, "1"):
            with self.subTest(export_pages=repr(invalid)):
                broken = {key: dict(value) for key, value in tasks.items()}
                broken["reuse-2"]["options"] = dict(
                    tasks["reuse-2"]["options"], pages=invalid
                )
                with self.assertRaisesRegex(ValueError, "full-document"):
                    EXPORT_TASK.export(
                        self.temp_root,
                        "reuse-2",
                        fetch_task=lambda identifier: broken[identifier],
                    )

    def test_m04_reused_task_requires_complete_lineage(self):
        source, task_json, output, task = self.copied_desk_fixture(status="reused")
        task.update(
            {
                "id": "reuse-2",
                "base_task_id": "task-1",
                "reused_from_task_id": "task-1",
                "lineage_task_ids": ["reuse-2", "task-1"],
            }
        )
        task_json.write_text(json.dumps(task), encoding="utf-8")

        _, source_map, _ = self.import_fixture(source, task_json, output)
        self.assertEqual(
            ["reuse-2", "task-1"], source_map["mineru"]["lineage_task_ids"]
        )

        del task["lineage_task_ids"]
        task_json.write_text(json.dumps(task), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lineage"):
            self.import_fixture(source, task_json, self.temp_root / "bad-lineage")

    def test_m05_running_cloud_and_interrupted_polling_never_submit_or_upload(self):
        source, _, _, task = self.copied_desk_fixture(status="running")
        submission_count = 1
        fetch_count = 0

        def fetch_running(identifier: str):
            nonlocal fetch_count
            fetch_count += 1
            self.assertEqual("task-1", identifier)
            return dict(task)

        with self.assertRaisesRegex(ValueError, "continue polling the same ID"):
            EXPORT_TASK.export(self.temp_root, "task-1", fetch_task=fetch_running)
        self.assertEqual(1, submission_count)
        self.assertEqual(1, fetch_count)

        cloud = dict(task)
        cloud["status"] = "completed"
        cloud["options"] = dict(task["options"], provider="cloud")
        with self.assertRaisesRegex(ValueError, "local"):
            EXPORT_TASK.export(
                self.temp_root, "task-1", fetch_task=lambda identifier: cloud
            )

        fallback = CONVERT.local_fallback_policy(
            ocr_available=False, unrecognized_pages=[1]
        )
        self.assertEqual("local_native", fallback["mode"])
        self.assertFalse(fallback["auto_upload"])
        self.assertEqual([1], fallback["unrecognized_pages"])
        self.assertIn("never auto-upload", fallback["notice"])
        self.assertEqual(sha256(source), sha256(source))

    def test_m05_submit_state_survives_poll_interruption_without_duplicate_submission(self):
        state_path = self.temp_root / "submission-state.json"
        _, _, _, task = self.copied_desk_fixture()
        request = {
            "source_sha256": hashlib.sha256(b"source").hexdigest(),
            "options": task["options"],
        }
        runtime_settings = dict(task["runtimeSettings"], modelSource="modelscope")
        submissions = []

        def submit(payload: dict[str, object]) -> str:
            submissions.append(payload)
            return "task-persisted"

        def interrupted_fetch(task_id: str):
            self.assertEqual("task-persisted", task_id)
            raise KeyboardInterrupt("simulated polling interruption")

        with self.assertRaises(KeyboardInterrupt):
            EXPORT_TASK.submit_resume_and_poll(
                state_path,
                request,
                submit,
                interrupted_fetch,
                runtime_settings=runtime_settings,
                max_polls=2,
            )
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("task-persisted", saved["task_id"])
        self.assertEqual(1, len(submissions))

        completed = EXPORT_TASK.submit_resume_and_poll(
            state_path,
            request,
            submit,
            lambda task_id: {"id": task_id, "status": "completed"},
            runtime_settings=runtime_settings,
            max_polls=2,
        )
        self.assertEqual("task-persisted", completed["id"])
        self.assertEqual(1, len(submissions))

        invalid_requests = {
            "backend": ({"options": dict(task["options"], backend="vlm")}, runtime_settings),
            "cloudMode": ({"options": dict(task["options"], cloudMode="upload")}, runtime_settings),
            "server": ({"options": task["options"], "server": "https://example.invalid"}, runtime_settings),
            "offline": ({"options": task["options"]}, dict(runtime_settings, offline=False)),
            "missing preflight": ({"options": task["options"]}, None),
        }
        for name, (patch, settings) in invalid_requests.items():
            with self.subTest(unsafe_submit=name):
                unsafe = {"source_sha256": request["source_sha256"], **patch}
                with self.assertRaises(ValueError):
                    EXPORT_TASK.submit_resume_and_poll(
                        self.temp_root / f"unsafe-{name}.json",
                        unsafe,
                        submit,
                        lambda task_id: {"id": task_id, "status": "completed"},
                        runtime_settings=settings,
                        max_polls=1,
                    )

        before_invalid_poll_settings = len(submissions)
        for name, poll_arguments in {
            "zero polls": {"max_polls": 0},
            "negative interval": {"poll_interval": -1},
        }.items():
            with self.subTest(invalid_poll_setting=name):
                with self.assertRaises(ValueError):
                    EXPORT_TASK.submit_resume_and_poll(
                        self.temp_root / f"invalid-poll-{name}.json",
                        request,
                        submit,
                        lambda task_id: {"id": task_id, "status": "completed"},
                        runtime_settings=runtime_settings,
                        **poll_arguments,
                    )
        self.assertEqual(before_invalid_poll_settings, len(submissions))

    def test_m05_cli_submit_resume_persists_id_before_poll_and_never_resubmits(self):
        source, _, _, task = self.copied_desk_fixture()
        task = dict(task)
        task.update(
            id="task-cli",
            status="completed",
            log="mineru-cli.py, version 3.4.5\n",
            runtimeSettings=dict(task["runtimeSettings"], modelSource="modelscope"),
        )
        request_path = self.temp_root / "request.json"
        state_path = self.temp_root / "submission.json"
        output_path = self.temp_root / "export.json"
        request = {
            "files": [str(source.resolve())],
            "outputRoot": str((self.temp_root / "desk-output").resolve()),
            "options": task["options"],
        }
        request_path.write_text(
            json.dumps(request, ensure_ascii=False), encoding="utf-8"
        )
        desk_root = self.temp_root / "desk"
        desk_root.mkdir()
        (desk_root / "Codex.ps1").write_text("# fixture\n", encoding="utf-8")
        submissions: list[list[str]] = []
        task_queries = 0

        def fake_run(command, **kwargs):
            nonlocal task_queries
            args = [str(value) for value in command]
            self.assertEqual("-EncodedCommand", args[-2])
            script = base64.b64decode(args[-1]).decode("utf-16le")
            if "'request' 'GET' 'state'" in script:
                payload = {
                    "paused": False,
                    "settings": {
                        "offline": True,
                        "modelSource": "modelscope",
                        "modelRoot": "models",
                    },
                }
            elif "'submit'" in script:
                submissions.append(args)
                submitted = json.loads(request_path.read_text(encoding="utf-8"))
                self.assertNotIn("runtimeSettings", submitted)
                payload = [{"id": "task-cli"}]
            elif "'request' 'GET' 'tasks/task-cli'" in script:
                task_queries += 1
                payload = (
                    {"id": "task-cli", "status": "running"}
                    if task_queries == 1
                    else task
                )
            else:
                self.fail(f"unexpected Desk command: {args}")
            return subprocess.CompletedProcess(
                command, 0, stdout=json.dumps(payload, ensure_ascii=False), stderr=""
            )

        arguments = [
            "--desk-root", str(desk_root),
            "--request", str(request_path),
            "--state", str(state_path),
            "--output", str(output_path),
            "--max-polls", "1",
            "--poll-interval", "0",
        ]
        with mock.patch.object(EXPORT_TASK.subprocess, "run", side_effect=fake_run):
            self.assertEqual(2, EXPORT_TASK.main(arguments))
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("task-cli", saved["task_id"])
            self.assertEqual(1, len(submissions))

            self.assertEqual(0, EXPORT_TASK.main(arguments))

        self.assertEqual(1, len(submissions))
        exported = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual("task-cli", exported["id"])
        self.assertEqual("modelscope", exported["runtimeSettings"]["modelSource"])

    def test_m05_task_query_preserves_failed_task_json_from_desk_exit_two(self):
        desk_root = self.temp_root / "failed-task-desk"
        desk_root.mkdir()
        (desk_root / "Codex.ps1").write_text("# fixture\n", encoding="utf-8")
        failed_task = {
            "id": "task-failed",
            "status": "failed",
            "error": "local conversion failed",
        }
        completed = subprocess.CompletedProcess(
            ["powershell.exe"],
            2,
            stdout=json.dumps(failed_task),
            stderr="",
        )
        with mock.patch.object(EXPORT_TASK.subprocess, "run", return_value=completed):
            result = EXPORT_TASK.run_codex(
                desk_root, "request", "GET", "tasks/task-failed"
            )
        self.assertEqual(failed_task, result)

        api_error = subprocess.CompletedProcess(
            ["powershell.exe"],
            1,
            stdout=json.dumps({"error": "service unavailable"}),
            stderr="",
        )
        with mock.patch.object(EXPORT_TASK.subprocess, "run", return_value=api_error):
            with self.assertRaises(RuntimeError):
                EXPORT_TASK.run_codex(
                    desk_root, "request", "GET", "tasks/task-failed"
                )

    def test_m01_exporter_hashes_original_and_validates_every_lineage_node(self):
        source, _, _, task = self.copied_desk_fixture(status="reused")
        base = dict(task)
        base.update(
            {
                "id": "base-1",
                "status": "completed",
                "log": "mineru-cli.py, version 3.4.5\n",
            }
        )
        middle = dict(task)
        middle.update({"id": "reuse-1", "status": "reused", "reusedFrom": "base-1"})
        head = dict(task)
        head.update({"id": "reuse-2", "status": "reused", "reusedFrom": "reuse-1"})
        tasks = {item["id"]: item for item in (head, middle, base)}

        exported = EXPORT_TASK.export(
            self.temp_root, "reuse-2", fetch_task=lambda identifier: tasks[identifier]
        )

        self.assertEqual(sha256(source), exported["source_sha256"])
        self.assertEqual(["reuse-2", "reuse-1", "base-1"], exported["lineage_task_ids"])
        self.assertEqual({}, exported["options"]["env"])
        self.assertNotIn("origin.pdf", json.dumps(exported, ensure_ascii=False))

        def assert_rejected(mutator, message: str):
            broken = {key: dict(value) for key, value in tasks.items()}
            broken = {
                key: {
                    **value,
                    "options": dict(value["options"]),
                    "runtimeSettings": dict(value["runtimeSettings"]),
                }
                for key, value in broken.items()
            }
            mutator(broken)
            with self.assertRaisesRegex(ValueError, message):
                EXPORT_TASK.export(
                    self.temp_root,
                    "reuse-2",
                    fetch_task=lambda identifier: broken[identifier],
                )

        cases = {
            "wrong returned task ID": (
                lambda value: value["reuse-1"].__setitem__("id", "wrong"),
                "returned task ID",
            ),
            "nonterminal lineage": (
                lambda value: value["reuse-1"].__setitem__("status", "running"),
                "completed or reused",
            ),
            "cloud lineage": (
                lambda value: value["reuse-1"]["options"].__setitem__("provider", "cloud"),
                "local",
            ),
            "partial pages": (
                lambda value: value["reuse-1"]["options"].__setitem__("pages", []),
                "full-document",
            ),
            "key mismatch": (
                lambda value: value["reuse-1"].__setitem__("key", "wrong"),
                "key",
            ),
            "source mismatch": (
                lambda value: value["reuse-1"].__setitem__("source", str(source) + ".other"),
                "source",
            ),
            "parameter mismatch": (
                lambda value: value["reuse-1"]["options"].__setitem__("language", "en"),
                "options",
            ),
            "online lineage": (
                lambda value: value["reuse-1"]["runtimeSettings"].__setitem__("offline", False),
                "offline",
            ),
            "secret option": (
                lambda value: value["reuse-2"]["options"].__setitem__("token", "secret"),
                "unsupported option",
            ),
            "nonempty env": (
                lambda value: value["reuse-2"]["options"].__setitem__(
                    "env", {"TOKEN": "secret"}
                ),
                "env",
            ),
            "nonempty extra args": (
                lambda value: value["reuse-2"]["options"].__setitem__(
                    "extraArgs", ["--unsafe"]
                ),
                "extraArgs",
            ),
            "wrong cloud mode": (
                lambda value: value["reuse-2"]["options"].__setitem__(
                    "cloudMode", "upload"
                ),
                "cloudMode",
            ),
            "wrong timeout type": (
                lambda value: value["reuse-2"]["options"].__setitem__(
                    "timeout", False
                ),
                "timeout",
            ),
            "cycle": (
                lambda value: value["base-1"].update(status="reused", reusedFrom="reuse-2"),
                "reuse chain",
            ),
        }
        for name, (mutator, message) in cases.items():
            with self.subTest(case=name):
                assert_rejected(mutator, message)

    def test_m06_atomic_publish_preserves_source_and_old_cache_on_validation_failure(self):
        source, task_json, imported, _ = self.copied_desk_fixture()
        source_before = sha256(source)
        markdown, source_map, stats = self.import_fixture(source, task_json, imported)
        prepared = self.temp_root / "prepared-valid"
        fingerprint = write_cache_fixture(prepared, source_before)
        destination = self.temp_root / "canonical-cache"
        destination.mkdir()
        (destination / "sentinel.txt").write_text("old cache", encoding="utf-8")

        invalid = self.temp_root / "prepared-invalid"
        shutil.copytree(prepared, invalid)
        (invalid / "conversion_report.md").unlink()
        with self.assertRaisesRegex(ValueError, "validation"):
            CONVERT.publish_cache_atomically(invalid, destination, fingerprint)
        self.assertEqual("old cache", (destination / "sentinel.txt").read_text())

        CONVERT.publish_cache_atomically(prepared, destination, fingerprint)
        valid, reason = CONVERT.validate_cache(destination, fingerprint)
        self.assertTrue(valid, reason)
        self.assertFalse((destination / "sentinel.txt").exists())
        self.assertEqual(source_before, sha256(source))
        self.assertIn("PDF 第 1 页", markdown)
        self.assertEqual(source_before, source_map["pdf_sha256"])
        self.assertEqual(2, stats["page_count"])

    def test_m06_publish_commit_survives_backup_cleanup_failure(self):
        source_hash = hashlib.sha256(b"source").hexdigest()
        destination = self.temp_root / "cleanup-failure-cache"
        destination.mkdir()
        (destination / "sentinel.txt").write_text("old", encoding="utf-8")
        prepared = self.temp_root / "cleanup-failure-prepared"
        fingerprint = write_cache_fixture(prepared, source_hash)

        def fail_cleanup(path: Path):
            raise OSError(f"simulated cleanup failure: {path.name}")

        warning = CONVERT.publish_cache_atomically(
            prepared, destination, fingerprint, cleanup_backup=fail_cleanup
        )

        self.assertIn("cleanup failed", warning)
        valid, reason = CONVERT.validate_cache(destination, fingerprint)
        self.assertTrue(valid, reason)
        self.assertFalse((destination / "sentinel.txt").exists())

    def test_m06_supplemental_update_is_atomic_on_late_asset_failure(self):
        source_hash = hashlib.sha256(b"source").hexdigest()
        destination = self.temp_root / "supplemental-cache"
        fingerprint = write_cache_fixture(destination, source_hash)
        before = {
            path.relative_to(destination).as_posix(): path.read_bytes()
            for path in destination.rglob("*")
            if path.is_file()
        }

        def failing_update(staging: Path):
            (staging / "assets" / "late.png").write_bytes(b"partial")
            raise OSError("late render failure")

        with self.assertRaisesRegex(OSError, "late render failure"):
            CONVERT.update_cache_atomically(destination, fingerprint, failing_update)

        after = {
            path.relative_to(destination).as_posix(): path.read_bytes()
            for path in destination.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual([], list(destination.parent.glob(f".{destination.name}.staging-*")))

    def test_license_gate_records_local_mineru_without_vendoring_wrapper(self):
        self.assertTrue(RELEASE_SCOPE.is_file())
        self.assertEqual(
            {"README.release-scope.md"},
            {
                path.relative_to(RELEASE_SCOPE.parent).as_posix()
                for path in RELEASE_SCOPE.parent.rglob("*")
                if path.is_file()
            },
        )
        text = RELEASE_SCOPE.read_text(encoding="utf-8")
        self.assertIn("local dependency", text.lower())
        self.assertIn("LICENSE", text)
        self.assertIn("must not", text)
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        mineru = next(item for item in lock["dependencies"] if item["name"] == "mineru")
        self.assertEqual("4.0.0-desk-local", mineru["version"])
        self.assertIsNone(mineru["license"])
        self.assertEqual("unknown-no-LICENSE-or-NOTICE", mineru["licenseStatus"])
        self.assertEqual(2, len(mineru["installations"]))
        available_metrics = []
        for installation in mineru["installations"]:
            self.assertRegex(installation["directorySha256"], r"^[0-9a-f]{64}$")
            path = Path(installation["path"])
            if path.is_dir():
                metrics = self.directory_metrics(path)
                available_metrics.append(metrics)
                self.assertEqual(installation["fileCount"], metrics["fileCount"])
                self.assertEqual(installation["bytes"], metrics["bytes"])
                self.assertEqual(installation["directorySha256"], metrics["directorySha256"])
        if len(available_metrics) == 2:
            self.assertEqual(available_metrics[0], available_metrics[1])
            self.assertTrue(mineru["rootsEqual"])
        release_files = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
        forbidden = [
            path for path in release_files
            if path.endswith((".pyc", ".pyo", ".pdf", ".zip", ".safetensors"))
            or "/models/" in f"/{path.lower()}/"
        ]
        self.assertEqual([], forbidden)

    @staticmethod
    def directory_metrics(root: Path) -> dict[str, object]:
        entries = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if "__pycache__" in relative.parts or relative.suffix in {".pyc", ".pyo"}:
                continue
            data = path.read_bytes()
            entries.append((relative.as_posix(), hashlib.sha256(data).hexdigest(), len(data)))
        entries.sort(key=lambda item: item[0])
        canonical = "".join(
            f"{relative}\t{digest}\t{size}\n" for relative, digest, size in entries
        ).encode("utf-8")
        return {
            "fileCount": len(entries),
            "bytes": sum(item[2] for item in entries),
            "directorySha256": hashlib.sha256(canonical).hexdigest(),
        }


if __name__ == "__main__":
    unittest.main()
