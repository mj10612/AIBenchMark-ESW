"""Map findings only to persistent candidate files with verified content hashes."""
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from aibenchmark_esw.provenance import text_sha256


def generate_sarif(results, model_name='unknown', metadata=None, *, source_root=None, source_mapping=None):
    root = Path(source_root or Path.cwd()).resolve()
    if not root.is_dir():
        raise ValueError('SARIF source root must be an existing directory')
    mapping = source_mapping or {}
    if not isinstance(mapping, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in mapping.items()):
        raise ValueError('SARIF source mapping must map task or task:sample IDs to file paths')
    rules: dict = {}
    published: dict = {}
    for result in results:
        provenance = result.provenance or {}
        sample = provenance.get('sample_run_id')
        source = mapping.get(result.task_id + ':' + str(sample), mapping.get(result.task_id, provenance.get('candidate_source')))
        relative, diagnostic = None, 'No persistent candidate source mapping'
        if source:
            path = Path(source)
            path = (root / path).resolve() if not path.is_absolute() else path.resolve()
            try:
                if not path.is_relative_to(root):
                    diagnostic = 'Candidate source is outside the explicit source root'
                elif not provenance.get('candidate_sha256') or text_sha256(path.read_text(encoding='utf-8')) != provenance['candidate_sha256']:
                    diagnostic = 'Candidate source hash does not match recorded evidence'
                else:
                    relative = path.relative_to(root).as_posix()
            except (OSError, UnicodeError):
                diagnostic = 'Persistent candidate source is missing or unreadable'
        for finding in result.safety_metrics.findings:
            rule = finding['rule_id']
            rules.setdefault(rule, {'id': rule, 'shortDescription': {'text': rule}, 'properties': {'engine': finding['engine']}})
            properties = {'task_id': result.task_id, 'model': model_name, 'severity': finding['severity'],
                          'candidate_sha256': provenance.get('candidate_sha256'), 'sample_run_ids': [sample] if sample else [],
                          'original_file': finding['file'], 'original_line': finding.get('line'),
                          'source_mapping': 'verified' if relative else 'diagnostic-only'}
            entry = {'ruleId': rule, 'level': 'error' if finding['severity'] == 'error' else 'warning',
                     'message': {'text': finding['message']}, 'properties': properties}
            identity = [result.task_id, relative, provenance.get('candidate_sha256'), rule, finding['engine'], finding.get('line')]
            if relative:
                physical = {'artifactLocation': {'uri': quote(relative, safe='/')}}
                if finding.get('line') is not None:
                    physical['region'] = {'startLine': finding['line']}
                entry['locations'] = [{'physicalLocation': physical}]
                entry['partialFingerprints'] = {'candidateLocation/v1': hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode('utf-8')).hexdigest()}
            else:
                properties['mapping_diagnostic'] = diagnostic
                # Keep diagnostics distinct when no verified source identity exists.
                identity += [sample, finding['file'], finding['message']]
            key = json.dumps(identity, ensure_ascii=False)
            if key in published:
                samples = published[key]['properties']['sample_run_ids']
                if sample and sample not in samples:
                    samples.append(sample)
            else:
                published[key] = entry
    return json.dumps({'$schema': 'https://json.schemastore.org/sarif-2.1.0.json', 'version': '2.1.0',
                       'runs': [{'tool': {'driver': {'name': 'AIBenchMark-ESW', 'rules': list(rules.values())}},
                                 'results': list(published.values()), 'properties': metadata or {}}]}, indent=2, allow_nan=False) + '\n'
