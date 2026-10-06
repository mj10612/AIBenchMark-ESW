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

Candidate C executes as a native program with the current user's permissions.
The ExecutionSandbox name refers to temporary workspaces, compilation, and
timeouts; it does not provide OS isolation. Static checks and the trusted-runner
completion marker are benchmark integrity checks, not a security boundary.

Run untrusted candidates in an isolated, disposable environment with no secrets
or sensitive mounted files. The evaluator does not restrict filesystem, network,
or child-process access. Provider evaluations require opt-in API access; CI runs
only checked-in test fixtures and golden references without provider credentials.


Native execution captures a bounded output prefix in a temporary file and owns
Windows Job/POSIX process groups. Opt-in process mode adds CPU and memory caps.
Filesystem and network access remain available; a POSIX descendant deliberately
calling setsid can escape the original group. Run untrusted code inside an
external container/VM with suitable access controls. Static host-API findings and
sanitizers provide diagnostic evidence, not access enforcement.

Footprint defaults to a host object, not an MCU image. Opt-in AVR/ARM compilation
measures allocated target-object sections with target-scoped budgets; it excludes
final linking, startup code, stack and heap. Host Unity tests still supply
functional evidence. MISRA heuristics cover allocation references, goto, floating
types, long/short and signed/unsigned basic types, and host capability APIs; plain
int for status/main and plain char for character data are deliberate exceptions.
