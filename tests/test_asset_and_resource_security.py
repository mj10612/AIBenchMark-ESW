import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw import resources
from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox
from aibenchmark_esw.sandbox.process_runner import run_bounded


class TestAssetAndResourceSecurity(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('AIBENCHMARK_TEST_CONTAINER') == '1' or os.environ.get('AIBENCHMARK_TEST_BWRAP') == '1', 'Explicit real containment integration required')
    def test_actual_containment_limits_scratch_and_workspace(self):
        from dataclasses import replace
        mode = 'container' if os.environ.get('AIBENCHMARK_TEST_CONTAINER') == '1' else 'bwrap'
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            (root / 'tests/test_limits.c').write_text('#include "unity.h"\nint limits(void);void setUp(void){}void tearDown(void){}void test_limits(void){TEST_ASSERT_EQUAL(1,limits());}int main(void){UNITY_BEGIN();RUN_TEST(test_limits);return UNITY_END();}', encoding='utf-8')
            task = replace(DatasetLoader().get_task('tier1_crc16'), task_dir=root)
            code = '''#include <sys/resource.h>
#include <sys/statvfs.h>
#include <stdio.h>
int limits(void){struct rlimit l;struct statvfs v;
if(getrlimit(RLIMIT_FSIZE,&l)||l.rlim_cur!=16777216)return 0;
if(getrlimit(RLIMIT_CORE,&l)||l.rlim_cur!=0)return 0;
if(getrlimit(RLIMIT_NPROC,&l)||l.rlim_cur!=64)return 0;
if(getrlimit(RLIMIT_NOFILE,&l)||l.rlim_cur!=256)return 0;
if(statvfs("/tmp",&v)||(unsigned long long)v.f_blocks*v.f_frsize>67108864)return 0;
if(statvfs(".",&v)||(unsigned long long)v.f_blocks*v.f_frsize>67108864)return 0;
FILE *f=fopen("../unexpected", "w");if(f){fclose(f);return 0;}
f=fopen("permitted", "w");if(!f)return 0;fclose(f);return 1;}
'''
            compiled, tests = ExecutionSandbox(isolation=mode, compiler_path='gcc').compile_and_test(task, code)
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertTrue(tests.passed, tests.output)

    def test_bundled_assets_verify_and_tampered_harness_is_rejected(self):
        root = resources.data_root()
        self.assertEqual(resources.unity_integrity_errors(root / 'third_party/unity'), [])
        task = DatasetLoader().get_task('tier1_crc16')
        self.assertEqual(resources.task_integrity_errors(task.task_dir), [])
        with TemporaryDirectory() as directory:
            copied = Path(directory) / 'unity'
            shutil.copytree(root / 'third_party/unity', copied)
            (copied / 'unity.h').write_text('/* forged */', encoding='utf-8')
            self.assertIn('unity.h', ';'.join(resources.unity_integrity_errors(copied)))
            executor = ExecutionSandbox()
            executor.unity_dir = copied
            compiled, _ = executor.compile_and_test(task, task.reference_path.read_text())
            self.addCleanup(compiled.cleanup)
            self.assertFalse(compiled.success)
            self.assertIn('integrity', compiled.error_message)

    def test_packaged_data_wins_over_adjacent_checkout_shape(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'package'
            (package / '_data').mkdir(parents=True)
            (root / 'tasks').mkdir()
            (root / 'third_party/unity').mkdir(parents=True)
            with patch.object(resources, '__file__', str(package / 'resources.py')), patch.dict(os.environ, {'AIBENCHMARK_ESW_DEV_CHECKOUT': '0'}):
                self.assertEqual(resources.data_root(), (package / '_data').resolve())

    def test_modified_bundled_task_fails_before_generation(self):
        import io
        from contextlib import redirect_stderr, redirect_stdout

        from aibenchmark_esw import cli
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = resources.data_root() / 'tasks/tier1_crc16'
            shutil.copytree(source, root / 'tasks/tier1_crc16')
            (root / 'tasks/tier1_crc16/include/crc16.h').write_text('/* forged API */', encoding='utf-8')
            with patch('aibenchmark_esw.resources.data_root', return_value=root), patch('aibenchmark_esw.dataset.data_root', return_value=root), patch.object(cli.LLMClient, 'generate_solution') as generate:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.cmd_run(cli.build_parser().parse_args(['run', '--model', 'mock', '--tasks', 'tier1_crc16'])), 1)
                generate.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Actual Windows Job active-process cap')
    def test_windows_job_caps_actual_descendants(self):
        code = '''import subprocess,sys,json
children=[]
for _ in range(80):
 try: children.append(subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000))
 except OSError: break
print(json.dumps(len(children)),flush=True)
'''
        result = run_bounded([sys.executable, '-c', code], timeout=15, max_output_bytes=4096)
        self.assertEqual(result.returncode, 0, result.stdout)
        count = json.loads(result.stdout)
        self.assertGreater(count, 0)
        self.assertLessEqual(count, 63)

    def test_hardening_and_runtime_limits_are_recorded(self):
        tcc = ExecutionSandbox(compiler_path='tcc')
        self.assertFalse(tcc.execution_settings()['hardening']['available'])
        self.assertEqual(ExecutionSandbox(compiler_path='gcc', hardening='off').hardening_flags(), [])
        with self.assertRaisesRegex(ValueError, 'TCC'):
            ExecutionSandbox(compiler_path='tcc', hardening='required').execution_settings()
        gcc = ExecutionSandbox(compiler_path='gcc')
        self.assertIn('-fstack-protector-strong', gcc.hardening_flags(True))
        self.assertNotIn('-pie', gcc.hardening_flags(True))
        msvc = ExecutionSandbox(compiler_path='cl')
        self.assertIn('/NXCOMPAT', msvc.hardening_flags())
        self.assertNotIn('/link', msvc.hardening_flags(True))

    @unittest.skipIf(os.name == 'nt', 'POSIX resource launcher')
    def test_actual_process_limits_and_large_file_write(self):
        code = 'import resource,json; print(json.dumps([resource.getrlimit(k)[0] for k in (resource.RLIMIT_NPROC,resource.RLIMIT_FSIZE,resource.RLIMIT_CORE,resource.RLIMIT_NOFILE)]))'
        result = run_bounded([sys.executable, '-c', code], timeout=5, max_output_bytes=4096, isolation='process')
        self.assertEqual(result.returncode, 0, result.stdout)
        limits = json.loads(result.stdout)
        if sys.platform == 'darwin':
            self.assertGreaterEqual(limits[0], 64)
        else:
            self.assertEqual(limits[0], 64)
        self.assertEqual(limits[1:], [16777216, 0, 256])
        with TemporaryDirectory() as directory:
            result = run_bounded([sys.executable, '-c', 'open("large", "wb").write(b"x" * 17000000)'], cwd=directory, timeout=5, max_output_bytes=4096, isolation='process')
            self.assertNotEqual(result.returncode, 0)
            self.assertLessEqual((Path(directory) / 'large').stat().st_size, 16777216)

    @unittest.skipIf(os.name == 'nt' or getattr(os, 'geteuid', lambda: 1)() == 0, 'Requires unprivileged POSIX RLIMIT_NPROC enforcement')
    def test_actual_fork_loop_is_bounded(self):
        code = '''import os,signal,json
children=[]
try:
 for _ in range(100):
  try: pid=os.fork()
  except OSError: break
  if pid==0: signal.pause();os._exit(0)
  children.append(pid)
 print(json.dumps(len(children)),flush=True)
finally:
 for pid in children: os.kill(pid,signal.SIGKILL);os.waitpid(pid,0)
'''
        result = run_bounded([sys.executable, '-c', code], timeout=10, max_output_bytes=4096, isolation='process')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertLessEqual(json.loads(result.stdout), 64 if sys.platform == 'darwin' else 63)

    @unittest.skipUnless(os.environ.get('AIBENCHMARK_TEST_CONTAINER') == '1' or os.environ.get('AIBENCHMARK_TEST_BWRAP') == '1', 'Explicit real containment integration required')
    def test_actual_contained_candidate_large_file_is_capped(self):
        from dataclasses import replace
        mode = 'container' if os.environ.get('AIBENCHMARK_TEST_CONTAINER') == '1' else 'bwrap'
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            (root / 'tests/test_quota.c').write_text('#include "unity.h"\nint quota(void);void setUp(void){}void tearDown(void){}void test_quota(void){TEST_ASSERT_EQUAL(1,quota());}int main(void){UNITY_BEGIN();RUN_TEST(test_quota);return UNITY_END();}', encoding='utf-8')
            task = replace(DatasetLoader().get_task('tier1_crc16'), task_dir=root)
            # Ignoring SIGXFSZ must still leave the kernel file-size cap in
            # force. Check EFBIG and actual size, including fopen failures.
            code = '''#include <stdio.h>
#include <signal.h>
#include <errno.h>
#include <sys/stat.h>
int quota(void){char b[4096]={0};struct stat s;signal(SIGXFSZ,SIG_IGN);
FILE *f=fopen("large","wb");if(!f){perror("fopen");return 0;}
setvbuf(f,NULL,_IONBF,0);int capped=0;
for(int i=0;i<4352;i++){errno=0;if(fwrite(b,1,sizeof b,f)!=sizeof b){capped=(errno==EFBIG);break;}}
fclose(f);if(stat("large",&s))return 0;
printf("quota capped=%d size=%lld\\n",capped,(long long)s.st_size);
return capped && s.st_size==16777216;}
'''
            compiled, tests = ExecutionSandbox(isolation=mode, compiler_path='gcc').compile_and_test(task, code)
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertTrue(tests.completed, tests.output)
            self.assertTrue(tests.passed, tests.output)

    def test_runtime_mounts_read_only_workspace_and_bounded_scratch(self):
        from aibenchmark_esw.sandbox.containment import ContainmentBackend
        with TemporaryDirectory() as directory:
            workspace = Path(directory)
            scratch = workspace / 'scratch'
            scratch.mkdir()
            (workspace / 'harness.receipt').touch()
            with patch('aibenchmark_esw.sandbox.containment.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'sha256:' + 'a'*64)), patch('shutil.which', return_value='/usr/bin/docker'):
                backend = ContainmentBackend('container')
            with patch('aibenchmark_esw.sandbox.containment.run_bounded', return_value=subprocess.CompletedProcess([], 0, b'')) as runner:
                backend.run(['/workspace/test'], cwd=scratch, timeout=2, max_output_bytes=4096)
                invocation = runner.call_args_list[0].args[0]
            self.assertIn('--memory=536870912', invocation)
            self.assertIn('--ulimit=fsize=16777216:16777216', invocation)
            self.assertTrue(any('target=/workspace,readonly' in value for value in invocation))
            self.assertTrue(any(value.startswith('--tmpfs=/workspace/scratch:') for value in invocation))
            self.assertTrue(any('target=/workspace/harness.receipt' in value for value in invocation))
