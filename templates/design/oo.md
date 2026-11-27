---
feature: {{feature}}
applies: undecided  # yes | no (no requires reason:)
reason:             # why this phase does not apply (only when applies: no)
---

# Object-oriented design: {{feature}}

Input: approved spec.md, verification.md and the earlier design docs. This is the last design phase before code.
The class and package structure below is what TDD implements. Diverging from it requires revising this doc.

## 1. Modules / packages & dependency rules
<!-- Layers (e.g. domain ← application ← adapters), allowed dependency direction. These become ArchUnit / import-linter rules. -->

| Module / package | Responsibility | May depend on | Must not depend on |
|------------------|----------------|---------------|--------------------|
|                  |                |               |                    |

## 2. Domain model
```mermaid
classDiagram
```

## 3. Types & responsibilities
| Type | Kind (entity / value / service / port / adapter / …) | Responsibility | Collaborators | Invariants (and how enforced: type, constructor, test) |
|------|-------------------------------------------------------|----------------|---------------|--------------------------------------------------------|
|      |                                                       |                |               |                                                        |

## 4. Mapping to API & data
<!-- Which type implements each API operation; how domain types map to the schema (repositories, DTOs, mappers). -->

## 5. Error handling
<!-- Exception / result types, where errors are translated between layers, what is never swallowed. -->

## 6. Patterns & extension points
<!-- Patterns used and why (strategy, ports & adapters, …). Seams needed by verification (clock, random, I/O ports). -->

## 7. Decisions
| ID     | Decision | Alternatives considered | Why |
|--------|----------|-------------------------|-----|
| D-OO-1 |          |                         |     |

## 8. Design-conformance checks
At least one `architecture` row: an ArchUnit test (Java) or an import-linter contract (Python, run by the gate as `lint-imports`).

| ID       | Decision | Dimension    | What exactly is checked | How (technique / tool) | Automated? | Command / location |
|----------|----------|--------------|-------------------------|------------------------|------------|--------------------|
| DC-OO-01 | D-OO-1   | architecture |                         |                        | yes        |                    |

## Revision history
<!-- Reopened after approval? List the revision IDs from ../revisions.md and what changed, e.g. "R-2: added bulk-get (from oo)". -->
