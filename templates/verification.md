---
feature: {{feature}}
---

# Verification design: {{feature}}

How we will *know* each acceptance criterion holds before any design or code exists.

**Derived from spec.md only.** Do not reference classes, endpoints, tables or other design choices here: the design
comes next and must make these rows achievable. Checks that the code follows the design live in `design/*.md` as DC-rows.
Every row gets an ID (`V-NN`). evidence.md must later show a PASS, MANUAL-PASS or ACCEPTED-RISK for each one.

## 1. Verification matrix

| ID   | AC   | Dimension | What exactly is checked | How (technique / tool) | Automated? | Command / location |
|------|------|-----------|-------------------------|------------------------|------------|--------------------|
| V-01 | AC-1 | functional |                        |                        | yes        |                    |

Dimensions to consider for **every** criterion. Write "n/a: <reason>" in the notes below rather than skipping one silently:
- **functional**: unit, integration, end-to-end
- **property**: invariants over generated inputs (Hypothesis / jqwik); round-trips, idempotence, ordering, conservation
- **edge**: empty, boundary, malformed, huge, unicode, timeouts, partial failure, retries
- **contract**: externally observable interface promised by the spec (outputs, error codes, compatibility)
- **static**: types (mypy --strict / javac + ErrorProne), lint (architecture rules belong to the design docs as DC-rows)
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

## 4. Test environment & data
<!-- Fixtures, containers (Testcontainers), fault injection (Toxiproxy), seeds, clocks. -->
