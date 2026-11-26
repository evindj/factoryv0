#!/usr/bin/env python3
"""Software Factory: gates and helpers for the Claude Code workflow kit.

The hooks and the user CLI both use this one module. It is stdlib-only so it runs anywhere python3 exists.

Workflow per feature (docs/specs/NNNN-slug/):
  spec.md -> verification.md -> [formal/] -> TDD -> evidence.md

Approvals are recorded by the *human* (`.factory/factory approve <doc>`) as a
sha256 of the document. Editing an approved document invalidates its approval.
Claude is blocked by hooks from writing approvals itself.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = PLUGIN_ROOT / "templates"
FACTORY_DIR = ".factory"
SPECS_DIR = Path("docs") / "specs"
MAX_STOP_BLOCKS = 3

# Exit codes understood by Claude Code hooks: 0 = ok, 2 = block (stderr shown to Claude).
OK, BLOCK = 0, 2


# --------------------------------------------------------------------------- project / state


def find_root(start: Path) -> Path | None:
    """Nearest ancestor (inclusive) that contains a .factory directory."""
    start = start.resolve()
    for p in [start, *start.parents]:
        if (p / FACTORY_DIR).is_dir():
            return p
    return None


@dataclass
class State:
    root: Path
    active: str | None = None
    mode: str = "normal"  # normal | spike
    stop_blocks: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return self.root / FACTORY_DIR / "state.json"

    @classmethod
    def load(cls, root: Path) -> State:
        p = root / FACTORY_DIR / "state.json"
        data = json.loads(p.read_text()) if p.exists() else {}
        return cls(
            root=root,
            active=data.pop("active", None),
            mode=data.pop("mode", "normal"),
            stop_blocks=data.pop("stop_blocks", 0),
            extra=data,
        )

    def save(self) -> None:
        data = {"active": self.active, "mode": self.mode, "stop_blocks": self.stop_blocks, **self.extra}
        self.path.write_text(json.dumps(data, indent=2) + "\n")

    @property
    def spec_dir(self) -> Path | None:
        return self.root / self.active if self.active else None


def load_config(root: Path) -> dict[str, Any]:
    p = root / FACTORY_DIR / "config.json"
    return json.loads(p.read_text()) if p.exists() else {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def approvals_path(root: Path) -> Path:
    return root / FACTORY_DIR / "approvals.json"


def load_approvals(root: Path) -> dict[str, Any]:
    p = approvals_path(root)
    return json.loads(p.read_text()) if p.exists() else {}


def is_approved(root: Path, doc: Path) -> tuple[bool, str]:
    if not doc.exists():
        return False, f"{doc.relative_to(root)} does not exist"
    rel = str(doc.relative_to(root))
    rec = load_approvals(root).get(rel)
    if not rec:
        return False, f"{rel} has not been approved by a human"
    if rec["sha256"] != sha256(doc):
        return False, f"{rel} changed after it was approved; it must be re-approved"
    return True, "approved"


def frontmatter(doc: Path) -> dict[str, str]:
    """Parse a minimal `key: value` YAML-ish frontmatter block."""
    if not doc.exists():
        return {}
    text = doc.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.split("#", 1)[0].strip()
    return out


# --------------------------------------------------------------------------- stack detection


def detect_stacks(root: Path) -> list[str]:
    stacks = []
    if (root / "pyproject.toml").exists() or (root / "setup.cfg").exists():
        stacks.append("python")
    if (root / "pom.xml").exists():
        stacks.append("maven")
    if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        stacks.append("gradle")
    return stacks


def _py_tool(root: Path, tool: str) -> list[str] | None:
    if (root / "uv.lock").exists() and shutil.which("uv"):
        return ["uv", "run", tool]
    for venv in (".venv", "venv"):
        cand = root / venv / "bin" / tool
        if cand.exists():
            return [str(cand)]
    found = shutil.which(tool)
    return [found] if found else None


def _mvn(root: Path) -> list[str] | None:
    if (root / "mvnw").exists():
        return [str(root / "mvnw")]
    found = shutil.which("mvn") or _plugin_tool("apache-maven-*/bin/mvn")
    return [found] if found else None


def _gradle(root: Path) -> list[str] | None:
    if (root / "gradlew").exists():
        return [str(root / "gradlew")]
    found = shutil.which("gradle") or _plugin_tool("gradle-*/bin/gradle")
    return [found] if found else None


def _plugin_tool(pattern: str) -> str | None:
    """Fallback to a tool unpacked into the plugin's .tools/ directory."""
    matches = sorted((PLUGIN_ROOT / ".tools").glob(pattern))
    return str(matches[-1]) if matches else None


@dataclass
class Check:
    name: str
    argv: list[str] | None  # None => tool missing
    missing: str = ""


def gate_checks(root: Path) -> list[Check]:
    """Whole-project checks the Stop gate runs (static + tests)."""
    cfg = load_config(root).get("commands", {})
    if "gate" in cfg:  # explicit override: list of shell commands
        return [Check(f"gate[{i}]", ["bash", "-c", c]) for i, c in enumerate(cfg["gate"])]
    checks: list[Check] = []
    for stack in detect_stacks(root):
        if stack == "python":
            for name, tool, args in (
                ("ruff format --check", "ruff", ["format", "--check", "."]),
                ("ruff check", "ruff", ["check", "."]),
                ("mypy", "mypy", []),
                ("pytest", "pytest", ["-q", f"--junitxml={root / FACTORY_DIR / 'reports' / 'pytest.xml'}"]),
            ):
                base = _py_tool(root, tool)
                checks.append(Check(name, base + args if base else None, f"{tool} not found (uv, .venv or PATH)"))
        elif stack == "maven":
            base = _mvn(root)
            checks.append(Check("mvn verify", [*base, "-q", "-B", "verify"] if base else None, "mvn/mvnw not found"))
        elif stack == "gradle":
            base = _gradle(root)
            checks.append(Check("gradle check", [*base, "-q", "check"] if base else None, "gradle/gradlew not found"))
    return checks


def file_checks(root: Path, file: Path) -> list[Check]:
    """Fast per-file format + lint run after every edit."""
    cfg = load_config(root).get("commands", {})
    suffix = file.suffix
    if suffix == ".py":
        if "python_file" in cfg:
            return [Check("python_file", ["bash", "-c", cfg["python_file"].replace("{file}", shlex.quote(str(file)))])]
        ruff = _py_tool(root, "ruff")
        if not ruff:
            return [Check("ruff", None, "ruff not found (uv, .venv or PATH)")]
        return [
            Check("ruff format", [*ruff, "format", str(file)]),
            Check("ruff check", [*ruff, "check", "--fix", str(file)]),
        ]
    if suffix in (".java", ".kt"):
        if "java_file" in cfg:
            return [Check("java_file", ["bash", "-c", cfg["java_file"].replace("{file}", shlex.quote(str(file)))])]
        stacks = detect_stacks(root)
        if "maven" in stacks:
            base = _mvn(root)
            if not base:
                return [Check("spotless", None, "mvn/mvnw not found")]
            return [
                Check(
                    "spotless:apply", [*base, "-q", "-B", "spotless:apply", f"-DspotlessFiles={re.escape(str(file))}"]
                )
            ]
        if "gradle" in stacks:
            base = _gradle(root)
            if not base:
                return [Check("spotless", None, "gradle/gradlew not found")]
            return [Check("spotlessApply", [*base, "-q", "spotlessApply", f"-PspotlessIdeHook={file}"])]
    return []


def run_checks(root: Path, checks: list[Check], timeout: int = 1800) -> tuple[bool, str]:
    report, ok = [], True
    for c in checks:
        if c.argv is None:
            ok = False
            report.append(f"✗ {c.name}: {c.missing}")
            continue
        try:
            proc = subprocess.run(c.argv, cwd=root, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            ok = False
            report.append(f"✗ {c.name}: timed out after {timeout}s")
            continue
        if proc.returncode == 0:
            report.append(f"✓ {c.name}")
        else:
            ok = False
            out = (proc.stdout + proc.stderr).strip()
            report.append(f"✗ {c.name} (exit {proc.returncode})\n{_tail(out, 60)}")
    return ok, "\n".join(report)


REPORT_GLOBS = (
    "target/surefire-reports/TEST-*.xml",
    "target/failsafe-reports/TEST-*.xml",
    "build/test-results/*/TEST-*.xml",
    f"{FACTORY_DIR}/reports/*.xml",
)


def skipped_tests(root: Path, since: float) -> list[str]:
    """Skipped test cases in JUnit-XML reports written after `since` (epoch seconds).

    A skipped test verifies nothing. jqwik, for instance, silently skips a @Property that has a
    JUnit annotation, so skips fail the gate unless allowed in .factory/config.json ("allow_skipped").
    """
    allowed = set(load_config(root).get("allow_skipped", []))
    found: list[str] = []
    for pattern in REPORT_GLOBS:
        for report in sorted(root.glob(pattern)):
            if report.stat().st_mtime < since:
                continue
            try:
                tree = ET.parse(report)
            except ET.ParseError:
                continue
            for case in tree.iter("testcase"):
                skip = case.find("skipped")
                if skip is None:
                    continue
                name = f"{case.get('classname', '')}::{case.get('name', '')}".lstrip(":")
                if name in allowed or case.get("name") in allowed:
                    continue
                found.append(f"{name}: {skip.get('message', '')}".rstrip(": "))
    return found


def run_gate(root: Path) -> tuple[bool, str]:
    """Static checks + tests, then reject skipped tests in fresh reports."""
    start = time.time() - 1
    ok, report = run_checks(root, gate_checks(root))
    if ok:
        skipped = skipped_tests(root, since=start)
        if skipped:
            ok = False
            report += (
                "\n✗ skipped tests (a skipped test verifies nothing; fix it or allow it in .factory/config.json):\n  "
                + "\n  ".join(skipped)
            )
    return ok, report


def _tail(text: str, n: int) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n:]) if len(lines) > n else text


# --------------------------------------------------------------------------- path classification


def is_production_code(root: Path, file: Path) -> bool:
    """True for source files that the verification gate protects."""
    try:
        rel = file.resolve().relative_to(root.resolve())
    except ValueError:
        return False  # outside the project: not ours to guard
    parts = rel.parts
    if not parts or parts[0] in (FACTORY_DIR, "docs", ".venv", "venv", "build", "target", ".git"):
        return False
    if file.suffix == ".py":
        name = file.name
        if "tests" in parts or "test" in parts or name.startswith("test_") or name.endswith("_test.py"):
            return False
        return name != "conftest.py"
    if file.suffix in (".java", ".kt", ".scala"):
        return "main" in parts and "src" in parts
    return False


# --------------------------------------------------------------------------- hooks


def _hook_input() -> dict[str, Any]:
    raw = sys.stdin.read()
    try:
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def _project_root_from_hook(data: dict[str, Any]) -> Path | None:
    base = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    return find_root(Path(base))


def _target_file(data: dict[str, Any]) -> Path | None:
    ti = data.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not fp:
        return None
    p = Path(fp)
    if not p.is_absolute():
        p = Path(data.get("cwd") or os.getcwd()) / p
    return p


def guard_edit(root: Path, file: Path) -> tuple[int, str]:
    """PreToolUse(Edit|Write|MultiEdit|NotebookEdit) policy."""
    try:
        rel = file.resolve().relative_to(root.resolve())
    except ValueError:
        return OK, ""
    if rel.parts[:2] == (FACTORY_DIR, "approvals.json") or rel == Path(FACTORY_DIR) / "approvals.json":
        return BLOCK, "Approvals are recorded by the human only (`! .factory/factory approve <doc>`)."
    if not is_production_code(root, file):
        return OK, ""
    state = State.load(root)
    if state.mode == "spike":
        return OK, "[factory] SPIKE MODE: verification gate disabled; this code must not ship as-is."
    if not state.spec_dir:
        return BLOCK, (
            f"[factory] Blocked edit to production code {rel}: no active feature spec.\n"
            "Start one with the `factory` skill (spec -> verification design) or run "
            "`! .factory/factory spike` for throwaway exploration."
        )
    problems = []
    for doc in ("spec.md", "verification.md"):
        ok, why = is_approved(root, state.spec_dir / doc)
        if not ok:
            problems.append(why)
    if not problems:
        fm = frontmatter(state.spec_dir / "verification.md")
        formal = fm.get("formal", "").lower()
        if formal == "required":
            ok, why = formal_passed(state.spec_dir)
            if not ok:
                problems.append(why)
        elif formal != "not-needed":
            problems.append("verification.md frontmatter `formal:` must be `required` or `not-needed`")
    if problems:
        return BLOCK, (
            f"[factory] Blocked edit to production code {rel}. The verification gate is not satisfied:\n  - "
            + "\n  - ".join(problems)
            + "\nFinish the spec / verification design (and formal spec if required) and ask the human to approve."
        )
    return OK, ""


APPROVE_CMD = re.compile(r"(factory(\.py)?|\.factory/factory)\b.*\b(approve|spike|unspike)\b")


def guard_bash(command: str) -> tuple[int, str]:
    """PreToolUse(Bash): Claude may not approve its own work or toggle spike mode."""
    if APPROVE_CMD.search(command):
        return BLOCK, (
            "[factory] Approvals and spike mode are human decisions. Ask the user to run it "
            "themselves, e.g. `! .factory/factory approve verification`."
        )
    if re.search(r"\.factory/approvals\.json", command) and re.search(r"(>|tee|sed\s+-i|mv|cp|rm)", command):
        return BLOCK, "[factory] .factory/approvals.json may only be written by `factory approve`."
    return OK, ""


def cmd_hook_pre(_: argparse.Namespace) -> int:
    data = _hook_input()
    root = _project_root_from_hook(data)
    if root is None:
        return OK  # project not factory-enabled: do nothing
    tool = data.get("tool_name", "")
    if tool == "Bash":
        code, msg = guard_bash((data.get("tool_input") or {}).get("command", ""))
    else:
        file = _target_file(data)
        code, msg = guard_edit(root, file) if file else (OK, "")
    if msg:
        print(msg, file=sys.stderr)
    return code


def cmd_hook_post(_: argparse.Namespace) -> int:
    data = _hook_input()
    root = _project_root_from_hook(data)
    file = _target_file(data)
    if root is None or file is None or not file.exists():
        return OK
    checks = file_checks(root, file)
    if not checks:
        return OK
    ok, report = run_checks(root, checks, timeout=300)
    if ok:
        return OK
    print(f"[factory] Static checks failed for {file.name}; fix before continuing:\n{report}", file=sys.stderr)
    return BLOCK


GENERATED_DIRS = {
    FACTORY_DIR,
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".hypothesis",
    "target",
    "build",
    ".gradle",
    ".tlc-states",
    "states",
    "mutants",
}


def worktree_fingerprint(root: Path) -> str | None:
    """Hash of the working tree's changes vs HEAD (None if not a git repo)."""
    try:
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--", ".", f":!{FACTORY_DIR}"], cwd=root, capture_output=True, text=True, timeout=30
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if diff.returncode != 0 or untracked.returncode != 0:
        return None
    h = hashlib.sha256(diff.stdout.encode())
    for name in sorted(untracked.stdout.split("\0")):
        p = root / name
        if name and not set(Path(name).parts) & GENERATED_DIRS and p.is_file():
            h.update(name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def cmd_hook_stop(_: argparse.Namespace) -> int:
    data = _hook_input()
    root = _project_root_from_hook(data)
    if root is None:
        return OK
    state = State.load(root)
    fp = worktree_fingerprint(root)
    if fp and fp == state.extra.get("last_green") and state.extra.get("stage") != "evidence":
        return OK  # nothing changed since the last green gate (e.g. a Q&A turn)
    ok, report = run_gate(root)
    problems = [] if ok else [report]
    if state.spec_dir and state.extra.get("stage") == "evidence":
        e_ok, e_report = evidence_check(state.spec_dir)
        if not e_ok:
            problems.append(e_report)
    if not problems:
        state.stop_blocks = 0
        fp_after = worktree_fingerprint(root)  # the gate itself may have touched the tree
        if fp_after:
            state.extra["last_green"] = fp_after
        state.save()
        return OK
    state.stop_blocks += 1
    state.save()
    if state.stop_blocks > MAX_STOP_BLOCKS:
        # Avoid an infinite loop, but say clearly that the work is not done.
        print(
            f"[factory] Gate still failing after {MAX_STOP_BLOCKS} attempts; allowing stop. "
            "Tell the user the work is NOT verified:\n" + "\n".join(problems),
            file=sys.stderr,
        )
        state.stop_blocks = 0
        state.save()
        return OK
    print("[factory] Not done: the gate failed.\n" + "\n".join(problems), file=sys.stderr)
    return BLOCK


# --------------------------------------------------------------------------- evidence / formal


ROW_ID = re.compile(r"\b(V-\d{2,})\b")
EVIDENCE_OK = ("PASS", "ACCEPTED-RISK", "MANUAL-PASS")


def verification_ids(spec_dir: Path) -> list[str]:
    doc = spec_dir / "verification.md"
    if not doc.exists():
        return []
    ids: list[str] = []
    for line in doc.read_text().splitlines():
        if line.lstrip().startswith("|"):
            m = ROW_ID.search(line.split("|")[1] if line.count("|") > 1 else line)
            if m and m.group(1) not in ids:
                ids.append(m.group(1))
    return ids


def evidence_check(spec_dir: Path) -> tuple[bool, str]:
    ids = verification_ids(spec_dir)
    ev = spec_dir / "evidence.md"
    if not ids:
        return False, f"{spec_dir.name}: verification.md has no V-NN rows"
    if not ev.exists():
        return False, f"{spec_dir.name}: evidence.md missing"
    status: dict[str, str] = {}
    for line in ev.read_text().splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and ROW_ID.fullmatch(cells[0]):
            status[cells[0]] = next((s for s in EVIDENCE_OK if any(s == c.upper() for c in cells)), "")
            if not status[cells[0]]:
                status[cells[0]] = "|".join(cells[1:])[:40] or "?"
    missing = [i for i in ids if i not in status]
    bad = [f"{i} ({status[i]})" for i in ids if i in status and status[i] not in EVIDENCE_OK]
    if missing or bad:
        msg = f"{spec_dir.name}: evidence incomplete."
        if missing:
            msg += " No evidence for: " + ", ".join(missing) + "."
        if bad:
            msg += " Not passing: " + ", ".join(bad) + "."
        return False, msg
    return True, f"{spec_dir.name}: all {len(ids)} verification rows have evidence"


def formal_passed(spec_dir: Path) -> tuple[bool, str]:
    logs = sorted((spec_dir / "formal").glob("*.model-check.log"))
    if not logs:
        return False, "verification.md says formal: required, but no model-check log exists in formal/"
    failed = []
    for log in logs:
        # <Spec>.model-check.log or <Spec>.<Cfg>.model-check.log
        tla = log.with_name(log.name.split(".", 1)[0] + ".tla")
        lines = log.read_text().splitlines()
        if not lines or lines[-1].strip() != "RESULT: PASS":
            failed.append(f"{log.name} is not passing")
        elif tla.exists() and f"sha256: {sha256(tla)}" not in lines:
            failed.append(f"{tla.name} changed since it was last model-checked")
    if failed:
        return False, "; ".join(failed)
    return True, "model-checked"


def parse_tlc(output: str) -> tuple[bool, str]:
    if "Model checking completed. No error has been found." in output:
        return True, "no error found"
    for pat in (
        r"Error: Invariant (\S+) is violated",
        r"Error: Temporal properties were violated",
        r"Error: Deadlock reached",
        r"Error: (.+)",
    ):
        m = re.search(pat, output)
        if m:
            return False, m.group(0)
    return False, "TLC did not report completion"


def tla_jar() -> Path | None:
    for cand in (
        os.environ.get("TLA2TOOLS_JAR"),
        PLUGIN_ROOT / ".tools" / "tla2tools.jar",
        Path.home() / ".factory" / "tla2tools.jar",
    ):
        if cand and Path(cand).exists():
            return Path(cand)
    return None


def cmd_model_check(args: argparse.Namespace) -> int:
    tla = Path(args.spec).resolve()
    cfg = Path(args.config).resolve() if args.config else tla.with_suffix(".cfg")
    jar = tla_jar()
    if not jar:
        print(
            "tla2tools.jar not found: set TLA2TOOLS_JAR or put it at ~/.factory/tla2tools.jar "
            "(https://github.com/tlaplus/tlaplus/releases)",
            file=sys.stderr,
        )
        return 1
    argv = [
        "java",
        "-XX:+UseParallelGC",
        "-cp",
        str(jar),
        "tlc2.TLC",
        "-workers",
        "auto",
        "-config",
        str(cfg),
        "-metadir",
        str(tla.parent / ".tlc-states"),
        str(tla),
    ]
    proc = subprocess.run(argv, cwd=tla.parent, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    no_error, summary = parse_tlc(out)
    if args.expect_violation:
        # Vacuity probes / seeded bugs: passing means TLC found the expected violation.
        found = (not no_error) and args.expect_violation in summary
        ok = found
        summary = f"expected violation of {args.expect_violation}: {'found' if found else 'NOT found'} ({summary})"
    else:
        ok = no_error
    name = tla.stem if cfg.stem == tla.stem else f"{tla.stem}.{cfg.stem}"
    log = tla.with_name(name + ".model-check.log")
    stamp = _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")
    log.write_text(
        f"# TLC run {stamp}\n# command: {shlex.join(argv)}\n{out}\n"
        f"sha256: {sha256(tla)}\nsummary: {summary}\nRESULT: {'PASS' if ok else 'FAIL'}\n"
    )
    print(f"{'PASS' if ok else 'FAIL'}: {summary}  (log: {log})")
    return 0 if ok else 1


# --------------------------------------------------------------------------- user CLI


SHIM = """#!/usr/bin/env bash
# Generated by software-factory `init`. Forwards to the plugin's CLI.
exec python3 {script} "$@"
"""


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    fdir = root / FACTORY_DIR
    fdir.mkdir(exist_ok=True)
    (root / SPECS_DIR).mkdir(parents=True, exist_ok=True)
    if not (fdir / "state.json").exists():
        State(root=root).save()
    shim = fdir / "factory"
    shim.write_text(SHIM.format(script=shlex.quote(str(Path(__file__).resolve()))))
    shim.chmod(0o755)
    claude_md = root / "CLAUDE.md"
    snippet = (TEMPLATES / "CLAUDE.md.snippet").read_text()
    marker = "<!-- software-factory -->"
    existing = claude_md.read_text() if claude_md.exists() else ""
    if marker not in existing:
        claude_md.write_text((existing + "\n\n" if existing else "") + snippet)
    print(f"factory initialised in {root} (stacks: {', '.join(detect_stacks(root)) or 'none detected'})")
    return 0


def _require_root() -> Path:
    root = find_root(Path.cwd())
    if root is None:
        sys.exit("not a factory project (run `factory init` first)")
    return root


def cmd_new(args: argparse.Namespace) -> int:
    root = _require_root()
    specs = root / SPECS_DIR
    specs.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for d in specs.iterdir() if (m := re.match(r"(\d{4})-", d.name))]
    slug = re.sub(r"[^a-z0-9]+", "-", args.slug.lower()).strip("-")
    d = specs / f"{(max(nums) + 1) if nums else 1:04d}-{slug}"
    d.mkdir()
    for name in ("spec.md", "verification.md", "evidence.md"):
        (d / name).write_text((TEMPLATES / name).read_text().replace("{{feature}}", args.slug))
    state = State.load(root)
    state.active = str(d.relative_to(root))
    state.extra["stage"] = "spec"
    state.save()
    print(state.active)
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    root = _require_root()
    state = State.load(root)
    state.extra["stage"] = args.stage
    state.save()
    print(f"stage: {args.stage}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    root = _require_root()
    state = State.load(root)
    if not state.spec_dir:
        sys.exit("no active spec")
    doc = state.spec_dir / (args.doc if args.doc.endswith(".md") else f"{args.doc}.md")
    if not doc.exists():
        sys.exit(f"{doc} not found")
    approvals = load_approvals(root)
    approvals[str(doc.relative_to(root))] = {
        "sha256": sha256(doc),
        "by": os.environ.get("USER", "human"),
        "at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
    }
    approvals_path(root).write_text(json.dumps(approvals, indent=2) + "\n")
    print(f"approved {doc.relative_to(root)}")
    return 0


def cmd_spike(args: argparse.Namespace) -> int:
    root = _require_root()
    state = State.load(root)
    state.mode = "normal" if args.off else "spike"
    state.save()
    print(f"mode: {state.mode}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    root = _require_root()
    state = State.load(root)
    print(f"root:   {root}\nstacks: {', '.join(detect_stacks(root)) or 'none'}\nmode:   {state.mode}")
    print(f"active: {state.active or '-'}  stage: {state.extra.get('stage', '-')}")
    if state.spec_dir:
        for doc in ("spec.md", "verification.md"):
            print(f"  {doc:16} {is_approved(root, state.spec_dir / doc)[1]}")
        fm = frontmatter(state.spec_dir / "verification.md")
        if fm.get("formal", "").lower() == "required":
            print(f"  {'formal':16} {formal_passed(state.spec_dir)[1]}")
        print(f"  {'evidence':16} {evidence_check(state.spec_dir)[1]}")
    return 0


def cmd_gate(_: argparse.Namespace) -> int:
    root = _require_root()
    ok, report = run_gate(root)
    print(report)
    return 0 if ok else 1


def cmd_evidence(_: argparse.Namespace) -> int:
    root = _require_root()
    state = State.load(root)
    if not state.spec_dir:
        sys.exit("no active spec")
    ok, msg = evidence_check(state.spec_dir)
    print(msg)
    return 0 if ok else 1


def cmd_record_red(args: argparse.Namespace) -> int:
    """Run a check that MUST fail (TDD red step) and log it as proof."""
    root = _require_root()
    state = State.load(root)
    if not state.spec_dir:
        sys.exit("no active spec")
    proc = subprocess.run(args.command, cwd=root, shell=True, capture_output=True, text=True)
    log = state.spec_dir / "tdd-log.md"
    stamp = _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")
    verdict = "RED (as expected)" if proc.returncode != 0 else "GREEN (unexpected: check did not fail)"
    with log.open("a") as f:
        f.write(
            f"\n## {args.row} red run, {stamp}: {verdict}\n\n`{args.command}` (exit {proc.returncode})\n\n"
            f"```\n{_tail(proc.stdout + proc.stderr, 25)}\n```\n"
        )
    print(f"{args.row}: {verdict}")
    return 0 if proc.returncode != 0 else 1


def cmd_detect(args: argparse.Namespace) -> int:
    print(" ".join(detect_stacks(Path(args.dir).resolve())))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="factory", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hook-pre").set_defaults(fn=cmd_hook_pre)
    sub.add_parser("hook-post").set_defaults(fn=cmd_hook_post)
    sub.add_parser("hook-stop").set_defaults(fn=cmd_hook_stop)
    s = sub.add_parser("init", help="enable the factory in a project")
    s.add_argument("dir", nargs="?", default=".")
    s.set_defaults(fn=cmd_init)
    s = sub.add_parser("new", help="create docs/specs/NNNN-slug and make it active")
    s.add_argument("slug")
    s.set_defaults(fn=cmd_new)
    s = sub.add_parser("stage", help="record the current stage")
    s.add_argument("stage", choices=["spec", "verify-design", "formal", "tdd", "evidence", "done"])
    s.set_defaults(fn=cmd_stage)
    s = sub.add_parser("approve", help="(human) approve spec|verification of the active feature")
    s.add_argument("doc")
    s.set_defaults(fn=cmd_approve)
    s = sub.add_parser("spike", help="(human) toggle spike mode")
    s.add_argument("--off", action="store_true")
    s.set_defaults(fn=cmd_spike)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("gate", help="run the full static + test gate").set_defaults(fn=cmd_gate)
    sub.add_parser("evidence", help="check evidence.md covers every V-NN row").set_defaults(fn=cmd_evidence)
    s = sub.add_parser("record-red", help="run a check that must fail and log it")
    s.add_argument("row")
    s.add_argument("command")
    s.set_defaults(fn=cmd_record_red)
    s = sub.add_parser("model-check", help="run TLC on a .tla spec and write a log")
    s.add_argument("spec")
    s.add_argument("--config")
    s.add_argument("--expect-violation", metavar="PROPERTY", help="pass only if TLC reports PROPERTY violated")
    s.set_defaults(fn=cmd_model_check)
    s = sub.add_parser("detect")
    s.add_argument("dir", nargs="?", default=".")
    s.set_defaults(fn=cmd_detect)
    args = p.parse_args(argv)
    rc: int = args.fn(args)
    return rc


if __name__ == "__main__":
    sys.exit(main())
