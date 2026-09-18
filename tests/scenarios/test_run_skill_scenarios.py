import unittest
import ast
import json
import re
import tempfile
from pathlib import Path

from tests.scenarios.run_skill_scenarios import (
    check_documentation_contract,
    compute_skill_provenance,
    load_scenarios,
    main,
    parse_id_spec,
)


SCENARIO_DIR = Path(__file__).resolve().parent


def replay_payload(
    skill: Path,
    *,
    scenario_id: str = "I03",
    observations: dict | None = None,
    output_text: str = "Synthetic passing transcript.",
) -> dict:
    return {
        "scenarioId": scenario_id,
        "expectedSkillDirectorySha256": compute_skill_provenance(skill)[
            "directorySha256"
        ],
        "inputKind": "synthetic-protocol-conformance-replay",
        "recordedAt": "2026-09-19T09:00:00+08:00",
        "status": "observed",
        "observations": observations
        or {
            "wholeDisciplineRescanCount": 0,
            "prematureWritingTransitionCount": 0,
            "ideaMode": "refinement",
            "maxQuestionsPerTurn": 1,
        },
        "outputText": output_text,
        "executionBoundary": (
            "synthetic deterministic protocol-conformance replay; "
            "no model invoked; not behavioral verification"
        ),
    }


class ScenarioSelectionTests(unittest.TestCase):
    def test_loads_requested_idea_scenarios_in_order(self) -> None:
        ids = parse_id_spec("I01-I03,I05")
        scenarios = load_scenarios(SCENARIO_DIR, ids)

        self.assertEqual(ids, ["I01", "I02", "I03", "I05"])
        self.assertEqual([item["id"] for item in scenarios], ids)


class ScenarioEvidenceTests(unittest.TestCase):
    def test_passing_replay_archives_exact_input_and_skill_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skill"
            inputs = root / "inputs"
            output = root / "output"
            (skill / "references").mkdir(parents=True)
            (skill / "__pycache__").mkdir()
            inputs.mkdir()
            (skill / "SKILL.md").write_text("# Test skill\n", encoding="utf-8")
            (skill / "plugin.json").write_text(
                json.dumps({"version": "9.9.9"}), encoding="utf-8"
            )
            (skill / "references" / "rule.md").write_text("rule\n", encoding="utf-8")
            (skill / "__pycache__" / "ignored.pyc").write_bytes(b"ignored")
            payload = replay_payload(skill)
            replay_bytes = (
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            ).encode()
            (inputs / "I03.json").write_bytes(replay_bytes)

            self.assertEqual(
                main(
                    [
                        "--skill",
                        str(skill),
                        "--ids",
                        "I03",
                        "--mode",
                        "candidate",
                        "--inputs",
                        str(inputs),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            result_dir = output / "results" / "I03"
            self.assertEqual((result_dir / "replay-input.json").read_bytes(), replay_bytes)
            result = json.loads((result_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(
                result["sourceEvidence"],
                [
                    "results/I03/replay-input.json",
                    "results/I03/model-output.md",
                    "results/I03/skill-provenance.json",
                ],
            )
            for source_path in result["sourceEvidence"]:
                self.assertTrue((output / source_path).is_file(), source_path)
            rationale = json.loads(
                (result_dir / "evaluator-rationale.json").read_text(encoding="utf-8")
            )
            self.assertTrue(rationale["evaluation"]["passed"])
            provenance = rationale["skillProvenance"]
            self.assertEqual(provenance["declaredVersion"], "9.9.9")
            self.assertEqual(provenance["resolvedPath"], str(skill.resolve()))
            self.assertEqual(
                provenance,
                json.loads(
                    (result_dir / "skill-provenance.json").read_text(encoding="utf-8")
                ),
            )
            self.assertNotIn("__pycache__/ignored.pyc", [item["path"] for item in provenance["files"]])

    def test_cli_exit_code_distinguishes_pass_from_criterion_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skill"
            inputs = root / "inputs"
            output = root / "output"
            skill.mkdir()
            inputs.mkdir()
            passing = replay_payload(skill)
            failing = json.loads(json.dumps(passing))
            failing["observations"]["ideaMode"] = "discovery"
            input_path = inputs / "I03.json"
            input_path.write_text(json.dumps(passing), encoding="utf-8")
            common = [
                "--skill",
                str(skill),
                "--ids",
                "I03",
                "--mode",
                "candidate",
                "--inputs",
                str(inputs),
                "--output",
                str(output),
            ]

            self.assertEqual(main(common), 0)
            input_path.write_text(json.dumps(failing), encoding="utf-8")
            self.assertEqual(main(common), 1)
            rationale = json.loads(
                (output / "results" / "I03" / "evaluator-rationale.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(rationale["evaluation"]["failedCriteria"], ["I03.pass.01"])

    def test_cli_without_replay_input_is_a_harness_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skill"
            references = skill / "references"
            references.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
            output = root / "output"

            exit_code = main(
                [
                    "--skill",
                    str(skill),
                    "--ids",
                    "I03",
                    "--mode",
                    "candidate",
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertFalse(output.exists())

    def test_runner_contains_no_dynamic_eval_or_exec(self) -> None:
        source_path = SCENARIO_DIR / "run_skill_scenarios.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        forbidden_calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec"}
        }

        self.assertEqual(forbidden_calls, set())

    def test_mode_is_only_a_label_and_does_not_change_replay_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skill"
            references = skill / "references"
            references.mkdir(parents=True)
            (skill / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
            inputs = root / "inputs"
            inputs.mkdir()
            payload = replay_payload(
                skill,
                observations={
                    "wholeDisciplineRescanCount": 0,
                    "prematureWritingTransitionCount": 0,
                    "ideaMode": "discovery",
                    "maxQuestionsPerTurn": 1,
                },
                output_text="Contradictory replay.",
            )
            (inputs / "I03.json").write_text(json.dumps(payload), encoding="utf-8")
            evaluations = []
            for mode in ("baseline", "candidate"):
                output = root / mode
                self.assertEqual(
                    main(
                        [
                            "--skill",
                            str(skill),
                            "--ids",
                            "I03",
                            "--mode",
                            mode,
                            "--inputs",
                            str(inputs),
                            "--output",
                            str(output),
                        ]
                    ),
                    1,
                )
                rationale = json.loads(
                    (output / "results" / "I03" / "evaluator-rationale.json").read_text(
                        encoding="utf-8"
                    )
                )
                evaluations.append(rationale["evaluation"])
                model_output = (output / "results" / "I03" / "model-output.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn("Mode is an evidence label only", model_output)
            self.assertEqual(evaluations[0], evaluations[1])

    def test_replay_bound_to_another_skill_is_a_harness_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recorded_skill = root / "recorded-skill"
            selected_skill = root / "selected-skill"
            inputs = root / "inputs"
            recorded_skill.mkdir()
            selected_skill.mkdir()
            inputs.mkdir()
            (recorded_skill / "SKILL.md").write_text("recorded\n", encoding="utf-8")
            (selected_skill / "SKILL.md").write_text("selected\n", encoding="utf-8")
            (inputs / "I03.json").write_text(
                json.dumps(replay_payload(recorded_skill)), encoding="utf-8"
            )

            exit_code = main(
                [
                    "--skill",
                    str(selected_skill),
                    "--ids",
                    "I03",
                    "--mode",
                    "candidate",
                    "--inputs",
                    str(inputs),
                    "--output",
                    str(root / "output"),
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertFalse((root / "output").exists())

    def test_fixture_object_id_and_duplicate_prefix_errors_return_two(self) -> None:
        valid_scenario = json.loads(
            (SCENARIO_DIR / "I03-refine-vague-idea.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skill"
            inputs = root / "inputs"
            skill.mkdir()
            inputs.mkdir()
            (skill / "SKILL.md").write_text("skill\n", encoding="utf-8")
            (inputs / "I03.json").write_text(
                json.dumps(replay_payload(skill)), encoding="utf-8"
            )

            cases = {
                "non-object": [("I03-bad.json", [])],
                "mismatched-id": [
                    ("I03-bad.json", {**valid_scenario, "id": "I04"})
                ],
                "duplicate-prefix": [
                    ("I03-one.json", valid_scenario),
                    ("I03-two.json", valid_scenario),
                ],
            }
            for case_name, fixtures in cases.items():
                with self.subTest(case=case_name):
                    scenario_dir = root / case_name
                    scenario_dir.mkdir()
                    for name, value in fixtures:
                        (scenario_dir / name).write_text(
                            json.dumps(value), encoding="utf-8"
                        )
                    output = root / f"output-{case_name}"
                    self.assertEqual(
                        main(
                            [
                                "--skill",
                                str(skill),
                                "--ids",
                                "I03",
                                "--mode",
                                "candidate",
                                "--inputs",
                                str(inputs),
                                "--output",
                                str(output),
                                "--scenario-dir",
                                str(scenario_dir),
                            ]
                        ),
                        2,
                    )
                    self.assertFalse(output.exists())

    def test_skill_hash_is_reproducible_and_excludes_caches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "skill"
            (skill / "references").mkdir(parents=True)
            (skill / ".pytest_cache").mkdir()
            (skill / "SKILL.md").write_text("alpha\n", encoding="utf-8")
            (skill / "references" / "a.md").write_text("beta\n", encoding="utf-8")
            (skill / ".pytest_cache" / "state").write_text("one", encoding="utf-8")

            first = compute_skill_provenance(skill)
            (skill / ".pytest_cache" / "state").write_text("two", encoding="utf-8")
            second = compute_skill_provenance(skill)
            self.assertEqual(first["directorySha256"], second["directorySha256"])
            (skill / "references" / "a.md").write_text("changed\n", encoding="utf-8")
            third = compute_skill_provenance(skill)
            self.assertNotEqual(first["directorySha256"], third["directorySha256"])

    def test_skill_documentation_contract_is_separate_from_behavioral_results(self) -> None:
        self.assertEqual(
            check_documentation_contract(
                SCENARIO_DIR.parents[1] / "skills" / "cyz-edu-research"
            ),
            [],
        )
        source = (SCENARIO_DIR / "run_skill_scenarios.py").read_text(encoding="utf-8")
        self.assertNotIn("_documentation_observations", source)

    def test_discovery_and_refinement_use_the_same_candidate_card_fields(self) -> None:
        skill = SCENARIO_DIR.parents[1] / "skills" / "cyz-edu-research"
        scout = (skill / "references" / "idea-scout.md").read_text(encoding="utf-8")
        refinement = (skill / "references" / "idea-refinement.md").read_text(
            encoding="utf-8"
        )

        scout_line = next(
            line for line in scout.splitlines() if line.startswith("- Candidate card:")
        )
        refinement_line = next(
            line
            for line in refinement.splitlines()
            if line.startswith("- Candidate card:")
        )
        self.assertEqual(
            re.findall(r"`([^`]+)`", scout_line),
            re.findall(r"`([^`]+)`", refinement_line),
        )


if __name__ == "__main__":
    unittest.main()
