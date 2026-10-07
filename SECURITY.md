# Security policy

## Reporting

Use the repository's private vulnerability reporting feature if the Security tab
offers **Report a vulnerability**. Otherwise, open an issue requesting a private
contact channel without including exploit code or sensitive information. Avoid
posting credentials, account details, or private model responses in public issues.

Reports should identify the affected revision, operating system/compiler, a
minimal reproducer, and the impact. Fixes target the current main branch; the
project does not currently provide long-term support branches or a response SLA.

## Execution boundary

By default, candidate C executes as a native program with the current user's
permissions. Native and process modes provide temporary workspaces, bounded
compilation/output, cancellation and timeouts. They provide no filesystem or
network isolation. Process mode also caps CPU time and optional memory.

Run untrusted candidates in an isolated, disposable environment with no secrets
or sensitive mounted files. Native/process mode does not restrict filesystem,
network or child-process access. Provider evaluations require opt-in API access; CI runs
only checked-in test fixtures and golden references without provider credentials.


Native execution captures a bounded output prefix in a temporary file and owns
Windows Job/POSIX process groups. Opt-in process mode adds CPU and memory caps.
Filesystem and network access remain available; a POSIX descendant deliberately
calling setsid can escape the original group. Run untrusted code inside an
external container/VM or select the explicit backend below. Static host-API findings and
sanitizers provide diagnostic evidence, not access enforcement.

The runner uses names without completion tokens, an empty scratch working
directory, and a receipt channel opened before the candidate runs. A receipt is
written only after the trusted suite returns. Candidate stdout alone cannot
complete the suite. These measures reject the published cwd-enumeration forgery;
they **cannot authenticate arbitrary hostile native code**. The candidate shares
the harness address space and can read its binary, inspect arguments or alter
its receipt. Static heuristics and completion tokens are integrity checks, not
a security boundary; container isolation protects the host, not the in-process
test oracle from malicious code that deliberately reverse-engineers it.

## External containment

`--isolation container --container-engine docker` (or `podman`) compiles and
executes candidates inside a previously pulled compiler-equipped image, default
`gcc:14`. Use `docker pull gcc:14` before evaluation. `--container-image` selects
another image; its resolved immutable image ID is recorded and used for every
invocation. Missing runtimes/images fail explicitly, without native fallback.
Container compiler names refer to executables inside that image; an installed
host toolchain is not required. Use an image containing Clang/cross tools when
requesting them, and avoid mounting the host checkout or credentials manually.

The backend mounts only the disposable evaluation workspace, after copying
trusted task headers and Unity into it. Containers use a read-only root, no
network, dropped capabilities, `no-new-privileges`, the non-root workspace owner's
uid/gid (65534 when the host runs as root or on Windows), a process quota,
one CPU, a private bounded `/tmp`, optional memory quota and the task deadline.
Compiler diagnostics and test output share the configured output cap. The
named container is forcibly removed after execution, including timeout or
cancellation; killing the engine client alone is insufficient. Docker/Podman
daemon access is a trusted administrative capability, and kernel/engine defects
remain outside this boundary. Prefer rootless Podman/Docker and a disposable VM
when evaluating intentionally adversarial code.

Linux `--isolation bwrap` uses private user/process/network namespaces and
read-only system compiler/runtime roots (`/usr`, `/bin`, `/lib`, `/lib64`), a
private `/proc`, `/dev` and `/tmp`, and the sole writable evaluation workspace.
Home directories and the checkout are not mounted. It requires working user
namespaces and bubblewrap; it does not silently relax unavailable restrictions.
System libraries and compiler files within those system roots remain readable.

Footprint defaults to a host object, not an MCU image. Opt-in AVR/ARM/RISC-V compilation
measures allocated target-object sections with target-scoped budgets; it excludes
final linking, startup code, stack and heap. Host Unity tests still supply
functional evidence. MISRA heuristics cover allocation references, goto, floating
types, long/short and signed/unsigned basic types, and host capability APIs; plain
int for status/main and plain char for character data are deliberate exceptions.
Mach-O sections/common symbols are supported; universal objects report the
componentwise maximum over architecture slices. This is a conservative budget
proxy rather than a sum of mutually exclusive deployment architectures.
`--extended-safety-rules` enables lexical advisories for stdio, nonlocal control,
nondeterminism, recursion, possible VLAs/alloca, math/complex dependencies and
busy-wait loops. These approximate diagnostics are not a formal MISRA checker.
`--warnings` adds compiler findings to safety scoring; both switches are off by
default and included in evaluation provenance.
