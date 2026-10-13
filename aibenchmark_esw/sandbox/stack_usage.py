"""Bounded compiler per-function stack evidence, separate from static object RAM."""

import re
from pathlib import Path


def unavailable_stack_usage(reason, provenance=None):
    return {'status': 'unavailable', 'reason': reason, 'functions': [],
            'bounded_functions': 0, 'total_functions': 0,
            'max_per_function_bytes': None, 'whole_program_peak_bytes': None,
            'whole_program_reason': 'Call paths, recursion and indirect calls are not analyzed',
            'provenance': provenance or {}}


def parse_stack_usage(text, provenance=None):
    evidence = unavailable_stack_usage('No compiler stack records', provenance)
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.rsplit('\t', 2)
        if len(fields) != 3 or not re.fullmatch(r'[0-9]{1,20}', fields[1]) or not fields[0].rsplit(':', 1)[-1].strip():
            return unavailable_stack_usage('Malformed compiler stack records', provenance)
        qualifiers = set(fields[2].strip().split(','))
        if qualifiers == {'static'}:
            classification = 'static'
        elif qualifiers == {'dynamic', 'bounded'}:
            classification = 'dynamic-bounded'
        elif qualifiers == {'dynamic'}:
            classification = 'unknown'
        else:
            return unavailable_stack_usage('Unsupported compiler stack classification', provenance)
        size = int(fields[1])
        evidence['functions'].append({'function': fields[0].rsplit(':', 1)[-1],
            'bytes': size if classification != 'unknown' else None,
            'reported_bytes': size, 'classification': classification})
    known = [row['bytes'] for row in evidence['functions'] if row['bytes'] is not None]
    evidence['total_functions'] = len(evidence['functions'])
    evidence['bounded_functions'] = len(known)
    evidence['max_per_function_bytes'] = max(known) if known else None
    if evidence['functions']:
        evidence['status'] = 'measured' if len(known) == len(evidence['functions']) else 'partial' if known else 'unavailable'
        evidence['reason'] = None if evidence['status'] == 'measured' else 'Dynamic unbounded function frames are unknown'
    return evidence


def read_stack_usage(path, max_bytes, provenance=None):
    path = Path(path)
    try:
        # Only consume the expected compiler artifact, never follow artifact links.
        if path.is_symlink() or not path.is_file():
            return unavailable_stack_usage('Compiler stack records missing', provenance)
        with path.open('rb') as stream:
            data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            return unavailable_stack_usage('Compiler stack records exceed output limit', provenance)
        return parse_stack_usage(data.decode('utf-8', errors='replace'), provenance)
    except OSError:
        return unavailable_stack_usage('Compiler stack records unreadable', provenance)


def validate_stack_usage(value):
    if value is None:
        return
    def count(number):
        return not isinstance(number, bool) and isinstance(number, int) and number >= 0
    if not isinstance(value, dict) or set(value) != {'candidate', 'reference'}:
        raise ValueError('stack_usage must contain candidate and reference evidence')
    for evidence in value.values():
        if not isinstance(evidence, dict) or evidence.get('status') not in ('measured', 'partial', 'unavailable'):
            raise ValueError('Invalid stack evidence status')
        rows = evidence.get('functions')
        if not isinstance(rows, list) or not isinstance(evidence.get('provenance'), dict):
            raise ValueError('Invalid stack evidence functions or provenance')
        known = []
        for row in rows:
            if (not isinstance(row, dict) or not isinstance(row.get('function'), str)
                    or not row['function'] or not count(row.get('reported_bytes'))
                    or row.get('classification') not in ('static', 'dynamic-bounded', 'unknown')):
                raise ValueError('Invalid stack function record')
            if row['classification'] == 'unknown':
                if row.get('bytes') is not None:
                    raise ValueError('Unknown stack frame must have unavailable bytes')
            elif not count(row.get('bytes')) or row['bytes'] != row['reported_bytes']:
                raise ValueError('Invalid bounded stack frame bytes')
            else:
                known.append(row['bytes'])
        expected_status = 'measured' if rows and len(rows) == len(known) else 'partial' if known else 'unavailable'
        if (evidence.get('status') != expected_status
                or not count(evidence.get('total_functions'))
                or not count(evidence.get('bounded_functions'))
                or evidence.get('max_per_function_bytes') is not None and not count(evidence['max_per_function_bytes'])
                or evidence.get('total_functions') != len(rows)
                or evidence.get('bounded_functions') != len(known)
                or evidence.get('max_per_function_bytes') != (max(known) if known else None)
                or evidence.get('whole_program_peak_bytes') is not None
                or not isinstance(evidence.get('whole_program_reason'), str)
                or evidence.get('reason') is not None and not isinstance(evidence['reason'], str)):
            raise ValueError('Inconsistent stack evidence coverage or maximum')


def stack_usage_lines(results):
    from aibenchmark_esw.metrics.text import markdown_text
    lines = []
    for result in results:
        if result.stack_usage is None:
            continue
        for role in ('candidate', 'reference'):
            evidence = result.stack_usage[role]
            value = evidence['max_per_function_bytes']
            maximum = f'{value} B' if value is not None else 'Unavailable'
            reason = f'; {evidence["reason"]}' if evidence.get('reason') else ''
            target = evidence.get('provenance', {}).get('target', result.footprint_target)
            lines.append(markdown_text(f'{result.task_id} {role} ({target}): stack per-function maximum {maximum}; '
                f'bounded coverage {evidence["bounded_functions"]}/{evidence["total_functions"]}{reason}.'))
    if lines:
        lines.append('Stack evidence is separate from static object RAM and scores; whole-program peak is unavailable (call paths, recursion and indirect calls are not analyzed). Hardware validation is required.')
    return lines
