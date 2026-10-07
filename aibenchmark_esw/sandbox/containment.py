"""Opt-in external execution boundaries; never silently fall back to native.

Only a disposable compilation workspace is writable. Task headers and Unity
are copied into it before invocation, so containers never mount the checkout.
Docker/Podman images must already be present; resolved image IDs pin execution.
"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from aibenchmark_esw.sandbox.process_runner import run_bounded


class ContainmentBackend:
    def __init__(self, mode, engine=None, image="gcc:14", runtime=None):
        self.mode, self.image, self.image_digest = mode, image, None
        uid, gid = getattr(os, "getuid", lambda: 0)(), getattr(os, "getgid", lambda: 0)()
        # Matching the non-root bind-mount owner lets the host inspect/chmod
        # compiler artifacts on later invocations. Root hosts remain unprivileged.
        self.user = f"{uid}:{gid}" if uid > 0 else "65534:65534"
        if mode == "bwrap":
            if os.name == "nt":
                raise ValueError("bwrap containment requires Linux")
            self.engine = "bwrap"
            self.runtime = runtime or shutil.which("bwrap")
        else:
            if engine is not None and engine not in ("docker", "podman"):
                raise ValueError("container_engine must be docker or podman")
            self.engine = engine or next((name for name in ("docker", "podman") if shutil.which(name)), "docker")
            self.runtime = runtime or shutil.which(self.engine)
        if not self.runtime:
            raise ValueError("Requested container runtime is unavailable; install Docker/Podman or bwrap explicitly")
        if mode == "container":
            try:
                inspected = subprocess.run([self.runtime, "image", "inspect", "--format={{.Id}}", image],
                                           capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
                identities = inspected.stdout.strip().splitlines()
                if inspected.returncode != 0 or not identities or not identities[0].startswith("sha256:"):
                    raise ValueError("Container image is unavailable; pull a compiler-equipped image first: " + image)
                self.image_digest = identities[0]
            except (OSError, subprocess.SubprocessError) as error:
                raise ValueError("Cannot inspect container runtime/image: " + str(error)) from error

    def settings(self):
        return {"backend": self.mode, "engine": self.engine, "image": self.image if self.mode == "container" else None,
                "image_digest": self.image_digest, "network": "none", "root_filesystem": "read-only",
                "mount_scope": "ephemeral-workspace", "capabilities": "none", "no_new_privileges": True,
                "user": self.user if self.mode == "container" else "current-user-namespace",
                "pids_limit": 64 if self.mode == "container" else None, "cpus": 1 if self.mode == "container" else None}

    def _workspace_command(self, command, cwd):
        cwd = Path(cwd).resolve()
        # Test execution begins in empty scratch below the binary workspace.
        workspace = cwd.parent if cwd.name == "scratch" else cwd
        workspace.mkdir(parents=True, exist_ok=True)
        workspace.chmod(0o777)
        copies = workspace / ".containment-inputs"
        mapping: dict = {}
        translated = []
        for index, argument in enumerate(command):
            value = str(argument)
            if index == 0 and not Path(value).is_relative_to(workspace):
                name = Path(value).name
                value = name[:-4] if name.lower().endswith(".exe") else name
            else:
                prefix = ""
                path = Path(value)
                if value.startswith("-I") and len(value) > 2:
                    prefix, path = "-I", Path(value[2:])
                if path.is_absolute():
                    resolved = path.resolve()
                    if not resolved.is_relative_to(workspace):
                        if not resolved.exists():
                            raise ValueError("Containment input does not exist: " + str(resolved))
                        if resolved not in mapping:
                            destination = copies / str(len(mapping)) / resolved.name
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            if resolved.is_dir():
                                shutil.copytree(resolved, destination, dirs_exist_ok=True)
                            else:
                                shutil.copy2(resolved, destination)
                            mapping[resolved] = destination
                        resolved = mapping[resolved]
                    value = prefix + "/workspace/" + resolved.relative_to(workspace).as_posix()
            translated.append(value)
        # A non-root container needs to create compiler artifacts and receipt.
        # Permissions apply solely to this ephemeral workspace.
        for path in workspace.rglob("*"):
            if path.is_symlink():
                continue
            if path.is_dir():
                path.chmod(0o777)
            else:
                path.chmod(0o777 if os.access(path, os.X_OK) else 0o666)
        container_cwd = "/workspace" + ("/scratch" if cwd != workspace else "")
        return workspace, container_cwd, translated

    def run(self, command, *, timeout, max_output_bytes, cwd, env=None, isolation=None,
            memory_limit_bytes=None, cancel_event=None):
        workspace, inner_cwd, inner = self._workspace_command(command, cwd)
        if self.mode == "container":
            name = "aibenchmark-" + uuid.uuid4().hex
            invocation = [self.runtime, "run", "--rm", "--pull=never", "--name", name,
                          "--read-only", "--network=none", "--cap-drop=ALL",
                          "--security-opt=no-new-privileges", "--user=" + self.user, "--pids-limit=64", "--cpus=1",
                          "--tmpfs=/tmp:rw,nosuid,nodev,size=64m", "--mount",
                          "type=bind,source=" + str(workspace) + ",target=/workspace",
                          "--workdir", inner_cwd]
            if memory_limit_bytes is not None:
                invocation += ["--memory=" + str(memory_limit_bytes), "--memory-swap=" + str(memory_limit_bytes)]
            for key in ("ASAN_OPTIONS", "UBSAN_OPTIONS"):
                if env and key in env:
                    invocation += ["--env", key + "=" + env[key]]
            invocation += [self.image_digest, *inner]
            finished = False
            try:
                result = run_bounded(invocation, timeout=timeout, max_output_bytes=max_output_bytes,
                                     cancel_event=cancel_event)
                finished = True
                return result
            finally:
                # Killing only the CLI cannot stop daemon-owned descendants.
                removed = run_bounded([self.runtime, "rm", "--force", name], timeout=5, max_output_bytes=65536)
                if not finished and removed.returncode != 0:
                    text = removed.stdout.decode("utf-8", errors="replace").lower()
                    absent = any(message in text for message in ("no such container", "no such object", "no container with"))
                    if not absent:
                        raise OSError("Container cleanup failed; runtime did not confirm removal: " + text)
        invocation = [self.runtime, "--unshare-all", "--die-with-parent", "--new-session",
                      "--cap-drop", "ALL", "--clearenv", "--setenv", "PATH", "/usr/bin:/bin",
                      "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
        for directory in ("/usr", "/bin", "/lib", "/lib64"):
            if Path(directory).exists():
                invocation += ["--ro-bind", directory, directory]
        for file in ("/etc/ld.so.cache", "/etc/ld.so.conf"):
            if Path(file).is_file():
                invocation += ["--ro-bind", file, file]
        invocation += ["--bind", str(workspace), "/workspace", "--chdir", inner_cwd]
        for key in ("ASAN_OPTIONS", "UBSAN_OPTIONS"):
            if env and key in env:
                invocation += ["--setenv", key, env[key]]
        invocation += ["--", *inner]
        return run_bounded(invocation, timeout=timeout, max_output_bytes=max_output_bytes,
                           isolation="process", memory_limit_bytes=memory_limit_bytes, cancel_event=cancel_event)
