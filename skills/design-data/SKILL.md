---
name: design-data
description: Design stage 3c of the software factory. Write design/data.md (store choice, entities, invariants and constraints, access patterns and indexes, transactions, migrations, retention/PII) and its schema artifact, hashed into the approval, plus DC-DATA conformance checks. Use after design/api.md is approved.
---

# Stage 3c: Persistence / data design

Prerequisites: spec, verification, architecture and api approved. Run `.factory/factory stage data`.

## Procedure
0. **Check upstream first.** Read every earlier approved document. If this phase can't be designed well without changing one of them (a missing operation, an entity the schema lacks, a resiliency assumption that doesn't hold, an AC that is infeasible), stop. Propose `.factory/factory revise <doc> --from data "<why>"` to the user, and do not compensate locally. Draft this phase once the revision is approved.
1. **Draft with the `data-designer` subagent.** It fills `design/data.md` and writes the target schema to `design/data/schema.sql` (start from `${CLAUDE_PLUGIN_ROOT}/templates/design/schema.sql`). For document or KV stores, it writes a JSON Schema or a key-layout file instead. Planned migration scripts can live in `design/data/migrations/`. List everything in `artifacts:`.
2. **Invariants first.** Put every cross-entity rule from the spec in the invariants table, and enforce it in the database where possible (PK, FK, UNIQUE, CHECK, NOT NULL). If a rule can only be enforced in application code, say why.
3. **Access patterns.** Every query and write that the API and architecture need gets an index or key. No query without one.
4. **Concurrency.** Define:
   - transaction boundaries and the isolation level
   - the locking strategy
   - an outbox for events
   - idempotent writes (matching architecture section 6.3)
5. **Migrations.**
   - Choose the tool: Flyway/Liquibase (Java) or Alembic (Python).
   - Plan the expand/contract steps, backfill and rollback.
   - Changes must be safe with old and new code running side by side.
6. **Conformance checks** (`DC-DATA-NN`), on the real engine via Testcontainers:
   - migrate from scratch and from the previous release
   - the resulting schema equals `schema.sql`
   - every constraint rejects a violating write
   - concurrent writers behave as designed
7. **Not applicable?** No persistence change → `applies: no` with a `reason:`.
8. **Approval.** Summarise the entities, invariants and where each is enforced, and the migration plan. Ask the user to run `! .factory/factory approve data`.
