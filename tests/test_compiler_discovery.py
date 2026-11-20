import subprocess
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import compiler_tools


class TestMSVCDiscovery(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(TemporaryDirectory())).resolve()
        self.locator = self.root / 'Microsoft Visual Studio/Installer/vswhere.exe'
        self.locator.parent.mkdir(parents=True)
        self.locator.touch()
        self.installation = self.root / 'VisualStudio'
        self.version_file = self.installation / 'VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt'
        self.version_file.parent.mkdir(parents=True)
        self.version_file.write_text('\ufeff14.44.35207\n', encoding='utf-8')
        self.compiler = self.installation / 'VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/cl.exe'
        self.compiler.parent.mkdir(parents=True)
        self.compiler.touch()
        stack.enter_context(patch.object(compiler_tools, 'os', SimpleNamespace(
            name='nt', environ={'ProgramFiles(x86)': str(self.root)})))
        self.which = stack.enter_context(patch.object(compiler_tools.shutil, 'which', return_value=None))
        self.run = stack.enter_context(patch.object(compiler_tools.subprocess, 'run', return_value=
            subprocess.CompletedProcess([], 0, str(self.installation) + '\n', '')))

    def test_path_compiler_has_priority_without_visual_studio_probe(self):
        self.which.return_value = 'configured-cl.exe'
        self.assertEqual(compiler_tools.find_msvc(), 'configured-cl.exe')
        self.run.assert_not_called()

    def test_default_toolset_is_found_through_installation_metadata(self):
        self.assertEqual(compiler_tools.find_msvc(), str(self.compiler))
        command = self.run.call_args.args[0]
        self.assertIn('-property', command)
        self.assertIn('installationPath', command)
        self.assertIn('Microsoft.VisualStudio.Component.VC.Tools.x86.x64', command)
        self.assertNotIn('-find', command)
        self.assertEqual(self.run.call_args.kwargs['timeout'], 10)

    def test_cold_start_timeout_retries_once_and_keeps_real_compiler_coverage(self):
        self.run.side_effect = [subprocess.TimeoutExpired('vswhere', 10), self.run.return_value]
        self.assertEqual(compiler_tools.find_msvc(), str(self.compiler))
        self.assertEqual(self.run.call_count, 2)

    def test_repeated_timeout_remains_a_failure_after_bounded_retry(self):
        self.run.side_effect = subprocess.TimeoutExpired('vswhere', 10)
        with self.assertRaises(subprocess.TimeoutExpired):
            compiler_tools.find_msvc()
        self.assertEqual(self.run.call_count, 2)

    def test_absent_locator_does_not_start_probe(self):
        self.locator.unlink()
        self.assertIsNone(compiler_tools.find_msvc())
        self.run.assert_not_called()

    def test_missing_or_failed_installation_lookup_is_unavailable(self):
        for result in (subprocess.CompletedProcess([], 0, '', ''), subprocess.CompletedProcess([], 1, '', 'failed')):
            with self.subTest(returncode=result.returncode):
                self.run.return_value = result
                self.assertIsNone(compiler_tools.find_msvc())

    def test_missing_default_toolset_metadata_is_unavailable(self):
        self.version_file.unlink()
        self.assertIsNone(compiler_tools.find_msvc())

    def test_missing_default_compiler_does_not_fall_back_to_recursive_search(self):
        self.compiler.unlink()
        self.assertIsNone(compiler_tools.find_msvc())
        self.assertEqual(self.run.call_count, 1)

    def test_non_windows_without_path_compiler_does_not_probe(self):
        compiler_tools.os.name = 'posix'
        self.assertIsNone(compiler_tools.find_msvc())
        self.run.assert_not_called()
