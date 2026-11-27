---
name: factory
description: Drive a feature through the verification-first software factory (spec → verification design → architecture/resiliency → API → data → OO design → optional formal spec → TDD → evidence), every stage gated by human approval. Use when the user asks to build, add, change or fix behaviour in a project that has a .factory/ directory, or says "/factory <feature>". Also use to enable the factory in a new Java or Python project.
---

# Software factory orchestrator

You build software the user can trust. Confidence comes from deciding **how a change will be verified before writing it**, then producing evidence for each decision. TDD here means verification-driven development, not just "write a unit test first".

## 0. Setup (once per project)
If the project has no `.factory/` directory, ask the user whether to enable the factory, then run:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/factory.py" init`
This creates `.factory/` (state + the `.factory/factory` CLI shim), `docs/specs/`, and a CLAUDE.md section.
If the static tooling is missing, offer the baselines in `${CLAUDE_PLUGIN_ROOT}/templates/python/` or `templates/java/`.

Always check where things stand first: `.factory/factory status`.

## Stages
Each stage ends at a gate. Do not start the next stage until the gate passes. Announce each transition with `.factory/factory stage <name>`.

| # | Stage | Skill | Output | Gate |
|---|-------|-------|--------|------|
| 1 | spec | `spec` | `spec.md` | `! .factory/factory approve spec` |
| 2 | verify-design | `verify-design` | `verification.md` (V-rows, from the spec only) | `! .factory/factory approve verification` |
| 3a | architecture | `design-architecture` | `design/architecture.md` (+ formal decision) | `! .factory/factory approve architecture` |
| 3b | api | `design-api` | `design/api.md` + contract artifact | `! .factory/factory approve api` |
| 3c | data | `design-data` | `design/data.md` + schema artifact | `! .factory/factory approve data` |
| 3d | oo | `design-oo` | `design/oo.md` + architecture rules | `! .factory/factory approve oo` |
| 3e | formal (if `formal: required`) | `formal-spec` | `formal/*.tla`, model-check log | `model-check` PASS |
| 4 | tdd | `tdd` | tests, code, `tdd-log.md` | every V- and DC-row has a red run, then green; `.factory/factory gate` passes |
| 5 | evidence | `evidence` | `evidence.md` | `.factory/factory evidence` passes and the Stop hook is green |

**Two layers of checks.**
- **V-rows** (verification.md) prove the *spec*. They are written before any design and must not depend on it.
- **DC-rows** (each design doc) prove the code follows the *design*. Examples: contract tests from the OpenAPI file, migration and schema tests, ArchUnit / import-linter rules, fault injection for the resiliency table.

Every design phase is approved, even one that doesn't apply: it then says `applies: no` with a `reason:`. Editing a design artifact (openapi.yaml, schema.sql, …) invalidates its document's approval.

### The approval loop
The first approvals go forward in order. But later work often shows that an earlier decision is wrong, so the gates form a loop:

```
 spec → verification → architecture → api → data → oo → design review → [formal] → TDD → evidence
   ▲          ▲              ▲          ▲      ▲     │        │               │        │
   └──────────┴──────────────┴──────────┴──────┴─────┴────────┴───────────────┴────────┘
                        revise <doc> --from <stage> "<why>"
```

1. **Reopen.** `.factory/factory revise <doc> --from <stage> "<why>"` records `R-n` in `revisions.md`. Production code is blocked from that moment, and later documents can't be approved while it is open.
2. **Fix** the earlier document (and its artifacts). Note the revision ID in its *Revision history*.
3. **The human approves the revised document.** This closes `R-n`. Approving a changed document without an open revision is refused, so every change has a recorded reason.
4. **The human re-confirms each later document.** `approve <doc>` shows which upstream documents changed and why, with `git diff` commands. The human reviews them, then runs `approve <doc> --yes`. If a later document no longer holds, it gets its own revision instead.
5. **Converge.** After oo is approved, and after every loop, run the `design-reviewer` subagent across all six documents. Each inconsistency it finds becomes another revision. Code starts only once it reports convergence.

A later phase never works around a flawed earlier decision. It loops back.

Start a feature with `.factory/factory new <slug>`. This creates `docs/specs/NNNN-slug/` from templates and makes it active.

## Hard rules
- **Never approve your own work.** Approvals are the human's: hooks block you from running `approve`/`spike` or writing `.factory/approvals.json`. When a document is ready, summarise it in a few lines and ask the user to run the command with the `!` prefix.
- Editing an approved document invalidates its approval. Ask for re-approval if you had to change it, and say what changed.
- Production code is blocked until all six documents are approved (spec, verification, architecture, api, data, oo) and, when required, the formal spec is model-checked. Tests, docs and specs are always editable. Writing tests or architecture rules during stages 2–3 is fine.
- **Implementation follows the design.** Packages, types, endpoints, tables, timeouts and retries are built as the approved design says. If the code can't follow it, stop, revise the design document, explain the change, and get re-approval.
- Never weaken a check to get green (skip/disable tests, loosen types, `# type: ignore`, `@SuppressWarnings`, deleting assertions, editing gate config) unless the user agrees. Record any such case as ACCEPTED-RISK in evidence.md.
- If you discover at any later stage that the spec, verification design or a design document is wrong, stop and loop back: `revise <doc> --from <stage> "<why>"`, update the document, explain the change, and ask for re-approval, then re-confirmation of the later documents. Don't silently diverge.
- Spike mode (`! .factory/factory spike`) is the human's escape hatch for exploration. Code written in a spike must go through the full flow before it ships.

## Subagents
- `verification-designer`: adversarial review of verification.md before you ask for approval.
- `architecture-designer`, `api-designer`, `data-designer`, `oo-designer`: draft each design document and its artifacts. Review the draft yourself before asking for approval.
- `spec-modeler`: writes and model-checks formal specs in stage 3e.
- `test-auditor`: before stage 5, confirms that tests map to V- and DC-rows, were seen failing, and would catch a broken implementation.
- `design-reviewer`: after oo is approved and after every revision loop, cross-checks the six documents against each other and proposes revisions. Code starts once it reports convergence.
- `design-auditor`: before stage 5, compares the implementation against the approved design documents and artifacts and reports drift.

## Finishing
End with a short report: what was built, the evidence status (V- and DC-rows), the design-auditor verdict (`.factory/factory evidence`), the mutation-testing result, and any ACCEPTED-RISK rows. Then `.factory/factory stage done`.
