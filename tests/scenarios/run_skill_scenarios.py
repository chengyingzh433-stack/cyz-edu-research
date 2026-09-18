"""Replay explicit CYZ scenario observations through the checked-in evaluator.

This harness does not generate observations and does not invoke or simulate a
language model.  Every behavioral value must come from an archived replay input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from tests.scenarios.schema_validator import evaluate_scenario_result
except ModuleNotFoundError:  # Direct script execution places this directory first.
    from schema_validator import evaluate_scenario_result


_ID = re.compile(r"^I([0-9]{2})$")
_CACHE_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}


def parse_id_spec(value: str) -> list[str]:
    """Expand comma-separated idea scenario IDs and inclusive ranges."""

    selected: list[str] = []
    for token in value.split(","):
        token = token.strip()
        if "-" not in token:
            if _ID.fullmatch(token) is None:
                raise ValueError(f"invalid idea scenario id: {token}")
            selected.append(token)
            continue
        start, end = token.split("-", 1)
        start_match = _ID.fullmatch(start)
        end_match = _ID.fullmatch(end)
        if start_match is None or end_match is None:
            raise ValueError(f"invalid idea scenario range: {token}")
        first = int(start_match.group(1))
        last = int(end_match.group(1))
        if first > last:
            raise ValueError(f"descending scenario range is not allowed: {token}")
        selected.extend(f"I{number:02d}" for number in range(first, last + 1))
    if len(selected) != len(set(selected)):
        raise ValueError("duplicate scenario id")
    return selected


def load_scenarios(scenario_dir: Path, ids: list[str]) -> list[dict[str, Any]]:
    """Load requested checked-in scenario fixtures, preserving caller order."""

    available: dict[str, Path] = {}
    for path in scenario_dir.glob("I[0-9][0-9]-*.json"):
        scenario_id = path.name[:3]
        if scenario_id in available:
            raise ValueError(
                "duplicate scenario fixture prefix "
                f"{scenario_id}: {available[scenario_id].name}, {path.name}"
            )
        available[scenario_id] = path
    missing = [scenario_id for scenario_id in ids if scenario_id not in available]
    if missing:
        raise ValueError(f"scenario fixture not found: {', '.join(missing)}")
    scenarios = []
    for scenario_id in ids:
        path = available[scenario_id]
        scenario = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(scenario, dict):
            raise ValueError(f"{path}: scenario fixture must be an object")
        if scenario.get("id") != scenario_id:
            raise ValueError(
                f"{path}: scenario id {scenario.get('id')!r} does not match "
                f"filename prefix {scenario_id}"
            )
        scenarios.append(scenario)
    return scenarios


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def compute_skill_provenance(skill_path: Path) -> dict[str, Any]:
    """Build a reproducible content manifest and hash for one skill directory."""

    resolved = skill_path.resolve()
    if not resolved.is_dir():
        raise ValueError(f"skill directory not found: {skill_path}")
    files = []
    for path in sorted(
        (candidate for candidate in resolved.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(resolved).as_posix(),
    ):
        relative = path.relative_to(resolved)
        if any(part in _CACHE_DIRECTORIES for part in relative.parts):
            continue
        if path.suffix.casefold() in {".pyc", ".pyo"}:
            continue
        content = path.read_bytes()
        files.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
        )
    canonical = json.dumps(
        files, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    declared_version = None
    plugin_path = resolved / "plugin.json"
    if plugin_path.is_file():
        plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
        declared_version = plugin.get("version")
    return {
        "resolvedPath": str(resolved),
        "declaredVersion": declared_version,
        "directorySha256": hashlib.sha256(canonical).hexdigest(),
        "fileCount": len(files),
        "contentBytes": sum(item["bytes"] for item in files),
        "hashRecipe": (
            "SHA-256 of UTF-8 canonical JSON for the path-sorted "
            "[{path,sha256,bytes}] manifest; cache directories and pyc/pyo excluded"
        ),
        "files": files,
    }


def check_documentation_contract(skill_path: Path) -> list[str]:
    """Check normative documentation requirements without inferring behavior."""

    requirements = {
        "SKILL.md": (
            "description: Use when",
            "idea-refinement.md",
            "skip broad discovery",
        ),
        "references/idea-scout.md": (
            "about 3–5",
            "Do not pad",
            "Stop broad discovery when",
        ),
        "references/idea-refinement.md": (
            "## Maturity Route",
            "counterevidence",
            "failure conditions",
            "existing | obtainable | new collection",
            "near-duplicate",
            "Candidate card",
            "Current topic",
            "Decision record",
            "Handoff",
        ),
        "references/guided-mentor.md": (
            "exactly one consequential question per turn",
            "When The User Answers `不知道`",
        ),
        "references/literature-workflow.md": (
            "discovery scan",
            "targeted idea check",
            "formal review",
        ),
        "references/project-protocol.md": (
            "idea_revision",
            "current_decision",
            "current_evidence",
        ),
        "references/integrity-gates.md": (
            "needs_verification",
            "Do not enter writing before user confirmation",
        ),
    }
    missing = []
    for relative, phrases in requirements.items():
        path = skill_path / relative
        if not path.is_file():
            missing.append(f"missing file: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase not in text:
                missing.append(f"{relative}: missing normative text {phrase!r}")
    skill_file = skill_path / "SKILL.md"
    if skill_file.is_file():
        description_line = next(
            (
                line.removeprefix("description: ")
                for line in skill_file.read_text(encoding="utf-8").splitlines()
                if line.startswith("description: ")
            ),
            "",
        )
        if len(description_line) >= 500:
            missing.append("SKILL.md: frontmatter description must be under 500 characters")
    candidate_fields = []
    for relative in (
        "references/idea-scout.md",
        "references/idea-refinement.md",
    ):
        path = skill_path / relative
        if not path.is_file():
            continue
        line = next(
            (
                item
                for item in path.read_text(encoding="utf-8").splitlines()
                if item.startswith("- Candidate card:")
            ),
            "",
        )
        if not line:
            missing.append(f"{relative}: missing canonical Candidate card field list")
            continue
        candidate_fields.append((relative, re.findall(r"`([^`]+)`", line)))
    if len(candidate_fields) == 2 and candidate_fields[0][1] != candidate_fields[1][1]:
        missing.append(
            "candidate card fields differ between idea-scout.md and idea-refinement.md"
        )
    return missing


def evaluate_and_save(
    scenario: dict[str, Any],
    result: dict[str, Any],
    output_root: Path,
    *,
    output_text: str,
    execution_boundary: str,
    input_kind: str,
    mode: str,
    replay_input: bytes,
    skill_provenance: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one explicit result and persist auditable evidence."""

    scenario_id = scenario["id"]
    evaluation = evaluate_scenario_result(
        scenario, result, f"results/{scenario_id}/result.json"
    )
    result_dir = output_root / "results" / scenario_id
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "replay-input.json").write_bytes(replay_input)
    _write_json(result_dir / "result.json", result)
    _write_json(result_dir / "skill-provenance.json", skill_provenance)
    (result_dir / "model-output.md").write_text(
        "# Recorded execution output\n\n"
        f"Mode label: {mode}. Mode is an evidence label only; it does not change "
        "observations or evaluation.\n\n"
        f"Input kind: {input_kind}.\n\n"
        f"Execution boundary: {execution_boundary}.\n\n"
        "The harness did not invoke or simulate a language model. The text below "
        "is copied from the explicit replay input.\n\n"
        f"{output_text.rstrip()}\n",
        encoding="utf-8",
    )
    _write_json(
        result_dir / "evaluator-rationale.json",
        {
            "scenarioId": scenario_id,
            "mode": mode,
            "modeSemantics": "evidence label only; never changes replay observations",
            "inputKind": input_kind,
            "executionBoundary": execution_boundary,
            "skillProvenance": skill_provenance,
            "evaluation": evaluation,
        },
    )
    return evaluation


def _load_replay_input(
    path: Path, scenario_id: str, skill_directory_sha256: str
) -> tuple[dict[str, Any], str, str, str, bytes]:
    replay_input = path.read_bytes()
    payload = json.loads(replay_input.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: replay input must be an object")
    if payload.get("scenarioId") != scenario_id:
        raise ValueError(
            f"{path}: replay scenarioId {payload.get('scenarioId')!r} does not match "
            f"selected scenario {scenario_id}"
        )
    expected_skill_hash = payload.get("expectedSkillDirectorySha256")
    if expected_skill_hash != skill_directory_sha256:
        raise ValueError(
            f"{path}: replay skill hash {expected_skill_hash!r} does not match "
            f"selected skill hash {skill_directory_sha256}"
        )
    observations = payload.get("observations")
    if not isinstance(observations, dict) or not observations:
        raise ValueError(f"{path}: observations must be a non-empty object")
    output_text = payload.get("outputText")
    boundary = payload.get("executionBoundary")
    input_kind = payload.get("inputKind")
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError(f"{path}: outputText must be a non-empty string")
    if not isinstance(boundary, str) or not boundary.strip():
        raise ValueError(f"{path}: executionBoundary must be a non-empty string")
    if not isinstance(input_kind, str) or not input_kind.strip():
        raise ValueError(f"{path}: inputKind must be a non-empty string")
    result = {
        "resultContractVersion": 1,
        "scenarioId": scenario_id,
        "recordedAt": payload.get("recordedAt"),
        "status": payload.get("status"),
        "observations": observations,
        "sourceEvidence": [
            f"results/{scenario_id}/replay-input.json",
            f"results/{scenario_id}/model-output.md",
            f"results/{scenario_id}/skill-provenance.json",
        ],
    }
    return result, output_text, boundary, input_kind, replay_input


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replay explicit CYZ idea-scenario observations; --mode is an evidence "
            "label only and never changes evaluation."
        )
    )
    parser.add_argument("--skill", type=Path, required=True)
    parser.add_argument("--ids", required=True)
    parser.add_argument("--mode", choices=("baseline", "candidate"), required=True)
    parser.add_argument(
        "--inputs",
        type=Path,
        help="Required directory of explicit replay JSON; observations are never generated.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--scenario-dir", type=Path, default=Path(__file__).resolve().parent
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output_root = args.output or Path(".tmp") / "skill-scenarios" / args.mode
    try:
        if not args.skill.is_dir():
            raise ValueError(f"skill directory not found: {args.skill}")
        if args.inputs is None:
            raise ValueError("--inputs is required for behavioral scenario replay")
        if not args.inputs.is_dir():
            raise ValueError(f"input directory not found: {args.inputs}")
        skill_provenance = compute_skill_provenance(args.skill)
        scenarios = load_scenarios(args.scenario_dir, parse_id_spec(args.ids))
        evaluations = []
        for scenario in scenarios:
            scenario_id = scenario["id"]
            result, output_text, boundary, input_kind, replay_input = _load_replay_input(
                args.inputs / f"{scenario_id}.json",
                scenario_id,
                skill_provenance["directorySha256"],
            )
            evaluations.append(
                evaluate_and_save(
                    scenario,
                    result,
                    output_root,
                    output_text=output_text,
                    execution_boundary=boundary,
                    input_kind=input_kind,
                    mode=args.mode,
                    replay_input=replay_input,
                    skill_provenance=skill_provenance,
                )
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"HARNESS ERROR: {error}", file=sys.stderr)
        return 2

    failed = [item["scenarioId"] for item in evaluations if not item["passed"]]
    if failed:
        print(f"SCENARIO FAIL: {', '.join(failed)}")
        return 1
    print(f"SCENARIO PASS: {', '.join(item['scenarioId'] for item in evaluations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
