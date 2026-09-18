import hashlib
import importlib.util
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "skills" / "cyz-edu-research" / "scripts" / "init_project.py"
VALIDATE = ROOT / "skills" / "cyz-edu-research" / "scripts" / "validate_project.py"
MIGRATE = ROOT / "skills" / "cyz-edu-research" / "scripts" / "migrate_project.py"
LEGACY_FIXTURE = ROOT / "tests" / "fixtures" / "legacy-project"


def run_script(script: Path, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(script), str(project), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=env,
    )


def read_state(project: Path) -> dict[str, str]:
    text = (project / "00-项目状态.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    state = {}
    for line in frontmatter.splitlines():
        match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if match:
            state[match.group(1)] = match.group(2).strip().strip('"\'')
    return state


def replace_state_value(project: Path, key: str, value: str) -> None:
    path = project / "00-项目状态.md"
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        rf"(?m)^{re.escape(key)}:\s*.*$", f'{key}: "{value}"', text
    )
    if count != 1:
        raise AssertionError(f"expected one {key} field, found {count}")
    path.write_text(updated, encoding="utf-8")


def append_idea_record(project: Path, record: str) -> None:
    path = project / "01-研究起点与问题.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("<!-- cyz:idea-canvas:end -->", record + "\n<!-- cyz:idea-canvas:end -->")
    path.write_text(text, encoding="utf-8")


class ProjectLifecycleTests(unittest.TestCase):
    def init_project(self, entry_mode: str) -> tuple[tempfile.TemporaryDirectory[str], Path, subprocess.CompletedProcess[str]]:
        temporary = tempfile.TemporaryDirectory()
        project = Path(temporary.name) / "project"
        result = run_script(INIT, project, "--entry-mode", entry_mode)
        return temporary, project, result

    def test_new_topic_project_has_schema2_idea_workspace(self):
        temporary, project, result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)

        self.assertEqual(0, result.returncode, result.stderr)
        state = read_state(project)
        self.assertEqual("2", state["workflow_schema"])
        self.assertEqual("refinement", state["idea_mode"])
        self.assertEqual("tentative_topic", state["idea_maturity"])
        self.assertEqual("refining", state["idea_status"])
        self.assertEqual("", state["current_decision"])
        self.assertEqual("", state["current_evidence"])
        self.assertEqual("01-研究起点与问题.md#交接区", state["handoff_path"])
        text = (project / "01-研究起点与问题.md").read_text(encoding="utf-8")
        self.assertEqual(1, text.count("<!-- cyz:idea-canvas:start -->"))
        self.assertEqual(1, text.count("<!-- cyz:idea-canvas:end -->"))
        self.assertNotIn("{{", text)

    def test_idea_workspace_provides_structured_record_templates(self):
        temporary, project, result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, result.returncode, result.stderr)
        text = (project / "01-研究起点与问题.md").read_text(encoding="utf-8")

        required_fields = {
            "candidate_id:",
            "topic_id:",
            "decision_id:",
            "evidence_id:",
            "handoff_id:",
            "idea_revision:",
            "scope:",
            "alternatives:",
            "evidence_locators:",
            "source_locator:",
            "claim_limits:",
            "decision_id_ref:",
            "evidence_ids:",
            "next_stage:",
            "required_actions:",
        }
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, text)
        for marker in (
            "cyz:candidate-template:start",
            "cyz:current-topic-template:start",
            "cyz:decision-template:start",
            "cyz:evidence-template:start",
            "cyz:handoff-template:start",
        ):
            with self.subTest(marker=marker):
                self.assertEqual(1, text.count(marker))

    def test_new_discovery_project_has_exploration_defaults(self):
        temporary, project, result = self.init_project("discovery")
        self.addCleanup(temporary.cleanup)

        self.assertEqual(0, result.returncode, result.stderr)
        state = read_state(project)
        self.assertEqual("2", state["workflow_schema"])
        self.assertEqual("discovery", state["idea_mode"])
        self.assertEqual("broad_interest", state["idea_maturity"])
        self.assertEqual("exploring", state["idea_status"])

    def test_materials_entry_records_pending_classification_instead_of_guessing(self):
        temporary, project, result = self.init_project("materials")
        self.addCleanup(temporary.cleanup)

        self.assertEqual(0, result.returncode, result.stderr)
        state = read_state(project)
        self.assertEqual("2", state["workflow_schema"])
        self.assertEqual("discovery", state["idea_mode"])
        self.assertEqual("broad_interest", state["idea_maturity"])
        self.assertEqual("not_started", state["idea_status"])
        text = (project / "01-研究起点与问题.md").read_text(encoding="utf-8")
        self.assertIn("待核对（不预判已有/可获取/需新增）", text)

    def test_allow_existing_never_overwrites_idea_workspace(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name) / "project"
        project.mkdir()
        idea_path = project / "01-研究起点与问题.md"
        original = b"# user-authored\r\n\r\nkeep exactly\r\n"
        idea_path.write_bytes(original)

        result = run_script(INIT, project, "--entry-mode", "topic", "--allow-existing")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(original, idea_path.read_bytes())
        self.assertIn("SKIPPED 01-研究起点与问题.md", result.stdout)

    def test_schema2_project_validates_structurally_without_claiming_academic_value(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)

        result = run_script(VALIDATE, project)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("仅完成结构校验", result.stdout)
        self.assertNotIn("学术价值已证明", result.stdout)
        self.assertNotIn("academic value proven", result.stdout.lower())

    def test_schema2_rejects_values_outside_task2_enums(self):
        cases = {
            "entry_mode": "other",
            "idea_mode": "brainstorm",
            "idea_maturity": "complete",
            "idea_status": "approved",
            "gate_status": "done",
        }
        for key, invalid in cases.items():
            with self.subTest(key=key):
                temporary, project, init_result = self.init_project("topic")
                self.addCleanup(temporary.cleanup)
                self.assertEqual(0, init_result.returncode, init_result.stderr)
                replace_state_value(project, key, invalid)

                result = run_script(VALIDATE, project)

                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertIn(f"invalid {key}", result.stdout)

    def test_duplicate_idea_canvas_markers_are_an_error(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        path = project / "01-研究起点与问题.md"
        path.write_text(
            path.read_text(encoding="utf-8") + "\n<!-- cyz:idea-canvas:start -->\n",
            encoding="utf-8",
        )

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("idea-canvas markers must occur exactly once", result.stdout)

    def test_ready_requires_current_decision_and_evidence(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        replace_state_value(project, "idea_status", "ready")

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("ready idea lacks current_decision", result.stdout)
        self.assertIn("ready idea lacks current_evidence", result.stdout)

    def test_ready_rejects_stale_decision_and_unstructured_evidence_reference(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        replace_state_value(project, "idea_revision", "2")
        replace_state_value(project, "idea_status", "ready")
        replace_state_value(project, "current_decision", "D-old")
        replace_state_value(project, "current_evidence", "03-文献证据矩阵.md")
        append_idea_record(
            project,
            """<!-- cyz:decision-record:start -->
- decision_id: D-old
- idea_revision: 1
- question: old question
- answer: old answer
- source: user_statement
- decided_at: 2026-09-19
- affects: topic
<!-- cyz:decision-record:end -->""",
        )

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            "current_decision does not reference a decision record for idea_revision 2",
            result.stdout,
        )
        self.assertIn(
            "current_evidence does not reference an evidence record for idea_revision 2",
            result.stdout,
        )

    def test_ready_accepts_current_revision_decision_and_evidence_record(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        replace_state_value(project, "idea_revision", "2")
        replace_state_value(project, "idea_status", "ready")
        replace_state_value(project, "current_decision", "D-002")
        replace_state_value(project, "current_evidence", "E-002")
        search_log = project / "02-文献" / "00-检索记录.md"
        search_log.write_text(
            search_log.read_text(encoding="utf-8") + "\n## evidence-e-002\n\nRecorded locator.\n",
            encoding="utf-8",
        )
        append_idea_record(
            project,
            """<!-- cyz:decision-record:start -->
- decision_id: D-002
- idea_revision: 2
- question: Which topic?
- answer: Topic A
- source: user_statement
- decided_at: 2026-09-19
- affects: current_topic
<!-- cyz:decision-record:end -->
<!-- cyz:evidence-record:start -->
- evidence_id: E-002
- idea_revision: 2
- claim_id: C-002
- source_type: literature_record
- source_locator: 02-文献/00-检索记录.md#evidence-e-002
- access_level: metadata
- verification_status: pending_verification
- recorded_at: 2026-09-19
<!-- cyz:evidence-record:end -->""",
        )

        result = run_script(VALIDATE, project)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_ready_rejects_evidence_record_pointing_only_to_untouched_template_file(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        replace_state_value(project, "idea_status", "ready")
        replace_state_value(project, "current_decision", "D-001")
        replace_state_value(project, "current_evidence", "E-001")
        append_idea_record(
            project,
            """<!-- cyz:decision-record:start -->
- decision_id: D-001
- idea_revision: 1
- question: Which topic?
- answer: Topic A
- source: user_statement
- decided_at: 2026-09-19
- affects: current_topic
<!-- cyz:decision-record:end -->
<!-- cyz:evidence-record:start -->
- evidence_id: E-001
- idea_revision: 1
- claim_id: C-001
- source_type: literature_record
- source_locator: 03-文献证据矩阵.md
- access_level: metadata
- verification_status: pending_verification
- recorded_at: 2026-09-19
<!-- cyz:evidence-record:end -->""",
        )

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            "current_evidence does not reference an evidence record for idea_revision 1",
            result.stdout,
        )

    def test_nonexistent_handoff_links_are_an_error(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        replace_state_value(project, "handoff_path", "missing/handoff.md")

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("handoff_path does not exist", result.stdout)

    def test_nonexistent_local_link_inside_handoff_section_is_an_error(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        path = project / "01-研究起点与问题.md"
        text = path.read_text(encoding="utf-8").replace(
            "<!-- cyz:handoff-template:end -->",
            "- missing_link: [不存在的交接记录](handoff/missing.md)\n"
            "<!-- cyz:handoff-template:end -->",
        )
        path.write_text(text, encoding="utf-8")

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("handoff link does not exist", result.stdout)

    def test_legacy_project_without_schema_warns_instead_of_failing(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        path = project / "00-项目状态.md"
        text = path.read_text(encoding="utf-8")
        legacy_keys = {
            "workflow_schema",
            "idea_mode",
            "idea_maturity",
            "idea_status",
            "idea_revision",
            "idea_workspace",
            "current_decision",
            "current_evidence",
            "handoff_path",
        }
        text = "\n".join(
            line
            for line in text.splitlines()
            if not any(line.startswith(f"{key}:") for key in legacy_keys)
        ) + "\n"
        path.write_text(text, encoding="utf-8")

        result = run_script(VALIDATE, project)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("legacy project lacks workflow_schema", result.stdout)

    def test_schema2_missing_required_field_is_an_error(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        path = project / "00-项目状态.md"
        text = re.sub(r"(?m)^idea_revision:.*\n", "", path.read_text(encoding="utf-8"))
        path.write_text(text, encoding="utf-8")

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("schema 2 lacks required field: idea_revision", result.stdout)

    def test_required_frontmatter_key_in_body_does_not_count(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        path = project / "00-项目状态.md"
        text = path.read_text(encoding="utf-8")
        frontmatter, body = text.split("---", 2)[1:]
        frontmatter = re.sub(r"(?m)^idea_revision:.*\n", "", frontmatter)
        path.write_text(f"---{frontmatter}---{body}\nidea_revision: 1\n", encoding="utf-8")

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("schema 2 lacks required field: idea_revision", result.stdout)

    def test_duplicate_frontmatter_key_is_an_error_even_when_later_value_is_invalid(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        path = project / "00-项目状态.md"
        text = path.read_text(encoding="utf-8")
        first, frontmatter, body = text.split("---", 2)
        frontmatter += 'idea_status: "approved"\n'
        path.write_text(f"{first}---{frontmatter}---{body}", encoding="utf-8")

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("duplicate frontmatter key: idea_status", result.stdout)
        self.assertIn("invalid idea_status: 'approved'", result.stdout)

    def test_frontmatter_rejects_malformed_line_and_spaced_duplicate_key(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        path = project / "00-项目状态.md"
        first, frontmatter, body = path.read_text(encoding="utf-8").split("---", 2)
        frontmatter += 'this is not a field\nidea_status : "approved"\n'
        path.write_text(f"{first}---{frontmatter}---{body}", encoding="utf-8")

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("malformed frontmatter line: this is not a field", result.stdout)
        self.assertIn("duplicate frontmatter key: idea_status", result.stdout)
        self.assertIn("invalid idea_status: 'approved'", result.stdout)

    def test_ready_rejects_duplicate_fields_in_managed_decision_record(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        replace_state_value(project, "idea_revision", "2")
        replace_state_value(project, "idea_status", "ready")
        replace_state_value(project, "current_decision", "D-002")
        replace_state_value(project, "current_evidence", "E-002")
        search_log = project / "02-文献" / "00-检索记录.md"
        search_log.write_text(
            search_log.read_text(encoding="utf-8") + "\n## evidence-e-002\n",
            encoding="utf-8",
        )
        append_idea_record(
            project,
            """<!-- cyz:decision-record:start -->
- decision_id: D-002
- idea_revision: 1
- idea_revision: 2
- question: Which topic?
- answer: Topic A
- source: user_statement
- decided_at: 2026-09-19
- affects: current_topic
<!-- cyz:decision-record:end -->
<!-- cyz:evidence-record:start -->
- evidence_id: E-002
- idea_revision: 2
- claim_id: C-002
- source_type: literature_record
- source_locator: 02-文献/00-检索记录.md#evidence-e-002
- access_level: metadata
- verification_status: pending_verification
- recorded_at: 2026-09-19
<!-- cyz:evidence-record:end -->""",
        )

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("duplicate decision record field: idea_revision", result.stdout)
        self.assertIn(
            "current_decision does not reference a decision record for idea_revision 2",
            result.stdout,
        )

    def test_ready_rejects_remote_evidence_locator_with_invalid_port(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        replace_state_value(project, "idea_status", "ready")
        replace_state_value(project, "current_decision", "D-001")
        replace_state_value(project, "current_evidence", "E-001")
        append_idea_record(
            project,
            """<!-- cyz:decision-record:start -->
- decision_id: D-001
- idea_revision: 1
- question: Which topic?
- answer: Topic A
- source: user_statement
- decided_at: 2026-09-19
- affects: current_topic
<!-- cyz:decision-record:end -->
<!-- cyz:evidence-record:start -->
- evidence_id: E-001
- idea_revision: 1
- claim_id: C-001
- source_type: web
- source_locator: https://example.com:abc/source
- access_level: full_text
- verification_status: verified
- recorded_at: 2026-09-19
<!-- cyz:evidence-record:end -->""",
        )

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            "current_evidence does not reference an evidence record for idea_revision 1",
            result.stdout,
        )

    def test_ready_accepts_legitimate_question_containing_dai_character(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        replace_state_value(project, "idea_status", "ready")
        replace_state_value(project, "current_decision", "D-001")
        replace_state_value(project, "current_evidence", "E-001")
        search_log = project / "02-文献" / "00-检索记录.md"
        search_log.write_text(
            search_log.read_text(encoding="utf-8") + "\n## evidence-e-001\n",
            encoding="utf-8",
        )
        append_idea_record(
            project,
            """<!-- cyz:decision-record:start -->
- decision_id: D-001
- idea_revision: 1
- question: 教师如何对待生成式 AI？
- answer: Preserve uncertainty
- source: user_statement
- decided_at: 2026-09-19
- affects: current_topic
<!-- cyz:decision-record:end -->
<!-- cyz:evidence-record:start -->
- evidence_id: E-001
- idea_revision: 1
- claim_id: C-001
- source_type: literature_record
- source_locator: 02-文献/00-检索记录.md#evidence-e-001
- access_level: metadata
- verification_status: pending_verification
- recorded_at: 2026-09-19
<!-- cyz:evidence-record:end -->""",
        )

        result = run_script(VALIDATE, project)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_utf8_bom_is_accepted_on_status_and_idea_workspace(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        for relative in ("00-项目状态.md", "01-研究起点与问题.md"):
            path = project / relative
            path.write_text("\ufeff" + path.read_text(encoding="utf-8"), encoding="utf-8")

        result = run_script(VALIDATE, project)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_ready_ignores_records_outside_idea_canvas(self):
        temporary, project, init_result = self.init_project("topic")
        self.addCleanup(temporary.cleanup)
        self.assertEqual(0, init_result.returncode, init_result.stderr)
        replace_state_value(project, "idea_status", "ready")
        replace_state_value(project, "current_decision", "D-outside")
        replace_state_value(project, "current_evidence", "E-outside")
        search_log = project / "02-文献" / "00-检索记录.md"
        search_log.write_text(
            search_log.read_text(encoding="utf-8") + "\n## evidence-outside\n",
            encoding="utf-8",
        )
        idea_path = project / "01-研究起点与问题.md"
        idea_path.write_text(
            idea_path.read_text(encoding="utf-8")
            + """
<!-- cyz:decision-record:start -->
- decision_id: D-outside
- idea_revision: 1
- question: Outside marker?
- answer: Must not count
- source: user_statement
- decided_at: 2026-09-19
- affects: current_topic
<!-- cyz:decision-record:end -->
<!-- cyz:evidence-record:start -->
- evidence_id: E-outside
- idea_revision: 1
- claim_id: C-outside
- source_type: literature_record
- source_locator: 02-文献/00-检索记录.md#evidence-outside
- access_level: metadata
- verification_status: pending_verification
- recorded_at: 2026-09-19
<!-- cyz:evidence-record:end -->
""",
            encoding="utf-8",
        )

        result = run_script(VALIDATE, project)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            "current_decision does not reference a decision record for idea_revision 1",
            result.stdout,
        )
        self.assertIn(
            "current_evidence does not reference an evidence record for idea_revision 1",
            result.stdout,
        )


class MigrationTests(unittest.TestCase):
    managed_files = ("00-项目状态.md", "01-研究起点与问题.md")

    def make_legacy_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        project = Path(temporary.name) / "project"
        initialized = run_script(INIT, project, "--entry-mode", "topic")
        self.assertEqual(0, initialized.returncode, initialized.stderr)
        for relative in self.managed_files:
            shutil.copyfile(LEGACY_FIXTURE / relative, project / relative)
        return temporary, project

    @staticmethod
    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def project_snapshot(project: Path) -> dict[str, bytes]:
        return {
            path.relative_to(project).as_posix(): path.read_bytes()
            for path in sorted(project.rglob("*"))
            if path.is_file()
        }

    @staticmethod
    def manifests(project: Path) -> list[Path]:
        return sorted((project / ".cyz-migrations").glob("*/manifest.json"))

    def test_check_reports_migratable_compatible_and_duplicate_markers(self):
        temporary, legacy = self.make_legacy_project()
        self.addCleanup(temporary.cleanup)

        migratable = run_script(MIGRATE, legacy, "--check")

        self.assertEqual(3, migratable.returncode, migratable.stdout + migratable.stderr)
        self.assertIn("MIGRATABLE", migratable.stdout)

        compatible_temp = tempfile.TemporaryDirectory()
        self.addCleanup(compatible_temp.cleanup)
        compatible = Path(compatible_temp.name) / "project"
        initialized = run_script(INIT, compatible, "--entry-mode", "topic")
        self.assertEqual(0, initialized.returncode, initialized.stderr)

        checked = run_script(MIGRATE, compatible, "--check")

        self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)
        self.assertIn("COMPATIBLE", checked.stdout)

        idea_path = legacy / "01-研究起点与问题.md"
        idea_path.write_bytes(
            idea_path.read_bytes()
            + b"\n<!-- cyz:idea-canvas:start -->\n"
            + b"<!-- cyz:idea-canvas:start -->\n"
        )

        malformed = run_script(MIGRATE, legacy, "--check")

        self.assertEqual(2, malformed.returncode, malformed.stdout + malformed.stderr)
        self.assertIn("managed markers", malformed.stderr)

    def test_check_rejects_schema2_project_missing_required_field(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name) / "project"
        initialized = run_script(INIT, project, "--entry-mode", "topic")
        self.assertEqual(0, initialized.returncode, initialized.stderr)
        state_path = project / "00-项目状态.md"
        state_path.write_text(
            re.sub(
                r"(?m)^idea_revision:.*\n",
                "",
                state_path.read_text(encoding="utf-8"),
            ),
            encoding="utf-8",
        )

        checked = run_script(MIGRATE, project, "--check")

        self.assertEqual(2, checked.returncode, checked.stdout + checked.stderr)
        self.assertNotIn("COMPATIBLE", checked.stdout)
        self.assertIn("idea_revision", checked.stderr)

    def test_apply_preserves_legacy_bytes_and_records_hashes_and_backups(self):
        temporary, project = self.make_legacy_project()
        self.addCleanup(temporary.cleanup)
        before = {
            relative: (project / relative).read_bytes()
            for relative in self.managed_files
        }

        result = run_script(MIGRATE, project, "--apply")

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        state = read_state(project)
        self.assertEqual("2", state["workflow_schema"])
        migrated_idea = (project / "01-研究起点与问题.md").read_bytes()
        self.assertIn(b"<!-- cyz:legacy-record:start -->", migrated_idea)
        self.assertIn(before["01-研究起点与问题.md"], migrated_idea)
        self.assertIn(b"<!-- cyz:legacy-record:end -->", migrated_idea)

        manifests = self.manifests(project)
        self.assertEqual(1, len(manifests))
        manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        self.assertEqual("complete", manifest["phase"])
        self.assertEqual("schema-2", manifest["target"])
        self.assertEqual(list(self.managed_files), [item["path"] for item in manifest["files"]])
        for item in manifest["files"]:
            relative = item["path"]
            self.assertEqual(self.sha256(before[relative]), item["before_sha256"])
            self.assertEqual(
                self.sha256((project / relative).read_bytes()),
                item["after_sha256"],
            )
            backup = manifests[0].parent / item["backup_path"]
            self.assertEqual(before[relative], backup.read_bytes())

        validated = run_script(VALIDATE, project)
        self.assertEqual(0, validated.returncode, validated.stdout + validated.stderr)

    def test_second_apply_is_byte_identical_and_creates_no_manifest(self):
        temporary, project = self.make_legacy_project()
        self.addCleanup(temporary.cleanup)
        first = run_script(MIGRATE, project, "--apply")
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        after_first = self.project_snapshot(project)

        second = run_script(MIGRATE, project, "--apply")

        self.assertEqual(0, second.returncode, second.stdout + second.stderr)
        self.assertEqual(after_first, self.project_snapshot(project))
        self.assertEqual(1, len(self.manifests(project)))

    def test_injected_failures_restore_originals_without_deleting_user_files(self):
        for fault in ("before-backup", "after-backup", "before-replace"):
            with self.subTest(fault=fault):
                temporary, project = self.make_legacy_project()
                self.addCleanup(temporary.cleanup)
                user_file = project / "user-created-during-project.md"
                user_file.write_bytes(b"owned by user\r\n")
                before = {
                    relative: (project / relative).read_bytes()
                    for relative in self.managed_files
                }

                result = run_script(
                    MIGRATE,
                    project,
                    "--apply",
                    "--simulate-failure",
                    fault,
                )

                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                for relative, original in before.items():
                    self.assertEqual(original, (project / relative).read_bytes())
                self.assertEqual(b"owned by user\r\n", user_file.read_bytes())
                self.assertNotIn("workflow_schema", read_state(project))
                manifests = self.manifests(project)
                self.assertEqual(1, len(manifests))
                manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
                self.assertEqual("failed", manifest["phase"])
                self.assertEqual(fault, manifest["failure"]["point"])
                self.assertEqual([], manifest["changed_paths"])

    def test_failure_after_first_replace_restores_changed_file_only(self):
        temporary, project = self.make_legacy_project()
        self.addCleanup(temporary.cleanup)
        user_file = project / "user-created-during-project.md"
        user_file.write_bytes(b"owned by user\r\n")
        before = {
            relative: (project / relative).read_bytes()
            for relative in self.managed_files
        }

        result = run_script(
            MIGRATE,
            project,
            "--apply",
            "--simulate-failure",
            "after-first-replace",
        )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        for relative, original in before.items():
            self.assertEqual(original, (project / relative).read_bytes())
        self.assertEqual(b"owned by user\r\n", user_file.read_bytes())
        self.assertNotIn("workflow_schema", read_state(project))
        manifest_path = self.manifests(project)[0]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("failed", manifest["phase"])
        self.assertEqual("after-first-replace", manifest["failure"]["point"])
        self.assertEqual([self.managed_files[0]], manifest["changed_paths"])
        self.assertEqual([self.managed_files[0]], manifest["restored_paths"])
        self.assertEqual([], manifest["restore_failures"])

    def test_user_edit_between_replaces_is_preserved_as_structural_conflict(self):
        temporary, project = self.make_legacy_project()
        self.addCleanup(temporary.cleanup)
        user_file = project / "user-created-during-project.md"
        user_file.write_bytes(b"owned by user\r\n")
        before = {
            relative: (project / relative).read_bytes()
            for relative in self.managed_files
        }
        simulated_edit = b"\n<!-- cyz:test-hook:user-edit -->\n"

        result = run_script(
            MIGRATE,
            project,
            "--apply",
            "--simulate-failure",
            "user-edit-before-second-replace",
        )

        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertEqual(before[self.managed_files[0]], (project / self.managed_files[0]).read_bytes())
        self.assertEqual(
            before[self.managed_files[1]] + simulated_edit,
            (project / self.managed_files[1]).read_bytes(),
        )
        self.assertEqual(b"owned by user\r\n", user_file.read_bytes())
        self.assertNotIn("workflow_schema", read_state(project))
        manifest = json.loads(self.manifests(project)[0].read_text(encoding="utf-8"))
        self.assertEqual("structural_conflict", manifest["failure"]["kind"])
        self.assertEqual([self.managed_files[0]], manifest["restored_paths"])
        self.assertEqual([], manifest["restore_failures"])

    def test_restore_attempts_every_changed_path_and_reports_each_failure(self):
        spec = importlib.util.spec_from_file_location("cyz_migrate_project", MIGRATE)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name)
        originals = {
            relative: f"original:{relative}".encode("utf-8")
            for relative in self.managed_files
        }
        for relative in self.managed_files:
            (project / relative).write_bytes(f"candidate:{relative}".encode("utf-8"))
        real_write_temp = module.write_temp

        def fail_one_restore(path: Path, data: bytes) -> Path:
            if path.name == self.managed_files[1]:
                raise OSError("injected restore failure")
            return real_write_temp(path, data)

        with mock.patch.object(module, "write_temp", side_effect=fail_one_restore):
            restored, failures = module.restore_changed(
                project,
                originals,
                list(self.managed_files),
            )

        self.assertEqual([self.managed_files[0]], restored)
        self.assertEqual(self.managed_files[1], failures[0]["path"])
        self.assertIn("injected restore failure", failures[0]["error"])
        self.assertEqual(originals[self.managed_files[0]], (project / self.managed_files[0]).read_bytes())
        self.assertNotEqual(originals[self.managed_files[1]], (project / self.managed_files[1]).read_bytes())


if __name__ == "__main__":
    unittest.main()
