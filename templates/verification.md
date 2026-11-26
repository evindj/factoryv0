---
feature: {{feature}}
formal: undecided   # required | not-needed (must be decided before approval)
---

# Verification design: {{feature}}

How we will *know* each acceptance criterion holds before any code is written.
Every row gets an ID (`V-NN`). evidence.md must later show a PASS, MANUAL-PASS or ACCEPTED-RISK for each one.

## 1. Verification matrix

| ID   | AC   | Dimension | What exactly is checked | How (technique / tool) | Automated? | Command / location |
|------|------|-----------|-------------------------|------------------------|------------|--------------------|
| V-01 | AC-1 | functional |                        |                        | yes        |                    |

Dimensions to consider for **every** criterion. Write "n/a: <reason>" in the notes below rather than skipping one silently:
- **functional**: unit, integration, end-to-end
- **property**: invariants over generated inputs (Hypothesis / jqwik); round-trips, idempotence, ordering, conservation
- **edge**: empty, boundary, malformed, huge, unicode, timeouts, partial failure, retries
- **contract**: public API, schema, CLI output, wire format, backward compatibility
- **static**: types (mypy --strict / javac + ErrorProne), lint, architecture rules (import-linter / ArchUnit)
- **concurrency**: races, deadlock, ordering, resource leaks, cancellation
- **non-functional**: performance budget, memory, security (input validation, authz, secrets), observability
- **strength**: mutation testing (mutmut / PIT) on the touched code. Would the tests notice a broken implementation?
- **manual**: anything that can't be automated, with exact steps and the expected observation

## 2. Dimension notes
<!-- Per AC: which dimensions are n/a and why. -->

## 3. Adversarial review: "how could this be wrong and still pass?"
<!-- For each answer: add a V-row that catches it, or accept the risk explicitly. -->

| Scenario | Caught by | or Accepted risk (why) |
|----------|-----------|------------------------|
|          |           |                        |

## 4. Formal specification decision
Answer each question. Any "yes" means a formal spec is proposed (stage 2b), and the human decides.

- Multiple processes, nodes or actors that communicate? 
- Messages can be lost, duplicated, delayed or reordered? 
- Shared mutable state, locks, or concurrent writers? 
- Ordering, exactly-once or idempotency guarantees? 
- A state machine with more than about 5 states, or non-trivial transitions? 
- Data-model invariants that span several entities? 

**Decision:** <!-- required: <what is modelled, which tool> | not-needed: <why> -->
(Set `formal:` in the frontmatter to match.)

## 5. Test environment & data
<!-- Fixtures, containers (Testcontainers), fault injection (Toxiproxy), seeds, clocks. -->
