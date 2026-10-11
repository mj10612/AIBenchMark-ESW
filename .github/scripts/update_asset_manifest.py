"""Reviewed asset edits require an explicit manifest refresh before committing."""
import json
from pathlib import Path

from aibenchmark_esw.resources import asset_digest

root = Path(__file__).resolve().parents[2]
assets = {}
for directory in (root / 'tasks', root / 'third_party/unity'):
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.suffix in ('.c', '.h', '.inc', '.json', '.md', '.txt'):
            assets[path.relative_to(root).as_posix()] = asset_digest(path)
(root / 'aibenchmark_esw/schemas/asset-manifest.json').write_text(json.dumps({'version': 1, 'assets': assets}, indent=2, sort_keys=True) + '\n', encoding='utf-8')
