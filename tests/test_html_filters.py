import json
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

from test_aggregation import fixture_report

from aibenchmark_esw.metrics.comparison import compare_runs, render_comparison
from aibenchmark_esw.metrics.exports import report_html
from aibenchmark_esw.metrics.reporter import BenchmarkReporter


class FilterDocument(HTMLParser):
    """Expose the generated document to a small DOM double for its inline JS."""

    def __init__(self, html):
        super().__init__()
        self.rows = []
        self.controls = {}
        self.script = ''
        self.in_body = False
        self.in_script = False
        self.row = None
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'tbody':
            self.in_body = True
        elif tag == 'tr' and self.in_body:
            self.row = {'attributes': attributes, 'textContent': ''}
        elif tag in ('input', 'select') and attributes.get('id'):
            self.controls[attributes['id']] = attributes.get('value', '')
        elif tag == 'script':
            self.in_script = True

    def handle_endtag(self, tag):
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == 'tbody':
            self.in_body = False
        elif tag == 'script':
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.script += data
        elif self.row is not None:
            self.row['textContent'] += data


NODE_FILTER_RUNNER = r'''
const fs = require('node:fs'), vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const rows = input.rows.map(row => ({...row, hidden: false,
    dataset: Object.fromEntries(Object.entries(row.attributes)
        .filter(([name]) => name.startsWith('data-'))
        .map(([name, value]) => [name.slice(5), value]))}));
const controls = Object.fromEntries(Object.entries(input.controls).map(([id, value]) =>
    [id, {value, addEventListener() {}, add() {}}]));
const document = {
    getElementById: id => controls[id] || null,
    querySelector: selector => controls[selector.slice(1)] || null,
    querySelectorAll(selector) {
        if (selector === 'th[data-sort]') return [];
        if (!selector.startsWith('tbody tr')) throw new Error('Unsupported selector: ' + selector);
        const attribute = selector.match(/\[([^\]]+)\]/)?.[1];
        return rows.filter(row => !attribute || Object.hasOwn(row.attributes, attribute));
    }
};
const context = vm.createContext({document, Option: function() {}});
vm.runInContext(input.script, context);
const snapshots = input.scenarios.map(values => {
    for (const [id, value] of Object.entries(input.controls)) controls[id].value = value;
    for (const [id, value] of Object.entries(values)) controls[id].value = value;
    vm.runInContext('filterRows()', context);
    return rows.map(row => Boolean(row.hidden));
});
process.stdout.write(JSON.stringify(snapshots));
'''


@unittest.skipUnless(shutil.which('node'), 'Node.js is required to execute offline HTML filter JavaScript')
class TestHtmlFilters(unittest.TestCase):
    def filter_states(self, document, scenarios):
        result = subprocess.run(
            [shutil.which('node'), '-e', NODE_FILTER_RUNNER],
            input=json.dumps({'rows': document.rows, 'controls': document.controls,
                              'script': document.script, 'scenarios': scenarios}),
            capture_output=True, text=True, encoding='utf-8', timeout=10, check=True)
        return json.loads(result.stdout)

    def test_task_filters_keep_tier_and_category_summaries_visible(self):
        report = fixture_report()
        document = FilterDocument(report_html(BenchmarkReporter.from_json_dict(report),
                                              report['model_name'], report['metadata']))
        self.assertEqual(len(document.rows), 3)  # One tier, one category, one task.
        states = self.filter_states(document, [
            {'minscore': '1'}, {'filter': 'not-a-task'}, {'status': 'FAIL'},
            {'tier': '2'}, {'category': 'not-a-category'}, {},
        ])
        for state, task_hidden in zip(states, (False, True, True, True, True, False)):
            self.assertEqual(state, [False, False, task_hidden])

    def test_comparison_score_and_search_filters_still_filter_model_rows(self):
        comparison = compare_runs([fixture_report(model='alpha'), fixture_report(50, model='beta')])
        document = FilterDocument(render_comparison(comparison, 'html'))
        model_rows = [index for index, row in enumerate(document.rows) if 'data-score' in row['attributes']]
        self.assertEqual(len(model_rows), 2)
        states = self.filter_states(document, [{'minscore': '75'}, {'filter': 'beta'}, {}])
        for state, expected in zip(states, ([False, True], [True, False], [False, False])):
            self.assertEqual([state[index] for index in model_rows], expected)
            self.assertTrue(all(not hidden for index, hidden in enumerate(state) if index not in model_rows))

    def test_filters_leave_nonfilterable_summary_rows_visible(self):
        report = fixture_report(50)
        document = FilterDocument(report_html(BenchmarkReporter.from_json_dict(report),
                                              report['model_name'], report['metadata']))
        states = self.filter_states(document, [
            {'minscore': '75'}, {'status': 'PASS'}, {'tier': '2'},
            {'category': 'other'}, {'filter': 'unmatched'},
        ])
        for state in states:
            self.assertEqual(state, [False, False, True])
