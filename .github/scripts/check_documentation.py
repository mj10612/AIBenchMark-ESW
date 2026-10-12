"""Keep live README claims aligned with the generated reference evidence."""

import json
import re
import sys
from pathlib import Path

from aibenchmark_esw.dataset import DatasetLoader


def main():
    report = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    text = Path('README.md').read_text(encoding='utf-8')
    claimed = re.search(r'(\d+) tasks and (\d+) C test cases', text)
    count = sum(task['test_result']['total'] for task in report['tasks'])
    if claimed is None or tuple(map(int, claimed.groups())) != (len(report['tasks']), count):
        raise ValueError(f'README baseline claim must match {len(report["tasks"])} tasks / {count} C test cases')
    for name in ('REPRODUCIBILITY.md', 'ROADMAP.md', 'TASK_VARIANTS.md'):
        document = (Path('docs') / name).read_text(encoding='utf-8')
        counts = re.search(r'(\d+) tasks(?: and |, )(\d+) (?:C test|Unity) cases', document)
        if counts is None or tuple(map(int, counts.groups())) != (len(report['tasks']), count):
            raise ValueError('Live documentation count disagrees with baseline: ' + name)
    labels = {'core_fundamentals': 'Core Fundamentals', 'fsm_and_protocols': 'FSM & Protocols',
              'device_drivers': 'Device Drivers', 'bug_fix_and_safety': 'Bug Fix & Safety',
              'fixed_point_control': 'Fixed-point Control', 'flash_management': 'Flash Management',
              'concurrency': 'Concurrency', 'general': 'General'}
    for task in DatasetLoader().list_tasks():
        pattern = rf'\| \*\*{task.tier}\*\* \| {re.escape(labels[task.category])} \| `{re.escape(task.id)}` \|'
        if not re.search(pattern, text):
            raise ValueError('README task tier/category disagrees with metadata: ' + task.id)
        if task.description == task.name:
            raise ValueError('Task description duplicates its name: ' + task.id)
    print('Live README counts and task metadata: PASS')


if __name__ == '__main__':
    main()
