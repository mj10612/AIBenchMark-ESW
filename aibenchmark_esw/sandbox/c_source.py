"""Mask C comments and literals while preserving token boundaries."""

import re


_NONCODE = re.compile(r"""//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'""", re.DOTALL)


def mask_noncode(source: str) -> str:
    # Translation phase 2 removes escaped newlines before comment recognition.
    logical = re.sub(r"\\\r?\n", "", source)
    return _NONCODE.sub(lambda match: re.sub(r"[^\n]", " ", match.group()), logical)
