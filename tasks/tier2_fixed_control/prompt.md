<!-- AIBENCHMARK_ESW_CANARY_V1_tier2_fixed_control -->
# Task: Q8 Saturating PID and Low-Pass Filter

Gains are signed Q8 (256=1.0); error/output are signed integers. Init accepts min<=max, zeroes previous/integral, sets ready; invalid reinit clears ready. Step with null/unready returns zero. Tentatively accumulate error into integral with INT32 saturation. Compute numerator kp*error + ki*tentative_integral + kd*(error-previous) in signed 64-bit then divide by256 truncating toward zero. Clamp output to configured limits. Anti-windup: when unclamped output exceeds max with positive error or is below min with negative error, reject tentative integral but return the clamped tentative output. Otherwise commit integral; always remember previous error. Filter alpha clamps to [0,256], computes `(previous*(256-alpha)+sample*alpha)/256` with truncation toward zero. Avoid narrowing before division or saturation.

Implement `src/fixed_control.c` using the public header. No allocation, host I/O, floating point, or unbounded loops. Caller owns all state and storage. The tests are public host fixtures, not hardware certification.
