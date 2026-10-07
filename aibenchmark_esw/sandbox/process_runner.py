"""Bounded native process execution; this does not isolate files or networks.

Output goes to a temporary file, so inherited pipe handles cannot block cleanup.
The retained prefix is bounded and the process tree is stopped on output excess.
Windows children join a Job before their first instruction; POSIX children use a
new session. POSIX programs deliberately creating new sessions can escape that
group, so this backend is resource containment, not a hostile-code sandbox.
"""

import math
import os
import signal
import subprocess
import tempfile
import time
import sys
from pathlib import Path


class OutputLimitExceeded(subprocess.SubprocessError):
    def __init__(self, output, limit):
        self.output = output
        super().__init__(f"Output limit exceeded ({limit} bytes); output truncated")


class ExecutionCancelled(subprocess.SubprocessError):
    def __init__(self, output):
        self.output = output
        super().__init__("Execution cancelled")


def _stop_posix_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)  # type: ignore[attr-defined]
    except ProcessLookupError:
        pass
    except PermissionError:
        # Darwin can reject signalling a group containing only its unreaped
        # zombie leader. Reap it and retry, still stopping any live descendants.
        # A live leader or a second permission denial remains an actual error.
        if process.poll() is None:
            raise
        try:
            os.killpg(process.pid, signal.SIGKILL)  # type: ignore[attr-defined]
        except ProcessLookupError:
            pass


class _WindowsJob:
    def __init__(self, cpu_seconds=None, memory_bytes=None):
        import ctypes
        from ctypes import wintypes as w

        self.ctypes = ctypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # Windows-only API; absent in POSIX ctypes stubs.
        size_t = ctypes.c_size_t

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                        ("flags", w.DWORD), ("min_working", size_t), ("max_working", size_t),
                        ("active", w.DWORD), ("affinity", size_t),
                        ("priority", w.DWORD), ("scheduling", w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", size_t),
                        ("job_memory", size_t), ("peak_process", size_t), ("peak_job", size_t)]

        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API; absent in POSIX ctypes stubs.
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if cpu_seconds is not None:
            limits.basic.flags |= 0x4  # JOB_OBJECT_LIMIT_JOB_TIME (all processes)
            limits.basic.job_time = math.ceil(cpu_seconds) * 10_000_000
        if memory_bytes is not None:
            limits.basic.flags |= 0x200  # JOB_OBJECT_LIMIT_JOB_MEMORY
            limits.job_memory = memory_bytes
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API; absent in POSIX ctypes stubs.
            self.close()
            raise error

    def assign_and_resume(self, process):
        """Assign a suspended child, then resume its primary thread safely."""
        import ctypes
        from ctypes import wintypes as w
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API; absent in POSIX ctypes stubs.

        class ThreadEntry(ctypes.Structure):
            _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("thread_id", w.DWORD),
                        ("owner_pid", w.DWORD), ("base_priority", w.LONG),
                        ("delta_priority", w.LONG), ("flags", w.DWORD)]

        self.api.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
        self.api.CreateToolhelp32Snapshot.restype = w.HANDLE
        self.api.Thread32First.argtypes = [w.HANDLE, ctypes.POINTER(ThreadEntry)]
        self.api.Thread32Next.argtypes = [w.HANDLE, ctypes.POINTER(ThreadEntry)]
        self.api.OpenThread.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.api.OpenThread.restype = w.HANDLE
        self.api.ResumeThread.argtypes = [w.HANDLE]
        self.api.ResumeThread.restype = w.DWORD
        snapshot = self.api.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API; absent in POSIX ctypes stubs.
        try:
            entry = ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            available = self.api.Thread32First(snapshot, ctypes.byref(entry))
            while available:
                if entry.owner_pid == process.pid:
                    thread = self.api.OpenThread(0x2, False, entry.thread_id)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API; absent in POSIX ctypes stubs.
                    try:
                        if self.api.ResumeThread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API; absent in POSIX ctypes stubs.
                    finally:
                        self.api.CloseHandle(thread)
                    return
                available = self.api.Thread32Next(snapshot, ctypes.byref(entry))
            raise OSError("Cannot locate suspended process thread")
        finally:
            self.api.CloseHandle(snapshot)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def run_bounded(command, *, timeout, max_output_bytes, cwd=None, env=None,
                isolation="native", memory_limit_bytes=None, cancel_event=None):
    """Return CompletedProcess with bounded byte output, or a diagnostic error.

    Deadline/output polling uses a 10 ms interval. Output storage can exceed the
    threshold between polls, but only max_output_bytes are read into memory.
    Process cleanup has a separate one-second wait bound and uses no readers.
    """
    cpu_seconds = timeout if isolation == "process" else None
    memory_bytes = memory_limit_bytes if isolation == "process" else None
    job = _WindowsJob(cpu_seconds, memory_bytes) if os.name == "nt" else None
    process = None
    reason = None
    try:
        with tempfile.TemporaryFile() as output:
            kwargs = dict(cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          stdout=output, stderr=subprocess.STDOUT)
            if os.name == "nt":
                kwargs["creationflags"] = 0x08000000 | 0x4  # CREATE_NO_WINDOW | CREATE_SUSPENDED
            else:
                kwargs["start_new_session"] = True
                if isolation == "process":
                    command = [sys.executable, str(Path(__file__).with_name("process_limits.py")),
                               str(max(1, math.ceil(timeout))), str(memory_bytes or 0)] + list(command)
            deadline = time.monotonic() + timeout
            process = subprocess.Popen(command, **kwargs)
            try:
                if job is not None:
                    job.assign_and_resume(process)
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        reason = "cancelled"
                        break
                    if os.fstat(output.fileno()).st_size > max_output_bytes:
                        reason = "output"
                        break
                    if process.poll() is not None:
                        break
                    if time.monotonic() >= deadline:
                        reason = "timeout"
                        break
                    time.sleep(0.01)
            finally:
                # Cleanup also runs on KeyboardInterrupt and assignment errors.
                try:
                    if job is not None:
                        job.close()
                    else:
                        _stop_posix_group(process)
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=1)
            output.seek(0)
            captured = output.read(max_output_bytes)
            truncated = os.fstat(output.fileno()).st_size > max_output_bytes
            if reason == "cancelled":
                raise ExecutionCancelled(captured)
            if reason == "timeout":
                error = subprocess.TimeoutExpired(command, timeout, output=captured)
                setattr(error, "output_truncated", truncated)
                raise error
            if reason == "output" or truncated:
                raise OutputLimitExceeded(captured, max_output_bytes)
            return subprocess.CompletedProcess(command, process.returncode, captured, b"")
    finally:
        if job is not None:
            job.close()
