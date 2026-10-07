"""Preflight output destinations to prevent accidental destruction of inputs."""

import os
from pathlib import Path


def _same_file(first, second):
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and first.samefile(second))


def _input_files(roots):
    """Scan aliases once, including linked roots, without following cycles."""
    pending, visited = list(roots), set()
    while pending:
        root = pending.pop()
        try:
            stat = root.stat()
            identity = (stat.st_dev, stat.st_ino) if stat.st_ino else str(root.resolve())
            if identity in visited:
                continue
            visited.add(identity)
            with os.scandir(root) as entries:
                for entry in entries:
                    if entry.is_dir():
                        pending.append(Path(entry.path))
                    elif entry.is_file():
                        yield Path(entry.path)
        except OSError as error:
            raise ValueError(f"Cannot validate protected input directory {root}: {error}") from error


def validate_output_paths(outputs, protected_files=(), protected_roots=()):
    """Reject path/alias collisions before writing any outputs.

    This is an accidental-overwrite check, not a boundary against concurrent
    filesystem changes or untrusted code executing in the benchmark process.
    """
    outputs = [Path(path) for path in outputs if path is not None]
    roots = [Path(root).resolve() for root in protected_roots]
    inputs = [Path(path) for path in protected_files]
    # Existing output files may be hard links to inputs outside their root.
    if any(path.exists() for path in outputs):
        inputs.extend(_input_files(root for root in roots if root.is_dir()))
    for index, path in enumerate(outputs):
        if path.is_dir():
            raise IsADirectoryError(f"Output must be a file: {path}")
        for parent in path.parents:
            if parent.exists() and not parent.is_dir():
                raise NotADirectoryError(f"Output parent is not a directory: {parent}")
        lexical = Path(os.path.abspath(path))
        # Resolve ancestors as well: a leaf symlink may point out of a protected
        # folder, and Windows may spell that folder using an 8.3 name alias.
        locations = [path.resolve(), *(parent.resolve() for parent in lexical.parents)]
        if any(location == root or root in location.parents for location in locations for root in roots):
            raise ValueError(f"Output would overwrite benchmark inputs: {path}")
        if any(_same_file(path, source) for source in inputs):
            raise ValueError(f"Output would overwrite an input file: {path}")
        if any(_same_file(path, other) for other in outputs[:index]):
            raise ValueError(f"Output destinations collide: {path}")
        resolved = path.resolve()
        if any(resolved in other.resolve().parents or other.resolve() in resolved.parents
               for other in outputs[:index]):
            raise ValueError(f"Output file collides with another output's parent directory: {path}")
