import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "dependencies.lock.json"
CHECK = ROOT / "skills" / "cyz-edu-research" / "scripts" / "check_semantic_lock.py"
INIT = ROOT / "skills" / "cyz-edu-research" / "scripts" / "init_project.py"
VALIDATE = ROOT / "skills" / "cyz-edu-research" / "scripts" / "validate_project.py"


def run_script(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(script), *(str(arg) for arg in args)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=env,
    )


def directory_metrics(root: Path) -> dict[str, object]:
    entries: list[tuple[str, str, int]] = []
    for base, directory_names, file_names in os.walk(root):
        directory_names.sort()
        file_names.sort()
        for file_name in file_names:
            path = Path(base) / file_name
            data = path.read_bytes()
            entries.append(
                (
                    path.relative_to(root).as_posix(),
                    hashlib.sha256(data).hexdigest(),
                    len(data),
                )
            )
    entries.sort(key=lambda item: item[0])
    canonical = "".join(
        f"{relative}\t{digest}\t{size}\n"
        for relative, digest, size in entries
    ).encode("utf-8")
    return {
        "fileCount": len(entries),
        "bytes": sum(item[2] for item in entries),
        "directorySha256": hashlib.sha256(canonical).hexdigest(),
    }


def replace_frontmatter_value(path: Path, key: str, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        rf"(?m)^{re.escape(key)}:\s*.*$", f'{key}: "{value}"', text
    )
    if count != 1:
        raise AssertionError(f"expected one {key} field, found {count}")
    path.write_text(updated, encoding="utf-8")


class SemanticLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.temp_root = Path(self.temporary.name)

    def copied_text_fixture(self) -> tuple[Path, Path]:
        fixture_root = Path(tempfile.mkdtemp(prefix="text-fixture-", dir=self.temp_root))
        seed = fixture_root / "seed"
        seed.mkdir()
        baseline = (
            "研究纳入120名学生，课程持续8周。结果与成绩相关[12]，"
            "且未发现显著差异。\n"
        )
        (seed / "manuscript.md").write_text(baseline, encoding="utf-8")
        case = fixture_root / "case"
        shutil.copytree(seed, case)
        before = case / "baseline.md"
        after = case / "output.md"
        shutil.copy2(case / "manuscript.md", before)
        shutil.copy2(case / "manuscript.md", after)
        return before, after

    def copied_dependency_fixture(self, *names: str) -> Path:
        seed = self.temp_root / "dependency-seed"
        for name in names:
            dependency = seed / name
            dependency.mkdir(parents=True)
            (dependency / "SKILL.md").write_text(
                f"---\nname: {name}\n---\n", encoding="utf-8"
            )
        fixture = self.temp_root / "dependency-fixture"
        shutil.copytree(seed, fixture)
        return fixture

    def copied_project_fixture(self) -> Path:
        seed = self.temp_root / "project-seed"
        initialized = run_script(INIT, seed, "--entry-mode", "topic")
        self.assertEqual(0, initialized.returncode, initialized.stdout + initialized.stderr)
        project = self.temp_root / "project-case"
        shutil.copytree(seed, project)
        return project

    def write_passing_report(self, project: Path) -> tuple[Path, Path, Path]:
        baseline = project / "07-论文草稿" / "baseline.md"
        master = project / "07-论文草稿" / "manuscript.md"
        baseline.write_text("基线文本。\n", encoding="utf-8")
        master.write_text("审阅后的文本。\n", encoding="utf-8")
        baseline_hash = hashlib.sha256(baseline.read_bytes()).hexdigest()
        master_hash = hashlib.sha256(master.read_bytes()).hexdigest()
        report = project / "07-论文草稿" / "学术语言打磨报告.md"
        report.write_text(
            "---\n"
            "cyz_academic_humanization_report: true\n"
            'status: "passed"\n'
            'baseline_path: "07-论文草稿/baseline.md"\n'
            f'baseline_sha256: "{baseline_hash}"\n'
            'master_path: "07-论文草稿/manuscript.md"\n'
            f'reviewed_sha256: "{master_hash}"\n'
            f'export_sha256: "{master_hash}"\n'
            "---\n\n"
            "## 基本信息\n\n"
            "## 语义锁检查\n\n"
            "## 人工语义回归\n\n"
            "## 最终结论\n",
            encoding="utf-8",
        )
        replace_frontmatter_value(
            project / "00-项目状态.md", "academic_language_pass_status", "passed"
        )
        return baseline, master, report

    def test_dependency_lock_records_actual_roots_and_canonical_hashes(self):
        lock = json.loads(LOCK.read_text(encoding="utf-8"))

        self.assertEqual(1, lock["schemaVersion"])
        self.assertEqual(
            {"zh": "humanizer-zh", "en": "humanizer"}, lock["languageRouting"]
        )
        self.assertEqual(
            "relativePath<TAB>fileSha256<TAB>byteLength<LF>, sorted by relativePath; SHA-256 of UTF-8 bytes",
            lock["canonicalDirectoryHashAlgorithm"],
        )
        dependencies = {item["name"]: item for item in lock["dependencies"]}
        self.assertEqual({"humanizer-zh", "humanizer"}, set(dependencies))

        expected_metadata = {
            "humanizer-zh": {
                "version": None,
                "versionStatus": "unknown",
                "upstream": "https://github.com/syw2039/humanizer-zh.git",
                "sourceStatus": "declared-in-README",
                "license": "MIT",
                "licenseStatus": "declared-in-LICENSE",
            },
            "humanizer": {
                "version": "2.9.1",
                "versionStatus": "declared",
                "upstream": "https://github.com/blader/humanizer.git",
                "sourceStatus": "declared-in-README",
                "license": "MIT",
                "licenseStatus": "declared-in-SKILL-and-LICENSE",
            },
        }
        for name, expected in expected_metadata.items():
            dependency = dependencies[name]
            for key, value in expected.items():
                self.assertEqual(value, dependency[key], f"{name}.{key}")
            self.assertEqual(2, len(dependency["installations"]))
            self.assertEqual({"codex", "agents"}, {
                item["root"] for item in dependency["installations"]
            })
            for installation in dependency["installations"]:
                with self.subTest(name=name, root=installation["root"]):
                    path = Path(installation["path"])
                    self.assertTrue(path.is_dir(), path)
                    self.assertEqual(directory_metrics(path), {
                        "fileCount": installation["fileCount"],
                        "bytes": installation["bytes"],
                        "directorySha256": installation["directorySha256"],
                    })

    def test_h01_routes_chinese_and_english_only_to_their_declared_dependencies(self):
        before, after = self.copied_text_fixture()
        skills_root = self.copied_dependency_fixture(
            "humanizer-zh", "humanizer", "qu-ai-wei"
        )

        results = {}
        for language in ("zh", "en"):
            result = run_script(
                CHECK,
                before,
                after,
                "--language",
                language,
                "--skills-root",
                skills_root,
                "--json",
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            results[language] = json.loads(result.stdout)

        self.assertEqual("humanizer-zh", results["zh"]["dependency"]["name"])
        self.assertEqual("humanizer", results["en"]["dependency"]["name"])
        for language in ("zh", "en"):
            dependency = results[language]["dependency"]
            self.assertEqual(
                directory_metrics(Path(dependency["path"]).parent),
                {
                    "fileCount": dependency["fileCount"],
                    "bytes": dependency["bytes"],
                    "directorySha256": dependency["directorySha256"],
                },
            )
        self.assertNotEqual(
            results["zh"]["dependency"]["path"],
            results["en"]["dependency"]["path"],
        )
        self.assertNotIn("qu-ai-wei", json.dumps(results, ensure_ascii=False))

    def test_h03_missing_dependency_fails_clearly_without_qu_ai_wei_substitution(self):
        before, after = self.copied_text_fixture()
        skills_root = self.copied_dependency_fixture("qu-ai-wei")

        result = run_script(
            CHECK,
            before,
            after,
            "--language",
            "zh",
            "--skills-root",
            skills_root,
            "--json",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("required language dependency 'humanizer-zh'", result.stderr)
        self.assertIn("no fallback was used", result.stderr)
        self.assertNotIn('"name": "qu-ai-wei"', result.stdout)

    def test_h02_rejects_digit_unit_citation_and_negation_changes(self):
        cases = {
            "digit": ("120名", "121名", "numbers"),
            "unit": ("8周", "8天", "units"),
            "citation": ("[12]", "[13]", "numeric_citations"),
            "negation": ("未发现", "发现", "negations"),
        }
        for label, (old, new, expected_category) in cases.items():
            with self.subTest(change=label):
                case_root = self.temp_root / label
                case_root.mkdir()
                seed_before, seed_after = self.copied_text_fixture()
                before = case_root / "baseline.md"
                after = case_root / "output.md"
                shutil.copy2(seed_before, before)
                shutil.copy2(seed_after, after)
                after.write_text(
                    after.read_text(encoding="utf-8").replace(old, new),
                    encoding="utf-8",
                )

                result = run_script(CHECK, before, after, "--json")

                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual("fail", payload["status"])
                self.assertEqual(
                    "fail", payload["categories"][expected_category]["status"]
                )

    def test_h02_saved_manual_review_rejects_correlation_to_causation(self):
        before, after = self.copied_text_fixture()
        after.write_text(
            after.read_text(encoding="utf-8").replace("与成绩相关", "导致成绩提高"),
            encoding="utf-8",
        )
        manual_review = self.temp_root / "manual-review.json"
        manual_review.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "reviewType": "manual-semantic-regression",
                    "baselineSha256": hashlib.sha256(before.read_bytes()).hexdigest(),
                    "outputSha256": hashlib.sha256(after.read_bytes()).hexdigest(),
                    "issue": "correlation_to_causation",
                    "disposition": "rejected",
                    "reason": "相关性陈述被强化为因果结论，超出原文证据边界。",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        automated = run_script(CHECK, before, after, "--json")
        reviewed = run_script(
            CHECK, before, after, "--manual-review", manual_review, "--json"
        )

        self.assertEqual(0, automated.returncode, automated.stdout + automated.stderr)
        self.assertEqual("pass", json.loads(automated.stdout)["status"])
        self.assertEqual(1, reviewed.returncode, reviewed.stdout + reviewed.stderr)
        payload = json.loads(reviewed.stdout)
        self.assertEqual("pass", payload["automated_status"])
        self.assertEqual("fail", payload["status"])
        self.assertEqual("rejected", payload["manual_review"]["disposition"])
        self.assertEqual(
            "correlation_to_causation", payload["manual_review"]["issue"]
        )

    def test_h04_changed_master_invalidates_a_previously_passing_report(self):
        project = self.copied_project_fixture()
        _, master, _ = self.write_passing_report(project)
        valid = run_script(VALIDATE, project)
        self.assertEqual(0, valid.returncode, valid.stdout + valid.stderr)

        master.write_text("审阅后又被改动的文本。\n", encoding="utf-8")
        stale = run_script(VALIDATE, project)

        self.assertEqual(1, stale.returncode, stale.stdout + stale.stderr)
        self.assertIn(
            "language report master_path hash differs from current file", stale.stdout
        )

    def test_passing_report_keeps_baseline_master_and_report_separate(self):
        project = self.copied_project_fixture()
        baseline, _, report = self.write_passing_report(project)
        baseline_hash = hashlib.sha256(baseline.read_bytes()).hexdigest()
        text = report.read_text(encoding="utf-8")
        text = re.sub(
            r'(?m)^master_path:\s*.*$',
            'master_path: "07-论文草稿/baseline.md"',
            text,
        )
        text = re.sub(
            r'(?m)^reviewed_sha256:\s*.*$',
            f'reviewed_sha256: "{baseline_hash}"',
            text,
        )
        text = re.sub(
            r'(?m)^export_sha256:\s*.*$',
            f'export_sha256: "{baseline_hash}"',
            text,
        )
        report.write_text(text, encoding="utf-8")

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("baseline_path and master_path must be different", result.stdout)


if __name__ == "__main__":
    unittest.main()
