"""Reproducible task authoring overlays; public assets are never called hidden."""

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from typing import Any, Dict

VARIANT_VERSION = "crc-polynomial-v1"


def _crc(data, polynomial):
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            value = ((value << 1) ^ (polynomial if value & 0x8000 else 0)) & 0xFFFF
    return value


def _crc_variant(task, seed):
    digest = hashlib.sha256(f"{VARIANT_VERSION}:{seed}:{task.id}".encode()).digest()
    polynomial = (int.from_bytes(digest[:2], "big") | 0x8001)
    old = {0x29B1: _crc(b"123456789", polynomial),
           0x84C0: _crc(bytes(4), polynomial), 0x1D0F: _crc(bytes([255] * 4), polynomial)}
    for folder in ("src", "reference", "tests", "include"):
        for path in sorted((task.task_dir / folder).glob("*")):
            if path.suffix not in (".c", ".h"):
                continue
            source = path.read_text(encoding="utf-8")
            source = re.sub(r"0x1021(?=[uUlL]*\b)", f"0x{polynomial:04X}", source, flags=re.IGNORECASE)
            source = re.sub(r"0x(?:29B1|84C0|1D0F)\b",
                            lambda match: f"0x{old[int(match.group(), 16)]:04X}", source, flags=re.IGNORECASE)
            path.write_text(source, encoding="utf-8")
    prompt = task.prompt + f"\nEvaluation variant: use CRC polynomial 0x{polynomial:04X} instead of 0x1021; init remains 0xFFFF, no reflection, no final XOR.\n"
    (task.task_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    return replace(task, prompt=prompt), {"polynomial": polynomial}


@contextmanager
def prepare_task_variants(tasks, variant_seed=None, heldout_tests=None):
    """Yield (tasks, evidence); temporary asset paths live for the whole context.

    Held-out root layout is TASK_ID/tests/test_*.c. A present task overlay
    replaces its whole tests directory, preserving public prompt/API assets.
    A seed changes CRC parameters only; evidence records this explicit scope.
    """
    tasks = list(tasks)
    if variant_seed is not None and (isinstance(variant_seed, bool) or not isinstance(variant_seed, int)):
        raise ValueError("variant_seed must be an integer")
    overlay = Path(heldout_tests).resolve() if heldout_tests is not None else None
    supplied = {}
    heldout_digest = hashlib.sha256()
    if overlay is not None:
        if not overlay.is_dir():
            raise ValueError("heldout_tests must be a directory")
        ids = {task.id for task in tasks}
        for entry in sorted(overlay.iterdir()):
            if not entry.is_dir() or entry.is_symlink() or entry.name not in ids:
                raise ValueError(f"Unknown or unsafe held-out task overlay: {entry.name}")
            tests = entry / "tests"
            if not tests.is_dir() or tests.is_symlink() or not list(tests.glob("test_*.c")):
                raise ValueError(f"Held-out task {entry.name} requires tests/test_*.c")
            for path in sorted(tests.rglob("*")):
                if path.is_symlink():
                    raise ValueError("Held-out assets cannot be symlinks")
                if path.is_file():
                    relative = path.relative_to(overlay).as_posix().encode()
                    content = path.read_bytes()
                    heldout_digest.update(len(relative).to_bytes(8, "big") + relative)
                    heldout_digest.update(len(content).to_bytes(8, "big") + content)
            supplied[entry.name] = tests
        if not supplied:
            raise ValueError("heldout_tests contains no task suites")
    evidence: Dict[str, Any] = {"variant_version": VARIANT_VERSION, "variant_seed": variant_seed,
                "heldout_tests_used": bool(supplied),
                "heldout_sha256": heldout_digest.hexdigest() if supplied else None,
                "variant_parameters": {}}
    if variant_seed is None and not supplied:
        yield tasks, evidence
        return
    with TemporaryDirectory(prefix="aibenchmark_variants_") as directory:
        prepared = []
        for task in tasks:
            destination = Path(directory) / task.id
            shutil.copytree(task.task_dir, destination)
            current = replace(task, task_dir=destination)
            if variant_seed is not None:
                if task.id == "tier1_crc16":
                    current, parameters = _crc_variant(current, variant_seed)
                    evidence["variant_parameters"][task.id] = parameters
                # Even unchanged tasks record seed identity in their task asset
                # fingerprint; provenance can distinguish authoring conditions.
                metadata_path = destination / "task.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["variant"] = {"version": VARIANT_VERSION, "seed": variant_seed}
                metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            if task.id in supplied:
                shutil.rmtree(destination / "tests")
                shutil.copytree(supplied[task.id], destination / "tests")
            prepared.append(current)
        yield prepared, evidence


def reference_similarity(candidate, reference):
    """Exact normalized token match is a warning, never evidence of memorization.

    Preserve string/character literals, unlike mask_noncode, and remove only
    comments and spacing. Different algorithms are not scored for similarity.
    """
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\r\n]*|[A-Za-z_]\w*|\d+(?:\.\d+)?|>>=|<<=|==|!=|<=|>=|->|\+\+|--|&&|\|\||[^\s]'
    def tokens(source):
        return tuple(token for token in re.findall(pattern, source, re.DOTALL)
                     if not token.startswith(("/*", "//")))
    return bool(candidate and reference and tokens(candidate) == tokens(reference))
