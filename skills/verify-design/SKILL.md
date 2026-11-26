---
name: verify-design
description: Stage 2 of the software factory. Before any test or code is written, brainstorm every way each acceptance criterion will be proven, run an adversarial "how could this pass and still be wrong?" review, and decide whether a formal spec (TLA+/Alloy) is needed. Writes verification.md.
---

# Stage 2: Verification design

This is the heart of the factory. The question is not "what unit tests do I write?" but **"what would convince a sceptical expert that this change is correct, and how do we produce that evidence automatically?"**

Prerequisite: spec.md is approved (`.factory/factory status`). Run `.factory/factory stage verify-design`.

## Procedure
1. **Enumerate per AC, per dimension.** For every `AC-n`, go through each dimension in the template: functional, property, edge, contract, static, concurrency, non-functional, strength, manual. Each one gets one or more `V-NN` rows, or a one-line "n/a: reason" in *Dimension notes*. Skipping a dimension silently is not allowed.
2. **Make every row concrete.** "Test the parser" is not a row. "`parse(b'')` raises `EmptyInput`; pytest `tests/test_parse.py::test_empty`" is. Name the technique and tool, and the command or test location you intend to use. Prefer:
   - Python: pytest, Hypothesis (incl. `RuleBasedStateMachine` for stateful code), mypy --strict, ruff, import-linter, mutmut, pytest-benchmark
   - Java: JUnit 5, AssertJ, jqwik (incl. stateful actions), ErrorProne/NullAway, ArchUnit, PIT, JMH, Testcontainers (+ Toxiproxy for faults)
3. **Prefer stronger techniques.** A property over generated inputs beats five hand-picked examples. A type that makes a bad state unrepresentable beats a test that checks for it. An architecture rule beats a code-review convention.
4. **Adversarial pass.** Ask the `verification-designer` subagent (or do it yourself, honestly) to list how the implementation could be wrong and still pass every row: off-by-one at boundaries, wrong but consistent units, tests that share the implementation's bug (oracle problem), mocks that hide integration failures, flaky timing, untested config paths, swallowed exceptions. Each scenario becomes a new V-row or an explicitly accepted risk.
5. **Formal spec decision.** Answer the checklist in section 4. If any answer is yes, propose a formal spec to the user: what would be modelled (protocol, state machine, invariants), which tool (TLA+ default, Alloy for structural/data-model invariants), and which properties (safety and liveness). Record the decision and set `formal: required` or `formal: not-needed` in the frontmatter. The edit guard refuses `undecided`.
6. **Feasibility.** You may write throwaway tests or harnesses to check that a technique works (e.g. Testcontainers starts). Production code stays blocked.
7. **Approval.** Give the user a compact summary: rows per AC, the strongest checks, accepted risks, and the formal-spec decision. Ask them to run `! .factory/factory approve verification`.

## Quality bar for the matrix
- Every AC has at least one automated row that would fail if the AC were violated.
- Every error path in the spec has a row.
- At least one `strength` row (mutation testing on the touched modules, with a target such as no surviving mutants in new code, or documented survivors).
- Static rows are real gates: they run in `.factory/factory gate`.
