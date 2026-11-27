---
name: evidence
description: Stage 5 of the software factory. Run every verification and design-conformance check, record proof for each V-NN and DC-* row in evidence.md, run mutation testing on the touched code, and refuse to call the work done until the evidence check passes.
---

# Stage 5: Evidence

Run `.factory/factory stage evidence`. From now on the Stop hook also requires `.factory/factory evidence` to pass.

1. **Audit first.**
   - Ask the `test-auditor` subagent to review the tests against verification.md, the design DC-rows and tdd-log.md.
   - Ask the `design-auditor` subagent to compare the implementation with the approved design docs and artifacts.
   - Fix what they find. A design drift is fixed in the code, or by revising the design doc with re-approval. Record the auditor verdict in evidence.md.
2. **Run everything.** `.factory/factory gate`, plus every row-specific command from verification.md and the design docs: integration tests, contract tests against the approved API artifact, migration and schema tests on the real engine, fault injection, benchmarks, architecture rules, and model checks. Re-run them; don't trust old logs.
3. **Mutation testing** on the touched modules:
   - Python: `mutmut run --paths-to-mutate <touched files>` then `mutmut results`
   - Java: `mvn org.pitest:pitest-maven:mutationCoverage -DtargetClasses=<pkg>.*` or `./gradlew pitest`
   Each surviving mutant is either killed by a new or improved test (going back through red/green) or explained as equivalent. Record the numbers.
4. **Fill evidence.md.** One table row per V-row and per DC-row (in the *Design conformance* table): `PASS` with the command and the key line of output (test name, counts, p99), `MANUAL-PASS` with who observed what, or `ACCEPTED-RISK` with the user's explicit agreement and the reason. Never write PASS for something you didn't run in this stage.
5. **Manual rows:** give the user the exact steps and the expected observation, and let them confirm.
6. `.factory/factory evidence` must report all rows covered. Then report to the user: summary, evidence table status, mutation score, residual risks. Finish with `.factory/factory stage done`.
