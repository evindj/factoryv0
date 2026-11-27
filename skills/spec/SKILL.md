---
name: spec
description: Write or revise the feature spec (docs/specs/NNNN-slug/spec.md) with testable Given/When/Then acceptance criteria. Stage 1 of the software factory.
---

# Stage 1: Spec

Goal: a short spec whose acceptance criteria are precise enough that verification can be designed against them.

1. If no feature is active, run `.factory/factory new <slug>` and `.factory/factory stage spec`.
2. Read the relevant code first. Ground the spec in what exists: interfaces, data types, current behaviour, existing tests.
3. Fill `spec.md`:
   - **Problem**: who needs what, and why. No solution.
   - **Scope / non-goals**: non-goals prevent scope creep later. Be explicit.
   - **Acceptance criteria** `AC-n`: each one observable from outside the unit (input → output, state change, message, log/metric). Avoid "works correctly", "fast", "robust". Quantify instead: "p99 < 50 ms at 1k rps", "rejects payloads > 1 MiB with error X".
   - **Constraints**: compatibility, performance, security, environments.
   - **Context & failure model**: actors, existing systems, and what can fail (dependencies down, messages lost or duplicated, crashes), with what the user must observe then. Requirements only; the solution is worked out in the design phases after verification.
   - **Open questions**: ask the user (AskUserQuestion) rather than guessing. Each one must be resolved or explicitly deferred.
4. Self-check before asking for approval:
   - Could two engineers read each AC and write the same test?
   - Is every error/failure path covered by an AC or a non-goal?
   - Does any AC hide two behaviours? Split it.
5. Show the user the ACs (not the whole file) and ask them to run `! .factory/factory approve spec`.
