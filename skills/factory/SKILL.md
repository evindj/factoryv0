---
name: factory
description: Drive a feature through the verification-first software factory (spec → verification design → optional formal spec → TDD → evidence). Use when the user asks to build, add, change or fix behaviour in a project that has a .factory/ directory, or says "/factory <feature>". Also use to enable the factory in a new Java or Python project.
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
| 1 | spec | `spec` | `spec.md` | human runs `! .factory/factory approve spec` |
| 2 | verify-design | `verify-design` | `verification.md` | human runs `! .factory/factory approve verification` |
| 2b | formal (if `formal: required`) | `formal-spec` | `formal/*.tla`, model-check log | `model-check` PASS |
| 3 | tdd | `tdd` | tests, code, `tdd-log.md` | every V-row has a red run, then green; `.factory/factory gate` passes |
| 4 | evidence | `evidence` | `evidence.md` | `.factory/factory evidence` passes and the Stop hook is green |

Start a feature with `.factory/factory new <slug>`. This creates `docs/specs/NNNN-slug/` from templates and makes it active.

## Hard rules
- **Never approve your own work.** Approvals are the human's: hooks block you from running `approve`/`spike` or writing `.factory/approvals.json`. When a document is ready, summarise it in a few lines and ask the user to run the command with the `!` prefix.
- Editing an approved document invalidates its approval. Ask for re-approval if you had to change it, and say what changed.
- Production code is blocked until spec and verification are approved (and, when required, the formal spec is model-checked). Tests, docs and specs are always editable. Writing tests during stage 2 to probe feasibility is fine.
- Never weaken a check to get green (skip/disable tests, loosen types, `# type: ignore`, `@SuppressWarnings`, deleting assertions, editing gate config) unless the user agrees. Record any such case as ACCEPTED-RISK in evidence.md.
- If you discover mid-TDD that the spec or verification design is wrong, stop. Update the document, explain the change, and get re-approval. Don't silently diverge.
- Spike mode (`! .factory/factory spike`) is the human's escape hatch for exploration. Code written in a spike must go through the full flow before it ships.

## Subagents
- `verification-designer`: adversarial review of verification.md before you ask for approval.
- `spec-modeler`: writes and model-checks formal specs in stage 2b.
- `test-auditor`: before stage 4, confirms that tests map to V-rows, were seen failing, and would catch a broken implementation.

## Finishing
End with a short report: what was built, the evidence status (`.factory/factory evidence`), the mutation-testing result, and any ACCEPTED-RISK rows. Then `.factory/factory stage done`.
