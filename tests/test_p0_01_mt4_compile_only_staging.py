"""Offline-only test suite for staging a source file without MT4 interaction."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.stage_mt4_compile_only import (
    MQ4_NAME, ROOT, SOURCE, stage_compile_only, staging_location_allowed,
)


class Mt4CompileOnlyStagingTests(unittest.TestCase):
    def test_source_is_staged_identically_outside_repo(self):
        with tempfile.TemporaryDirectory(prefix="fx-metaeditor-staging-") as folder:
            dest = Path(folder) / "CompileOnly"
            status = stage_compile_only(dest)
            self.assertTrue(status.startswith("STAGED:"), status)
            self.assertEqual((dest / MQ4_NAME).read_bytes(), SOURCE.read_bytes())
            self.assertFalse((dest / MQ4_NAME).with_suffix(".ex4").exists())

    def test_staging_never_overwrites_existing_source(self):
        with tempfile.TemporaryDirectory(prefix="fx-metaeditor-staging-") as folder:
            dest = Path(folder) / "CompileOnly"
            dest.mkdir()
            old = dest / MQ4_NAME
            old.write_text("Private / edited local copy, do not replace",
                           encoding="utf-8")
            before = old.read_bytes()
            self.assertIn("SOURCE_ALREADY_STAGED", stage_compile_only(dest))
            self.assertEqual(before, old.read_bytes())

    def test_staging_rejects_repository_root_and_child(self):
        self.assertFalse(staging_location_allowed(ROOT))
        self.assertFalse(staging_location_allowed(ROOT / "mt4" / "read_only"))
        self.assertIn("DESTINATION_INSIDE_GIT_OR_MT4_LOCATION",
                      stage_compile_only(ROOT))

    def test_staging_rejects_metaquotes_and_terminal_script_locations(self):
        with tempfile.TemporaryDirectory(prefix="fx-metaeditor-staging-") as folder:
            root = Path(folder)
            for relative in (
                "MetaQuotes/Terminal/AAA/MQL4/Scripts",
                "MT4/MQL4/Scripts",
                "Terminal/Experts",
                "MQL4",
            ):
                with self.subTest(path=relative):
                    loc = root / relative
                    self.assertFalse(staging_location_allowed(loc))
                    self.assertIn("BLOCKED:", stage_compile_only(loc))
                    self.assertFalse((loc / MQ4_NAME).exists())

    def test_staging_contains_no_terminal_launch_or_build_automation(self):
        text = (ROOT / "scripts/stage_mt4_compile_only.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("subprocess", text)
        self.assertNotIn("os.system", text)
        self.assertNotIn("Start-Process", text)
        self.assertNotIn("ShellExecute", text)
        self.assertNotIn("metaeditor.exe", text)
        self.assertNotIn("terminal.exe", text)

    def test_module_entrypoint_only_stages_source(self):
        with tempfile.TemporaryDirectory(prefix="fx-metaeditor-staging-") as folder:
            dest = Path(folder) / "CompileOnly"
            result = subprocess.run(
                [sys.executable, "-m", "scripts.stage_mt4_compile_only",
                 "--output-dir", str(dest)], cwd=ROOT,
                check=False, text=True, capture_output=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("NO_COMPILE_ATTEMPTED", result.stdout)
            self.assertTrue((dest / MQ4_NAME).exists())

    def test_direct_entrypoint_only_stages_source(self):
        with tempfile.TemporaryDirectory(prefix="fx-metaeditor-staging-") as folder:
            dest = Path(folder) / "CompileOnly"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/stage_mt4_compile_only.py"),
                 "--output-dir", str(dest)], cwd=ROOT, check=False, text=True,
                capture_output=True, timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("NO_COMPILE_ATTEMPTED", result.stdout)
            self.assertTrue((dest / MQ4_NAME).exists())


if __name__ == "__main__":
    unittest.main()
