"""Regression coverage for accidental native fallback (no Desk service needed)."""
import contextlib
import io
import importlib.util
import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from test_cache_integrity import CONVERT, ROOT, write_cache_fixture
from test_release_package import BUILD


class MineruRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / 'paper.pdf'
        self.pdf.write_bytes(b'%PDF synthetic routing fixture')
        self.output = self.root / 'cache'

    def run_converter(self, *extra):
        argv = ['convert', str(self.pdf), '--output-dir', str(self.output), *extra]
        stderr = io.StringIO()
        # PDF decoding is unrelated to routing; cache IO and main are real.
        with mock.patch('sys.argv', argv), mock.patch.object(
            CONVERT, 'get_pdf_info', return_value=(2, 'Fixture')
        ), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            result = CONVERT.main()
        return result, stderr.getvalue()

    def test_cache_miss_requires_desk_before_native_including_force(self):
        for extra in [(), ('--force',)]:
            with self.subTest(extra=extra):
                result, message = self.run_converter(*extra)
                self.assertEqual(2, result)
                self.assertIn('MINERU_REQUIRED', message)
                self.assertFalse(self.output.exists())
                self.assertEqual([], list(self.root.glob('.cache.staging-*')))

    def test_read_only_probe_still_returns_cache_miss(self):
        self.assertEqual(3, self.run_converter('--check-cache')[0])
        self.assertFalse(self.output.exists())

    def test_valid_cache_needs_no_desk_or_fallback_reason(self):
        write_cache_fixture(self.output, CONVERT.sha256_file(self.pdf))
        self.assertEqual(0, self.run_converter()[0])

    def test_blank_fallback_reason_is_rejected(self):
        result, message = self.run_converter('--fallback-reason', '   ')
        self.assertEqual(2, result)
        self.assertIn('MINERU_REQUIRED', message)

    def test_release_carries_desk_skill_and_its_reference_without_global_install(self):
        files = BUILD.collect_package_files(ROOT, (ROOT / 'VERSION').read_text().strip())
        base = 'cyz-edu-research/references/mineru/'
        self.assertIn(base + 'SKILL.md', list(files))
        self.assertIn(base + 'references/desk-local.md', list(files))
        self.assertNotIn(base + 'scripts/mineru.py', files)
        entry = files[base + 'SKILL.md'].decode('utf-8')
        self.assertIn('Codex.ps1', entry)
        self.assertNotIn('D:/cyz', entry)
        lock = json.loads(files['cyz-edu-research/dependencies.lock.json'])
        mineru = next(item for item in lock['dependencies'] if item['name'] == 'mineru')
        self.assertFalse(mineru['installedSeparately'])
        self.assertTrue(mineru['deskInstalledSeparately'])


@unittest.skipUnless(importlib.util.find_spec('pypdf'), 'real PDF smoke requires pypdf')
class RealPdfRoutingTests(unittest.TestCase):
    def test_real_cli_blocks_implicit_fallback_and_records_explicit_reason(self):
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / 'synthetic.pdf'
            writer = PdfWriter()
            writer.add_blank_page(width=200, height=200)
            with pdf.open('wb') as handle:
                writer.write(handle)
            cache = root / 'cache'
            command = [sys.executable, str(CONVERT.__file__), str(pdf),
                       '--output-dir', str(cache), '--image-mode', 'none']
            def run(*extra):
                return subprocess.run(command + list(extra), capture_output=True,
                                      text=True, encoding='utf-8')
            blocked = run()
            self.assertEqual(2, blocked.returncode, blocked.stderr)
            self.assertIn('MINERU_REQUIRED', blocked.stderr)
            self.assertFalse(cache.exists())
            reason = 'Synthetic test: user explicitly selected native extraction'
            converted = run('--fallback-reason', reason)
            self.assertEqual(0, converted.returncode, converted.stderr)
            manifest = json.loads((cache / 'conversion_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(reason, manifest['local_fallback']['reason'])
            self.assertIn(reason, (cache / 'conversion_report.md').read_text(encoding='utf-8'))
            self.assertEqual([1], manifest['local_fallback']['unrecognized_pages'])
            reused = run()
            self.assertEqual(0, reused.returncode, reused.stderr)
            self.assertIn('CACHE_REUSED', reused.stdout)
            before = (cache / 'paper.md').read_bytes()
            forced = run('--force')
            self.assertEqual(2, forced.returncode)
            self.assertEqual(before, (cache / 'paper.md').read_bytes())


if __name__ == '__main__':
    unittest.main()
