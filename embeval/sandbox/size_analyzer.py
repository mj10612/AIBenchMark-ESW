import os
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from embeval.models import SizeMetrics


class SizeAnalyzer:
    def __init__(self, size_tool: Optional[str] = None):
        self.size_tool = size_tool or shutil.which("size")

    def analyze(self, binary_path: Path, ref_binary_path: Optional[Path] = None) -> SizeMetrics:
        """
        Measures Flash (code + read-only data) and RAM (initialized data + bss).
        """
        flash, ram = self._measure_file(binary_path)
        ref_flash, ref_ram = (0, 0)
        if ref_binary_path and ref_binary_path.exists():
            ref_flash, ref_ram = self._measure_file(ref_binary_path)

        return SizeMetrics(
            flash_bytes=flash,
            ram_bytes=ram,
            ref_flash_bytes=ref_flash,
            ref_ram_bytes=ref_ram,
        )

    def _measure_file(self, file_path: Path) -> Tuple[int, int]:
        if not file_path.exists():
            return 0, 0

        # Attempt 1: Using GNU 'size' tool if available
        if self.size_tool:
            try:
                proc = subprocess.run(
                    [self.size_tool, str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if proc.returncode == 0:
                    lines = proc.stdout.strip().splitlines()
                    if len(lines) >= 2:
                        parts = lines[1].split()
                        if len(parts) >= 3:
                            text = int(parts[0])
                            data = int(parts[1])
                            bss = int(parts[2])
                            flash = text + data
                            ram = data + bss
                            return flash, ram
            except Exception:
                pass

        # Attempt 2: Direct PE/COFF or ELF section parser
        try:
            return self._parse_binary_sections(file_path)
        except Exception:
            # Fallback: file size estimation
            fsize = file_path.stat().st_size
            return fsize, max(32, fsize // 10)

    def _parse_binary_sections(self, file_path: Path) -> Tuple[int, int]:
        with open(file_path, "rb") as f:
            data = f.read()

        # Check for ELF magic (0x7F 'E' 'L' 'F')
        if data.startswith(b"\x7fELF"):
            return self._parse_elf(data)

        # Check for DOS/PE header (MZ)
        if data.startswith(b"MZ"):
            return self._parse_pe(data)

        # Default fallback
        size = len(data)
        return size, 64

    def _parse_pe(self, data: bytes) -> Tuple[int, int]:
        # PE header offset is at 0x3C
        if len(data) < 0x40:
            return len(data), 64
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_offset + 24 > len(data):
            return len(data), 64

        magic = data[pe_offset:pe_offset+4]
        if magic != b"PE\x00\x00":
            return len(data), 64

        num_sections = struct.unpack_from("<H", data, pe_offset + 6)[0]
        opt_hdr_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
        section_start = pe_offset + 24 + opt_hdr_size

        flash_size = 0
        ram_size = 0

        for i in range(num_sections):
            sec_offset = section_start + i * 40
            if sec_offset + 40 > len(data):
                break
            name = data[sec_offset:sec_offset+8].rstrip(b"\x00").decode("latin1", errors="ignore").lower()
            virt_size = struct.unpack_from("<I", data, sec_offset + 8)[0]
            raw_size = struct.unpack_from("<I", data, sec_offset + 16)[0]
            sec_size = max(virt_size, raw_size)

            if ".text" in name or ".rdata" in name or "code" in name:
                flash_size += sec_size
            elif ".data" in name or ".bss" in name:
                ram_size += sec_size

        if flash_size == 0:
            flash_size = min(len(data), 1024)
        if ram_size == 0:
            ram_size = 64

        return flash_size, ram_size

    def _parse_elf(self, data: bytes) -> Tuple[int, int]:
        is_64 = (data[4] == 2)
        endian = "<" if data[5] == 1 else ">"

        if is_64:
            sh_offset = struct.unpack_from(f"{endian}Q", data, 40)[0]
            sh_size = struct.unpack_from(f"{endian}H", data, 58)[0]
            sh_num = struct.unpack_from(f"{endian}H", data, 60)[0]
            sh_strndx = struct.unpack_from(f"{endian}H", data, 62)[0]
        else:
            sh_offset = struct.unpack_from(f"{endian}I", data, 32)[0]
            sh_size = struct.unpack_from(f"{endian}H", data, 46)[0]
            sh_num = struct.unpack_from(f"{endian}H", data, 48)[0]
            sh_strndx = struct.unpack_from(f"{endian}H", data, 50)[0]

        # Extract string table
        str_tab_offset = 0
        if sh_strndx < sh_num:
            entry = sh_offset + sh_strndx * sh_size
            if is_64:
                str_tab_offset = struct.unpack_from(f"{endian}Q", data, entry + 24)[0]
            else:
                str_tab_offset = struct.unpack_from(f"{endian}I", data, entry + 16)[0]

        flash_size = 0
        ram_size = 0

        for i in range(sh_num):
            entry = sh_offset + i * sh_size
            if is_64:
                name_idx = struct.unpack_from(f"{endian}I", data, entry)[0]
                size = struct.unpack_from(f"{endian}Q", data, entry + 32)[0]
            else:
                name_idx = struct.unpack_from(f"{endian}I", data, entry)[0]
                size = struct.unpack_from(f"{endian}I", data, entry + 20)[0]

            name = ""
            if str_tab_offset and (str_tab_offset + name_idx < len(data)):
                end = data.find(b"\x00", str_tab_offset + name_idx)
                if end != -1:
                    name = data[str_tab_offset + name_idx:end].decode("latin1", errors="ignore")

            if name in [".text", ".rodata"]:
                flash_size += size
            elif name in [".data", ".bss"]:
                ram_size += size

        return flash_size, ram_size
