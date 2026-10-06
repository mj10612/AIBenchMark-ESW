"""POSIX resource-limit launcher, avoiding preexec_fn in parallel evaluators."""

import os
import resource
import sys


if __name__ == "__main__":
    cpu, memory = int(sys.argv[1]), int(sys.argv[2])
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))  # type: ignore[attr-defined]  # Launcher executes only on POSIX.
    if memory:
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))  # type: ignore[attr-defined]  # Launcher executes only on POSIX.
    os.execvpe(sys.argv[3], sys.argv[3:], os.environ)
