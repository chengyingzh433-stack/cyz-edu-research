import json
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "workflow-v1.json"
SCENARIO_ROOT = ROOT / "tests" / "scenarios"
SCHEMA_PATH = SCENARIO_ROOT / "scenario-contract.schema.json"

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

        self.assertEqual(1, data["contractVersion"])
        self.assertEqual(2, data["projectSchemaVersion"])
        self.assertNotEqual(data["contractVersion"], data["projectSchemaVersion"])
        self.assertEqual(
            [f"S{i}" for i in range(9)],
            [stage["id"] for stage in data["stages"]],
        )
        for stage in data["stages"]:
            with self.subTest(stage=stage["id"]):
                self.assertTrue(stage["name"])
                self.assertIsInstance(stage["gate"], dict)
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
        self.assertEqual(set(REQUIRED_ENTITY_FIELDS), set(data["entities"]))
        for entity, required in REQUIRED_ENTITY_FIELDS.items():
            with self.subTest(entity=entity):
                self.assertTrue(required <= set(data["entities"][entity]["required"]))

        transitions = data["allowedTransitions"]["ideaStatus"]
        self.assertIn("exploring", transitions["not_started"])
        self.assertIn("refining", transitions["not_started"])
        self.assertIn("ready", transitions["refining"])
        self.assertIn("needs_verification", transitions["ready"])
        self.assertIn("refining", transitions["ready"])
        self.assertTrue(data["readyDoesNotPassStages"])

    def test_scenario_schema_requires_executable_oracles(self):
        schema = load_json(SCHEMA_PATH)

        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertEqual(
            {"id", "title", "mapsTo", "executionMode", "preconditions", "inputs", "actor", "steps", "forbiddenBehavior", "passCriteria", "evidence"},
            set(schema["required"]),
        )
        self.assertEqual(
            ["deterministic", "scripted", "live"],
            schema["properties"]["executionMode"]["enum"],
        )
        predicate = schema["$defs"]["predicate"]
        self.assertEqual(
            {"predicate", "oracle", "evidenceRequired"}, set(predicate["required"])
        )

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
                self.assertTrue(
                    all(
                        {"predicate", "oracle", "evidenceRequired"} <= criterion.keys()
                        and criterion["predicate"]
                        and criterion["oracle"]
                        and criterion["evidenceRequired"]
                        for criterion in item["passCriteria"]
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
