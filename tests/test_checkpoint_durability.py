import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from aibenchmark_esw import report_io


class TestCheckpointDurability(unittest.TestCase):
    def test_parent_directory_is_synced_after_replace(self):
        events = []
        original_fsync, original_replace = os.fsync, os.replace
        fake_os = Mock(wraps=os)
        fake_os.name = "posix"
        fake_os.O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
        fake_os.O_RDONLY = os.O_RDONLY
        fake_os.open.side_effect = lambda *args: events.append("directory-open") or 987654
        fake_os.close.side_effect = lambda *args: events.append("directory-close")
        def fsync(fd):
            if fd == 987654:
                events.append("directory-fsync")
            else:
                events.append("file-fsync")
                original_fsync(fd)
        def replace(before, after):
            events.append("replace")
            original_replace(before, after)
        fake_os.fsync.side_effect = fsync
        fake_os.replace.side_effect = replace
        with TemporaryDirectory() as directory, patch.object(report_io, "os", fake_os):
            output = Path(directory) / "run.json"
            report_io.atomic_write_json(output, {"complete": True})
            self.assertIn('"complete": true', output.read_text())
        self.assertEqual(events, ["file-fsync", "replace", "directory-open", "directory-fsync", "directory-close"])

    @unittest.skipUnless(os.name == "posix", "real directory fsync is POSIX")
    def test_actual_posix_directory_fsync_and_replacement(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "run.json"
            report_io.atomic_write_json(output, {"value": 1})
            report_io.atomic_write_json(output, {"value": 2})
            self.assertIn('"value": 2', output.read_text())
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])
