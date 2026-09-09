"""Coverage for `ensure_profile_file.py` (B12) — the seed, and all four `REENTRY_PROFILE_SOURCE` states.

    python plugins/cairn/tools/test_ensure_profile_file.py

WHY THIS EXISTS. `ensure_profile_file.py` is the half of B12 that carries the PERSON out of the
shipped payload and into `~/.claude/reentry-profile.md`. Two of its properties are load-bearing
and neither is visible from a single run:

  1. IT MUST NEVER EAT A PROFILE. The file holds text the user wrote by hand, in their own words,
     that nothing else on the machine has a copy of. Every path that overwrites it backs it up
     first, and the no-source path never overwrites at all.
  2. IT MUST BE SILENT IN THE STEADY STATE. `install_rules.py`'s own docstring records the bug
     class: a naive read-back that never equals what was written makes an installer rewrite on
     EVERY session start, churning a backup each time. Caught there by testing the SECOND run
     rather than the first — so every case here runs twice and pins the second run's silence.

THE ORDERING THIS DOES NOT TEST. `install_rules.install()` calls `ensure()` before writing the
managed block, so the `@~/.claude/reentry-profile.md` import is never written in a run where the
target does not exist. That is pinned in section 5 at the seam (the file exists once `install()`
returns), but whether the `@` import actually reaches the model's context is a property of Claude
Code's launch-time CLAUDE.md parse, not of this module — it cannot be observed from a test.

Runs entirely under `tempfile.mkdtemp()` with `CLAUDE_CONFIG_DIR` pointed at it, never the real
`~/.claude/`. `run_tests.py` fails the suite on a leak into the real state dir; this file sets the
override before importing anything that reads it.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

HOOKS = Path(sys.argv[1] if len(sys.argv) > 1
             else Path(__file__).resolve().parent.parent / "hooks").resolve()
sys.path.insert(0, str(HOOKS))

import ensure_profile_file                              # noqa: E402
import install_rules                                    # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + label + ("" if ok else f"   got={got!r} want={want!r}"))
    if not ok:
        fails.append(label)


def sandbox(name):
    """A throwaway config dir, set as CLAUDE_CONFIG_DIR, with no source configured."""
    cfg = Path(tempfile.mkdtemp(prefix="profile-%s-" % name))
    os.environ["CLAUDE_CONFIG_DIR"] = str(cfg)
    os.environ.pop(ensure_profile_file.SOURCE_ENV, None)
    return cfg


def profile(cfg):
    return cfg / ensure_profile_file.FILENAME


def write(path, text, *, age=0.0):
    """Write `text`, optionally back-dating the mtime so 'newer' is unambiguous on a fast disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    if age:
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))


print("1. No source configured — seed once, then never touch it again")
cfg = sandbox("seed")
line = ensure_profile_file.ensure()
check("first run reports", bool(line and "TEMPLATE" in line), True)
check("file created", profile(cfg).is_file(), True)
check("seeded with the template", profile(cfg).read_text(encoding="utf-8"),
      ensure_profile_file.TEMPLATE)
check("template names the source env var",
      ensure_profile_file.SOURCE_ENV in ensure_profile_file.TEMPLATE, True)
check("second run is silent", ensure_profile_file.ensure(), None)

print("\n2. No source, hand-edited profile — the user's words are never overwritten")
marker = "MY OWN WORDS, written by hand, that nothing else has a copy of.\n"
write(profile(cfg), marker)
check("run is silent", ensure_profile_file.ensure(), None)
check("hand-written content survives", profile(cfg).read_text(encoding="utf-8"), marker)
check("no backup churned", (cfg / (ensure_profile_file.FILENAME + ".bak-reentry-profile")).exists(),
      False)

print("\n3. Source configured")
cfg = sandbox("source")
src = Path(tempfile.mkdtemp(prefix="profile-src-")) / "profile.md"

print("   3a. source set but missing — falls back to seeding, never an error")
os.environ[ensure_profile_file.SOURCE_ENV] = str(src)
line = ensure_profile_file.ensure()
check("seeded the template instead", profile(cfg).read_text(encoding="utf-8"),
      ensure_profile_file.TEMPLATE)
check("reported as a creation, not a failure", bool(line and "TEMPLATE" in line), True)
check("second run silent", ensure_profile_file.ensure(), None)

print("   3b. source newer than target — copied, previous content backed up")
write(profile(cfg), "OLD local copy\n", age=600)
write(src, "NEW from the source repo\n")
line = ensure_profile_file.ensure()
check("reports a refresh", bool(line and "Refreshed" in line), True)
check("target now matches source", profile(cfg).read_text(encoding="utf-8"),
      "NEW from the source repo\n")
check("previous content backed up beside it",
      (cfg / (ensure_profile_file.FILENAME + ".bak-reentry-profile")).read_text(encoding="utf-8"),
      "OLD local copy\n")
check("second run silent (copy2 preserved mtime)", ensure_profile_file.ensure(), None)

print("   3c. source OLDER than target — a local edit wins until the source itself changes")
write(src, "STALE source\n", age=600)
write(profile(cfg), "local edit made after the last sync\n")
check("run is silent", ensure_profile_file.ensure(), None)
check("local edit survives", profile(cfg).read_text(encoding="utf-8"),
      "local edit made after the last sync\n")

print("   3d. source newer but IDENTICAL — no backup churn (the install_rules bug class)")
same = "identical on both sides\n"
write(profile(cfg), same, age=600)
write(src, same)
backup = cfg / (ensure_profile_file.FILENAME + ".bak-reentry-profile")
before = backup.read_text(encoding="utf-8") if backup.exists() else None
check("run is silent", ensure_profile_file.ensure(), None)
after = backup.read_text(encoding="utf-8") if backup.exists() else None
check("backup untouched", after, before)

print("   3e. an UNTOUCHED TEMPLATE loses to an older source — the install-first ordering trap")
# Install the plugin, THEN set the source: the template is written now, the source in a repo was
# edited earlier, so a pure mtime test keeps the template forever and the real profile never lands.
write(profile(cfg), ensure_profile_file.TEMPLATE)          # seeded now = newest thing on disk
write(src, "the real profile, edited yesterday\n", age=86400)
line = ensure_profile_file.ensure()
check("older source still replaces the template", profile(cfg).read_text(encoding="utf-8"),
      "the real profile, edited yesterday\n")
check("reported", bool(line and "Refreshed" in line), True)
write(profile(cfg), "a REAL local edit, made just now\n")
write(src, "still yesterday's source\n", age=86400)
check("but a real local edit still wins over an older source",
      ensure_profile_file.ensure(), None)
check("the local edit survives", profile(cfg).read_text(encoding="utf-8"),
      "a REAL local edit, made just now\n")

print("   3f. CRLF on one side only is not a content change")
write(profile(cfg), "line one\nline two\n", age=600)
src.write_bytes(b"line one\r\nline two\r\n")
check("run is silent", ensure_profile_file.ensure(), None)

print("\n3g. B103 — a source that resolves INSIDE the current project is refused")
cfg = sandbox("contain")
project = Path(tempfile.mkdtemp(prefix="profile-project-"))
(project / ".git").mkdir()                              # a real repo, so toplevel() matches it
inside_src = project / "profile.md"
write(inside_src, "a HOSTILE profile checked in by the repo itself\n")
os.environ[ensure_profile_file.SOURCE_ENV] = str(inside_src)
line = ensure_profile_file.ensure(project_root=project)
check("refused, not copied", bool(line and "Refused" in line), True)
check("refusal names the project", bool(line and str(project) in line), True)
check("nothing written — seeds the template instead", profile(cfg).read_text(encoding="utf-8"),
      ensure_profile_file.TEMPLATE)

print("   3h. same, but the source path is RELATIVE (the cheaper form B103's dossier found)")
cfg = sandbox("contain-rel")
cwd_before = Path.cwd()
os.chdir(project)
try:
    os.environ[ensure_profile_file.SOURCE_ENV] = "profile.md"
    line = ensure_profile_file.ensure(project_root=project)
finally:
    os.chdir(cwd_before)
check("refused for being relative", bool(line and "Refused" in line), True)
check("nothing written — seeds the template instead", profile(cfg).read_text(encoding="utf-8"),
      ensure_profile_file.TEMPLATE)

print("   3i. a source OUTSIDE the project still copies normally")
cfg = sandbox("contain-outside")
outside_src = Path(tempfile.mkdtemp(prefix="profile-outside-")) / "profile.md"
write(outside_src, "a legitimate cross-machine profile\n")
os.environ[ensure_profile_file.SOURCE_ENV] = str(outside_src)
line = ensure_profile_file.ensure(project_root=project)
check("installed, not refused", bool(line and "Installed" in line), True)
check("content copied", profile(cfg).read_text(encoding="utf-8"), "a legitimate cross-machine profile\n")

print("   3j. no project_root passed — containment check is skipped, absolute source still copies")
cfg = sandbox("contain-noroot")
os.environ[ensure_profile_file.SOURCE_ENV] = str(outside_src)
line = ensure_profile_file.ensure()
check("installed with no project_root given", bool(line and "Installed" in line), True)

print("\n4. Never fails the session")
cfg = sandbox("robust")
os.environ[ensure_profile_file.SOURCE_ENV] = str(cfg)        # a DIRECTORY, not a file
check("a directory as the source is ignored, not raised",
      bool(ensure_profile_file.ensure()), True)              # falls through to seeding
os.environ[ensure_profile_file.SOURCE_ENV] = ""
check("empty source var behaves as unset", ensure_profile_file.ensure(), None)

print("\n5. install_rules writes the import only once the profile exists")
cfg = sandbox("ordering")
report, in_context = install_rules.install()
check("profile exists after install()", profile(cfg).is_file(), True)
check("import line written into the block",
      install_rules.PROFILE_IMPORT in (cfg / "CLAUDE.md").read_text(encoding="utf-8"), True)
check("import target resolves to a real file", profile(cfg).is_file(), True)
check("first install is not in context", in_context, False)
check("first install reports both layers",
      bool(report and "reentry-profile.md" in report and "CLAUDE.md" in report), True)
report2, in_context2 = install_rules.install()
check("second install is silent", report2, None)
check("second install IS in context", in_context2, True)

print()
if fails:
    print(f"FAILED: {fails}")
    sys.exit(1)
print("ALL PASS")
