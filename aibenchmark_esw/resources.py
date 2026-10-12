"""Prefer installed trusted assets; check bundled integrity before compilation."""
import hashlib
import json
import os
from pathlib import Path


def data_root() -> Path:
    package = Path(__file__).resolve().parent
    checkout, bundled = package.parent, package / "_data"
    developer = os.environ.get('AIBENCHMARK_ESW_DEV_CHECKOUT') == '1'
    if bundled.is_dir() and not developer:
        return bundled
    project = checkout / 'pyproject.toml'
    if project.is_file() and 'name = "aibenchmark-esw"' in project.read_text(encoding='utf-8'):
        if (checkout / 'tasks').is_dir() and (checkout / 'third_party/unity').is_dir():
            return checkout
    if developer:
        raise ValueError('Developer checkout opt-in requires the aibenchmark-esw project')
    return bundled


def asset_digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def asset_manifest():
    return json.loads((Path(__file__).resolve().parent / 'schemas/asset-manifest.json').read_text(encoding='utf-8'))['assets']


def _verify(directory, prefix, only=None):
    directory = Path(directory).resolve()
    expected = {key[len(prefix):]: value for key, value in asset_manifest().items() if key.startswith(prefix)}
    if only is not None:
        expected = {key: value for key, value in expected.items() if key in only}
    if not expected:
        return ['Trusted asset manifest has no entries for ' + prefix]
    errors = []
    for name, digest in expected.items():
        path = directory / name
        try:
            if not path.resolve().is_relative_to(directory) or asset_digest(path) != digest:
                errors.append('Trusted asset integrity mismatch: ' + prefix + name)
        except OSError:
            errors.append('Trusted asset unreadable or missing: ' + prefix + name)
    for path in directory.rglob('*') if only is None else ():
        if path.is_file() and path.suffix in ('.c', '.h', '.inc', '.json') and path.relative_to(directory).as_posix() not in expected:
            if not any(part in ('build', 'CMakeFiles', '__pycache__') for part in path.relative_to(directory).parts):
                errors.append('Unlisted trusted asset: ' + prefix + path.relative_to(directory).as_posix())
    return errors


def unity_integrity_errors(directory):
    return _verify(directory, 'third_party/unity/')


def task_integrity_errors(directory, *, config_only=False):
    original = Path(directory).absolute()
    directory = original.resolve()
    trusted = (data_root() / 'tasks').resolve()
    if original.parent == trusted and directory.parent != trusted:
        return ['Trusted task directory escapes its data root: ' + str(original)]
    if directory.parent != trusted:
        return []  # Explicit external datasets/variants are recorded by fingerprint, not declared bundled-trusted.
    return _verify(directory, 'tasks/' + directory.name + '/', only={'task.json'} if config_only else None)
