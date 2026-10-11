"""POSIX resource-limit launcher; no preexec_fn in parallel evaluators."""
import os
import resource
import signal
import subprocess
import sys


def limit(kind, value):
    _, hard = resource.getrlimit(kind)  # type: ignore[attr-defined]  # POSIX launcher.
    effective = value if hard == resource.RLIM_INFINITY else min(value, hard)  # type: ignore[attr-defined]
    resource.setrlimit(kind, (effective, effective))  # type: ignore[attr-defined]


if __name__ == "__main__":
    # Python ignores SIGXFSZ at startup; restore it before exec'ing native code.
    signal.signal(signal.SIGXFSZ, signal.SIG_DFL)  # type: ignore[attr-defined]
    cpu, memory, processes = map(int, sys.argv[1:4])
    if cpu:
        limit(resource.RLIMIT_CPU, cpu)  # type: ignore[attr-defined]
    if memory:
        limit(resource.RLIMIT_AS, memory)  # type: ignore[attr-defined]
    if processes:
        # macOS runners already have more than 64 processes under their UID.
        # NPROC is per UID, so reserve the requested additional process budget
        # above the current population instead of preventing even clang exec.
        if sys.platform == "darwin":
            population = subprocess.check_output(
                ["/bin/ps", "-U", str(os.getuid()), "-o", "pid="], timeout=2,
            ).splitlines()
            processes += max(0, len(population) - 1)
        limit(resource.RLIMIT_NPROC, processes)  # type: ignore[attr-defined]
    limit(resource.RLIMIT_FSIZE, 16777216)  # type: ignore[attr-defined]
    limit(resource.RLIMIT_CORE, 0)  # type: ignore[attr-defined]
    limit(resource.RLIMIT_NOFILE, 256)  # type: ignore[attr-defined]
    os.execvpe(sys.argv[4], sys.argv[4:], os.environ)
