import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestContainment(unittest.TestCase):
    def backend(self, engine='docker'):
        from aibenchmark_esw.sandbox.containment import ContainmentBackend
        with patch('aibenchmark_esw.sandbox.containment.shutil.which', return_value='/usr/bin/' + engine), patch(
                'aibenchmark_esw.sandbox.containment.subprocess.run',
                return_value=subprocess.CompletedProcess([], 0, 'sha256:' + 'a'*64 + '\n', '')):
            return ContainmentBackend('container', engine, 'gcc:14')

    def test_container_engine_missing_fails_without_native_fallback(self):
        with patch('shutil.which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'container runtime'):
                ExecutionSandbox(isolation='container')

    def test_compilation_mounts_only_workspace_with_security_controls(self):
        backend = self.backend()
        with TemporaryDirectory() as directory, TemporaryDirectory() as inputs:
            root = Path(directory)
            include = Path(inputs) / 'include'
            include.mkdir()
            (include / 'api.h').write_text('int answer(void);')
            source = root / 'candidate.c'
            source.write_text('int answer(void){return 7;}')
            output = root / 'test'
            commands = []
            def run(command, **options):
                commands.append(command)
                output.write_bytes(b'object')
                return subprocess.CompletedProcess(command, 0, b'', b'')
            with patch('aibenchmark_esw.sandbox.containment.run_bounded', side_effect=run):
                backend.run(['gcc', '-I', str(include), str(source), '-o', str(output)],
                            cwd=root, timeout=2, max_output_bytes=1000, memory_limit_bytes=123456)
            command = commands[0]
            for flag in ('--read-only', '--network=none', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                         '--user=65534:65534', '--pids-limit=64', '--memory=123456', '--cpus=1'):
                self.assertIn(flag, command)
            self.assertEqual(command.count('--mount'), 1)
            self.assertFalse(any(str(include) in value for value in command))
            self.assertIn('/workspace/candidate.c', command)
            self.assertIn('sha256:' + 'a'*64, command)
            self.assertEqual(commands[-1][1:3], ['rm', '--force'])
            self.assertTrue(any(p.name == 'api.h' for p in root.rglob('api.h')))

    def test_container_timeout_removes_container(self):
        backend = self.backend('podman')
        commands = []
        def run(command, **options):
            commands.append(command)
            if 'run' in command:
                raise subprocess.TimeoutExpired(command, 1, output=b'partial')
            return subprocess.CompletedProcess(command, 0, b'', b'')
        with TemporaryDirectory() as directory, patch(
                'aibenchmark_esw.sandbox.containment.run_bounded', side_effect=run):
            with self.assertRaises(subprocess.TimeoutExpired):
                backend.run(['gcc', '--version'], cwd=directory, timeout=1, max_output_bytes=1024)
        self.assertEqual(commands[-1][1:3], ['rm', '--force'])

    def test_image_identity_is_resolved_and_recorded(self):
        settings = self.backend().settings()
        self.assertEqual(settings['image_digest'], 'sha256:' + 'a'*64)
        self.assertEqual(settings['network'], 'none')
        self.assertEqual(settings['mount_scope'], 'ephemeral-workspace')

    def test_bwrap_command_uses_private_namespaces_and_minimal_system_roots(self):
        from aibenchmark_esw.sandbox.containment import ContainmentBackend
        with patch('aibenchmark_esw.sandbox.containment.os.name', 'posix'), patch(
                'aibenchmark_esw.sandbox.containment.shutil.which', return_value='/usr/bin/bwrap'):
            backend = ContainmentBackend('bwrap')
        with TemporaryDirectory() as directory, patch(
                'aibenchmark_esw.sandbox.containment.run_bounded',
                return_value=subprocess.CompletedProcess([], 0, b'', b'')) as run:
            backend.run(['gcc', '--version'], cwd=directory, timeout=1, max_output_bytes=1024)
        command = run.call_args.args[0]
        self.assertIn('--unshare-all', command)
        self.assertIn('--die-with-parent', command)
        self.assertIn('--new-session', command)
        self.assertNotIn('--ro-bind / /', ' '.join(command))
        self.assertNotIn('/home', command)

    @unittest.skipUnless(os.environ.get('AIBENCHMARK_TEST_CONTAINER') == '1', 'Explicit real container integration required')
    def test_real_container_blocks_host_file_and_network_access(self):
        from dataclasses import replace
        from aibenchmark_esw.dataset import DatasetLoader
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tests').mkdir()
            sentinel = root / 'host-secret'
            sentinel.write_text('secret')
            (root / 'tests/test_boundary.c').write_text(
                '#include "unity.h"\nint boundary(void);void setUp(void){}void tearDown(void){}'
                'void test_boundary(void){TEST_ASSERT_EQUAL_INT(1,boundary());}'
                'int main(void){UNITY_BEGIN();RUN_TEST(test_boundary);return UNITY_END();}')
            task = replace(DatasetLoader().get_task('tier1_crc16'), task_dir=root)
            # Host sentinel is outside the ephemeral evaluation mount. The
            # internet connect must fail with the private network namespace.
            code = ('#include <stdio.h>\n#include <unistd.h>\n#include <sys/socket.h>\n#include <arpa/inet.h>\n'
                    'int boundary(void){FILE *f=fopen("' + sentinel.as_posix() + '","w");'
                    'int s=socket(AF_INET,SOCK_STREAM,0);struct sockaddr_in a={0};'
                    'a.sin_family=AF_INET;a.sin_port=htons(80);a.sin_addr.s_addr=inet_addr("1.1.1.1");'
                    'int rc=connect(s,(struct sockaddr *)&a,sizeof a);close(s);if(f){fclose(f);return 0;}return rc<0;}')
            compiled, result = ExecutionSandbox(isolation='container').compile_and_test(task, code)
            self.addCleanup(compiled.cleanup)
            self.assertTrue(compiled.success, compiled.output)
            self.assertTrue(result.passed, result.output)
            self.assertEqual(sentinel.read_text(), 'secret')


if __name__ == '__main__':
    unittest.main()
