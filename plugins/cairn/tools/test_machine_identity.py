"""Machine identity, and the silence it must not break (v1.31.0).

    python plugins/cairn/tools/test_machine_identity.py

WHY THIS IS A TEST AND NOT A CODE REVIEW. `machine_identity.check()` itself is four lines and
obvious. The thing worth protecting is the CALL SITE: the line is printed only on the path that
already prints a queue, so a project with no `NEXT.md` stays bit-for-bit silent. That property is
what makes the SessionStart hook safe to run in every repo, and it is invisible from the outside --
a hook that prints one extra line in a thousand unrelated repos looks exactly like a hook that
works. A later session tempted to "tidy" the print into the `always_on` cluster's silence branch
(`session_orientation.py`, the `if always_on or _installed ...` early return) breaks it silently.

So: the resolver is tested directly, and the silence is tested end-to-end by running the real hook
in a throwaway repo with no `NEXT.md` and asserting on EMPTY STDOUT.

Nothing here touches the network or any file in the repo.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))

import machine_identity as mi                            # noqa: E402

NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


print("\n1. the resolver")

real_node = mi.platform.node
try:
    mi.platform.node = lambda: "ORG-LAPTOP2"
    check("a normal hostname becomes one line", mi.check(), "machine: ORG-LAPTOP2")

    mi.platform.node = lambda: "WORKSTATION"
    check("the personal machine's real hostname", mi.check(), "machine: WORKSTATION")

    # The hostname is passed through VERBATIM -- no id lookup, no normalisation, no interpretation.
    # Asserted so nobody "improves" check() into resolving ids: comparing an annotation against the
    # host is a separate item, and its hard part is the silence boundary, not the string match.
    check("passed through verbatim", mi.check(), "machine: " + "WORKSTATION")

    mi.platform.node = lambda: "  padded-host  "
    check("whitespace is stripped", mi.check(), "machine: padded-host")

    mi.platform.node = lambda: ""
    check("an empty hostname is silence, not 'machine: '", mi.check(), None)

    mi.platform.node = lambda: "   "
    check("a whitespace-only hostname is silence", mi.check(), None)

    def _boom():
        raise OSError("no hostname on this platform")

    mi.platform.node = _boom
    check("a raising platform.node is silence", mi.check(), None)
finally:
    mi.platform.node = real_node

print("\n2. it resolves something real on this machine")
line = mi.check()
check("returns a line here", isinstance(line, str) and line.startswith("machine: "), True)
print(f"        (this machine: {line})")


print("\n3. the silence a project with no NEXT.md must keep")

tmp = Path(tempfile.mkdtemp(prefix="machine-id-"))
repo = tmp / "plain-repo"
repo.mkdir()
subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True, **NW)
(repo / "README.md").write_text("# no NEXT.md here\n", encoding="utf-8")

env = dict(os.environ)
env["CLAUDE_PROJECT_DIR"] = str(repo)
env["CLAUDE_CONFIG_DIR"] = str(tmp / "cfg")

# First run is discarded: install_rules and ensure_mistakes_file legitimately report once into a
# fresh config dir. The SECOND run is the steady state, and the steady state must be empty.
for _ in range(2):
    done = subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                          input='{"source":"startup"}', capture_output=True, text=True,
                          env=env, cwd=str(repo), **NW)

check("exits 0", done.returncode, 0)
check("stdout is EMPTY in a repo with no NEXT.md", done.stdout, "")
if done.stdout:
    print("        leaked: %r" % done.stdout[:400])

print("\n4. and it DOES print where there is a queue")

queued = tmp / "queued-repo"
queued.mkdir()
subprocess.run(["git", "init", "-q"], cwd=str(queued), capture_output=True, **NW)
(queued / "NEXT.md").write_text(
    "# NEXT — test\n\n## Queue\n\n"
    "1. **Something to do** — Sonnet 5 · medium · AFK/Auto\n\n"
    "## Watching\n\n---\n\nAim: prove the machine line reaches a real queue.\n",
    encoding="utf-8")

env["CLAUDE_PROJECT_DIR"] = str(queued)
done2 = subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                       input='{"source":"startup"}', capture_output=True, text=True,
                       env=env, cwd=str(queued), **NW)

check("exits 0", done2.returncode, 0)
check("the machine line is present", any(
    ln.startswith("machine: ") for ln in done2.stdout.splitlines()), True)
check("exactly one machine line", sum(
    ln.startswith("machine: ") for ln in done2.stdout.splitlines()), 1)
check("the queue still renders", "Something to do" in done2.stdout, True)

print("\n5. B28 -- the machine mapping file: ensure, parse, resolve")

mtmp = Path(tempfile.mkdtemp(prefix="machines-"))
_saved_cfg = os.environ.get("CLAUDE_CONFIG_DIR")
os.environ["CLAUDE_CONFIG_DIR"] = str(mtmp)
try:
    line = mi.ensure_file()
    check("first call reports creation", isinstance(line, str) and "Created" in line, True)
    check("the file now exists", (mtmp / mi.MACHINES_FILENAME).is_file(), True)
    check("second call is silent", mi.ensure_file(), None)

    check("the SHIPPED template on its own yields an empty table -- the placeholder row must "
          "never read as a known machine",
          mi._load_table(), {})

    (mtmp / mi.MACHINES_FILENAME).write_text(
        "# Machines\n\n| Hostname | Id |\n|---|---|\n"
        "| ORG-LAPTOP1 | LAPTOP1 |\n| ORG-LAPTOP2 | LAPTOP2 |\n| WORKSTATION | WORKSTATION |\n"
        "| `<hostname substring, e.g. ORG-LAPTOP1>` | `<id used in NEXT.md, e.g. LAPTOP1>` |\n",
        encoding="utf-8")
    table = mi._load_table()
    check("real rows parse", table,
          {"org-laptop1": "LAPTOP1", "org-laptop2": "LAPTOP2", "workstation": "WORKSTATION"})
    check("the placeholder row is excluded", len(table), 3)

    check("exact hostname resolves", mi._own_id("ORG-LAPTOP1", table), "LAPTOP1")
    check("case-insensitive", mi._own_id("org-laptop1", table), "LAPTOP1")
    check("a hostname that IS its own id resolves", mi._own_id("WORKSTATION", table),
          "WORKSTATION")
    check("an unrecognised hostname resolves to nothing", mi._own_id("some-other-box", table),
          None)
    check("an empty hostname resolves to nothing", mi._own_id("", table), None)
finally:
    if _saved_cfg is None:
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
    else:
        os.environ["CLAUDE_CONFIG_DIR"] = _saved_cfg


print("\n6. B28 -- mismatch_warning: silence unless BOTH ids are known, and they disagree")

mtmp2 = Path(tempfile.mkdtemp(prefix="machines2-"))
os.environ["CLAUDE_CONFIG_DIR"] = str(mtmp2)
real_node2 = mi.platform.node
try:
    mi.platform.node = lambda: "ORG-LAPTOP1"

    check("no MACHINES.md at all -> silence", mi.mismatch_warning(["**run on LAPTOP2**"]), None)

    (mtmp2 / mi.MACHINES_FILENAME).write_text(
        "| Hostname | Id |\n|---|---|\n| ORG-LAPTOP1 | LAPTOP1 |\n| ORG-LAPTOP2 | LAPTOP2 |\n",
        encoding="utf-8")

    check("no `run on` annotation anywhere -> silence",
          mi.mismatch_warning(["1. **Something** — Sonnet 5 · medium · AFK/Auto"]), None)
    check("a `run on` annotation for THIS machine -> silence",
          mi.mismatch_warning(["1. **Something** — Sonnet 5 · **run on LAPTOP1**"]), None)

    hit = mi.mismatch_warning(["1. **Something** — Sonnet 5 · **run on LAPTOP2**"])
    check("a `run on` annotation for a DIFFERENT known machine fires", hit is not None, True)
    check("it names the mismatched machine", "LAPTOP2" in hit, True)
    check("it names THIS machine too", "LAPTOP1" in hit, True)

    check("an UNKNOWN machine named in the annotation stays silent -- not a guess",
          mi.mismatch_warning(["1. **Something** — Sonnet 5 · **run on BOX9**"]), None)

    mi.platform.node = lambda: "some-unlisted-box"
    check("this machine itself unrecognised in the table -> silence even for a real annotation",
          mi.mismatch_warning(["1. **Something** — Sonnet 5 · **run on LAPTOP2**"]), None)
finally:
    mi.platform.node = real_node2
    if _saved_cfg is None:
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
    else:
        os.environ["CLAUDE_CONFIG_DIR"] = _saved_cfg


print("\n7. end-to-end: the mismatch line reaches a real queue, and a matched item stays quiet")

e2e = Path(tempfile.mkdtemp(prefix="machine-mismatch-e2e-"))
real_host = mi.hostname()
check("this machine has a real hostname to build the fixture on", bool(real_host), True)

cfg = e2e / "cfg"
cfg.mkdir(parents=True, exist_ok=True)
(cfg / mi.MACHINES_FILENAME).write_text(
    "| Hostname | Id |\n|---|---|\n"
    f"| {real_host} | TEST-THIS |\n| some-other-host | TEST-OTHER |\n", encoding="utf-8")

repo2 = e2e / "queued-repo"
repo2.mkdir()
subprocess.run(["git", "init", "-q"], cwd=str(repo2), capture_output=True, **NW)
(repo2 / "NEXT.md").write_text(
    "# NEXT — test\n\n## Queue\n\n"
    "1. **Something to do** — Sonnet 5 · medium · AFK/Auto · **run on TEST-OTHER**\n\n"
    "## Watching\n\n---\n\nAim: test.\n", encoding="utf-8")

env2 = dict(os.environ)
env2["CLAUDE_PROJECT_DIR"] = str(repo2)
env2["CLAUDE_CONFIG_DIR"] = str(cfg)
done3 = subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                       input='{"source":"startup"}', capture_output=True, text=True,
                       env=env2, cwd=str(repo2), **NW)
check("exits 0", done3.returncode, 0)
check("the mismatch line is present", "TEST-OTHER" in done3.stdout, True)
check("it names this machine's own resolved id too", "TEST-THIS" in done3.stdout, True)

(repo2 / "NEXT.md").write_text(
    "# NEXT — test\n\n## Queue\n\n"
    "1. **Something to do** — Sonnet 5 · medium · AFK/Auto · **run on TEST-THIS**\n\n"
    "## Watching\n\n---\n\nAim: test.\n", encoding="utf-8")
done4 = subprocess.run([sys.executable, str(HOOKS / "session_orientation.py")],
                       input='{"source":"startup"}', capture_output=True, text=True,
                       env=env2, cwd=str(repo2), **NW)
check("exits 0", done4.returncode, 0)
check("a correctly-placed item stays silent about a mismatch", "TEST-OTHER" in done4.stdout,
      False)

print("\n%s" % ("ALL PASS" if not fails else "FAILED: %s" % fails))
sys.exit(1 if fails else 0)
