---
name: design-oo
description: Design stage 3d of the software factory, the last step before code. Write design/oo.md (module layering and dependency rules, domain model, types and invariants, mapping to API and data, error handling, seams) and DC-OO conformance checks, including at least one ArchUnit / import-linter architecture rule enforced by the gate. Use after design/data.md is approved.
---

# Stage 3d: Object-oriented design

Prerequisites: spec, verification, architecture, api and data approved. Run `.factory/factory stage oo`.

## Procedure
0. **Check upstream first.** Read every earlier approved document. If this phase can't be designed well without changing one of them (a missing operation, an entity the schema lacks, a resiliency assumption that doesn't hold, an AC that is infeasible), stop. Propose `.factory/factory revise <doc> --from oo "<why>"` to the user, and do not compensate locally. Draft this phase once the revision is approved.
1. **Draft with the `oo-designer` subagent.** It reads the codebase and every earlier design doc, then fills `design/oo.md`:
   - **Modules and dependency rules.** Layers and the allowed dependency direction (e.g. domain ← application ← adapters; the domain imports no framework).
   - **Domain model.** A mermaid class diagram. For each type: its kind, responsibility, collaborators and invariants.
   - **Invariants enforced by types where possible:** value objects, constructors that reject invalid states, sealed types / enums, `NewType`/`Final`, records.
   - **Mapping.** Which type serves each API operation; how domain types map to the schema (repositories, mappers, DTOs).
   - **Error handling:** where errors are raised, translated and reported; never swallowed.
   - **Seams the verification needs:** clock, randomness, I/O ports, fault-injection points.
   Prefer extending existing project structure and patterns over inventing new ones.
2. **Architecture rules are mandatory.** At least one `DC-OO-NN` row with dimension `architecture`. Approval is refused without it.
   - Java: an ArchUnit test under `src/test/java` (runs in `mvn verify` / `gradle check`).
   - Python: an import-linter contract in `pyproject.toml` (`[tool.importlinter]`). The gate then runs `lint-imports` automatically.
   Write these rules now. Tests and config are editable during design, and the rules should pass on the existing code or fail only for the reason the design changes things.
3. **Other conformance checks:**
   - type-level checks (mypy --strict / NullAway on the new types)
   - a test per invariant showing that invalid construction is rejected
   - wiring tests showing each API operation is served by the designed type
4. **Not applicable?** Trivial change inside one existing class → `applies: no` with a `reason:`. Architecture rules are only required when the doc applies.
5. **Approval.** Summarise the modules and rules, the key types and invariants, and the DC rows. Ask the user to run `! .factory/factory approve oo`. Then run the `design-reviewer` subagent across all six documents (the convergence step). Each inconsistency it finds is a revision loop. Production code is unblocked once all documents are approved with no open revision (and the formal spec, if required, comes first).
