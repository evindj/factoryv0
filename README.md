# software-factory

A Claude Code plugin for writing Java and Python software with high confidence.
Each feature goes through gated stages, and hooks enforce the gates, so they don't depend on the model remembering to follow them.

```
spec ──approve──▶ verification design ──approve──▶ [formal spec ─model-check─▶] TDD ──▶ evidence
 (what)             (how we'll KNOW it's right)       (protocols, concurrency)    (red→green)  (proof per row)
```

**Verification design comes before TDD.** For each acceptance criterion you brainstorm every way to prove it: functional, property-based, edge cases, contracts, static/architecture, concurrency, non-functional, mutation strength and manual checks. Then you do an adversarial pass: *"how could this be wrong and still pass?"*. Only then are tests written. When the design involves distributed protocols, concurrency or non-trivial state machines, a **formal specification** (TLA+/Alloy) is written and model-checked before any code. Each of its properties is then linked to a code-level check.

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

The same goes for `verification`. The `!` prefix matters: approvals are human-only, and hooks block Claude from approving its own work. Editing a document after approval invalidates the approval.

| Command (`.factory/factory …`) | Who | What |
|---|---|---|
| `status` | anyone | active feature, approvals, formal and evidence status |
| `new <slug>` | Claude | create `docs/specs/NNNN-slug/` from templates |
| `approve spec\|verification` | **human** | record the sha256 of the approved doc |
| `spike` / `spike --off` | **human** | escape hatch for exploration (loudly disables the edit guard) |
| `gate` | anyone | format check + lint + types + tests |
| `record-red V-NN "<cmd>"` | Claude | run a check that must fail and log it to `tdd-log.md` |
| `model-check <Spec.tla> [--config X.cfg] [--expect-violation P]` | Claude | run TLC, write `<Spec>[.<Cfg>].model-check.log`; `--expect-violation` is for vacuity probes and seeded bugs |
| `evidence` | anyone | check `evidence.md` covers every `V-NN` row |

## What the hooks enforce
All hooks do nothing in projects without `.factory/`.

| Hook | Enforces |
|---|---|
| PreToolUse Edit/Write | production code (`src/**/*.py` outside tests, `src/main/**`) is blocked until spec + verification are approved, `formal:` is decided, and required formal specs pass model checking on their current content |
| PreToolUse Bash/Write | Claude cannot run `approve`/`spike` or write `.factory/approvals.json` |
| PostToolUse Edit/Write | format + lint the touched file (ruff, or Spotless via mvnw/gradlew); lint failures go back to Claude |
| Stop | full gate (also fails on any **skipped** test in fresh JUnit-XML reports, unless allowed) : ruff format/check, mypy, pytest, or `mvn verify` / `gradle check`; must pass before Claude can say it's done; during the evidence stage `evidence.md` must also be complete. Skipped when nothing changed since the last green run; gives up loudly after 3 attempts |

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
skills/   factory · spec · verify-design · formal-spec · tdd · evidence
agents/   verification-designer · spec-modeler · test-auditor
templates/  fixtures/  tests/
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
