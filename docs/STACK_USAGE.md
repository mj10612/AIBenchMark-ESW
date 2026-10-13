# Optional compiler stack evidence

Add `--stack-usage` to `run`, `eval`, or `replay` to request
compiler-produced per-function stack records alongside the existing object
Flash/RAM measurement. For example:

```sh
aibenchmark-esw run --model baseline --tasks tier3_spi_flash --compiler clang --stack-usage --output stack.json
aibenchmark-esw report --results stack.json --format markdown --output stack.md
```

The existing memory score measures static object sections and common symbols.
Stack evidence is a separate `tasks[].stack_usage` object with `candidate` and
`reference` records. It does not change scoring or add a stack budget. Default
runs omit this object. JSON preserves each function, compiler identity/version,
target, and compile flags; Markdown and HTML show bounded-function coverage and
the maximum among available per-function records. HTML also includes the full
evidence in task details.

Supported GCC/Clang drivers use `-fstack-usage` during the same implementation
object compilation used for footprint measurement. The test harness and runtime
are excluded. Reference evidence is retained in the reference-validation cache;
the cache includes evaluation settings, so opt-in and default runs cannot share
incompatible entries. Compiler artifacts are read before temporary workspaces
are cleaned up, with an output-size limit. Missing, malformed, excessive,
unsupported, or unsuccessful compiler records are explicitly unavailable, never
replaced by zero. A compiler that explicitly rejects the evidence flag is retried
without that flag for ordinary object measurement.

Record classifications are `static`, `dynamic-bounded`, and `unknown`. Unbounded
dynamic records preserve the compiler's known frame component in
`reported_bytes`, while their bound in `bytes` remains null. The reported
`max_per_function_bytes` covers only bounded records; coverage exposes omitted
unknown frames. A compiler-reported static zero is valid evidence, unlike a
missing measurement.

This maximum is **not a whole-program peak stack bound**. Recursion, nested call
chains, interrupts, and indirect calls are not analyzed. The report therefore
always leaves `whole_program_peak_bytes` null. Variable allocations may make a
function bound unknown. Compiler optimization and ABI choices can eliminate or
reshape automatic storage: the SPI reference's 260-byte staging buffer should
produce nonzero evidence on supported toolchains, but its frame need not equal
260 bytes. Hardware validation remains necessary.

Native records identify the `host` target. With, for example,
`--target arm:cortex-m0 --cross-compiler clang --stack-usage`, the records come
from the ARM implementation object and identify that target and cross compiler.
Unity tests still run on the host. ARM, AVR, RISC-V, and native measurements must
be interpreted separately; they are not calibrated task-level stack budgets.

The file format and qualifier meanings follow the official
[GCC stack-usage documentation](https://gcc.gnu.org/onlinedocs/gcc-14.1.0/gnat_ugn/Static-Stack-Usage-Analysis.html).
Clang documents its supported flag in the
[command-line reference](https://clang.llvm.org/docs/ClangCommandLineReference.html#cmdoption-clang-fstack-usage).
