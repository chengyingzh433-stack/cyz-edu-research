import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build_release.py"
INSTALL_SCRIPT = ROOT / "scripts" / "install_skill.py"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_release.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = load_module("task8_build_release", BUILD_SCRIPT)
INSTALL = load_module("task8_install_skill", INSTALL_SCRIPT)
VERIFY = load_module("task8_verify_release", VERIFY_SCRIPT)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite_archive(
    source: Path,
    destination: Path,
    *,
    replace: dict[str, bytes] | None = None,
    remove: set[str] | None = None,
    refresh_manifest: bool = True,
) -> None:
    replace = replace or {}
    remove = remove or set()
    with zipfile.ZipFile(source) as archive:
        files = {
            item.filename: archive.read(item)
            for item in archive.infolist()
            if not item.is_dir() and item.filename not in remove
        }
    files.update(replace)
    manifest_name = "cyz-edu-research/release-manifest.json"
    if refresh_manifest:
        files.pop(manifest_name, None)
        manifest = {
            "schemaVersion": 1,
            "package": "cyz-edu-research",
            "version": files["cyz-edu-research/VERSION"].decode("utf-8").strip(),
            "files": [
                {
                    "path": name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                for name, data in sorted(files.items())
            ],
        }
        files[manifest_name] = (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    BUILD.write_deterministic_zip(destination, files)


class ReleasePackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.temp_root = Path(self.temporary.name)
        self.dist = self.temp_root / "dist"
        result = BUILD.build_release(ROOT, self.dist, source_commit="test-commit")
        self.archive = Path(result["archive"])

    def assert_rejected(self, archive: Path, fragment: str) -> None:
        errors = VERIFY.verify_archive(archive)
        self.assertTrue(errors, "modified archive unexpectedly passed verification")
        self.assertTrue(
            any(fragment.lower() in error.lower() for error in errors),
            f"expected {fragment!r} in errors: {errors}",
        )

    def test_build_is_deterministic_and_distribution_verifies(self):
        first_hash = sha256(self.archive)
        second = self.temp_root / "second"
        result = BUILD.build_release(ROOT, second, source_commit="test-commit")
        self.assertEqual(first_hash, sha256(Path(result["archive"])))
        self.assertEqual([], VERIFY.verify_distribution(self.dist))

        with zipfile.ZipFile(self.archive) as archive:
            names = sorted(item.filename for item in archive.infolist() if not item.is_dir())
            manifest = json.loads(
                archive.read("cyz-edu-research/release-manifest.json")
            )
        listed = sorted(item["path"] for item in manifest["files"])
        self.assertEqual(
            sorted(set(names) - {"cyz-edu-research/release-manifest.json"}),
            listed,
        )
        self.assertNotIn("mineru-desk-skill", "\n".join(names))

    def test_rejects_version_mismatch(self):
        bad = self.temp_root / "version.zip"
        rewrite_archive(
            self.archive,
            bad,
            replace={"cyz-edu-research/VERSION": b"9.9.9\n"},
        )
        self.assert_rejected(bad, "version mismatch")

    def test_rejects_missing_required_notice_or_license(self):
        for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            with self.subTest(filename=filename):
                bad = self.temp_root / f"missing-{filename.replace('.', '-')}.zip"
                rewrite_archive(
                    self.archive,
                    bad,
                    remove={f"cyz-edu-research/{filename}"},
                )
                self.assert_rejected(bad, filename)

    def test_rejects_personal_paths_tokens_bytecode_weights_and_pdfs(self):
        cases = {
            "personal-path": (
                "cyz-edu-research/leak.txt",
                b"C:" + b"\\Users\\private-person\\Documents\\paper.txt\n",
                "absolute personal path",
            ),
            "token": (
                "cyz-edu-research/leak.txt",
                b"github_" + b"pat_abcdefghijklmnopqrstuvwxyz1234567890\n",
                "token-like",
            ),
            "bytecode": (
                "cyz-edu-research/scripts/leak.pyc",
                b"compiled",
                ".pyc",
            ),
            "weights": (
                "cyz-edu-research/models/private.safetensors",
                b"weights",
                "model weight",
            ),
            "pdf": (
                "cyz-edu-research/private-paper.pdf",
                b"%PDF-1.7\n",
                "PDF",
            ),
        }
        for label, (name, data, fragment) in cases.items():
            with self.subTest(label=label):
                bad = self.temp_root / f"{label}.zip"
                rewrite_archive(self.archive, bad, replace={name: data})
                self.assert_rejected(bad, fragment)

    def test_rejects_broken_relative_link(self):
        bad = self.temp_root / "broken-link.zip"
        rewrite_archive(
            self.archive,
            bad,
            replace={
                "cyz-edu-research/references/broken.md": (
                    b"# Broken\n\n[missing](does-not-exist.md)\n"
                )
            },
        )
        self.assert_rejected(bad, "broken relative link")

    def test_rejects_wrong_manifest_hash(self):
        bad = self.temp_root / "wrong-hash.zip"
        rewrite_archive(
            self.archive,
            bad,
            replace={"cyz-edu-research/SKILL.md": b"changed without manifest refresh\n"},
            refresh_manifest=False,
        )
        self.assert_rejected(bad, "hash mismatch")

    def test_distribution_rejects_checksum_tampering(self):
        sums = self.dist / "SHA256SUMS.txt"
        sums.write_text(
            "0" * 64 + f"  {self.archive.name}\n", encoding="utf-8"
        )
        errors = VERIFY.verify_distribution(self.dist)
        self.assertTrue(any("distribution hash mismatch" in error for error in errors))

    def test_rejects_undeclared_skill_dependency(self):
        with zipfile.ZipFile(self.archive) as archive:
            skill = archive.read("cyz-edu-research/SKILL.md")
        bad = self.temp_root / "undeclared.zip"
        rewrite_archive(
            self.archive,
            bad,
            replace={
                "cyz-edu-research/SKILL.md": skill
                + b"\nUse the `private-helper` skill dependency.\n"
            },
        )
        self.assert_rejected(bad, "undeclared dependency")

    def test_fresh_install_initializes_and_validates_in_two_roots(self):
        for number in (1, 2):
            with self.subTest(root=number):
                skill_root = self.temp_root / f"skills-{number}"
                result = INSTALL.install_archive(self.archive, skill_root)
                self.assertEqual("installed", result["status"])
                installed = skill_root / "cyz-edu-research"
                project = self.temp_root / f"project-{number}"
                init = subprocess.run(
                    [
                        sys.executable,
                        str(installed / "scripts" / "init_project.py"),
                        str(project),
                        "--entry-mode",
                        "discovery",
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, init.returncode, init.stderr + init.stdout)
                validate = subprocess.run(
                    [
                        sys.executable,
                        str(installed / "scripts" / "validate_project.py"),
                        str(project),
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(0, validate.returncode, validate.stderr + validate.stdout)

    def test_upgrade_conflict_is_backed_up_and_rollback_restores_hashes(self):
        skill_root = self.temp_root / "upgrade-root"
        INSTALL.install_archive(self.archive, skill_root)
        installed = skill_root / "cyz-edu-research"
        edited = installed / "SKILL.md"
        edited.write_text(
            edited.read_text(encoding="utf-8") + "\nlocal user edit\n",
            encoding="utf-8",
        )
        before = INSTALL.tree_manifest(installed)

        conflict = INSTALL.install_archive(self.archive, skill_root)
        self.assertEqual("conflict", conflict["status"])
        self.assertTrue(Path(conflict["backup"]).is_dir())
        self.assertEqual(before, INSTALL.tree_manifest(installed))

        upgraded = INSTALL.install_archive(
            self.archive, skill_root, allow_conflicts=True
        )
        self.assertEqual("upgraded_with_conflicts", upgraded["status"])
        self.assertNotEqual(before, INSTALL.tree_manifest(installed))
        rollback = INSTALL.rollback_install(skill_root, Path(upgraded["backup"]))
        self.assertEqual("rolled_back", rollback["status"])
        self.assertEqual(before, INSTALL.tree_manifest(installed))


if __name__ == "__main__":
    unittest.main()
