---
feature: {{feature}}
applies: undecided  # yes | no (no requires reason:)
reason:             # why this phase does not apply (only when applies: no)
formal: undecided   # required | not-needed (must be decided before approval)
---

# High-level architecture & resiliency: {{feature}}

Input: the approved spec.md and verification.md. The design must make every V-row achievable (design for testability).
Decisions get stable IDs (`D-ARCH-n`). Each decision is enforced by at least one conformance check (`DC-ARCH-NN`).

## 1. Context
<!-- Actors, external systems, trust boundaries. Mermaid C4-style context/container diagram. -->

```mermaid
flowchart LR
  client[Client] --> svc[This service]
```

## 2. Components & responsibilities
| Component | Responsibility | Owns state? | Talks to |
|-----------|----------------|-------------|----------|
|           |                |             |          |

## 3. Data flow
<!-- Main request/event paths, sync vs async, where state changes. One sequence diagram per critical AC. -->

## 4. Deployment & runtime
<!-- Processes, instances, scaling, configuration sources, environments. -->

## 5. Quality attributes
| Attribute | Target (from spec AC / constraint) | How the architecture achieves it |
|-----------|------------------------------------|----------------------------------|
|           |                                    |                                  |

## 6. Resiliency
### 6.1 Failure modes
Every dependency and every component the spec's failure model admits.

| Dependency / component | Failure | Detection | Response (timeout, retry + backoff + jitter, circuit breaker, bulkhead, fallback, fail fast) | User-visible effect |
|------------------------|---------|-----------|------------------------------------------------------------------------------------------------|---------------------|
|                        |         |           |                                                                                                |                     |

### 6.2 Timeouts & retry budget
<!-- Concrete numbers. Retries only on idempotent operations. Total budget below the caller's timeout. -->

### 6.3 Idempotency, consistency & ordering
<!-- Idempotency keys, exactly/at-least-once, consistency model, ordering guarantees. -->

### 6.4 Overload & backpressure
<!-- Queues, bounded buffers, load shedding, rate limits. -->

### 6.5 Observability
<!-- Metrics, logs, traces, health checks, alerts and SLOs that prove the behaviour above in production. -->

## 7. Decisions
| ID       | Decision | Alternatives considered | Why |
|----------|----------|-------------------------|-----|
| D-ARCH-1 |          |                         |     |

## 8. Formal specification decision
Answer each question. Any "yes" means a formal spec is proposed, and the human decides.

- Multiple processes, nodes or actors that communicate? 
- Messages can be lost, duplicated, delayed or reordered? 
- Shared mutable state, locks, or concurrent writers? 
- Ordering, exactly-once or idempotency guarantees? 
- A state machine with more than about 5 states, or non-trivial transitions? 
- Data-model invariants that span several entities? 

**Decision:** <!-- required: <what is modelled, which tool> | not-needed: <why> -->
(Set `formal:` in the frontmatter to match.)

## 9. Design-conformance checks
How we will know the implementation follows this design. Dimensions: `architecture` (module/dependency rules), `resiliency` (fault injection, timeout/retry tests), `config`, `observability`, `formal` (model property → code check).

| ID         | Decision | Dimension  | What exactly is checked | How (technique / tool) | Automated? | Command / location |
|------------|----------|------------|-------------------------|------------------------|------------|--------------------|
| DC-ARCH-01 | D-ARCH-1 | resiliency |                         |                        | yes        |                    |

## Revision history
<!-- Reopened after approval? List the revision IDs from ../revisions.md and what changed, e.g. "R-2: added bulk-get (from oo)". -->
