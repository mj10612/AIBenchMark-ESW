import json
import os
import sys
import threading
import time
import unittest
from unittest.mock import patch

import test_replay
from test_runtime_controls import child_alive

from aibenchmark_esw.evaluation import failed_evaluation
from aibenchmark_esw.metrics.reporter import BenchmarkReporter
from aibenchmark_esw.provenance import text_sha256
from aibenchmark_esw.replay import replay_candidates


class TestReplayCancellation(unittest.TestCase):
    setUp = test_replay.ReplayTests.setUp
    tearDown = test_replay.ReplayTests.tearDown

    def test_parallel_interrupt_sets_event_before_shutdown(self):
        started = threading.Event()
        self.executor.cancel_event = threading.Event()
        observed = []

        def grade(task, *args, **kwargs):
            started.set()
            observed.append(self.executor.cancel_event.wait(2))
            return failed_evaluation(task, 'origin', 'cancelled')

        def interrupt(futures):
            self.assertTrue(started.wait(2))
            raise KeyboardInterrupt()

        output = self.root / 'interrupted.json'
        with patch('aibenchmark_esw.replay.evaluate_task', side_effect=grade), patch(
                'aibenchmark_esw.replay.as_completed', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                replay_candidates(self.origin, self.sources, self.tasks, self.executor,
                                  self.analyzer, jobs=2, output=output)
        self.assertTrue(self.executor.cancel_event.is_set())
        self.assertTrue(observed and all(observed))
        report = json.loads(output.read_text())
        self.assertEqual(report['metadata']['run_status'], 'interrupted')
        self.assertEqual(report['metadata']['pending_tasks'], [task.id for task in self.tasks])
        self.assertTrue(all(task['scores']['total'] == 0 for task in report['tasks']))
        BenchmarkReporter.from_json_dict(report)

    def test_worker_exception_cancels_sibling_work(self):
        started = threading.Event()
        self.executor.cancel_event = threading.Event()
        observed = []

        def grade(task, *args, **kwargs):
            if task.id == self.tasks[0].id:
                self.assertTrue(started.wait(2))
                raise RuntimeError('worker failed')
            started.set()
            observed.append(self.executor.cancel_event.wait(2))
            return failed_evaluation(task, 'origin', 'cancelled')

        output = self.root / 'aborted.json'
        with patch('aibenchmark_esw.replay.evaluate_task', side_effect=grade):
            with self.assertRaisesRegex(RuntimeError, 'worker failed'):
                replay_candidates(self.origin, self.sources, self.tasks, self.executor,
                                  self.analyzer, jobs=2, output=output)
        self.assertTrue(self.executor.cancel_event.is_set())
        self.assertEqual(observed, [True])
        self.assertEqual(json.loads(output.read_text())['metadata']['run_status'], 'aborted')

    def test_real_candidate_interrupt_cleans_up_descendants(self):
        script = self.root / 'descendants.py'
        marker = self.root / 'pids.json'
        script.write_text('import json,os,subprocess,sys,time\n'
                          'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"])\n'
                          'with open(sys.argv[1]+".tmp","w") as f: json.dump([os.getpid(),child.pid],f)\n'
                          'os.replace(sys.argv[1]+".tmp",sys.argv[1])\n'
                          'time.sleep(30)\n', encoding='utf-8')
        task = self.tasks[0]
        # Spawn with argv directly: Windows system()/cmd strips nested quotes.
        executable, script_arg, marker_arg = (json.dumps(str(path).replace('\\', '/'))
                                               for path in (sys.executable, script, marker))
        launch = f"""{{
#ifdef _WIN32
    if (_spawnl(_P_WAIT, {executable}, {executable}, {script_arg}, {marker_arg}, (char *)0) == -1) abort();
#else
    pid_t child = fork();
    if (child == -1) abort();
    if (child == 0) {{ execl({executable}, {executable}, {script_arg}, {marker_arg}, (char *)0); _exit(127); }}
    if (waitpid(child, NULL, 0) == -1) abort();
#endif
}} return crc;"""
        source = ("#include <stdlib.h>\n#ifdef _WIN32\n#include <process.h>\n"
                  "#else\n#include <unistd.h>\n#include <sys/wait.h>\n#endif\n"
                  + self.loader.get_reference_solution(task.id))
        source = source.replace('return crc;', launch, 1)
        (self.sources / (task.id + '.c')).write_text(source, encoding='utf-8')
        self.origin['tasks'][0]['provenance']['candidate_sha256'] = text_sha256(source)
        reached = []

        def interrupt(futures):
            deadline = time.monotonic() + 15
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            diagnostics = [future.result().error_log for future in futures if future.done()]
            self.assertTrue(marker.exists(), f'candidate did not launch descendants: {diagnostics}')
            reached.extend(json.loads(marker.read_text()))
            raise KeyboardInterrupt()

        output = self.root / 'real-interrupted.json'
        started = time.monotonic()
        try:
            with patch('aibenchmark_esw.replay.as_completed', side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    replay_candidates(self.origin, self.sources, self.tasks, self.executor,
                                      self.analyzer, jobs=2, output=output)
            self.assertLess(time.monotonic() - started, 15)
            self.assertTrue(reached)
            self.assertTrue(all(not child_alive(pid) for pid in reached))
            report = json.loads(output.read_text())
            self.assertEqual(report['metadata']['run_status'], 'interrupted')
            self.assertIn(task.id, report['metadata']['pending_tasks'])
            self.assertEqual(report['tasks'][0]['scores']['total'], 0)
        finally:
            for pid in reached:
                if child_alive(pid):
                    if os.name == 'nt':
                        import subprocess
                        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True)
                    else:
                        import signal
                        os.kill(pid, signal.SIGKILL)

    def test_parallel_interrupt_preserves_completed_score_and_origin(self):
        from aibenchmark_esw.evaluation import evaluate_task
        sibling_started = threading.Event()
        self.executor.cancel_event = threading.Event()
        output = self.root / 'partial.json'
        completed_task, pending_task = self.tasks

        def grade(task, *args, **kwargs):
            if task.id == completed_task.id:
                return evaluate_task(task, *args, **kwargs)
            sibling_started.set()
            self.assertTrue(self.executor.cancel_event.wait(10))
            return failed_evaluation(task, 'origin', 'cancelled')

        def interrupt_after_one(futures):
            self.assertTrue(sibling_started.wait(5))
            completed_future = next(future for future, task_id in futures.items()
                                    if task_id == completed_task.id)
            completed_future.result(timeout=10)
            yield completed_future
            checkpoint = json.loads(output.read_text())
            self.assertEqual(checkpoint['tasks'][0]['scores']['total'], 100)
            raise KeyboardInterrupt()

        with patch('aibenchmark_esw.replay.evaluate_task', side_effect=grade), patch(
                'aibenchmark_esw.replay.as_completed', side_effect=interrupt_after_one):
            with self.assertRaises(KeyboardInterrupt):
                replay_candidates(self.origin, self.sources, self.tasks, self.executor,
                                  self.analyzer, jobs=2, output=output)
        report = json.loads(output.read_text())
        self.assertEqual(report['metadata']['run_status'], 'interrupted')
        self.assertEqual(report['metadata']['pending_tasks'], [pending_task.id])
        self.assertEqual(report['tasks'][0]['scores']['total'], 100)
        self.assertEqual(report['tasks'][1]['scores']['total'], 0)
        self.assertEqual(report['tasks'][0]['provenance']['origin_run_id'], 'origin-run')
        self.assertEqual(report['tasks'][0]['provenance']['origin_generation']['cost_usd'], 1)
        BenchmarkReporter.from_json_dict(report)

    def test_cli_replay_interrupt_exits_130_with_checkpoint(self):
        import io
        from contextlib import redirect_stderr

        from aibenchmark_esw import cli
        origin = self.root / 'origin.json'
        output = self.root / 'cli-interrupted.json'
        origin.write_text(json.dumps(self.origin), encoding='utf-8')

        def interrupt(_futures):
            raise KeyboardInterrupt()

        argv = ['aibenchmark-esw', 'replay', '--results', str(origin),
                '--solutions', str(self.sources), '--output', str(output), '--jobs', '2']
        with patch.object(sys, 'argv', argv), patch('aibenchmark_esw.replay.as_completed',
                side_effect=interrupt), redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaises(SystemExit) as caught:
                cli.main()
        self.assertEqual(caught.exception.code, 130)
        self.assertIn('checkpoint', stderr.getvalue())
        report = json.loads(output.read_text())
        self.assertEqual(report['metadata']['run_status'], 'interrupted')
        self.assertEqual(report['metadata']['pending_tasks'], [task.id for task in self.tasks])
        BenchmarkReporter.from_json_dict(report)
