import shutil
import struct
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from aibenchmark_esw.models import SizeMetrics


class UnsupportedBinaryFormat(ValueError):
    pass


class SizeAnalyzer:
    def __init__(self, size_tool: Optional[str] = None):
        self.size_tool = size_tool or shutil.which("size")

    def analyze(self, binary_path: Path, ref_binary_path: Optional[Path] = None) -> SizeMetrics:
        flash, ram = self._measure_file(binary_path)
        ref_flash, ref_ram = self._measure_file(ref_binary_path) if ref_binary_path is not None else (0, 0)
        return SizeMetrics(flash, ram, ref_flash, ref_ram, measured=ref_binary_path is not None)

    def _measure_file(self, file_path: Path) -> Tuple[int, int]:
        if not file_path.is_file():
            raise FileNotFoundError(f"Memory measurement artifact not found: {file_path}")
        # Native object parsing includes common symbols, which the default GNU
        # size summary can omit. Never let a tool summary override those counts.
        try:
            return self._parse_binary_sections(file_path)
        except UnsupportedBinaryFormat:
            pass
        except (struct.error, IndexError) as error:
            raise ValueError(f"Malformed memory measurement artifact: {file_path}") from error
        if self.size_tool:
            try:
                proc = subprocess.run([self.size_tool, str(file_path)], capture_output=True,
                                      text=True, timeout=5)
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        parts = line.split()
                        # Accept only a Berkeley/GNU text,data,bss,dec,hex,file
                        # row. Other layouts (notably Mach-O segment totals)
                        # cannot be interpreted using this accounting policy.
                        if len(parts) < 6:
                            continue
                        try:
                            text, data, bss = map(int, parts[:3])
                            total, hexadecimal = int(parts[3]), int(parts[4], 16)
                        except ValueError:
                            continue
                        if min(text, data, bss) >= 0 and total == hexadecimal == text + data + bss:
                            return text + data, data + bss
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
        raise UnsupportedBinaryFormat(f"Unsupported binary format: {file_path}")

    def _parse_binary_sections(self, file_path: Path) -> Tuple[int, int]:
        data = file_path.read_bytes()
        if data[:4] in (b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
                        b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
                        b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
                        b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"):
            raise ValueError("Mach-O memory measurement is unsupported: segment totals do not distinguish zero-filled RAM from Flash")
        if data.startswith(b"\x7fELF"):
            return self._parse_elf(data)
        if data.startswith(b"MZ"):
            pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
            if data[pe_offset:pe_offset + 4] != b"PE\0\0":
                raise ValueError("Invalid PE signature")
            return self._parse_coff(data, pe_offset + 4, image=True)
        if len(data) >= 20 and struct.unpack_from("<H", data)[0] in (0x014C, 0x8664, 0xAA64):
            return self._parse_coff(data, 0)
        raise UnsupportedBinaryFormat("Unsupported binary format; memory usage cannot be estimated reliably")

    def _parse_coff(self, data: bytes, header: int, image: bool = False) -> Tuple[int, int]:
        count = struct.unpack_from("<H", data, header + 2)[0]
        optional_size = struct.unpack_from("<H", data, header + 16)[0]
        start = header + 20 + optional_size
        flash = ram = 0
        for index in range(count):
            section = start + index * 40
            virtual_size = struct.unpack_from("<I", data, section + 8)[0]
            raw_size = struct.unpack_from("<I", data, section + 16)[0]
            flags = struct.unpack_from("<I", data, section + 36)[0]
            size = virtual_size if image else raw_size
            if flags & 0x00000800 or flags & 0x02000000:
                continue
            if flags & 0x00000020:
                flash += size
            elif flags & 0x00000040:
                flash += size
                if flags & 0x80000000:
                    ram += size
            elif flags & 0x00000080:
                ram += size
        if not image:
            # MSVC can represent tentative external definitions as common
            # symbols instead of .bss sections. Their Value field is their size.
            symbol_offset, symbol_count = struct.unpack_from("<II", data, header + 8)
            if symbol_count and (not symbol_offset or symbol_offset + symbol_count * 18 > len(data)):
                raise ValueError("Invalid COFF symbol table")
            index = 0
            while index < symbol_count:
                entry = symbol_offset + index * 18
                value, section, _, storage, auxiliaries = struct.unpack_from("<IhHBB", data, entry + 8)
                if storage == 2 and section == 0 and value > 0:
                    ram += value
                index += 1 + auxiliaries
                if index > symbol_count:
                    raise ValueError("Invalid COFF auxiliary symbol count")
        return flash, ram

    def _parse_elf(self, data: bytes) -> Tuple[int, int]:
        if data[4] not in (1, 2) or data[5] not in (1, 2):
            raise ValueError("Unsupported ELF class or byte order")
        is_64 = data[4] == 2
        endian = "<" if data[5] == 1 else ">"
        if is_64:
            offset = struct.unpack_from(endian + "Q", data, 40)[0]
            entry_size, count = struct.unpack_from(endian + "HH", data, 58)
            fmt = endian + "IIQQQQIIQQ"
        else:
            offset = struct.unpack_from(endian + "I", data, 32)[0]
            entry_size, count = struct.unpack_from(endian + "HH", data, 46)
            fmt = endian + "IIIIIIIIII"
        if entry_size < struct.calcsize(fmt):
            raise ValueError("Invalid ELF section header size")
        if count == 0 and offset:
            count = struct.unpack_from(fmt, data, offset)[5]
        flash = ram = 0
        sections = []
        for index in range(count):
            section = struct.unpack_from(fmt, data, offset + index * entry_size)
            sections.append(section)
            kind, flags, size = section[1], section[2], section[5]
            if not flags & 0x2:
                continue
            if kind == 8:
                ram += size
            else:
                flash += size
                if flags & 0x1:
                    ram += size
        common: dict = {}
        symbol_fmt = endian + ("IBBHQQ" if is_64 else "IIIBBH")
        symbol_size = struct.calcsize(symbol_fmt)
        for section_index, section in enumerate(sections):
            if section[1] not in (2, 11):  # SHT_SYMTAB / SHT_DYNSYM
                continue
            start, size, link, stride = section[4], section[5], section[6], section[9]
            if (stride < symbol_size or size % stride or start + size > len(data)
                    or link >= len(sections) or sections[link][1] != 3):
                raise ValueError("Invalid ELF symbol table")
            strings = sections[link]
            if strings[4] + strings[5] > len(data):
                raise ValueError("Invalid ELF string table")
            names = data[strings[4]:strings[4] + strings[5]]
            for symbol_index, position in enumerate(range(start, start + size, stride)):
                symbol = struct.unpack_from(symbol_fmt, data, position)
                name = symbol[0]
                index, allocated = (symbol[3], symbol[5]) if is_64 else (symbol[5], symbol[2])
                if index != 0xFFF2:  # SHN_COMMON reserves RAM outside sections
                    continue
                if name >= len(names):
                    raise ValueError("Invalid ELF common symbol name")
                end = names.find(b"\0", name)
                if end == -1:
                    raise ValueError("Unterminated ELF common symbol name")
                key = names[name:end] if name else (section_index, symbol_index)
                # A symbol may be exposed through more than one symbol table.
                common[key] = max(common.get(key, 0), allocated)
        return flash, ram + sum(common.values())
