---
name: design-architecture
description: Design stage 3a of the software factory. Write design/architecture.md (high-level architecture and resiliency: components, data flow, deployment, failure modes, timeouts, retries, idempotency, overload, observability), decide whether a formal spec is needed, and define DC-ARCH conformance checks. Use after verification.md is approved.
---

# Stage 3a: High-level architecture & resiliency

Prerequisites: spec.md and verification.md approved (`.factory/factory status`). Run `.factory/factory stage architecture`.

## Procedure
0. **Check upstream first.** Read every earlier approved document. If this phase can't be designed well without changing one of them (a missing operation, an entity the schema lacks, a resiliency assumption that doesn't hold, an AC that is infeasible), stop. Propose `.factory/factory revise <doc> --from architecture "<why>"` to the user, and do not compensate locally. Draft this phase once the revision is approved.
1. **Read the inputs.** The approved spec (ACs, constraints, context & failure model) and verification.md. Every V-row must be achievable by this design. If a row needs a seam (fake clock, fault-injection point, port), the architecture must provide it.
2. **Draft with the `architecture-designer` subagent.** Give it the feature directory. It fills `design/architecture.md`:
   - components and responsibilities, context and data-flow diagrams, deployment
   - quality attributes traced to ACs and constraints
   - **resiliency**: a row per dependency and failure mode, with detection and a concrete response; timeout and retry budgets with numbers; idempotency, consistency and ordering; backpressure and load shedding; observability that proves it in production
   - `D-ARCH-n` decisions with the alternatives considered
3. **Formal decision.** Answer section 8. If any answer is yes, propose a formal spec to the user: what is modelled, which tool, which safety and liveness properties. Set `formal: required` or `formal: not-needed`. Approval is refused while it is `undecided`.
4. **Conformance checks.** Add `DC-ARCH-NN` rows that prove the code follows this design. Examples:
   - fault injection per failure-mode row (Testcontainers + Toxiproxy, or a fake dependency that fails on cue)
   - tests asserting the configured timeouts and retry limits
   - module-boundary rules (ArchUnit / import-linter)
   - metrics and health endpoints present
   These rows are not V-rows. They check the *design*. Spec behaviour stays in verification.md.
5. **Not applicable?** For a change with no architectural impact (e.g. a pure function inside one module), set `applies: no` with a one-line `reason:`. `formal:` must still be decided.
6. **Self-check.**
   - Does every failure in the spec's failure model have a resiliency row?
   - Is every retry on an idempotent operation?
   - Does the retry budget fit inside the caller's timeout?
   - Does every decision have a check?
7. **Approval.** Summarise the components, the top failure modes and their responses, the formal decision and the DC rows. Ask the user to run `! .factory/factory approve architecture`.
