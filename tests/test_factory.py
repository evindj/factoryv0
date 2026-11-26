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


def approve_all(root: Path, formal: str = "not-needed") -> Path:
    assert run_cli(root, "new", "dedup").returncode == 0
    spec_dir = root / factory.State.load(root).active  # type: ignore[operator]
    ver = spec_dir / "verification.md"
    ver.write_text(ver.read_text().replace("formal: undecided", f"formal: {formal}"))
    assert run_cli(root, "approve", "spec").returncode == 0
    assert run_cli(root, "approve", "verification").returncode == 0
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


def test_guard_requires_both_approvals_and_formal_decision(py_project: Path) -> None:
    run_cli(py_project, "new", "dedup")
    target = edit(py_project, "src/sample/dedup.py")
    run_cli(py_project, "approve", "spec")
    r = hook("pre", py_project, target)
    assert r.returncode == 2
    assert "verification.md has not been approved" in r.stderr
    run_cli(py_project, "approve", "verification")
    r = hook("pre", py_project, target)  # formal still "undecided"
    assert r.returncode == 2
    assert "formal:" in r.stderr


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
        "python3 /x/scripts/factory.py approve spec",
        ".factory/factory spike",
        "echo '{}' > .factory/approvals.json",
    ],
)
def test_claude_cannot_self_approve(py_project: Path, command: str) -> None:
    r = hook("pre", py_project, {"tool_name": "Bash", "tool_input": {"command": command}})
    assert r.returncode == 2


@pytest.mark.parametrize("command", [".factory/factory status", "pytest -q", "cat .factory/approvals.json"])
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
    assert factory.evidence_check(spec_dir)[0]


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
