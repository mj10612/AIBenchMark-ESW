import json
import re
import shutil
import subprocess
import unittest

from test_aggregation import fixture_report

from aibenchmark_esw.metrics.exports import report_html
from aibenchmark_esw.metrics.reporter import BenchmarkReporter


@unittest.skipUnless(shutil.which('node'), 'Node.js is required to execute exported HTML filters')
class TestHtmlFilters(unittest.TestCase):
    def test_filters_leave_nonfilterable_summary_rows_visible(self):
        report = fixture_report()
        html = report_html(BenchmarkReporter.from_json_dict(report), report['model_name'])
        script = re.search(r'<script>(.*?)</script>', html, re.S).group(1)
        harness = r'''
const summary={dataset:{},textContent:'Summary mean 100',hidden:false};
const task={dataset:{score:'25',status:'PASS',tier:'1',category:'general'},textContent:'Task',hidden:false};
const rows=[summary,task];
const inputs=Object.fromEntries(['filter','status','tier','category','minscore'].map(id=>[id,{value:'',add(){},addEventListener(){}}]));
global.Option=function(){};
const document={querySelector(s){return inputs[s.slice(1)]},getElementById(s){return inputs[s]},
querySelectorAll(s){if(s==='tbody tr')return rows;if(s==='tbody tr[data-score]')return rows.filter(r=>'score' in r.dataset);return []}};
'''
        checks = r'''
const output=[];
for(const [id,value] of [['minscore','50'],['status','FAIL'],['tier','2'],['category','other'],['filter','unmatched']]){
 for(const input of Object.values(inputs))input.value='';
 summary.hidden=false;task.hidden=false;inputs[id].value=value;filterRows();
 output.push({summaryHidden:!!summary.hidden,taskHidden:!!task.hidden});
}
console.log(JSON.stringify(output));
'''
        result = subprocess.run([shutil.which('node'), '-e', harness + script + checks],
                                capture_output=True, text=True, check=True, timeout=10)
        for state in json.loads(result.stdout):
            self.assertFalse(state['summaryHidden'])
            self.assertTrue(state['taskHidden'])
