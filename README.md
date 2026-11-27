# software-factory

A Claude Code plugin for writing Java and Python software with high confidence.
Each feature goes through gated stages, and hooks enforce the gates, so they don't depend on the model remembering to follow them.

```
spec ─▶ verification ─▶ architecture+resiliency ─▶ API ─▶ data ─▶ OO ─▶ [formal] ─▶ TDD ─▶ evidence
(what)  (how we'll KNOW   (components, failure     (contract (schema  (types,  (TLA+)   (red→   (proof per
         it's right)       modes, timeouts, retries) artifact) artifact) layers)           green)   V/DC row)
   every arrow before TDD is a human approval; any later stage can loop back to any earlier document
```

**Verification design comes before design and TDD.** For each acceptance criterion you brainstorm every way to prove it: functional, property-based, edge cases, contracts, static/architecture, concurrency, non-functional, mutation strength and manual checks. Then you do an adversarial pass: *"how could this be wrong and still pass?"*. Only then are tests written. When the design involves distributed protocols, concurrency or non-trivial state machines, a **formal specification** (TLA+/Alloy) is written and model-checked before any code. Each of its properties is then linked to a code-level check.

**Then four gated design phases**, each a document in `design/` approved by the human:

| Phase | Document | Artifact (hashed into the approval) | Design-conformance checks (`DC-*` rows) |
|---|---|---|---|
| High-level architecture & resiliency | `architecture.md` | – | fault injection per failure mode, timeout/retry config tests, module boundaries; also holds the formal-spec decision |
| API | `api.md` | `openapi.yaml` / AsyncAPI / `.proto` / `.pyi` stub / Java interface | contract tests generated from the artifact, breaking-change diff |
| Persistence | `data.md` | `schema.sql` / migrations | migrations on the real DB (Testcontainers), schema diff vs `schema.sql`, constraint tests |
| Object-oriented | `oo.md` | – | at least one ArchUnit / import-linter rule, which runs in the gate |

There are **two layers of checks**:
- **V-rows** prove the spec. They are derived from the spec alone, so they don't share the design's blind spots and they survive a redesign.
- **DC-rows** prove the code follows the design.

**The gates form a loop, not a one-way chain.** When a later stage shows that an approved document is wrong, Claude runs `.factory/factory revise <doc> --from <stage> "<why>"`. This records the reason in `revisions.md` and blocks code. Claude then fixes the document, and you re-approve it. Every later document must then be re-confirmed: `approve <doc>` shows what changed upstream and why, and you confirm with `--yes`. Re-approving a changed document without an open revision is refused. After oo, a `design-reviewer` subagent checks that all six documents agree before code starts.

Evidence must cover both. A phase that doesn't apply says `applies: no` with a `reason:`, and the human still approves it. A `design-auditor` subagent checks the implementation against the approved design before the evidence stage.

## Install

```bash
# try it in one session
claude --plugin-dir /path/to/software-factory

# or add this repo as a local marketplace and install it
claude plugin marketplace add /path/to/software-factory
claude plugin install software-factory@software-factory
```

Then, inside a Java or Python project:

```
> /software-factory:factory enable the factory here
```
or directly: `python3 /path/to/software-factory/scripts/factory.py init`.

This creates `.factory/` (state plus a `.factory/factory` CLI shim), `docs/specs/`, and a section in `CLAUDE.md`.
**Commit `.factory/approvals.json` and `docs/specs/`.** They're the audit trail.

## Daily use

```
> /software-factory:factory add rate limiting to the ingest endpoint
```

Claude writes the spec and asks you to approve it. You review it and run:

```
! .factory/factory approve spec
```

The same goes for `verification`, `architecture`, `api`, `data` and `oo`, in that order. The `!` prefix matters: approvals are human-only, and hooks block Claude from approving its own work. Editing a document (or a design artifact) after approval invalidates the approval. Re-approving an earlier document invalidates every later one.

| Command (`.factory/factory …`) | Who | What |
|---|---|---|
| `status` | anyone | active feature, approvals, formal and evidence status |
| `new <slug>` | Claude | create `docs/specs/NNNN-slug/` (spec, verification, `design/*`, evidence) from templates |
| `stage <name>` | Claude | record the current stage (`spec`, `verify-design`, `architecture`, `api`, `data`, `oo`, `formal`, `tdd`, `evidence`, `done`) |
| `approve spec\|verification\|architecture\|api\|data\|oo [--yes]` | **human** | in order; validates the doc, then records the sha256 of the doc plus its artifacts. A changed doc needs an open revision. `--yes` re-confirms an unchanged doc after upstream changes |
| `revise <doc> --from <stage> "<why>"` | Claude | reopen an approved doc (the loop back); logged in `revisions.md`; blocks code until re-approved |
| `spike` / `spike --off` | **human** | escape hatch for exploration (loudly disables the edit guard) |
| `gate` | anyone | format check + lint + types + tests |
| `record-red V-NN "<cmd>"` | Claude | run a check that must fail and log it to `tdd-log.md` |
| `model-check <Spec.tla> [--config X.cfg] [--expect-violation P]` | Claude | run TLC, write `<Spec>[.<Cfg>].model-check.log`; `--expect-violation` is for vacuity probes and seeded bugs |
| `evidence` | anyone | check `evidence.md` covers every `V-NN` row and every `DC-*` row of the design docs that apply |

## What the hooks enforce
All hooks do nothing in projects without `.factory/`.

| Hook | Enforces |
|---|---|
| PreToolUse Edit/Write | production code (`src/**/*.py` outside tests, `src/main/**`) is blocked until all six documents (spec, verification, architecture, api, data, oo) are approved and unchanged, including design artifacts, no revision is open, `formal:` is decided in architecture.md, and required formal specs pass model checking on their current content |
| PreToolUse Bash/Write | Claude cannot run `approve`/`spike` or write `.factory/approvals.json` |
| PostToolUse Edit/Write | format + lint the touched file (ruff, or Spotless via mvnw/gradlew); lint failures go back to Claude |
| Stop | full gate (also fails on any **skipped** test in fresh JUnit-XML reports, unless allowed) : ruff format/check, mypy, pytest, `lint-imports` (when import-linter is configured), or `mvn verify` / `gradle check` (ArchUnit runs here); must pass before Claude can say it's done; during the evidence stage `evidence.md` must also be complete. Skipped when nothing changed since the last green run; gives up loudly after 3 attempts |

Override commands per project in `.factory/config.json`:
```json
{ "commands": { "gate": ["uv run pytest -q", "uv run mypy"], "python_file": "uv run ruff check {file}" } }
```

## Toolchain baselines
- `templates/python/pyproject.toml`: uv, pytest, Hypothesis, ruff (bug-oriented rules), mypy --strict, coverage, mutmut, import-linter
- `templates/java/maven/` and `templates/java/gradle/`: JUnit 5, AssertJ, jqwik, ArchUnit, Spotless (google-java-format), ErrorProne + NullAway, JaCoCo, PIT
- `templates/formal/`: TLA+ module and .cfg skeleton, Alloy skeleton
- Tool lookup: project wrapper (`mvnw`/`gradlew`, `uv`, `.venv`), then `PATH`, then the plugin's git-ignored `.tools/` (`apache-maven-*`, `gradle-*`, `tla2tools.jar`). TLC can also use `TLA2TOOLS_JAR` or `~/.factory/tla2tools.jar`.

## Layout
```
.claude-plugin/plugin.json   hooks/hooks.json   scripts/factory.py (stdlib only)
skills/   factory · spec · verify-design · design-architecture · design-api · design-data · design-oo · formal-spec · tdd · evidence
agents/   verification-designer · architecture-designer · api-designer · data-designer · oo-designer · design-reviewer · spec-modeler · test-auditor · design-auditor
templates/  (design/ holds the four design templates + openapi.yaml / schema.sql starters)  fixtures/  tests/
```

## Developing the factory
```bash
python3 -m venv .venv && .venv/bin/pip install pytest hypothesis mypy ruff
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/mypy && .venv/bin/pytest
```
The fixtures are the factory's own verification targets:
- `fixtures/python-sample`: real ruff/mypy/pytest runs, including a regression test derived from a TLC counterexample
- `fixtures/java-*-sample`: build tools are stubbed in unit tests. `.factory/factory gate` there runs real `mvn verify` / `gradle check` (ErrorProne, Spotless, JUnit + jqwik, JaCoCo). `mvn org.pitest:pitest-maven:mutationCoverage` gives 12/12 mutants killed.
- `fixtures/formal-sample`: `Dedup.tla` passes, including liveness. `DedupRace.cfg` (seeded check-then-act race) and `DedupProbe.cfg` (vacuity probe) must report violations. The Python and Java regression tests V-03/V-04 replay the two counterexamples TLC found.
