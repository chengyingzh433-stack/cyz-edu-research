import copy
import json
import re
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "workflow-v1.json"
SCENARIO_ROOT = ROOT / "tests" / "scenarios"
SCHEMA_PATH = SCENARIO_ROOT / "scenario-contract.schema.json"
RESULT_SCHEMA_PATH = SCENARIO_ROOT / "result-contract.schema.json"

SCENARIO_FILES = {
    "I01": "I01-discovery-domain.json",
    "I02": "I02-discovery-seed-papers.json",
    "I03": "I03-refine-vague-idea.json",
    "I04": "I04-review-complete-plan.json",
    "I05": "I05-beginner-unknown.json",
    "I06": "I06-material-paths.json",
    "I07": "I07-near-duplicate.json",
    "I08": "I08-summary-only-offline.json",
    "I09": "I09-qualitative-fit.json",
    "I10": "I10-resume-project.json",
    "I11": "I11-evidence-reversal.json",
    "I12": "I12-handoff-boundaries.json",
    "I13": "I13-legacy-upgrade.json",
    "I14": "I14-install-consistency.json",
    "H01": "H01-chinese-humanizer.json",
    "H02": "H02-semantic-strength.json",
    "H03": "H03-missing-dependency.json",
    "H04": "H04-review-invalidation.json",
    "M01": "M01-live-local-pdf.json",
    "M02": "M02-cache-reuse.json",
    "M03": "M03-cache-integrity.json",
    "M04": "M04-task-lineage.json",
    "M05": "M05-desk-unavailable.json",
    "M06": "M06-original-preserved.json",
}

REQUIRED_ENTITY_FIELDS = {
    "task": {"taskId", "stageId", "status", "title", "inputs", "outputs", "createdAt", "updatedAt"},
    "artifact": {"artifactId", "kind", "path", "sha256", "stageId", "status", "provenance", "createdAt"},
    "evidence": {"evidenceId", "claimId", "sourceType", "sourceLocator", "accessLevel", "verificationStatus", "recordedAt"},
    "decision": {"decisionId", "question", "answer", "source", "ideaRevision", "affects", "decidedAt"},
    "event": {"eventId", "eventType", "actor", "occurredAt", "payload"},
    "recoveryPoint": {"recoveryPointId", "createdAt", "reason", "manifestPath", "fileHashes", "status"},
}
WF_IDS = {f"WF{i:02d}" for i in range(1, 13)}
EVIDENCE_PATH = re.compile(
    r"^results/[IHM][0-9]{2}/(?:(?!\.+(?:/|$))[A-Za-z0-9._-]+/)*"
    r"(?!\.+$)[A-Za-z0-9._-]+$"
)
OPAQUE_BOOLEAN_NAME = re.compile(r"(?:passed|valid|unchanged)$", re.IGNORECASE)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_scenarios() -> dict[str, dict[str, Any]]:
    scenarios = {}
    for scenario_id, filename in SCENARIO_FILES.items():
        scenario = load_json(SCENARIO_ROOT / filename)
        scenarios[scenario_id] = scenario
    return scenarios


class WorkflowContractTests(unittest.TestCase):
    def test_contract_separates_file_contract_from_project_schema(self):
        data = load_json(CONTRACT_PATH)

        self.assertEqual(
            {"contractVersion", "projectSchemaVersion", "readyDoesNotPassStages", "stages", "ideaEnums", "entities", "allowedTransitions", "invariants"},
            set(data),
        )
        self.assertEqual(1, data["contractVersion"])
        self.assertEqual(2, data["projectSchemaVersion"])
        self.assertNotEqual(data["contractVersion"], data["projectSchemaVersion"])
        self.assertEqual(
            [f"S{i}" for i in range(9)],
            [stage["id"] for stage in data["stages"]],
        )
        for stage in data["stages"]:
            with self.subTest(stage=stage["id"]):
                self.assertEqual({"id", "name", "gate"}, set(stage))
                self.assertTrue(stage["name"])
                self.assertIsInstance(stage["gate"], dict)
                self.assertEqual(
                    {"passCriteria", "evidenceRequired"}, set(stage["gate"])
                )
                self.assertTrue(stage["gate"]["passCriteria"])
                self.assertTrue(stage["gate"]["evidenceRequired"])

    def test_contract_defines_idea_enums_entities_and_transitions(self):
        data = load_json(CONTRACT_PATH)

        self.assertEqual(["discovery", "refinement"], data["ideaEnums"]["ideaMode"])
        self.assertEqual(
            ["broad_interest", "tentative_topic", "method_first", "positioned_question", "study_plan"],
            data["ideaEnums"]["ideaMaturity"],
        )
        self.assertEqual(
            ["not_started", "exploring", "refining", "needs_verification", "ready", "blocked"],
            data["ideaEnums"]["ideaStatus"],
        )
        self.assertEqual(
            ["pending", "running", "completed", "failed", "blocked", "cancelled"],
            data["ideaEnums"]["taskStatus"],
        )
        self.assertEqual(
            {"entryMode", "ideaMode", "ideaMaturity", "ideaStatus", "gateStatus", "taskStatus", "provenance"},
            set(data["ideaEnums"]),
        )
        self.assertEqual(set(REQUIRED_ENTITY_FIELDS), set(data["entities"]))
        for entity, required in REQUIRED_ENTITY_FIELDS.items():
            with self.subTest(entity=entity):
                self.assertEqual({"required"}, set(data["entities"][entity]))
                self.assertEqual(required, set(data["entities"][entity]["required"]))

        transitions = data["allowedTransitions"]["ideaStatus"]
        self.assertIn("exploring", transitions["not_started"])
        self.assertIn("refining", transitions["not_started"])
        self.assertIn("ready", transitions["refining"])
        self.assertIn("needs_verification", transitions["ready"])
        self.assertIn("refining", transitions["ready"])
        self.assertTrue(data["readyDoesNotPassStages"])

        enum_by_machine = {
            "ideaStatus": set(data["ideaEnums"]["ideaStatus"]),
            "gateStatus": set(data["ideaEnums"]["gateStatus"]),
            "taskStatus": set(data["ideaEnums"]["taskStatus"]),
        }
        self.assertEqual(set(enum_by_machine), set(data["allowedTransitions"]))
        for machine, values in enum_by_machine.items():
            with self.subTest(machine=machine):
                graph = data["allowedTransitions"][machine]
                self.assertEqual(values, set(graph))
                self.assertTrue(
                    all(set(destinations) <= values for destinations in graph.values())
                )

    def test_scenario_schema_requires_executable_oracles(self):
        schema = load_json(SCHEMA_PATH)

        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertEqual(
            {"id", "title", "criteriaDslVersion", "mapsTo", "executionMode", "preconditions", "inputs", "actor", "steps", "forbiddenBehavior", "passCriteria", "evidence"},
            set(schema["required"]),
        )
        self.assertEqual([1], schema["properties"]["criteriaDslVersion"]["enum"])
        self.assertEqual(
            ["deterministic", "scripted", "live"],
            schema["properties"]["executionMode"]["enum"],
        )
        self.assertEqual(sorted(WF_IDS), sorted(schema["properties"]["mapsTo"]["items"]["enum"]))
        criterion = schema["$defs"]["criterion"]
        self.assertEqual(
            {"id", "oracle", "condition", "evidenceRequired"},
            set(criterion["required"]),
        )
        self.assertEqual(
            ["eq", "not_eq", "gte", "lte", "exists", "unchanged"],
            schema["$defs"]["condition"]["properties"]["operator"]["enum"],
        )

    def test_schema_is_applied_to_every_fixture(self):
        from tests.scenarios.schema_validator import validate_scenario

        schema = load_json(SCHEMA_PATH)
        for scenario_id, item in load_scenarios().items():
            with self.subTest(scenario=scenario_id):
                validate_scenario(item, schema)

    def test_schema_validator_rejects_negative_mutations(self):
        from tests.scenarios.schema_validator import SchemaValidationError, validate_scenario

        schema = load_json(SCHEMA_PATH)
        original = load_scenarios()["I01"]
        mutations = []

        missing_actor = copy.deepcopy(original)
        del missing_actor["actor"]
        mutations.append(("missing required field", missing_actor))

        invalid_mode = copy.deepcopy(original)
        invalid_mode["executionMode"] = "manual"
        mutations.append(("invalid enum", invalid_mode))

        extra_field = copy.deepcopy(original)
        extra_field["undeclared"] = True
        mutations.append(("additional property", extra_field))

        invalid_operator = copy.deepcopy(original)
        invalid_operator["passCriteria"][0]["condition"]["operator"] = "eval"
        mutations.append(("unsafe operator", invalid_operator))

        invalid_dsl_version = copy.deepcopy(original)
        invalid_dsl_version["criteriaDslVersion"] = 2
        mutations.append(("unsupported DSL version", invalid_dsl_version))

        invalid_wf = copy.deepcopy(original)
        invalid_wf["mapsTo"] = ["WF13"]
        mutations.append(("out-of-contract WF mapping", invalid_wf))

        invalid_numeric_type = copy.deepcopy(original)
        invalid_numeric_type["passCriteria"][0]["condition"].update(
            {"operator": "gte", "expected": "two"}
        )
        mutations.append(("numeric operator with string expected", invalid_numeric_type))

        invalid_boolean_type = copy.deepcopy(original)
        invalid_boolean_type["passCriteria"][0]["condition"].update(
            {"operator": "exists", "expected": "yes"}
        )
        mutations.append(("boolean operator with string expected", invalid_boolean_type))

        prose_pass = copy.deepcopy(original)
        prose_pass["passCriteria"][0] = "looks good"
        mutations.append(("prose-only pass rule", prose_pass))

        prose_forbidden = copy.deepcopy(original)
        prose_forbidden["forbiddenBehavior"][0] = "do not hallucinate"
        mutations.append(("prose-only forbidden rule", prose_forbidden))

        for unsafe_path in (
            "/tmp/evidence.json",
            "C:/evidence.json",
            "//server/share/evidence.json",
            "results/I01/../evidence.json",
            "results/I01/./evidence.json",
            "results/I01/.../evidence.json",
            "results/I02/wrong-scenario.json",
        ):
            unsafe_evidence = copy.deepcopy(original)
            unsafe_evidence["evidence"][0] = unsafe_path
            unsafe_evidence["passCriteria"][0]["evidenceRequired"][0] = unsafe_path
            mutations.append((f"unsafe evidence path {unsafe_path}", unsafe_evidence))

        undeclared_evidence = copy.deepcopy(original)
        undeclared_evidence["passCriteria"][0]["evidenceRequired"] = [
            "results/I01/not-declared.json"
        ]
        mutations.append(("criterion evidence not declared at top level", undeclared_evidence))

        unsupported_schema = copy.deepcopy(schema)
        unsupported_schema["properties"]["title"]["maxLength"] = 100

        for label, mutation in mutations:
            with self.subTest(mutation=label):
                with self.assertRaises(SchemaValidationError):
                    validate_scenario(mutation, schema)
        with self.assertRaisesRegex(SchemaValidationError, "unsupported schema keyword"):
            validate_scenario(original, unsupported_schema)

    def test_condition_dsl_has_a_safe_non_eval_evaluator(self):
        from tests.scenarios.schema_validator import (
            SchemaValidationError,
            evaluate_condition,
        )

        observed = {
            "checks": {"passed": True, "count": 2},
            "hashes": {"source": {"before": "abc", "after": "abc"}},
        }
        self.assertTrue(
            evaluate_condition(
                observed, {"path": "checks.passed", "operator": "eq", "expected": True}
            )
        )
        self.assertTrue(
            evaluate_condition(
                observed, {"path": "checks.count", "operator": "gte", "expected": 2}
            )
        )
        self.assertTrue(
            evaluate_condition(
                observed,
                {"path": "hashes.source", "operator": "unchanged", "expected": True},
            )
        )
        self.assertTrue(
            evaluate_condition(
                observed, {"path": "checks.missing", "operator": "exists", "expected": False}
            )
        )
        with self.assertRaises(SchemaValidationError):
            evaluate_condition(
                observed, {"path": "checks.passed", "operator": "eval", "expected": True}
            )
        self.assertFalse(
            evaluate_condition(
                {"value": True}, {"path": "value", "operator": "eq", "expected": 1}
            )
        )
        self.assertFalse(
            evaluate_condition(
                {"value": False}, {"path": "value", "operator": "eq", "expected": 0}
            )
        )
        self.assertTrue(
            evaluate_condition(
                {"value": True}, {"path": "value", "operator": "not_eq", "expected": 1}
            )
        )
        self.assertTrue(
            evaluate_condition(
                {"value": False}, {"path": "value", "operator": "not_eq", "expected": 0}
            )
        )
        self.assertFalse(
            evaluate_condition(
                {"pair": {"before": True, "after": 1}},
                {"path": "pair", "operator": "unchanged", "expected": True},
            )
        )

    def test_result_document_contract_defines_raw_observation_shape(self):
        from tests.scenarios.schema_validator import validate_result

        schema = load_json(RESULT_SCHEMA_PATH)
        self.assertEqual(1, schema["properties"]["resultContractVersion"]["enum"][0])
        self.assertEqual(
            {"resultContractVersion", "scenarioId", "recordedAt", "status", "observations", "sourceEvidence"},
            set(schema["required"]),
        )
        self.assertEqual("object", schema["properties"]["observations"]["type"])
        self.assertGreaterEqual(schema["properties"]["observations"]["minProperties"], 1)
        expected_ids = {
            *(f"I{number:02d}" for number in range(1, 15)),
            *(f"H{number:02d}" for number in range(1, 5)),
            *(f"M{number:02d}" for number in range(1, 7)),
        }
        self.assertEqual(expected_ids, set(schema["properties"]["scenarioId"]["enum"]))
        valid = {
            "resultContractVersion": 1,
            "scenarioId": "M06",
            "recordedAt": "2026-09-19T00:00:00+08:00",
            "status": "observed",
            "observations": {"sourceHashes": {"before": "abc", "after": "abc"}},
            "sourceEvidence": ["results/M06/artifacts/source-hashes.json"],
        }
        validate_result(valid, schema)
        utc_result = copy.deepcopy(valid)
        utc_result["recordedAt"] = "2026-09-19T00:00:00Z"
        validate_result(utc_result, schema)

    def test_result_document_rejects_invalid_identity_evidence_and_timestamp(self):
        from tests.scenarios.schema_validator import SchemaValidationError, validate_result

        schema = load_json(RESULT_SCHEMA_PATH)
        valid = {
            "resultContractVersion": 1,
            "scenarioId": "M06",
            "recordedAt": "2026-09-19T00:00:00+08:00",
            "status": "observed",
            "observations": {"sourceHashes": {"before": "abc", "after": "abc"}},
            "sourceEvidence": ["results/M06/artifacts/source-hashes.json"],
        }
        unknown_scenario = copy.deepcopy(valid)
        unknown_scenario["scenarioId"] = "I99"
        unknown_scenario["sourceEvidence"] = ["results/I99/evidence.json"]
        cross_scenario = copy.deepcopy(valid)
        cross_scenario["sourceEvidence"] = ["results/I01/evidence.json"]
        invalid_timestamp = copy.deepcopy(valid)
        invalid_timestamp["recordedAt"] = "x"

        for label, mutation in (
            ("unknown scenario", unknown_scenario),
            ("cross-scenario evidence", cross_scenario),
            ("invalid timestamp", invalid_timestamp),
        ):
            with self.subTest(mutation=label):
                with self.assertRaises(SchemaValidationError):
                    validate_result(mutation, schema)

    def test_every_required_scenario_has_an_oracle(self):
        self.assertEqual(
            set(SCENARIO_FILES.values()),
            {path.name for path in SCENARIO_ROOT.glob("[IHM][0-9][0-9]-*.json")},
        )
        scenarios = load_scenarios()
        self.assertEqual(set(SCENARIO_FILES), set(scenarios))

        for scenario_id, item in scenarios.items():
            with self.subTest(scenario=scenario_id):
                self.assertEqual(scenario_id, item["id"])
                self.assertEqual(1, item["criteriaDslVersion"])
                self.assertTrue(item["title"])
                self.assertTrue(item["mapsTo"])
                self.assertIn(item["executionMode"], {"deterministic", "scripted", "live"})
                self.assertTrue(item["preconditions"])
                self.assertTrue(item["inputs"])
                self.assertTrue(item["actor"])
                self.assertTrue(item["steps"])
                self.assertTrue(item["forbiddenBehavior"])
                self.assertTrue(item["passCriteria"])
                self.assertTrue(item["evidence"])
                self.assertTrue(set(item["mapsTo"]) <= WF_IDS)

    def test_every_oracle_and_forbidden_rule_is_executable(self):
        seen_ids = set()
        for scenario_id, item in load_scenarios().items():
            declared_evidence = set(item["evidence"])
            for group_name in ("passCriteria", "forbiddenBehavior"):
                for criterion in item[group_name]:
                    with self.subTest(scenario=scenario_id, criterion=criterion):
                        self.assertIsInstance(criterion, dict)
                        self.assertEqual(
                            {"id", "oracle", "condition", "evidenceRequired"},
                            set(criterion),
                        )
                        self.assertRegex(
                            criterion["id"],
                            rf"^{scenario_id}\.(?:pass|forbid)\.[0-9]{{2}}$",
                        )
                        self.assertNotIn(criterion["id"], seen_ids)
                        seen_ids.add(criterion["id"])
                        self.assertTrue(criterion["oracle"])
                        self.assertEqual(
                            {"path", "operator", "expected"},
                            set(criterion["condition"]),
                        )
                        self.assertTrue(
                            set(criterion["evidenceRequired"]) <= declared_evidence
                        )

    def test_evidence_paths_are_scenario_local_and_safe(self):
        for scenario_id, item in load_scenarios().items():
            all_paths = list(item["evidence"])
            for group_name in ("passCriteria", "forbiddenBehavior"):
                for criterion in item[group_name]:
                    all_paths.extend(criterion["evidenceRequired"])
            for evidence_path in all_paths:
                with self.subTest(scenario=scenario_id, path=evidence_path):
                    self.assertRegex(evidence_path, EVIDENCE_PATH)
                    self.assertTrue(evidence_path.startswith(f"results/{scenario_id}/"))
                    self.assertNotIn("..", evidence_path.split("/"))
                    self.assertNotIn("\\", evidence_path)

    def test_criteria_read_raw_observations_not_aggregate_attestations(self):
        criterion_count = 0
        for scenario_id, item in load_scenarios().items():
            for group_name in ("passCriteria", "forbiddenBehavior"):
                for criterion in item[group_name]:
                    criterion_count += 1
                    condition = criterion["condition"]
                    leaf = condition["path"].split(".")[-1]
                    with self.subTest(scenario=scenario_id, criterion=criterion["id"]):
                        self.assertTrue(condition["path"].startswith("observations."))
                        if isinstance(condition["expected"], bool):
                            self.assertNotRegex(leaf, OPAQUE_BOOLEAN_NAME)
        self.assertEqual(108, criterion_count)

        scenarios = load_scenarios()
        self.assertEqual(
            62, sum(len(item["passCriteria"]) for item in scenarios.values())
        )
        self.assertEqual(
            46, sum(len(item["forbiddenBehavior"]) for item in scenarios.values())
        )
        m02 = {
            criterion["condition"]["path"]
            for criterion in scenarios["M02"]["passCriteria"]
        }
        self.assertTrue(
            {
                "observations.conversionInvocationCount",
                "observations.submissionCountDelta",
                "observations.cacheHitCount",
                "observations.sourceFingerprintMatchCount",
                "observations.parameterFingerprintMatchCount",
                "observations.lineageTaskIdCount",
            }
            <= m02
        )
        m06 = scenarios["M06"]["passCriteria"]
        self.assertTrue(
            any(
                item["condition"]
                == {
                    "path": "observations.sourceHashes",
                    "operator": "unchanged",
                    "expected": True,
                }
                for item in m06
            )
        )

    def test_original_idea_scenarios_keep_one_to_one_numbering(self):
        scenarios = load_scenarios()
        for number in range(1, 15):
            scenario_id = f"I{number:02d}"
            with self.subTest(scenario=scenario_id):
                self.assertEqual(number, scenarios[scenario_id]["sourceScenario"])
                self.assertIn(f"WF{1 if number <= 2 else 3 if number <= 7 else 4 if number <= 9 else 5 if number <= 13 else 12:02d}", scenarios[scenario_id]["mapsTo"])


if __name__ == "__main__":
    unittest.main()
