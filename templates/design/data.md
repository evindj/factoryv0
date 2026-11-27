---
feature: {{feature}}
applies: undecided  # yes | no (no requires reason:)
reason:             # why this phase does not apply (only when applies: no)
artifacts: design/data/schema.sql   # schema, ERD source or migrations dir; hashed into the approval
---

# Persistence / data design: {{feature}}

Input: approved spec.md, verification.md, design/architecture.md and design/api.md.
The schema artifact is the target state. Editing it invalidates this approval.

## 1. Store choice
<!-- Which store(s) and why: relational, document, KV, queue, file. Consistency and durability needed. -->

## 2. Entities & relationships
<!-- Mermaid erDiagram. -->

```mermaid
erDiagram
```

## 3. Invariants & constraints
| Invariant | Enforced by (PK / FK / UNIQUE / CHECK / NOT NULL / app code + why) |
|-----------|--------------------------------------------------------------------|
|           |                                                                    |

## 4. Access patterns & indexes
| Query / write | Frequency | Index or key that serves it |
|---------------|-----------|-----------------------------|
|               |           |                             |

## 5. Transactions & concurrency
<!-- Transaction boundaries, isolation level, optimistic/pessimistic locking, outbox, idempotent writes. -->

## 6. Migrations
<!-- Tool (Flyway / Liquibase / Alembic), expand/contract steps, backfill, rollback, zero-downtime constraints. -->

## 7. Retention, privacy & security
<!-- PII fields, encryption, retention/deletion, access control. -->

## 8. Decisions
| ID       | Decision | Alternatives considered | Why |
|----------|----------|-------------------------|-----|
| D-DATA-1 |          |                         |     |

## 9. Design-conformance checks
Run against the real engine (Testcontainers), not an in-memory substitute:
- migrations apply from scratch **and** from the previous released version
- the migrated schema matches `schema.sql` (schema diff / information_schema assertions)
- each constraint in section 3 rejects a violating write
- concurrency rows for section 5 (e.g. two writers, one wins)

| ID         | Decision | Dimension | What exactly is checked | How (technique / tool) | Automated? | Command / location |
|------------|----------|-----------|-------------------------|------------------------|------------|--------------------|
| DC-DATA-01 | D-DATA-1 | migration |                         |                        | yes        |                    |

## Revision history
<!-- Reopened after approval? List the revision IDs from ../revisions.md and what changed, e.g. "R-2: added bulk-get (from oo)". -->
