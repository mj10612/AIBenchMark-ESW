import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer


class TestSizeAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = SizeAnalyzer()
        self.analyzer.size_tool = None

    def test_missing_artifact_raises_instead_of_reporting_zero(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                self.analyzer.analyze(Path(directory) / "missing.o")

    def test_unknown_format_is_not_estimated(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bad.o"
            path.write_bytes(b"not an object file")
            with self.assertRaises(ValueError):
                self.analyzer.analyze(path)

    def test_elf_counts_allocated_sections_and_initialized_data(self):
        for is_64, endian in [(True, "<"), (False, ">")]:
            with self.subTest(is_64=is_64, endian=endian):
                header = bytearray(64 if is_64 else 52)
                header[:6] = b"\x7fELF" + bytes([2 if is_64 else 1, 1 if endian == "<" else 2])
                fmt = endian + ("IIQQQQIIQQ" if is_64 else "IIIIIIIIII")
                section_size = struct.calcsize(fmt)
                struct.pack_into(endian + ("Q" if is_64 else "I"), header, 40 if is_64 else 32, len(header))
                struct.pack_into(endian + "HH", header, 58 if is_64 else 46, section_size, 5)
                sections = b"".join(struct.pack(fmt, 0, kind, flags, 0, 0, size, 0, 0, 1, 0)
                                    for kind, flags, size in [(1, 6, 100), (1, 2, 20), (1, 3, 12), (8, 3, 30), (1, 0, 500)])
                self.assertEqual(self.analyzer._parse_elf(bytes(header) + sections), (132, 42))

    def test_coff_counts_read_only_and_writable_data_without_invented_ram(self):
        header = struct.pack("<HHIIIHH", 0x8664, 4, 0, 0, 0, 0, 0)
        sections = b"".join(struct.pack("<8sIIIIIIHHI", name, 0, 0, size, 0, 0, 0, 0, 0, flags)
                            for name, size, flags in [(b".text", 100, 0x60000020),
                                                     (b".rdata", 20, 0x40000040),
                                                     (b".data", 12, 0xC0000040),
                                                     (b".bss", 30, 0xC0000080)])
        self.assertEqual(self.analyzer._parse_coff(header + sections, 0), (132, 42))
        only_code = struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 0, 0) + sections[:40]
        self.assertEqual(self.analyzer._parse_coff(only_code, 0), (100, 0))


if __name__ == "__main__":
    unittest.main()
