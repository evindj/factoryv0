---
name: tdd
description: Stage 3 of the software factory. Turn each approved verification row (V-NN) into an executable check, prove it fails (red), implement until it passes (green), then refactor, with static checks enforced on every edit.
---

# Stage 3: Verification-driven TDD

Prerequisites: spec and verification approved; formal spec model-checked if required. Run `.factory/factory stage tdd`.

## Loop, one V-row (or a small cohesive group) at a time
1. **Write the check** exactly as verification.md describes it: test, property, architecture rule, type-level constraint, benchmark assertion. Name tests after the row, e.g. `test_v03_rejects_oversized_payload` / `@DisplayName("V-03 ...")`.
2. **Red:** `.factory/factory record-red V-03 "<command that runs just this check>"`. It must fail *for the right reason*: an assertion about missing behaviour, not an import error or typo. If it passes before you've implemented anything, the check is wrong or the behaviour already exists. Investigate before going on. The run is logged in `tdd-log.md`.
3. **Green:** write the minimum production code that makes it pass. The post-edit hook formats and lints every file you touch. Fix what it reports right away.
4. **Refactor** while green. Run `.factory/factory gate` (format, lint, types, all tests) before moving on.
5. Tick the row off mentally. Keep going until every automated row is green.

## Rules
- Static checks are part of "green". mypy --strict / ErrorProne errors are failures, not warnings.
- Don't change a test to fit the implementation unless the test was wrong. If the test was wrong, say why in `tdd-log.md`.
- No `sleep`-based timing in tests. Use fake clocks, latches or awaitility-style polling with timeouts.
- Property tests: keep the failing seed or example Hypothesis/jqwik reports as an explicit regression example.
- If a row turns out to be infeasible or wrong, stop and update verification.md. That needs re-approval.
- A skipped test verifies nothing. The gate fails on any skipped test in fresh JUnit-XML reports (pytest, surefire, Gradle) unless the human lists it under `allow_skipped` in `.factory/config.json`.
- jqwik gotcha: a `@Property` carrying JUnit annotations (`@DisplayName`, `@Test`) is silently skipped. Use jqwik's `@Label`.
- Red must fail *for the right reason*: if the first red is an ImportError or compile error, add the minimal API stub (keeping the old behaviour) and get a behavioural red.
- **Manual** rows: do not fake them. Leave them for the evidence stage, where the human performs or witnesses them.

## Exit
`.factory/factory gate` passes, every automated V-row has a red entry in `tdd-log.md` and is now green. Then hand off to the `test-auditor` subagent and the `evidence` skill.
