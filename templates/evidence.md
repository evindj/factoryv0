---
feature: {{feature}}
---

# Evidence: {{feature}}

One row per `V-NN` in verification.md and per `DC-*` row in every design doc that applies. Result must be one of `PASS`, `MANUAL-PASS`, `ACCEPTED-RISK`, `FAIL`.
`.factory/factory evidence` checks this table mechanically.

| ID   | Result | Proof (command + key output, or test name) | Red run seen? |
|------|--------|--------------------------------------------|---------------|
| V-01 |        |                                            |               |

## Design conformance
<!-- One row per DC-* in design/architecture.md, api.md, data.md, oo.md (skip docs marked applies: no). -->

| ID | Result | Proof (command + key output, or test name) | Red run seen? |
|----|--------|--------------------------------------------|---------------|

## Design-auditor verdict
<!-- Summary of the design-auditor findings and how each was resolved. -->

## Formal properties
<!-- If design/architecture.md says formal: required. List each property, the model-check log and the code-level check enforcing it. -->

| Property | Kind (safety/liveness) | Model check | Code-level check |
|----------|------------------------|-------------|------------------|

## Mutation testing

## Residual risks
