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
            return self._parse_macho(data)
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

    def _parse_macho(self, data: bytes) -> Tuple[int, int]:
        """Account relocatable Mach-O sections and common symbols, never segments.

        Universal objects have no single deployment footprint: return the
        componentwise maximum over slices, a conservative portable budget.
        Debug sections are excluded; allocated unwind sections consume Flash
        just as allocated ELF unwind sections do.
        """
        magic = data[:4]
        fat = magic in (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")
        if fat:
            endian = ">" if magic[:1] == b"\xca" else "<"
            wide = magic in (b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca")
            count = struct.unpack_from(endian + "I", data, 4)[0]
            stride, fmt = (32, endian + "IIQQII") if wide else (20, endian + "IIIII")
            if not count or count > (len(data) - 8) // stride:
                raise ValueError("Invalid Mach-O fat architecture table")
            footprints = []
            intervals: list = []
            for index in range(count):
                entry = struct.unpack_from(fmt, data, 8 + index * stride)
                offset, size = entry[2:4]
                if offset < 8 + count * stride or not size or offset + size > len(data):
                    raise ValueError("Invalid Mach-O fat slice bounds")
                if any(offset < end and offset + size > start for start, end in intervals):
                    raise ValueError("Overlapping Mach-O fat slices")
                intervals.append((offset, offset + size))
                if data[offset:offset + 4] in (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"):
                    raise ValueError("Nested Mach-O fat object")
                footprints.append(self._parse_macho(data[offset:offset + size]))
            return max(x[0] for x in footprints), max(x[1] for x in footprints)
        if magic not in (b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe"):
            raise ValueError("Invalid Mach-O object magic")
        endian = ">" if magic[:1] == b"\xfe" else "<"
        wide = magic in (b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe")
        _, _, _, filetype, count, commands_size, _ = struct.unpack_from(endian + "7I", data)
        if filetype != 1:
            raise ValueError("Mach-O footprint requires MH_OBJECT, not a linked image")
        header_size = 32 if wide else 28
        limit = header_size + commands_size
        if limit > len(data) or count > commands_size // 8:
            raise ValueError("Invalid Mach-O load command bounds")
        position = header_size
        flash = ram = 0
        symbols = []
        for _ in range(count):
            command, length = struct.unpack_from(endian + "II", data, position)
            if length < 8 or position + length > limit:
                raise ValueError("Invalid Mach-O load command size")
            if command in (1, 0x19):  # LC_SEGMENT / LC_SEGMENT_64
                segment_wide = command == 0x19
                segment_size, section_size = (72, 80) if segment_wide else (56, 68)
                if length < segment_size:
                    raise ValueError("Truncated Mach-O segment")
                nsections = struct.unpack_from(endian + "I", data, position + (64 if segment_wide else 48))[0]
                if segment_size + nsections * section_size > length:
                    raise ValueError("Invalid Mach-O section table")
                for index in range(nsections):
                    section = position + segment_size + index * section_size
                    name, segment = struct.unpack_from("16s16s", data, section)
                    name, segment = name.rstrip(b"\0"), segment.rstrip(b"\0")
                    size = struct.unpack_from(endian + ("Q" if segment_wide else "I"), data,
                                              section + (40 if segment_wide else 36))[0]
                    offset = struct.unpack_from(endian + "I", data, section + (48 if segment_wide else 40))[0]
                    flags = struct.unpack_from(endian + "I", data, section + (64 if segment_wide else 56))[0]
                    kind = flags & 0xff
                    zerofill = kind in (1, 0xc, 0x12)
                    if not zerofill and offset + size > len(data):
                        raise ValueError("Invalid Mach-O section data bounds")
                    if flags & 0x02000000 or segment == b"__DWARF":
                        continue
                    if zerofill:
                        ram += size
                    else:
                        flash += size
                        # Instructions and __TEXT constants consume Flash only;
                        # object __DATA/__DATA_CONST needs initialization RAM.
                        if segment != b"__TEXT" and not flags & (0x80000000 | 0x400):
                            ram += size
            elif command == 2:  # LC_SYMTAB
                if length < 24:
                    raise ValueError("Truncated Mach-O symbol command")
                symbols.append(struct.unpack_from(endian + "IIII", data, position + 8))
            position += length
        if position != limit:
            raise ValueError("Inconsistent Mach-O load command count")
        common: dict = {}
        stride, fmt = (16, endian + "IBBHQ") if wide else (12, endian + "IBBHI")
        for offset, count, strings_offset, strings_size in symbols:
            if offset + count * stride > len(data) or strings_offset + strings_size > len(data):
                raise ValueError("Invalid Mach-O symbol table bounds")
            names = data[strings_offset:strings_offset + strings_size]
            for index in range(count):
                name, kind, section, _, value = struct.unpack_from(fmt, data, offset + index * stride)
                if kind & 0xe0 or kind & 0x0e or not kind & 1 or section or not value:
                    continue
                if name >= len(names) or names.find(b"\0", name) < 0:
                    raise ValueError("Invalid Mach-O common symbol name")
                key = names[name:names.find(b"\0", name)]
                common[key] = max(common.get(key, 0), value)
        return flash, ram + sum(common.values())

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
