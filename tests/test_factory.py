"""Tests for scripts/factory.py: the hooks are exercised through their real stdin/exit-code interface."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "factory.py"
FIXTURES = REPO / "fixtures"
VENV_BIN = REPO / ".venv" / "bin"

sys.path.insert(0, str(REPO / "scripts"))
import factory  # noqa: E402

# ----------------------------------------------------------------------------- helpers


def env() -> dict[str, str]:
    e = dict(os.environ)
    e["PATH"] = f"{VENV_BIN}:{e['PATH']}"  # ruff/mypy/pytest for the python fixture
    e.pop("CLAUDE_PROJECT_DIR", None)
    return e


def run_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=root, env=env(), capture_output=True, text=True)


def hook(kind: str, root: Path, payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    payload = {"cwd": str(root), **payload}
    return subprocess.run(
        [sys.executable, str(SCRIPT), f"hook-{kind}"],
        input=json.dumps(payload),
        env=env(),
        capture_output=True,
        text=True,
        cwd=root,
    )


def edit(root: Path, rel: str) -> dict[str, Any]:
    return {"tool_name": "Edit", "tool_input": {"file_path": str(root / rel)}}


@pytest.fixture
def py_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    shutil.copytree(FIXTURES / "python-sample", root)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=root, check=True)
    assert run_cli(root, "init").returncode == 0
    return root


def set_frontmatter(doc: Path, **values: str) -> None:
    """Replace `key: ...` lines inside the frontmatter of doc."""
    head, sep, body = doc.read_text().partition("\n---\n")
    lines = head.splitlines()
    for key, value in values.items():
        lines = [f"{key}: {value}" if ln.startswith(f"{key}:") else ln for ln in lines]
        if not any(ln.startswith(f"{key}:") for ln in lines):
            lines.append(f"{key}: {value}")
    doc.write_text("\n".join(lines) + sep + body)


def new_feature(root: Path) -> Path:
    assert run_cli(root, "new", "dedup").returncode == 0
    return root / factory.State.load(root).active  # type: ignore[operator]


def fill_design(spec_dir: Path, formal: str = "not-needed") -> None:
    """Architecture + OO apply (template DC rows), API + data are n/a."""
    d = spec_dir / "design"
    set_frontmatter(d / "architecture.md", applies="yes", formal=formal)
    set_frontmatter(d / "api.md", applies="no", reason="pure library, no new interface")
    set_frontmatter(d / "data.md", applies="no", reason="no persistence")
    set_frontmatter(d / "oo.md", applies="yes")


def approve(root: Path, *docs: str) -> None:
    for doc in docs:
        r = run_cli(root, "approve", *doc.split())
        assert r.returncode == 0, r.stderr


CHAIN = ("spec", "verification", "architecture", "api", "data", "oo")


def approve_all(root: Path, formal: str = "not-needed") -> Path:
    spec_dir = new_feature(root)
    fill_design(spec_dir, formal)
    approve(root, *CHAIN)
    return spec_dir


# ----------------------------------------------------------------------------- detection / init


def test_detect_stacks_on_fixtures() -> None:
    assert factory.detect_stacks(FIXTURES / "python-sample") == ["python"]
    assert factory.detect_stacks(FIXTURES / "java-maven-sample") == ["maven"]
    assert factory.detect_stacks(FIXTURES / "java-gradle-sample") == ["gradle"]
    assert factory.detect_stacks(FIXTURES / "formal-sample") == []


def test_init_is_idempotent_and_writes_claude_md(py_project: Path) -> None:
    assert run_cli(py_project, "init").returncode == 0
    text = (py_project / "CLAUDE.md").read_text()
    assert text.count("<!-- software-factory -->") == 1
    assert os.access(py_project / ".factory" / "factory", os.X_OK)


def test_hooks_are_noops_outside_factory_projects(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("import os\n")  # unused import would fail lint
    assert hook("pre", tmp_path, edit(tmp_path, "x.py")).returncode == 0
    assert hook("post", tmp_path, edit(tmp_path, "x.py")).returncode == 0
    assert hook("stop", tmp_path, {}).returncode == 0


# ----------------------------------------------------------------------------- edit guard


@pytest.mark.parametrize(
    ("rel", "prod"),
    [
        ("src/sample/dedup.py", True),
        ("tests/test_dedup.py", False),
        ("conftest.py", False),
        ("docs/specs/0001-x/spec.md", False),
        ("src/main/java/a/B.java", True),
        ("src/test/java/a/BTest.java", False),
        ("README.md", False),
    ],
)
def test_production_code_classification(tmp_path: Path, rel: str, prod: bool) -> None:
    assert factory.is_production_code(tmp_path, tmp_path / rel) is prod


def test_guard_blocks_prod_edit_without_spec(py_project: Path) -> None:
    r = hook("pre", py_project, edit(py_project, "src/sample/dedup.py"))
    assert r.returncode == 2
    assert "no active feature spec" in r.stderr


def test_guard_allows_tests_and_docs_anytime(py_project: Path) -> None:
    assert hook("pre", py_project, edit(py_project, "tests/test_new.py")).returncode == 0
    assert hook("pre", py_project, edit(py_project, "docs/notes.md")).returncode == 0


def test_guard_requires_every_approval_in_the_chain(py_project: Path) -> None:
    spec_dir = new_feature(py_project)
    fill_design(spec_dir)
    target = edit(py_project, "src/sample/dedup.py")
    for i, doc in enumerate(CHAIN):
        r = hook("pre", py_project, target)
        assert r.returncode == 2
        assert f"{factory.DOC_NAMES[doc]} has not been approved" in r.stderr
        approve(py_project, doc)
        assert i < len(CHAIN) - 1 or hook("pre", py_project, target).returncode == 0


def test_approval_order_is_enforced(py_project: Path) -> None:
    spec_dir = new_feature(py_project)
    fill_design(spec_dir)
    approve(py_project, "spec", "verification")
    r = run_cli(py_project, "approve", "api")
    assert r.returncode != 0
    assert "approve the earlier documents first" in r.stderr
    assert "architecture.md has not been approved" in r.stderr
    assert not factory.is_approved(py_project, spec_dir / "design/api.md")[0]


def test_unknown_doc_is_refused(py_project: Path) -> None:
    new_feature(py_project)
    assert run_cli(py_project, "approve", "evidence").returncode != 0


@pytest.mark.parametrize(
    ("doc", "frontmatter", "message"),
    [
        ("architecture", {"applies": "undecided"}, "`applies:` must be `yes` or `no`"),
        ("architecture", {"formal": "undecided"}, "`formal:` must be `required` or `not-needed`"),
        ("api", {"applies": "no", "reason": ""}, "gives no `reason:`"),
        ("api", {"applies": "yes"}, "artifact design/api/openapi.yaml does not exist"),
        ("api", {"applies": "yes", "artifacts": ""}, "declares no `artifacts:`"),
        ("data", {"applies": "yes"}, "artifact design/data/schema.sql does not exist"),
    ],
)
def test_design_doc_must_be_complete_before_approval(
    py_project: Path, doc: str, frontmatter: dict[str, str], message: str
) -> None:
    spec_dir = new_feature(py_project)
    fill_design(spec_dir)
    set_frontmatter(spec_dir / factory.DOC_NAMES[doc], **frontmatter)
    for earlier in CHAIN[: CHAIN.index(doc)]:
        approve(py_project, earlier)
    r = run_cli(py_project, "approve", doc)
    assert r.returncode != 0
    assert message in r.stderr


def test_oo_needs_an_architecture_rule_row(py_project: Path) -> None:
    spec_dir = new_feature(py_project)
    fill_design(spec_dir)
    oo = spec_dir / "design/oo.md"
    oo.write_text(
        oo.read_text().replace("| DC-OO-01 | D-OO-1   | architecture |", "| DC-OO-01 | D-OO-1   | functional |")
    )
    approve(py_project, *CHAIN[:-1])
    r = run_cli(py_project, "approve", "oo")
    assert r.returncode != 0
    assert "dimension `architecture`" in r.stderr


def test_applicable_design_doc_needs_dc_rows(py_project: Path) -> None:
    spec_dir = new_feature(py_project)
    fill_design(spec_dir)
    arch = spec_dir / "design/architecture.md"
    arch.write_text(arch.read_text().replace("| DC-ARCH-01 |", "| todo |"))
    approve(py_project, "spec", "verification")
    r = run_cli(py_project, "approve", "architecture")
    assert r.returncode != 0
    assert "no DC-* design-conformance rows" in r.stderr


@pytest.mark.parametrize("as_dir", [False, True])
def test_editing_api_artifact_invalidates_approval(py_project: Path, as_dir: bool) -> None:
    spec_dir = new_feature(py_project)
    fill_design(spec_dir)
    art_dir = spec_dir / "design/api"
    art_dir.mkdir()
    (art_dir / "openapi.yaml").write_text("openapi: 3.1.0\n")
    set_frontmatter(
        spec_dir / "design/api.md", applies="yes", artifacts="design/api" if as_dir else "design/api/openapi.yaml"
    )
    approve(py_project, *CHAIN)
    target = edit(py_project, "src/sample/dedup.py")
    assert hook("pre", py_project, target).returncode == 0
    (art_dir / "openapi.yaml").write_text("openapi: 3.1.0\npaths: {}\n")
    r = hook("pre", py_project, target)
    assert r.returncode == 2
    assert "design/api.md or one of its artifacts changed" in r.stderr
    assert run_cli(py_project, "revise", "api", "--from", "oo", "contract tweak").returncode == 0
    approve(py_project, "api")
    r = hook("pre", py_project, target)  # later docs were approved against the old API contract
    assert r.returncode == 2
    assert "design/oo.md was approved before design/api.md (R-1: contract tweak) changed" in r.stderr
    r = run_cli(py_project, "approve", "data")  # data comes first: oo waits until data is re-confirmed
    assert r.returncode != 0
    assert "git diff -- " in r.stderr
    assert ("design/api" if as_dir else "design/api/openapi.yaml") in r.stderr  # the hint names the artifacts too
    approve(py_project, "data --yes", "oo --yes")
    assert hook("pre", py_project, target).returncode == 0


def test_approval_loop_back_from_later_phase(py_project: Path) -> None:
    spec_dir = approve_all(py_project)
    target = edit(py_project, "src/sample/dedup.py")
    assert hook("pre", py_project, target).returncode == 0

    # OO design discovers the architecture needs a change: reopen it, with a reason.
    r = run_cli(py_project, "revise", "architecture", "--from", "oo", "need a cache | per tenant")
    assert r.returncode == 0
    assert "R-1 opened" in r.stdout
    assert factory.State.load(py_project).extra["stage"] == "architecture"
    rev = factory.open_revisions(spec_dir)
    assert [(x["id"], x["doc"], x["from"], x["reason"]) for x in rev] == [
        ("R-1", "design/architecture.md", "oo", "need a cache / per tenant")
    ]
    r = hook("pre", py_project, target)  # blocked as soon as the revision is open, before any edit
    assert r.returncode == 2
    assert "revision R-1 on design/architecture.md is open" in r.stderr
    assert "R-1" in run_cli(py_project, "status").stdout

    arch = spec_dir / "design/architecture.md"
    arch.write_text(arch.read_text() + "\nper-tenant cache\n")
    r = run_cli(py_project, "approve", "architecture")
    assert r.returncode == 0, r.stderr
    assert "closes R-1" in r.stdout
    assert "design/api.md" in r.stdout  # later docs need re-confirmation
    assert not factory.open_revisions(spec_dir)
    assert "closed" in (spec_dir / "revisions.md").read_text()

    # Re-confirming an unchanged later doc shows what changed upstream and needs an explicit --yes.
    r = run_cli(py_project, "approve", "api")
    assert r.returncode != 0
    assert "design/architecture.md (R-1: need a cache / per tenant)" in r.stderr
    assert "git diff -- " in r.stderr
    r = run_cli(py_project, "approve", "api", "--yes")
    assert r.returncode == 0
    assert "re-confirmed" in r.stdout
    assert hook("pre", py_project, target).returncode == 2  # data and oo still stale
    approve(py_project, "data --yes", "oo --yes")
    assert hook("pre", py_project, target).returncode == 0


def test_changed_approved_doc_needs_a_revision(py_project: Path) -> None:
    spec_dir = approve_all(py_project)
    oo = spec_dir / "design/oo.md"
    oo.write_text(oo.read_text() + "\nsilent change\n")
    r = run_cli(py_project, "approve", "oo")
    assert r.returncode != 0
    assert "no revision is open" in r.stderr
    assert run_cli(py_project, "revise", "oo", "--from", "tdd", "split the processor").returncode == 0
    approve(py_project, "oo")


def test_spec_change_loops_through_everything(py_project: Path) -> None:
    spec_dir = approve_all(py_project)
    assert run_cli(py_project, "revise", "spec", "--from", "data", "AC-1 is infeasible").returncode == 0
    assert factory.State.load(py_project).extra["stage"] == "spec"
    spec = spec_dir / "spec.md"
    spec.write_text(spec.read_text() + "\nclarified AC-1\n")
    r = run_cli(py_project, "approve", "spec")
    assert r.returncode == 0
    assert "later documents to re-confirm" in r.stdout
    assert "verification.md" in r.stdout
    r = hook("pre", py_project, edit(py_project, "src/sample/dedup.py"))
    assert r.returncode == 2
    assert "verification.md was approved before spec.md (R-1: AC-1 is infeasible) changed" in r.stderr
    approve(py_project, *[f"{d} --yes" for d in CHAIN[1:]])
    assert hook("pre", py_project, edit(py_project, "src/sample/dedup.py")).returncode == 0


def test_later_docs_wait_for_open_upstream_revision(py_project: Path) -> None:
    approve_all(py_project)
    assert run_cli(py_project, "revise", "api", "--from", "oo", "rename op").returncode == 0
    r = run_cli(py_project, "approve", "oo", "--yes")
    assert r.returncode != 0
    assert "revision R-1 on design/api.md is still open" in r.stderr


def test_revise_needs_an_approved_doc(py_project: Path) -> None:
    new_feature(py_project)
    r = run_cli(py_project, "revise", "api", "--from", "oo", "x")
    assert r.returncode != 0
    assert "just edit it" in r.stderr


def test_new_creates_design_docs(py_project: Path) -> None:
    spec_dir = new_feature(py_project)
    for name in factory.DESIGN_DOCS:
        assert factory.frontmatter(spec_dir / name)["applies"] == "undecided"
    r = run_cli(py_project, "status")
    assert "design/oo.md" in r.stdout
    assert "`applies:` must be `yes` or `no`" in r.stdout


def test_guard_allows_prod_edit_once_approved(py_project: Path) -> None:
    approve_all(py_project)
    assert hook("pre", py_project, edit(py_project, "src/sample/dedup.py")).returncode == 0


def test_editing_approved_doc_invalidates_approval(py_project: Path) -> None:
    spec_dir = approve_all(py_project)
    (spec_dir / "spec.md").write_text((spec_dir / "spec.md").read_text() + "\nsneaky change\n")
    r = hook("pre", py_project, edit(py_project, "src/sample/dedup.py"))
    assert r.returncode == 2
    assert "changed after it was approved" in r.stderr


def test_formal_required_blocks_until_model_check_passes(py_project: Path) -> None:
    spec_dir = approve_all(py_project, formal="required")
    target = edit(py_project, "src/sample/dedup.py")
    r = hook("pre", py_project, target)
    assert r.returncode == 2
    assert "no model-check log" in r.stderr

    formal = spec_dir / "formal"
    formal.mkdir()
    tla = formal / "Dedup.tla"
    tla.write_text("---- MODULE Dedup ----\n====\n")
    log = formal / "Dedup.model-check.log"
    log.write_text(f"sha256: {factory.sha256(tla)}\nRESULT: FAIL\n")
    assert hook("pre", py_project, target).returncode == 2
    log.write_text(f"sha256: {factory.sha256(tla)}\nRESULT: PASS\n")
    assert hook("pre", py_project, target).returncode == 0
    tla.write_text(tla.read_text() + "\\* edited\n")
    r = hook("pre", py_project, target)
    assert r.returncode == 2
    assert "changed since it was last model-checked" in r.stderr


def test_spike_mode_disables_guard_loudly(py_project: Path) -> None:
    run_cli(py_project, "spike")
    r = hook("pre", py_project, edit(py_project, "src/sample/dedup.py"))
    assert r.returncode == 0
    assert "SPIKE MODE" in r.stderr
    run_cli(py_project, "spike", "--off")
    assert hook("pre", py_project, edit(py_project, "src/sample/dedup.py")).returncode == 2


@pytest.mark.parametrize(
    "command",
    [
        ".factory/factory approve verification",
        ".factory/factory approve oo",
        ".factory/factory approve oo --yes",
        "cd x && .factory/factory status; .factory/factory approve spec",
        "python3 /x/scripts/factory.py approve spec",
        ".factory/factory spike",
        "echo '{}' > .factory/approvals.json",
    ],
)
def test_claude_cannot_self_approve(py_project: Path, command: str) -> None:
    r = hook("pre", py_project, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert r.returncode == 2


@pytest.mark.parametrize(
    "command",
    [
        ".factory/factory status",
        "pytest -q",
        "cat .factory/approvals.json",
        '.factory/factory revise api --from oo "approve flow needs a bulk operation"',
    ],
)
def test_harmless_bash_allowed(py_project: Path, command: str) -> None:
    assert hook("pre", py_project, {"tool_name": "Bash", "tool_input": {"command": command}}).returncode == 0


def test_claude_cannot_write_approvals_file(py_project: Path) -> None:
    r = hook(
        "pre",
        py_project,
        {"tool_name": "Write", "tool_input": {"file_path": str(py_project / ".factory/approvals.json")}},
    )
    assert r.returncode == 2


# ----------------------------------------------------------------------------- post-edit static checks


def test_post_edit_formats_clean_file(py_project: Path) -> None:
    f = py_project / "src/sample/dedup.py"
    f.write_text(f.read_text().replace("    def process(", "    def   process("))
    assert hook("post", py_project, edit(py_project, "src/sample/dedup.py")).returncode == 0
    assert "def   process(" not in f.read_text()  # ruff format fixed it


def test_post_edit_blocks_on_lint_error(py_project: Path) -> None:
    f = py_project / "src/sample/bad.py"
    f.write_text("def f(x):\n    try:\n        return x\n    except:\n        pass\n")
    r = hook("post", py_project, edit(py_project, "src/sample/bad.py"))
    assert r.returncode == 2
    assert "ruff check" in r.stderr


# ----------------------------------------------------------------------------- stop gate


def test_stop_gate_green_on_clean_fixture(py_project: Path) -> None:
    r = hook("stop", py_project, {})
    assert r.returncode == 0, r.stderr


def test_stop_gate_blocks_on_failing_test(py_project: Path) -> None:
    (py_project / "tests/test_broken.py").write_text("def test_broken() -> None:\n    assert 1 == 2\n")
    r = hook("stop", py_project, {})
    assert r.returncode == 2
    assert "pytest" in r.stderr


def test_stop_gate_blocks_on_type_error(py_project: Path) -> None:
    (py_project / "src/sample/typed.py").write_text("def f(x: int) -> str:\n    return x\n")
    r = hook("stop", py_project, {})
    assert r.returncode == 2
    assert "mypy" in r.stderr


def test_stop_gate_detects_seeded_dedup_bug(py_project: Path) -> None:
    """Reintroduce the DedupRace check-then-act bug; the TLC-derived regression test must catch it."""
    f = py_project / "src/sample/dedup.py"
    claim = "            self._claimed.add(request_id)\n"
    original = f.read_text()
    assert original.count(claim) == 1
    buggy = original.replace(claim, "").replace(
        "            effect()\n", "            effect()\n            self._claimed.add(request_id)\n"
    )
    f.write_text(buggy)
    r = hook("stop", py_project, {})
    assert r.returncode == 2
    assert "test_v03_regression" in r.stderr


def test_stop_gate_detects_premature_ack_bug(py_project: Path) -> None:
    """Reintroduce the bug TLC found in the first 'fixed' design (AckedImpliesApplied)."""
    f = py_project / "src/sample/dedup.py"
    original = f.read_text()
    buggy = original.replace("return Outcome.IN_PROGRESS", "return Outcome.ALREADY_DONE")
    assert buggy != original
    f.write_text(buggy)
    r = hook("stop", py_project, {})
    assert r.returncode == 2
    assert "test_v04_regression" in r.stderr


def test_stop_gate_skips_when_tree_unchanged_since_green(py_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert hook("stop", py_project, {}).returncode == 0
    state = factory.State.load(py_project)
    assert state.extra.get("last_green")
    # Make the gate command fail if it ran: an unchanged tree must not re-run it.
    (py_project / ".factory/config.json").write_text(json.dumps({"commands": {"gate": ["false"]}}))
    assert hook("stop", py_project, {}).returncode == 0
    (py_project / "src/sample/new.py").write_text("X = 1\n")  # tree changed -> gate runs -> fails
    assert hook("stop", py_project, {}).returncode == 2


def test_stop_gate_gives_up_after_max_blocks(py_project: Path) -> None:
    (py_project / ".factory/config.json").write_text(json.dumps({"commands": {"gate": ["false"]}}))
    codes = [hook("stop", py_project, {}).returncode for _ in range(factory.MAX_STOP_BLOCKS + 1)]
    assert codes == [2] * factory.MAX_STOP_BLOCKS + [0]


def test_missing_tool_fails_closed(py_project: Path) -> None:
    checks = [factory.Check("ruff", None, "ruff not found")]
    ok, report = factory.run_checks(py_project, checks)
    assert not ok
    assert "ruff not found" in report


# ----------------------------------------------------------------------------- java stacks (stubbed build tool)


@pytest.mark.parametrize(
    ("kind", "wrapper", "expected_args"), [("maven", "mvnw", "-q -B verify"), ("gradle", "gradlew", "-q check")]
)
def test_java_gate_invokes_wrapper(tmp_path: Path, kind: str, wrapper: str, expected_args: str) -> None:
    root = tmp_path / "j"
    shutil.copytree(FIXTURES / f"java-{kind}-sample", root)
    log = root / "calls.log"
    stub = root / wrapper
    stub.write_text(f'#!/usr/bin/env bash\necho "$@" >> {log}\nexit "${{STUB_EXIT:-0}}"\n')
    stub.chmod(0o755)
    run_cli(root, "init")
    assert hook("stop", root, {}).returncode == 0
    assert expected_args in log.read_text()

    env_fail = env() | {"STUB_EXIT": "1"}
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "hook-stop"],
        input=json.dumps({"cwd": str(root)}),
        env=env_fail,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2


def test_java_post_edit_runs_spotless_on_file(tmp_path: Path) -> None:
    root = tmp_path / "j"
    shutil.copytree(FIXTURES / "java-maven-sample", root)
    log = root / "calls.log"
    (root / "mvnw").write_text(f'#!/usr/bin/env bash\necho "$@" >> {log}\n')
    (root / "mvnw").chmod(0o755)
    run_cli(root, "init")
    rel = "src/main/java/com/example/dedup/DedupProcessor.java"
    assert hook("post", root, edit(root, rel)).returncode == 0
    assert "spotless:apply" in log.read_text()
    assert "DedupProcessor" in log.read_text()


@pytest.mark.skipif(shutil.which("javac") is None, reason="javac not installed")
def test_java_fixture_main_sources_compile(tmp_path: Path) -> None:
    for kind in ("maven", "gradle"):
        src = FIXTURES / f"java-{kind}-sample/src/main/java/com/example/dedup/DedupProcessor.java"
        r = subprocess.run(
            ["javac", "-Xlint:all", "-Werror", "-d", str(tmp_path / kind), str(src)], capture_output=True, text=True
        )
        assert r.returncode == 0, r.stderr


# ----------------------------------------------------------------------------- evidence / tdd / formal


def test_evidence_check(py_project: Path) -> None:
    spec_dir = approve_all(py_project)
    ver = spec_dir / "verification.md"
    ver.write_text(
        ver.read_text().replace(
            "| V-01 | AC-1 | functional |",
            "| V-02 | AC-1 | property | p | hypothesis | yes | t |\n| V-01 | AC-1 | functional |",
        )
    )
    ok, msg = factory.evidence_check(spec_dir)
    assert not ok
    assert "V-01" in msg
    ev = spec_dir / "evidence.md"
    ev.write_text(ev.read_text().replace("| V-01 |        |", "| V-01 | PASS |") + "\n| V-02 | FAIL | x | y |\n")
    ok, msg = factory.evidence_check(spec_dir)
    assert not ok
    assert "V-02" in msg
    assert "V-01" not in msg
    ev.write_text(ev.read_text().replace("| V-02 | FAIL |", "| V-02 | ACCEPTED-RISK |"))
    ok, msg = factory.evidence_check(spec_dir)
    assert not ok  # design-conformance rows of the applicable docs (architecture, oo) still missing
    assert "DC-ARCH-01" in msg
    assert "DC-OO-01" in msg
    ev.write_text(ev.read_text() + "| DC-ARCH-01 | PASS | t | yes |\n| DC-OO-01 | PASS | t | yes |\n")
    assert factory.evidence_check(spec_dir)[0]


def test_na_design_docs_contribute_no_dc_rows(py_project: Path) -> None:
    spec_dir = approve_all(py_project)  # api and data are applies: no, but keep their template DC rows
    ids = factory.design_conformance_ids(spec_dir)
    assert ids == ["DC-ARCH-01", "DC-OO-01"]


def test_gate_runs_import_linter_when_configured(py_project: Path) -> None:
    assert "lint-imports" not in [c.name for c in factory.gate_checks(py_project)]
    pyproject = py_project / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.importlinter]\nroot_package = "sample"\n')
    checks = {c.name: c for c in factory.gate_checks(py_project)}
    assert "lint-imports" in checks
    if checks["lint-imports"].argv is None:  # fails closed when the tool is missing
        ok, report = factory.run_checks(py_project, [checks["lint-imports"]])
        assert not ok
        assert "lint-imports not found" in report


def test_stop_gate_enforces_evidence_in_evidence_stage(py_project: Path) -> None:
    approve_all(py_project)
    run_cli(py_project, "stage", "evidence")
    r = hook("stop", py_project, {})
    assert r.returncode == 2
    assert "evidence incomplete" in r.stderr


def test_record_red_logs_expected_failure(py_project: Path) -> None:
    spec_dir = approve_all(py_project)
    assert run_cli(py_project, "record-red", "V-01", "exit 1").returncode == 0
    assert run_cli(py_project, "record-red", "V-02", "exit 0").returncode == 1
    log = (spec_dir / "tdd-log.md").read_text()
    assert "V-01 red run" in log
    assert "RED (as expected)" in log
    assert "V-02 red run" in log
    assert "unexpected" in log


@pytest.mark.parametrize(
    ("output", "ok", "fragment"),
    [
        ("...\nModel checking completed. No error has been found.\n", True, "no error"),
        ("Error: Invariant AppliedAtMostOnce is violated.\n", False, "AppliedAtMostOnce"),
        ("Error: Temporal properties were violated.\n", False, "Temporal"),
        ("Error: Deadlock reached.\n", False, "Deadlock"),
        ("killed\n", False, "did not report"),
    ],
)
def test_parse_tlc(output: str, ok: bool, fragment: str) -> None:
    got_ok, summary = factory.parse_tlc(output)
    assert got_ok is ok
    assert fragment in summary


needs_tlc = pytest.mark.skipif(
    factory.tla_jar() is None or shutil.which("java") is None, reason="tla2tools.jar / java not available"
)


@needs_tlc
def test_tlc_proves_fixed_dedup(tmp_path: Path) -> None:
    d = tmp_path / "f"
    shutil.copytree(FIXTURES / "formal-sample", d)
    r = run_cli(d, "model-check", str(d / "Dedup.tla"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert (d / "Dedup.model-check.log").read_text().rstrip().endswith("RESULT: PASS")


@needs_tlc
@pytest.mark.parametrize(("cfg", "violated"), [("DedupRace", "AppliedAtMostOnce"), ("DedupProbe", "ProbeNeverAcked")])
def test_tlc_finds_seeded_bug_and_probe(tmp_path: Path, cfg: str, violated: str) -> None:
    d = tmp_path / "f"
    shutil.copytree(FIXTURES / "formal-sample", d)
    args = ["model-check", str(d / "Dedup.tla"), "--config", str(d / f"{cfg}.cfg")]
    r = run_cli(d, *args)
    assert r.returncode == 1
    assert violated in r.stdout
    r = run_cli(d, *args, "--expect-violation", violated)
    assert r.returncode == 0, r.stdout
    assert (d / f"Dedup.{cfg}.model-check.log").read_text().rstrip().endswith("RESULT: PASS")


@needs_tlc
def test_expect_violation_fails_when_spec_holds(tmp_path: Path) -> None:
    d = tmp_path / "f"
    shutil.copytree(FIXTURES / "formal-sample", d)
    r = run_cli(d, "model-check", str(d / "Dedup.tla"), "--expect-violation", "AppliedAtMostOnce")
    assert r.returncode == 1
    assert "NOT found" in r.stdout


def test_formal_logs_per_config_all_count(tmp_path: Path) -> None:
    formal = tmp_path / "formal"
    formal.mkdir()
    tla = formal / "Dedup.tla"
    tla.write_text("x")
    (formal / "Dedup.model-check.log").write_text(f"sha256: {factory.sha256(tla)}\nRESULT: PASS\n")
    (formal / "Dedup.DedupProbe.model-check.log").write_text(f"sha256: {factory.sha256(tla)}\nRESULT: PASS\n")
    assert factory.formal_passed(tmp_path)[0]
    tla.write_text("y")  # probe log is stale too
    ok, msg = factory.formal_passed(tmp_path)
    assert not ok
    assert "changed since" in msg


# ----------------------------------------------------------------------------- skipped tests


def test_gate_rejects_skipped_python_test(py_project: Path) -> None:
    (py_project / "tests/test_skip.py").write_text(
        'import pytest\n\n\n@pytest.mark.skip(reason="later")\ndef test_later() -> None:\n    pass\n'
    )
    r = hook("stop", py_project, {})
    assert r.returncode == 2
    assert "skipped tests" in r.stderr
    assert "test_later" in r.stderr
    (py_project / ".factory/config.json").write_text(json.dumps({"allow_skipped": ["test_later"]}))
    assert hook("stop", py_project, {}).returncode == 0


def test_gate_rejects_skips_in_fresh_surefire_report(tmp_path: Path) -> None:
    root = tmp_path / "j"
    shutil.copytree(FIXTURES / "java-maven-sample", root)
    reports = root / "target/surefire-reports"
    xml = (
        '<testsuite name="T" tests="1" skipped="1"><testcase classname="com.x.T" name="prop">'
        '<skipped message="A @Property method must not have JUnit annotations"/></testcase></testsuite>'
    )
    (root / "mvnw").write_text(f"#!/usr/bin/env bash\nmkdir -p {reports}\necho '{xml}' > {reports}/TEST-T.xml\n")
    (root / "mvnw").chmod(0o755)
    run_cli(root, "init")
    r = hook("stop", root, {})
    assert r.returncode == 2
    assert "com.x.T::prop" in r.stderr


def test_stale_reports_are_ignored(tmp_path: Path) -> None:
    reports = tmp_path / "target/surefire-reports"
    reports.mkdir(parents=True)
    report = reports / "TEST-old.xml"
    report.write_text('<testsuite><testcase classname="A" name="b"><skipped/></testcase></testsuite>')
    os.utime(report, (1, 1))
    assert factory.skipped_tests(tmp_path, since=100) == []
    assert factory.skipped_tests(tmp_path, since=0) == ["A::b"]
