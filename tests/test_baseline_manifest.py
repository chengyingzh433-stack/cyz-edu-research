import hashlib
import json
import os
import re
import stat
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_MANIFEST = ROOT / "docs" / "baseline-manifest.json"
WORK_MANIFEST = ROOT.parents[1] / "baseline-manifest.json"
SNAPSHOT_ROOT = ROOT / "docs" / "source-snapshots"
SECRET_LIKE_KEY = re.compile(
    r"(?:token|secret|password|passwd|credential|api[_-]?key|"
    r"access[_-]?key|private[_-]?key)",
    re.IGNORECASE,
)


def load_manifest() -> dict[str, Any]:
    return json.loads(REPO_MANIFEST.read_text(encoding="utf-8"))


def is_cache_file(relative_path: Path) -> bool:
    return "__pycache__" in relative_path.parts or relative_path.suffix == ".pyc"


def is_link_or_reparse(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return path.is_symlink() or bool(attributes & reparse_flag)


def tree_inventory(root: Path, *, exclude_cache: bool = False) -> list[dict[str, Any]]:
    entries = []
    if is_link_or_reparse(root):
        raise AssertionError(f"inventory root must not be a link or reparse point: {root}")

    def visit(directory: Path) -> None:
        with os.scandir(directory) as children:
            for child in children:
                path = Path(child.path)
                if is_link_or_reparse(path):
                    raise AssertionError(f"inventory contains link or reparse point: {path}")
                if child.is_dir(follow_symlinks=False):
                    visit(path)
                    continue
                if not child.is_file(follow_symlinks=False):
                    continue
                relative_path = path.relative_to(root)
                if exclude_cache and is_cache_file(relative_path):
                    continue
                data = path.read_bytes()
                entries.append(
                    {
                        "relativePath": relative_path.as_posix(),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "bytes": len(data),
                    }
                )

    visit(root)
    # Python's default string ordering is ordinal by Unicode code point.
    return sorted(entries, key=lambda item: item["relativePath"])


def inventory_hash(entries: list[dict[str, Any]]) -> str:
    canonical = "".join(
        f'{item["relativePath"]}\t{item["sha256"]}\t{item["bytes"]}\n'
        for item in entries
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def tree_metrics(root: Path, *, exclude_cache: bool = False) -> dict[str, Any]:
    entries = tree_inventory(root, exclude_cache=exclude_cache)
    return {
        "fileCount": len(entries),
        "bytes": sum(item["bytes"] for item in entries),
        "sha256": inventory_hash(entries),
    }


def iter_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from iter_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_keys(child)


class BaselineManifestTests(unittest.TestCase):
    def test_inventory_entries_are_structured_objects(self):
        manifest = load_manifest()

        self.assertEqual(1, manifest["schemaVersion"])
        installs = manifest["cyzEduResearchInstalls"]
        self.assertIsInstance(installs["codex"]["full"], dict)
        self.assertIsInstance(installs["codex"]["cacheExcluded"], dict)
        self.assertIsInstance(installs["agents"]["full"], dict)
        self.assertIsInstance(installs["agents"]["cacheExcluded"], dict)

        controlled = installs["controlledFiles"]
        self.assertEqual(31, len(controlled))
        self.assertTrue(all(isinstance(item, dict) for item in controlled))
        self.assertTrue(
            all({"relativePath", "sha256", "bytes"} <= item.keys() for item in controlled)
        )

        dependencies = manifest["dependencySkills"]
        self.assertEqual(4, len(dependencies))
        for dependency in dependencies:
            self.assertIsInstance(dependency, dict)
            self.assertIsInstance(dependency["installations"], list)
            self.assertEqual(2, len(dependency["installations"]))
            self.assertTrue(
                all(isinstance(item, dict) for item in dependency["installations"])
            )

    def test_snapshot_inventory_matches_repository_files(self):
        manifest = load_manifest()
        snapshots = manifest["sourceSnapshots"]

        self.assertEqual(7, len(snapshots))
        self.assertTrue(all(isinstance(item, dict) for item in snapshots))
        self.assertEqual(
            {path.name for path in SNAPSHOT_ROOT.iterdir() if path.is_file()},
            {item["file"] for item in snapshots},
        )
        for item in snapshots:
            data = (SNAPSHOT_ROOT / item["file"]).read_bytes()
            self.assertEqual(item["bytes"], len(data), item["file"])
            self.assertEqual(
                item["sha256"], hashlib.sha256(data).hexdigest(), item["file"]
            )

    def test_manifest_has_no_secret_like_field_names(self):
        manifest = load_manifest()
        secret_like = sorted(key for key in iter_keys(manifest) if SECRET_LIKE_KEY.search(key))
        self.assertEqual([], secret_like)

    def test_work_manifest_is_byte_identical_when_available(self):
        repo_bytes = REPO_MANIFEST.read_bytes()
        if WORK_MANIFEST.exists():
            self.assertEqual(WORK_MANIFEST.read_bytes(), repo_bytes)

    def test_baseline_controlled_inventory_remains_valid_when_source_evolves(self):
        manifest = load_manifest()
        controlled = manifest["cyzEduResearchInstalls"]["controlledFiles"]

        # This is immutable G0 evidence, not a lock on the evolving repository tree.
        # Installed copies and backups are still re-hashed in the tests below.
        self.assertEqual(31, len(controlled))
        paths = [item["relativePath"] for item in controlled]
        self.assertEqual(len(paths), len(set(paths)))
        for item in controlled:
            relative = Path(item["relativePath"])
            self.assertFalse(relative.is_absolute())
            self.assertNotIn("..", relative.parts)
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertIsInstance(item["bytes"], int)
            self.assertGreaterEqual(item["bytes"], 0)

        backup_root = Path(manifest["paths"]["baselineBackupRoot"])
        available_backups = [
            backup_root / root_name / "cyz-edu-research"
            for root_name in ("codex", "agents")
            if (backup_root / root_name / "cyz-edu-research").is_dir()
        ]
        for backup in available_backups:
            for item in controlled:
                with self.subTest(backup=str(backup), path=item["relativePath"]):
                    path = backup / item["relativePath"]
                    self.assertTrue(path.is_file())
                    data = path.read_bytes()
                    self.assertEqual(item["bytes"], len(data))
                    self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())

    def test_cyz_install_tree_hashes_match_actual_files(self):
        manifest = load_manifest()
        installs = manifest["cyzEduResearchInstalls"]
        for root_name in ("codex", "agents"):
            with self.subTest(root=root_name):
                path = Path(installs[root_name]["path"])
                if not path.exists() and not path.is_symlink():
                    self.skipTest(f"installation root unavailable: {path}")
                self.assertEqual(installs[root_name]["full"], tree_metrics(path))
                self.assertEqual(
                    installs[root_name]["cacheExcluded"],
                    tree_metrics(path, exclude_cache=True),
                )

    def test_cyz_backup_tree_hashes_match_manifest(self):
        manifest = load_manifest()
        installs = manifest["cyzEduResearchInstalls"]
        backup_root = Path(manifest["paths"]["baselineBackupRoot"])
        for root_name in ("codex", "agents"):
            with self.subTest(root=root_name):
                path = backup_root / root_name / "cyz-edu-research"
                if not path.exists() and not path.is_symlink():
                    self.skipTest(f"backup root unavailable: {path}")
                self.assertEqual(installs[root_name]["full"], tree_metrics(path))
                self.assertEqual(
                    installs[root_name]["cacheExcluded"],
                    tree_metrics(path, exclude_cache=True),
                )

    def test_dependency_install_hashes_match_actual_files(self):
        manifest = load_manifest()
        for dependency in manifest["dependencySkills"]:
            for installation in dependency["installations"]:
                with self.subTest(
                    dependency=dependency["name"], root=installation["root"]
                ):
                    path = Path(installation["path"])
                    if not path.exists() and not path.is_symlink():
                        self.skipTest(f"dependency installation unavailable: {path}")
                    actual = tree_metrics(path)
                    expected = {
                        "fileCount": installation["fileCount"],
                        "bytes": installation["bytes"],
                        "sha256": installation["sha256"],
                    }
                    self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
