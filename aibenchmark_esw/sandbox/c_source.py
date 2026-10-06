"""Mask C non-code and literal inactive branches without expanding macros.

Unknown preprocessor conditions remain visible in both branches. This is not a
replacement for the compiler's preprocessor.
"""

import re


def _mask_line(line, in_comment):
    result = list(line)
    index = 0
    while index < len(line):
        if in_comment:
            closing = line.find("*/", index)
            end = len(line) if closing < 0 else closing + 2
            in_comment = closing < 0
        elif line.startswith("/*", index):
            in_comment = True
            continue
        elif line.startswith("//", index):
            end = len(line)
        elif line[index] in "\"'":
            quote = line[index]
            end = index + 1
            while end < len(line) and line[end] not in "\r\n":
                if line[end] == "\\":
                    end += 2
                elif line[end] == quote:
                    end += 1
                    break
                else:
                    end += 1
            end = min(end, len(line))
        else:
            index += 1
            continue
        for position in range(index, end):
            if result[position] not in "\r\n":
                result[position] = " "
        index = end
    return "".join(result), in_comment


def _constant_condition(expression):
    value = expression.strip().strip("() ")
    if re.fullmatch(r"[01][uUlL]*", value):
        return value[0] == "1"
    return None


def mask_noncode(source: str) -> str:
    # Translation phase 2 precedes comment recognition.
    logical = re.sub(r"\\\r?\n", "", source)
    output, stack = [], []
    active, in_comment = True, False
    for line in logical.splitlines(keepends=True):
        masked, in_comment = _mask_line(line, in_comment)
        directive = re.match(r"\s*#\s*(\w+)\b(.*)", masked)
        if directive:
            name, expression = directive.groups()
            if name in ("if", "ifdef", "ifndef"):
                condition = _constant_condition(expression) if name == "if" else None
                stack.append([active, condition])
                active = active and condition is not False
            elif name in ("else", "elif") and stack:
                parent, taken = stack[-1]
                condition = True if name == "else" else _constant_condition(expression)
                active = bool(parent) and taken is not True and condition is not False
                if taken is True or condition is True:
                    stack[-1][1] = True
                elif taken is None or condition is None:
                    stack[-1][1] = None
            elif name == "endif" and stack:
                active = bool(stack.pop()[0])
            # Macro definitions stay visible for named API alias checks.
            if name != "define" or not active:
                masked = re.sub(r"[^\r\n]", " ", masked)
        elif not active:
            masked = re.sub(r"[^\r\n]", " ", masked)
        output.append(masked)
    return "".join(output)


def code_tokens(source: str):
    """Return identifiers and punctuation, excluding comments and literals."""
    return re.findall(r"[A-Za-z_]\w*|->|[^\s]", mask_noncode(source))
