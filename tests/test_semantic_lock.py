import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath


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
            relative_path = path.relative_to(root)
            if "__pycache__" in relative_path.parts or relative_path.suffix in {
                ".pyc",
                ".pyo",
            }:
                continue
            data = path.read_bytes()
            entries.append(
                (
                    relative_path.as_posix(),
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


def serialized_path_is_absolute(value: str) -> bool:
    return PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()


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
        metadata = {
            "humanizer-zh": {
                "skill": "---\nname: humanizer-zh\nlicense: MIT\n---\n",
                "upstream": "https://github.com/syw2039/humanizer-zh.git",
            },
            "humanizer": {
                "skill": (
                    "---\nname: humanizer\nlicense: MIT\nmetadata:\n"
                    '  version: "2.9.1"\n---\n'
                ),
                "upstream": "https://github.com/blader/humanizer.git",
            },
            "qu-ai-wei": {
                "skill": "---\nname: qu-ai-wei\n---\n",
                "upstream": "https://example.invalid/qu-ai-wei.git",
            },
        }
        for name in names:
            dependency = seed / name
            dependency.mkdir(parents=True)
            (dependency / "SKILL.md").write_text(
                metadata[name]["skill"], encoding="utf-8"
            )
            (dependency / "README.md").write_text(
                f"Source: {metadata[name]['upstream']}\n", encoding="utf-8"
            )
            (dependency / "LICENSE").write_text("MIT License\n", encoding="utf-8")
            transient = dependency / "__pycache__"
            transient.mkdir()
            (transient / "ignored.pyc").write_bytes(b"transient")
        fixture = self.temp_root / "dependency-fixture"
        shutil.copytree(seed, fixture)
        return fixture

    def write_dependency_lock(self, skills_root: Path) -> Path:
        dependencies = []
        metadata = {
            "humanizer-zh": {
                "version": None,
                "versionStatus": "unknown",
                "versionEvidence": None,
                "upstream": "https://github.com/syw2039/humanizer-zh.git",
                "sourceStatus": "declared-in-README",
                "licenseStatus": "declared-in-LICENSE",
            },
            "humanizer": {
                "version": "2.9.1",
                "versionStatus": "declared",
                "versionEvidence": "SKILL.md metadata.version",
                "upstream": "https://github.com/blader/humanizer.git",
                "sourceStatus": "declared-in-README",
                "licenseStatus": "declared-in-SKILL-and-LICENSE",
            },
        }
        for name, item in metadata.items():
            path = skills_root / name
            metrics = (
                directory_metrics(path)
                if path.is_dir()
                else {"fileCount": 0, "bytes": 0, "directorySha256": "0" * 64}
            )
            dependencies.append(
                {
                    "name": name,
                    **item,
                    "license": "MIT",
                    "installations": [
                        {"root": "fixture", "path": str(path), **metrics}
                    ],
                    "rootsEqual": True,
                }
            )
        lock = self.temp_root / f"dependencies-{len(list(self.temp_root.glob('dependencies-*.lock.json')))}.lock.json"
        lock.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "languageRouting": {"zh": "humanizer-zh", "en": "humanizer"},
                    "canonicalDirectoryHashAlgorithm": (
                        "relativePath<TAB>fileSha256<TAB>byteLength<LF>, sorted by "
                        "relativePath, excluding __pycache__, *.pyc, and *.pyo; "
                        "SHA-256 of UTF-8 bytes"
                    ),
                    "dependencies": dependencies,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return lock

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

    def test_dependency_lock_records_portable_routes_and_host_evidence(self):
        lock = json.loads(LOCK.read_text(encoding="utf-8"))

        self.assertEqual(1, lock["schemaVersion"])
        self.assertEqual(
            {"zh": "humanizer-zh", "en": "humanizer"}, lock["languageRouting"]
        )
        self.assertEqual(
            "relativePath<TAB>fileSha256<TAB>byteLength<LF>, sorted by relativePath, excluding __pycache__, *.pyc, and *.pyo; SHA-256 of UTF-8 bytes",
            lock["canonicalDirectoryHashAlgorithm"],
        )
        dependencies = {item["name"]: item for item in lock["dependencies"]}
        self.assertEqual({"humanizer-zh", "humanizer", "mineru"}, set(dependencies))
        self.assertNotIn("mineru", lock["languageRouting"].values())

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
            "mineru": {
                "version": "4.0.0-desk-local",
                "versionStatus": "declared",
                "upstream": None,
                "sourceStatus": "unknown-local-wrapper",
                "license": None,
                "licenseStatus": "unknown-no-LICENSE-or-NOTICE",
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
                self.assertRegex(installation["directorySha256"], r"^[0-9a-f]{64}$")
                self.assertTrue(serialized_path_is_absolute(installation["path"]))

    def test_serialized_absolute_paths_are_validated_independently_of_host_os(self):
        self.assertTrue(serialized_path_is_absolute(r"C:\Users\W\.codex\skills"))
        self.assertTrue(serialized_path_is_absolute(r"\\server\share\skills"))
        self.assertTrue(serialized_path_is_absolute("/opt/agent/skills"))
        self.assertFalse(serialized_path_is_absolute("relative/skills"))
        self.assertFalse(serialized_path_is_absolute(r"C:relative\skills"))

    def test_available_host_installations_match_canonical_hashes(self):
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        checked = 0
        for dependency in lock["dependencies"]:
            for installation in dependency["installations"]:
                with self.subTest(
                    name=dependency["name"], root=installation["root"]
                ):
                    path = Path(installation["path"])
                    if not path.is_dir():
                        continue
                    checked += 1
                    self.assertEqual(directory_metrics(path), {
                        "fileCount": installation["fileCount"],
                        "bytes": installation["bytes"],
                        "directorySha256": installation["directorySha256"],
                    })
        if checked == 0:
            self.skipTest("recorded host dependency installations are unavailable")

    def test_h01_routes_chinese_and_english_only_to_their_declared_dependencies(self):
        before, after = self.copied_text_fixture()
        skills_root = self.copied_dependency_fixture(
            "humanizer-zh", "humanizer", "qu-ai-wei"
        )
        dependency_lock = self.write_dependency_lock(skills_root)
        for name in ("humanizer-zh", "humanizer"):
            (skills_root / name / "__pycache__" / "ignored.pyc").write_bytes(
                b"changed transient cache"
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
                "--dependency-lock",
                dependency_lock,
                "--json",
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            results[language] = json.loads(result.stdout)

        self.assertEqual("humanizer-zh", results["zh"]["dependency"]["name"])
        self.assertEqual("humanizer", results["en"]["dependency"]["name"])
        self.assertIsNone(results["zh"]["dependency"]["version"])
        self.assertEqual("unknown", results["zh"]["dependency"]["versionStatus"])
        self.assertEqual("2.9.1", results["en"]["dependency"]["version"])
        self.assertEqual(
            "https://github.com/blader/humanizer.git",
            results["en"]["dependency"]["upstream"],
        )
        self.assertEqual("MIT", results["en"]["dependency"]["license"])
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
        dependency_lock = self.write_dependency_lock(skills_root)

        result = run_script(
            CHECK,
            before,
            after,
            "--language",
            "zh",
            "--skills-root",
            skills_root,
            "--dependency-lock",
            dependency_lock,
            "--json",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("required language dependency 'humanizer-zh'", result.stderr)
        self.assertIn("no fallback was used", result.stderr)
        self.assertNotIn('"name": "qu-ai-wei"', result.stdout)

    def test_dependency_resolution_accepts_matching_copy_but_rejects_missing_lock_and_wrong_hash(self):
        before, after = self.copied_text_fixture()
        approved_root = self.copied_dependency_fixture("humanizer-zh", "humanizer")
        dependency_lock = self.write_dependency_lock(approved_root)

        missing_lock = run_script(
            CHECK,
            before,
            after,
            "--language",
            "zh",
            "--skills-root",
            approved_root,
            "--dependency-lock",
            self.temp_root / "missing.lock.json",
            "--json",
        )
        self.assertEqual(2, missing_lock.returncode)
        self.assertIn("dependency lock does not exist", missing_lock.stderr)

        unapproved_root = self.temp_root / "unapproved-root"
        shutil.copytree(approved_root, unapproved_root)
        alternate_path = run_script(
            CHECK,
            before,
            after,
            "--language",
            "zh",
            "--skills-root",
            unapproved_root,
            "--dependency-lock",
            dependency_lock,
            "--json",
        )
        self.assertEqual(
            0, alternate_path.returncode, alternate_path.stdout + alternate_path.stderr
        )
        alternate_payload = json.loads(alternate_path.stdout)
        self.assertEqual("humanizer-zh", alternate_payload["dependency"]["name"])
        self.assertEqual(
            str(unapproved_root / "humanizer-zh" / "SKILL.md"),
            alternate_payload["dependency"]["path"],
        )

        (approved_root / "humanizer-zh" / "SKILL.md").write_text(
            "---\nname: humanizer-zh\nlicense: MIT\n---\n# tampered\n",
            encoding="utf-8",
        )
        tampered = run_script(
            CHECK,
            before,
            after,
            "--language",
            "zh",
            "--skills-root",
            approved_root,
            "--dependency-lock",
            dependency_lock,
            "--json",
        )
        self.assertEqual(2, tampered.returncode)
        self.assertIn("directory hash mismatch", tampered.stderr)
        self.assertIn("no fallback was used", tampered.stderr)

    def test_dependency_resolution_rejects_wrong_locked_source_even_with_matching_hash(self):
        before, after = self.copied_text_fixture()
        skills_root = self.copied_dependency_fixture("humanizer-zh", "humanizer")
        (skills_root / "humanizer-zh" / "README.md").write_text(
            "Source: https://example.invalid/wrong.git\n", encoding="utf-8"
        )
        dependency_lock = self.write_dependency_lock(skills_root)

        result = run_script(
            CHECK,
            before,
            after,
            "--language",
            "zh",
            "--skills-root",
            skills_root,
            "--dependency-lock",
            dependency_lock,
            "--json",
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("upstream source does not match the dependency lock", result.stderr)
        self.assertIn("no fallback was used", result.stderr)

    def test_dependency_resolution_rejects_wrong_version_and_license_evidence(self):
        before, after = self.copied_text_fixture()
        skills_root = self.copied_dependency_fixture("humanizer-zh", "humanizer")
        skill = skills_root / "humanizer" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace('version: "2.9.1"', 'version: "9.9.9"'),
            encoding="utf-8",
        )
        version_lock = self.write_dependency_lock(skills_root)

        wrong_version = run_script(
            CHECK,
            before,
            after,
            "--language",
            "en",
            "--skills-root",
            skills_root,
            "--dependency-lock",
            version_lock,
            "--json",
        )
        self.assertEqual(2, wrong_version.returncode)
        self.assertIn("declared version does not match", wrong_version.stderr)

        skill.write_text(
            "---\nname: humanizer\nlicense: Apache-2.0\nmetadata:\n"
            '  version: "2.9.1"\n---\n',
            encoding="utf-8",
        )
        license_lock = self.write_dependency_lock(skills_root)
        wrong_license = run_script(
            CHECK,
            before,
            after,
            "--language",
            "en",
            "--skills-root",
            skills_root,
            "--dependency-lock",
            license_lock,
            "--json",
        )
        self.assertEqual(2, wrong_license.returncode)
        self.assertIn("SKILL.md license does not match", wrong_license.stderr)

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

    def test_h02_correlation_to_causation_cannot_be_accepted_by_manual_record(self):
        before, after = self.copied_text_fixture()
        after.write_text(
            after.read_text(encoding="utf-8").replace("与成绩相关", "导致成绩提高"),
            encoding="utf-8",
        )
        manual_review = self.temp_root / "invalid-acceptance.json"
        manual_review.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "reviewType": "manual-semantic-regression",
                    "baselineSha256": hashlib.sha256(before.read_bytes()).hexdigest(),
                    "outputSha256": hashlib.sha256(after.read_bytes()).hexdigest(),
                    "issue": "correlation_to_causation",
                    "disposition": "accepted",
                    "reason": "错误地接受因果强化。",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = run_script(
            CHECK, before, after, "--manual-review", manual_review, "--json"
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("correlation_to_causation must be rejected", result.stderr)

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
