"""Real Linux namespace checks, explicitly enabled by the containment CI job."""

import json
import os
import socket
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aibenchmark_esw.dataset import DatasetLoader
from aibenchmark_esw.sandbox.executor import ExecutionSandbox


class TestBwrapUnavailable(unittest.TestCase):
    def test_missing_runtime_never_falls_back_to_native(self):
        with patch('aibenchmark_esw.sandbox.containment.shutil.which', return_value=None), \
                self.assertRaisesRegex(ValueError, 'runtime is unavailable|bwrap containment requires Linux'):
            ExecutionSandbox(compiler_path='gcc', isolation='bwrap')


@unittest.skipUnless(os.environ.get('AIBENCHMARK_TEST_BWRAP') == '1' and os.name == 'posix',
                     'Real bubblewrap tests require opt-in Linux namespaces')
class TestRealBwrap(unittest.TestCase):
    def test_environment_filesystem_and_network_boundary(self):
        loader = DatasetLoader()
        task = loader.get_task('tier1_crc16')
        with TemporaryDirectory() as directory, socket.socket() as listener:
            outside = Path(directory) / 'private.txt'
            outside.write_text('host sentinel', encoding='utf-8')
            forbidden = Path(directory) / 'candidate-write.txt'
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            port = listener.getsockname()[1]
            probe = f'''
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>
#include <arpa/inet.h>
__attribute__((constructor)) static void check_boundary(void) {{
    if (getenv("BWRAP_HOST_SECRET")) _exit(101);
    FILE *file = fopen({json.dumps(str(outside))}, "rb");
    if (file) _exit(102);
    file = fopen({json.dumps(str(forbidden))}, "wb");
    if (file) _exit(103);
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in address = {{0}};
    address.sin_family = AF_INET;
    address.sin_port = htons({port});
    address.sin_addr.s_addr = htonl(0x7f000001U);
    if (connect(fd, (struct sockaddr *)&address, sizeof(address)) == 0) _exit(104);
    close(fd);
}}
'''
            with patch.dict(os.environ, {'BWRAP_HOST_SECRET': 'sentinel'}):
                compiled, tests = ExecutionSandbox('gcc', isolation='bwrap').compile_and_test(
                    task, probe + loader.get_reference_solution(task.id))
            self.assertTrue(compiled.success, compiled.output)
            self.assertTrue(tests.passed, tests.output)
            self.assertEqual(outside.read_text(encoding='utf-8'), 'host sentinel')
            self.assertFalse(forbidden.exists())

    def test_timeout_kills_namespace_descendants(self):
        loader = DatasetLoader()
        task = loader.get_task('tier1_crc16')
        task = replace(task, limits=replace(task.limits, timeout_seconds=1))
        code = '''#include <unistd.h>
__attribute__((constructor)) static void hang(void) { if (fork() == 0) for (;;) pause(); for (;;) pause(); }
''' + loader.get_reference_solution(task.id)
        compiled, tests = ExecutionSandbox('gcc', isolation='bwrap').compile_and_test(task, code)
        self.assertTrue(compiled.success, compiled.output)
        self.assertFalse(tests.completed)
        self.assertFalse(tests.passed)


if __name__ == '__main__':
    unittest.main()
