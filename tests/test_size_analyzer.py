import os
import shutil
import struct
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw.sandbox.size_analyzer import SizeAnalyzer
from compiler_tools import find_clang


class TestSizeAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = SizeAnalyzer()
        self.analyzer.size_tool = None

    def test_missing_artifact_raises_instead_of_reporting_zero(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                self.analyzer.analyze(Path(directory) / "missing.o")

    def test_real_macho_is_explicitly_unavailable_instead_of_miscounted(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest("Clang is required for Darwin object validation")
        with TemporaryDirectory() as directory:
            source = Path(directory) / "memory.c"
            obj = Path(directory) / "memory.o"
            source.write_text("unsigned char buffer[2048]; unsigned char data[256]={1}; "
                              "int read_memory(int i){return buffer[i&2047]+data[i&255];}")
            result = subprocess.run([compiler, "--target=x86_64-apple-darwin", "-std=c99", "-Os",
                                     "-c", str(source), "-o", str(obj)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.analyzer.size_tool = "size"
            with patch("aibenchmark_esw.sandbox.size_analyzer.subprocess.run") as size_run:
                with self.assertRaisesRegex(ValueError, "Mach-O memory measurement is unsupported"):
                    self.analyzer._measure_file(obj)
                size_run.assert_not_called()

    def test_unknown_external_column_layout_is_rejected(self):
        with TemporaryDirectory() as directory:
            obj = Path(directory) / "unknown.o"
            obj.write_bytes(b"unknown object")
            self.analyzer.size_tool = "size"
            for output in ("104 2304 0 0 2408 968\n", "100 20 30\n", "100 20 30 151 97 object\n"):
                with self.subTest(output=output), patch(
                        "aibenchmark_esw.sandbox.size_analyzer.subprocess.run",
                        return_value=subprocess.CompletedProcess([], 0, output, "")):
                    with self.assertRaises(ValueError):
                        self.analyzer._measure_file(obj)

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

    def elf_with_common_symbol(self, is_64, endian):
        header = bytearray(64 if is_64 else 52)
        header[:7] = b"\x7fELF" + bytes([2 if is_64 else 1, 1 if endian == "<" else 2, 1])
        section_fmt = endian + ("IIQQQQIIQQ" if is_64 else "IIIIIIIIII")
        section_size = struct.calcsize(section_fmt)
        struct.pack_into(endian + ("Q" if is_64 else "I"), header, 40 if is_64 else 32, len(header))
        struct.pack_into(endian + "HH", header, 58 if is_64 else 46, section_size, 5)
        symbol_fmt = endian + ("IBBHQQ" if is_64 else "IIIBBH")
        symbol_size = struct.calcsize(symbol_fmt)
        common = struct.pack(symbol_fmt, *( (1, 0x11, 0, 0xFFF2, 16, 2048) if is_64
                                           else (1, 16, 2048, 0x11, 0, 0xFFF2) ))
        symbols = bytes(symbol_size) + common
        names = b"\0buffer\0"
        data_start = len(header) + section_size * 5
        names_start, symbols_start = data_start + 256, data_start + 256 + len(names)
        sections = [
            (0, 0, 0, 0, 0),
            (1, 3, data_start, 256, 0),
            (3, 0, names_start, len(names), 0),
            (2, 0, symbols_start, len(symbols), symbol_size),
            (11, 0, symbols_start, len(symbols), symbol_size),
        ]
        table = b"".join(struct.pack(section_fmt, 0, kind, flags, 0, offset, size,
                                    2 if kind in (2, 11) else 0, 0, 1, stride)
                         for kind, flags, offset, size, stride in sections)
        return bytes(header) + table + bytes(256) + names + symbols

    def test_elf_common_symbols_count_once_across_symbol_tables(self):
        for is_64 in (False, True):
            for endian in ("<", ">"):
                with self.subTest(is_64=is_64, endian=endian):
                    self.assertEqual(self.analyzer._parse_elf(self.elf_with_common_symbol(is_64, endian)), (256, 2304))

    def test_malformed_elf_symbol_table_is_rejected(self):
        data = self.elf_with_common_symbol(True, "<")
        with self.assertRaisesRegex(ValueError, "symbol table"):
            self.analyzer._parse_elf(data[:-1])

    def test_real_elf_common_and_bss_reserve_equal_ram(self):
        compiler = find_clang()
        if compiler is None:
            self.skipTest("Clang is required for ELF common-symbol integration")
        with TemporaryDirectory() as directory:
            source = Path(directory) / "memory.c"
            source.write_text("unsigned char buffer[2048];\nunsigned char data[256] = {1};\n"
                              "int read_memory(int index) { return buffer[index & 2047] + data[index & 255]; }\n",
                              encoding="utf-8")
            for mode in ("-fcommon", "-fno-common"):
                with self.subTest(mode=mode):
                    obj = Path(directory) / f"{mode[2:]}.o"
                    compiled = subprocess.run([compiler, "--target=x86_64-unknown-linux-gnu", "-std=c99", "-Os", mode,
                                               "-c", str(source), "-o", str(obj)], capture_output=True, text=True,
                                              errors="backslashreplace", timeout=30)
                    self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                    self.assertEqual(self.analyzer._measure_file(obj)[1], 2304)

    def _coff_with_common_symbol(self):
        # An MSVC-style static .bss plus a tentative external definition.
        header = struct.pack("<HHIIIHH", 0x8664, 1, 0, 60, 3, 0, 0)
        section = struct.pack("<8sIIIIIIHHI", b".bss", 0, 0, 256, 0, 0, 0, 0, 0, 0xC0000080)
        section_symbol = struct.pack("<8sIhHBB", b".bss", 0, 1, 0, 3, 1)
        # Auxiliary section data must not be interpreted as a common symbol.
        auxiliary = struct.pack("<8sIhHBB", b"ignored", 9999, 0, 0, 2, 0)
        common = struct.pack("<8sIhHBB", b"buffer", 2048, 0, 0, 2, 0)
        return header + section + section_symbol + auxiliary + common

    def test_coff_common_symbols_contribute_to_ram(self):
        self.assertEqual(self.analyzer._parse_coff(self._coff_with_common_symbol(), 0), (0, 2304))

    def test_native_coff_common_count_is_not_overridden_by_size_tool(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "memory.obj"
            source.write_bytes(self._coff_with_common_symbol())
            self.analyzer.size_tool = "size"
            with patch("aibenchmark_esw.sandbox.size_analyzer.subprocess.run") as run:
                self.assertEqual(self.analyzer._measure_file(source), (0, 2304))
                run.assert_not_called()

    def test_invalid_coff_symbol_table_is_rejected(self):
        data = bytearray(self._coff_with_common_symbol())
        struct.pack_into("<I", data, 8, len(data) + 1)
        with self.assertRaisesRegex(ValueError, "symbol table"):
            self.analyzer._parse_coff(bytes(data), 0)

    @unittest.skipUnless(os.name == "nt", "MSVC object integration requires Windows")
    def test_real_msvc_common_and_static_bss_are_counted(self):
        compiler = shutil.which("cl")
        if compiler is None:
            vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
            if vswhere.is_file():
                discovery = subprocess.run([str(vswhere), "-latest", "-products", "*", "-find",
                                            "VC/Tools/MSVC/**/bin/Hostx64/x64/cl.exe"],
                                           capture_output=True, text=True, timeout=10)
                candidates = discovery.stdout.splitlines()
                if discovery.returncode == 0 and candidates:
                    compiler = candidates[-1]
        if compiler is None:
            self.skipTest("MSVC is not installed")
        for declaration in ("unsigned char buffer[2048];", "static volatile unsigned char buffer[2048];"):
            with self.subTest(declaration=declaration), TemporaryDirectory() as directory:
                source = Path(directory) / "memory.c"
                object_file = Path(directory) / "memory.obj"
                source.write_text(declaration + "\nunsigned char data[256] = {1};\n"
                                  "int read_memory(int index) { return buffer[index & 2047] + data[index & 255]; }\n",
                                  encoding="utf-8")
                compiled = subprocess.run([compiler, "/nologo", "/TC", "/O1", "/c", str(source),
                                           f"/Fo{object_file}"], cwd=directory,
                                          capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
                flash, ram = self.analyzer._measure_file(object_file)
                self.assertGreaterEqual(flash, 256)
                self.assertEqual(ram, 2304)

    def test_size_tool_finds_numbers_after_preamble_and_localized_header(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "unsupported.o"
            source.write_bytes(b"format handled by external size tool")
            self.analyzer.size_tool = "size"
            stdout = "Notice: tool output\n\n코드 데이터 BSS 합계 파일\n\n 100 20 30 150 96 unsupported.o\n"
            with patch("aibenchmark_esw.sandbox.size_analyzer.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 0, stdout, "")):
                self.assertEqual(self.analyzer._measure_file(source), (120, 50))


if __name__ == "__main__":
    unittest.main()
