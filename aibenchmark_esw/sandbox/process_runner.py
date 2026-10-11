"""Bounded native process execution; this does not isolate files or networks.

Output goes to a non-seekable pipe drained without blocking on inherited handles.
The retained prefix is bounded and the process tree is stopped on output excess.
Windows children join a Job before their first instruction; POSIX children use a
new session. POSIX programs deliberately creating new sessions can escape that
group, so this backend is resource containment, not a hostile-code sandbox.
"""

import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


class OutputLimitExceeded(subprocess.SubprocessError):
    def __init__(self, output, limit):
        self.output = output
        super().__init__(f"Output limit exceeded ({limit} bytes); output truncated")


class ExecutionCancelled(subprocess.SubprocessError):
    def __init__(self, output):
        self.output = output
        super().__init__("Execution cancelled")


class ExecutionCleanupError(subprocess.SubprocessError):
    def __init__(self, output, error, reason=None):
        self.output = output
        context = "output limit (output truncated)" if reason == "output" else reason or "execution"
        super().__init__(f"Process cleanup failed after {context}: {error}")


class _OutputCapture:
    """Poll a pipe on both platforms, retaining a bounded immutable prefix."""
    def __init__(self, stream, limit):
        self.stream, self.limit = stream, limit
        self.output = bytearray()
        self.exceeded = False
        if os.name == "nt":
            import ctypes
            import msvcrt
            from ctypes import wintypes
            self.api = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # Windows-only API.
            self.api.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                               ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
            self.handle = msvcrt.get_osfhandle(stream.fileno())  # type: ignore[attr-defined]  # Windows-only API.
        else:
            os.set_blocking(stream.fileno(), False)  # type: ignore[attr-defined]  # POSIX-only branch.

    def drain(self):
        while not self.exceeded:
            amount = min(65536, self.limit - len(self.output) + 1)
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes
                available = wintypes.DWORD()
                if not self.api.PeekNamedPipe(self.handle, None, 0, None, ctypes.byref(available), None):
                    if ctypes.get_last_error() == 109:  # type: ignore[attr-defined]  # Windows ERROR_BROKEN_PIPE.
                        return
                    raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API.
                if not available.value:
                    return
                amount = min(amount, available.value)
            try:
                chunk = os.read(self.stream.fileno(), amount)
            except BlockingIOError:
                return
            if not chunk:
                return
            remaining = self.limit - len(self.output)
            self.output.extend(chunk[:remaining])
            self.exceeded = len(chunk) > remaining


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
        self.api.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        self.api.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                       w.DWORD, ctypes.c_void_p]
        self.api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        self.api.OpenProcess.restype = w.HANDLE
        self.api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API; absent in POSIX ctypes stubs.
        limits = Extended()
        limits.basic.active = 64
        limits.basic.flags = 0x2000 | 0x8  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
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
            import ctypes
            from ctypes import wintypes

            class Accounting(ctypes.Structure):
                _fields_ = [(name, ctypes.c_longlong) for name in
                            ("user_time", "kernel_time", "period_user_time", "period_kernel_time")]
                _fields_ += [(name, wintypes.DWORD) for name in
                             ("page_faults", "total_processes", "active_processes", "terminated_processes")]
            handles = []
            try:
                # Job accounting can reach zero before process-object teardown
                # releases inherited file handles. Wait on the process objects too.
                capacity = 64
                while True:
                    identities = ctypes.create_string_buffer(8 + capacity * ctypes.sizeof(ctypes.c_size_t))
                    if self.api.QueryInformationJobObject(self.handle, 3, identities, len(identities), None):
                        count = ctypes.c_uint32.from_buffer(identities, 4).value
                        pids = (ctypes.c_size_t * count).from_buffer(identities, 8)
                        for pid in pids:
                            handle = self.api.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
                            if handle:
                                handles.append(handle)
                        break
                    if ctypes.get_last_error() != 234 or capacity >= 4096:  # type: ignore[attr-defined]  # Windows ERROR_MORE_DATA.
                        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API.
                    capacity *= 2
                if not self.api.TerminateJobObject(self.handle, 1):
                    raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API.
                deadline = time.monotonic() + 1
                while True:
                    accounting = Accounting()
                    if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting),
                                                               ctypes.sizeof(accounting), None):
                        raise ctypes.WinError(ctypes.get_last_error())  # type: ignore[attr-defined]  # Windows-only API.
                    if accounting.active_processes == 0:
                        break
                    if time.monotonic() >= deadline:
                        raise OSError("Windows Job descendants did not terminate within the cleanup deadline")
                    time.sleep(0.005)
                for handle in handles:
                    remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
                    if self.api.WaitForSingleObject(handle, remaining_ms) != 0:
                        raise OSError("Windows Job process handles did not close within the cleanup deadline")
            finally:
                for handle in handles:
                    self.api.CloseHandle(handle)
                self.api.CloseHandle(self.handle)
                self.handle = None


def run_bounded(command, *, timeout, max_output_bytes, cwd=None, env=None,
                isolation="native", memory_limit_bytes=None, cancel_event=None):
    """Return CompletedProcess with bounded byte output, or a diagnostic error.

    Deadline/output polling uses a 10 ms interval. The pipe's kernel buffer and
    retained prefix are bounded. Seeking/truncating stdout cannot reset accounting.
    Process cleanup has a separate one-second wait bound and uses no reader threads.
    """
    cpu_seconds = timeout if isolation == "process" else None
    memory_bytes = memory_limit_bytes if isolation == "process" else None
    job = _WindowsJob(cpu_seconds, memory_bytes) if os.name == "nt" else None
    process = None
    reason = None
    capture = None
    cleanup_error = None
    try:
        kwargs = dict(cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000 | 0x4  # CREATE_NO_WINDOW | CREATE_SUSPENDED
        else:
            kwargs["start_new_session"] = True
            if isolation in ("native", "process"):
                command = [sys.executable, str(Path(__file__).with_name("process_limits.py")),
                           str(max(1, math.ceil(timeout)) if isolation == "process" else 0), str(memory_bytes or 0),
                           "64" if isolation == "process" else "0"] + list(command)
        deadline = time.monotonic() + timeout
        process = subprocess.Popen(command, **kwargs)
        assert process.stdout is not None
        with process.stdout:
            capture = _OutputCapture(process.stdout, max_output_bytes)
            try:
                if job is not None:
                    job.assign_and_resume(process)
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        reason = "cancelled"
                        break
                    capture.drain()
                    if capture.exceeded:
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
                except OSError as teardown_error:
                    cleanup_error = teardown_error
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=1)
            capture.drain()
            captured = bytes(capture.output)
            truncated = capture.exceeded
            if cleanup_error is not None:
                raise ExecutionCleanupError(captured, cleanup_error, reason)
            if reason == "cancelled":
                raise ExecutionCancelled(captured)
            if reason == "timeout":
                error = subprocess.TimeoutExpired(command, timeout, output=captured)
                error.output_truncated = truncated  # type: ignore[attr-defined]  # Preserve bounded diagnostic metadata.
                raise error
            if reason == "output" or truncated:
                raise OutputLimitExceeded(captured, max_output_bytes)
            return subprocess.CompletedProcess(command, process.returncode, captured, b"")
    finally:
        if job is not None:
            job.close()
