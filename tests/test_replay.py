import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.models import TaskEvaluationResult, TestResult, SizeMetrics, StaticSafetyMetrics, DimensionScores
from aibenchmark_esw.provenance import text_sha256
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.static_analyzer import StaticAnalyzer


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.loader=DatasetLoader()
        self.tasks=[self.loader.get_task(task) for task in ('tier1_crc16','tier1_ring_buffer')]
        self.executor=ExecutionSandbox()
        self.analyzer=StaticAnalyzer(cppcheck_cmd='')
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.sources=self.root/'solutions'
        self.sources.mkdir()
        results=[]
        for task in self.tasks:
            source=self.loader.get_reference_solution(task.id)
            (self.sources/(task.id+'.c')).write_text(source,encoding='utf-8')
            results.append(TaskEvaluationResult(task.id,task.tier,'origin',False,TestResult(completed=False),SizeMetrics(measured=False),StaticSafetyMetrics(cppcheck_status='not_run'),DimensionScores(),0,weights=task.weights,limits=task.limits,target_standard=task.target_standard,generation={'usage':{'total_tokens':99},'cost_usd':1},provenance={'candidate_sha256':text_sha256(source)}))
        self.origin=BenchmarkReporter.to_json_dict(results,'origin',{'run_id':'origin-run','selected_tasks':[task.id for task in self.tasks],'run_status':'completed','pending_tasks':[]})

    def tearDown(self):
        self.temp.cleanup()

    def test_two_candidates_evaluated_offline_fresh_identity_and_origin_evidence(self):
        from aibenchmark_esw.replay import replay_candidates
        with patch('aibenchmark_esw.llm.client.LLMClient',side_effect=AssertionError('provider forbidden')):
            replay=replay_candidates(self.origin,self.sources,self.tasks,self.executor,self.analyzer,output=self.root/'replay.json')
        self.assertNotEqual(replay['metadata']['run_id'],'origin-run')
        self.assertEqual(replay['metadata']['origin_run_id'],'origin-run')
        self.assertEqual(replay['metadata']['run_mode'],'replay')
        self.assertEqual(len(replay['tasks']),2)
        self.assertTrue(all(task['test_result']['all_passed'] for task in replay['tasks']))
        self.assertTrue(all(task['generation'] is None for task in replay['tasks']))
        self.assertEqual(replay['tasks'][0]['provenance']['origin_generation']['cost_usd'],1)
        BenchmarkReporter.from_json_dict(replay)
        from aibenchmark_esw.metrics.aggregation import aggregate_runs
        with self.assertRaisesRegex(ValueError,'replay'):
            aggregate_runs([replay])
        self.assertIn('replay',BenchmarkReporter.generate_markdown(BenchmarkReporter.from_json_dict(replay),'origin',replay['metadata']))
        self.assertEqual(json.loads((self.root/'replay.json').read_text())['metadata']['run_status'],'completed')

    def test_missing_source_keeps_failed_denominator(self):
        from aibenchmark_esw.replay import replay_candidates
        (self.sources/(self.tasks[1].id+'.c')).unlink()
        replay=replay_candidates(self.origin,self.sources,self.tasks,self.executor,self.analyzer)
        self.assertEqual(len(replay['tasks']),2)
        self.assertEqual(replay['pass_at_1_pct'],50)
        self.assertIn('Missing',replay['tasks'][1]['error_log'])

    def test_parallel_order_and_truncated_slots(self):
        from aibenchmark_esw.replay import replay_candidates
        path=self.sources/(self.tasks[1].id+'.c')
        path.rename(self.sources/(self.tasks[1].id+'.truncated.c'))
        replay=replay_candidates(self.origin,self.sources,list(reversed(self.tasks)),self.executor,self.analyzer,jobs=2)
        self.assertEqual([task['task_id'] for task in replay['tasks']],[task.id for task in self.tasks])
        self.assertEqual(replay['pass_at_1_pct'],50)
        self.assertIn('Truncated',replay['tasks'][1]['error_log'])

    def test_ambiguous_mapping_rejected_before_output(self):
        from aibenchmark_esw.replay import replay_candidates
        task=self.tasks[0]
        folder=self.sources/task.id
        folder.mkdir()
        (folder/Path(task.entry_file).name).write_text(self.loader.get_reference_solution(task.id),encoding='utf-8')
        output=self.root/'should-not-exist.json'
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            replay_candidates(self.origin,self.sources,self.tasks,self.executor,self.analyzer,output=output)
        self.assertFalse(output.exists())

    def test_hash_mismatch_and_output_collision_rejected_before_grading(self):
        from aibenchmark_esw.replay import replay_candidates
        source=self.sources/(self.tasks[0].id+'.c')
        with patch('aibenchmark_esw.replay.evaluate_task',side_effect=AssertionError('grading started')):
            with self.assertRaisesRegex(ValueError,'overwrite'):
                replay_candidates(self.origin,self.sources,self.tasks,self.executor,self.analyzer,output=source)
            source.write_text('tampered',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'hash'):
                replay_candidates(self.origin,self.sources,self.tasks,self.executor,self.analyzer)

    def test_interrupted_checkpoint_preserves_completed_slot(self):
        from aibenchmark_esw.replay import replay_candidates
        from aibenchmark_esw.evaluation import evaluate_task
        calls=[]
        def grading(*args,**kwargs):
            calls.append(args[0].id)
            if len(calls)==2:
                raise KeyboardInterrupt()
            return evaluate_task(*args,**kwargs)
        output=self.root/'checkpoint.json'
        with patch('aibenchmark_esw.replay.evaluate_task',side_effect=grading):
            with self.assertRaises(KeyboardInterrupt):
                replay_candidates(self.origin,self.sources,self.tasks,self.executor,self.analyzer,output=output)
        report=json.loads(output.read_text())
        self.assertEqual(report['metadata']['run_status'],'interrupted')
        self.assertTrue(report['tasks'][0]['test_result']['all_passed'])
        self.assertEqual(report['metadata']['pending_tasks'],[self.tasks[1].id])
        BenchmarkReporter.from_json_dict(report)
