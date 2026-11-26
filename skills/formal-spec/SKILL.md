---
name: formal-spec
description: Stage 2b of the software factory. Write and model-check a formal specification (TLA+/PlusCal by default, Alloy for data-model invariants) of key design aspects such as distributed protocols, concurrency, retries/idempotency or complex state machines, then link each property to code-level checks. Use when verification.md has formal: required.
---

# Stage 2b: Formal specification

Use this when tests alone can't give confidence because the space of interleavings, failures or states is too large to enumerate by hand. Model the **design**, not the code. Keep it small enough to model-check in minutes.

Run `.factory/factory stage formal`. Delegate the heavy lifting to the `spec-modeler` subagent if helpful.

## Procedure
1. **Pick the aspect and the tool.**
   - TLA+ (PlusCal if the algorithm reads naturally as processes): protocols, concurrency, retries, leader election, replication, consensus, caches and invalidation, workflows.
   - Alloy: structural invariants over relations (permissions models, schemas, graph shapes).
   - Start from `${CLAUDE_PLUGIN_ROOT}/templates/formal/`.
2. **Write the spec** in `docs/specs/NNNN-slug/formal/<Name>.tla` plus `<Name>.cfg`:
   - State variables mirror the design sketch in spec.md.
   - Model the **environment** explicitly: message loss, duplication and reordering, crashes and restarts, clock skew. Only include what the spec's failure model admits, and say so in a comment.
   - Define a `TypeOK` invariant, then the **safety** invariants (e.g. `AtMostOneLeaderPerTerm`, `NoLostAcknowledgedWrite`), then the **liveness** properties under explicit fairness (e.g. `<>[] AllRequestsAnswered`).
   - Choose model bounds in the .cfg (e.g. 3 nodes, 2 terms, 3 messages) and write *why these bounds are enough* in a comment at the top of the spec. Typical reason: small-scope hypothesis plus which bug classes need N ≥ 3.
3. **Model-check:** `.factory/factory model-check docs/specs/NNNN-slug/formal/<Name>.tla`. This writes `<Name>.model-check.log` with a sha256 of the spec. Editing the spec afterwards invalidates the result.
   - Counterexample → read the trace, decide whether the *design* or the *spec* is wrong, fix it, and re-run. If the design changed, update spec.md/verification.md and get re-approval.
   - **Sanity check (vacuity):** a spec that can't fail proves nothing. Add a probe `.cfg` whose INVARIANT claims a state you expect to reach is unreachable (e.g. `ProbeNeverAcked == acked = {}`). Run `.factory/factory model-check <Name>.tla --config <Probe>.cfg --expect-violation ProbeNeverAcked`; it passes only if TLC finds the trace. For liveness, confirm the property fails when you remove the fairness assumption it depends on.
   - Keep the probe and seeded-bug configs. Each run writes `<Name>.<Cfg>.model-check.log`, and all of them must pass and match the current spec.
   - Real example: in `fixtures/formal-sample/Dedup.tla` TLC found that the first "fixed" design acknowledged a duplicate while the original was still being applied (`AckedImpliesApplied`, a 7-step trace). Unit tests had encoded that behaviour as correct.
4. **Link spec to code.** Add V-rows to verification.md (this needs re-approval) for:
   - each invariant → a property-based / stateful test (Hypothesis `RuleBasedStateMachine`, jqwik actions) that checks the same predicate on the implementation, plus a cheap runtime assertion where sensible;
   - each counterexample TLC found → a deterministic regression test that replays that interleaving;
   - fault injection matching the modelled environment (Testcontainers + Toxiproxy: partitions, latency, drops);
   - optionally, trace validation: the implementation logs state transitions and a checker validates them against the spec's Next relation.
5. In evidence.md, fill the *Formal properties* table: property → model-check log → code-level check.

The edit guard keeps production code blocked until every `formal/*.model-check.log` ends with `RESULT: PASS` and matches the current spec file.

## Tooling
- Needs Java and `tla2tools.jar`. Set `TLA2TOOLS_JAR` or place it at `~/.factory/tla2tools.jar`.
- Apalache (symbolic, for larger or unbounded parameters) and Quint are acceptable alternatives. Record their output in a `<Name>.model-check.log` ending in `RESULT: PASS`/`FAIL` with the spec's sha256 line.
