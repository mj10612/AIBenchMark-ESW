import csv
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aibenchmark_esw.metrics.comparison import render_comparison
from aibenchmark_esw.report_io import atomic_write_text


class TestAtomicTextReports(unittest.TestCase):
    def test_temporary_windows_reader_lock_retries_without_partial_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            path.write_text("original", encoding="utf-8")
            replace = os.replace
            error = PermissionError("temporarily shared by a Windows reader")
            error.winerror = 32
            calls = []
            def transient(source, destination):
                calls.append(source)
                if len(calls) == 1:
                    self.assertEqual(path.read_text(), "original")
                    raise error
                return replace(source, destination)
            with patch("aibenchmark_esw.report_io.os.replace", side_effect=transient):
                atomic_write_text(path, "complete replacement")
            self.assertEqual(path.read_text(), "complete replacement")
            self.assertEqual(len(calls), 2)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_csv_export_has_no_translated_double_carriage_returns(self):
        data = {"models": [{"model": 'model,"quoted"', "score": 1}], "warnings": []}
        rendered = render_comparison(data, "csv")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.csv"
            atomic_write_text(path, rendered)
            self.assertNotIn(b"\r", path.read_bytes())
            rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
            self.assertEqual(rows, [{"model": 'model,"quoted"', "score": "1"}])
        # The same LF-only string also survives Windows stdout translation once.
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="utf-8", newline="\r\n")
        stream.write(rendered)
        stream.flush()
        self.assertNotIn(b"\r\r\n", buffer.getvalue())

    def test_replace_failure_preserves_original_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.md"
            path.write_text("original", encoding="utf-8")
            with patch("aibenchmark_esw.report_io.os.replace", side_effect=OSError("cannot replace")):
                with self.assertRaises(OSError):
                    atomic_write_text(path, "new content")
            self.assertEqual(path.read_text(encoding="utf-8"), "original")
            self.assertEqual(list(Path(directory).iterdir()), [path])
