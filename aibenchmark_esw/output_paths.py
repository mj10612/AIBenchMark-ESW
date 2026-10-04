"""Preflight output destinations to prevent accidental destruction of inputs."""

from pathlib import Path


def _same_file(first, second):
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and first.samefile(second))


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
        inputs.extend(path for root in roots for path in root.rglob("*") if path.is_file())
    for index, path in enumerate(outputs):
        if path.is_dir():
            raise IsADirectoryError(f"Output must be a file: {path}")
        for parent in path.parents:
            if parent.exists() and not parent.is_dir():
                raise NotADirectoryError(f"Output parent is not a directory: {parent}")
        resolved = path.resolve()
        if any(resolved == root or root in resolved.parents for root in roots):
            raise ValueError(f"Output would overwrite benchmark inputs: {path}")
        if any(_same_file(path, source) for source in inputs):
            raise ValueError(f"Output would overwrite an input file: {path}")
        if any(_same_file(path, other) for other in outputs[:index]):
            raise ValueError(f"Output destinations collide: {path}")
