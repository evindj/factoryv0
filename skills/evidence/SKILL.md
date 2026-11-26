---
name: evidence
description: Stage 4 of the software factory. Run every verification check, record proof for each V-NN row in evidence.md, run mutation testing on the touched code, and refuse to call the work done until the evidence check passes.
---

# Stage 4: Evidence

Run `.factory/factory stage evidence`. From now on the Stop hook also requires `.factory/factory evidence` to pass.

1. **Audit first.** Ask the `test-auditor` subagent to review the tests against verification.md and tdd-log.md. Fix what it finds.
2. **Run everything.** `.factory/factory gate`, plus every row-specific command from verification.md: integration tests, benchmarks, architecture tests, and model checks (re-run them, don't trust old logs).
3. **Mutation testing** on the touched modules:
   - Python: `mutmut run --paths-to-mutate <touched files>` then `mutmut results`
   - Java: `mvn org.pitest:pitest-maven:mutationCoverage -DtargetClasses=<pkg>.*` or `./gradlew pitest`
   Each surviving mutant is either killed by a new or improved test (going back through red/green) or explained as equivalent. Record the numbers.
4. **Fill evidence.md.** One table row per V-row: `PASS` with the command and the key line of output (test name, counts, p99), `MANUAL-PASS` with who observed what, or `ACCEPTED-RISK` with the user's explicit agreement and the reason. Never write PASS for something you didn't run in this stage.
5. **Manual rows:** give the user the exact steps and the expected observation, and let them confirm.
6. `.factory/factory evidence` must report all rows covered. Then report to the user: summary, evidence table status, mutation score, residual risks. Finish with `.factory/factory stage done`.
