"""Rules-version drift, and the scope guard it must NOT inherit (v1.32.0, B41).

    python plugins/cairn/tools/test_version_drift.py

WHAT IS ACTUALLY WORTH PROTECTING HERE. The comparison itself is one `!=`. Two properties around
it are the reason B41 existed at all, and both are invisible from the outside:

  1. THE RULES CHECK IS NOT SCOPE-GUARDED. Repo-vs-installed needs `plugins/cairn/.claude-plugin/
     plugin.json` and so is correctly silent outside `agent-reentry`. Installed-vs-rules needs no
     repo, and the rules it is about are loaded in EVERY project — so if a later session "tidies"
     the two checks under one guard, the warning vanishes from the fifteen repos where it matters
     and stays only in the one where it doesn't. That reads as working.

  2. "NO MARKER" IS NOT "UP TO DATE". A `~/.claude/CLAUDE.md` that has never been installed into
     must not compare equal to one that is current. This is the B30/B35/B37 family — an absent
     record reported identically to a satisfied one — and this module is not going to be a fourth
     instance.

WHY THERE IS NO END-TO-END *STALE* TEST. `session_orientation.py` calls `install_rules.install()`
before it calls `version_drift.check()`, so on any healthy machine the two numbers already agree by
the time the check runs. That is by design: a mismatch means the install did not happen or did not
stick. Staging that end-to-end would mean sabotaging the installer, which tests the sabotage rather
than the check. So the branches are unit-tested against a temp config dir, and the end-to-end test
asserts the property that a bug would actually break — that a healthy machine stays SILENT.

Nothing here touches the network, `~/.claude`, or any file in the repo: every case runs against a
throwaway `CLAUDE_CONFIG_DIR`.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).resolve().parent.parent).resolve()
HOOKS = ROOT / "hooks"
sys.path.insert(0, str(HOOKS))

import version_drift as vd                               # noqa: E402

NW = {"creationflags": 0x08000000} if os.name == "nt" else {}

fails = []


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  got={got!r} want={want!r}"))


def contains(label, got, needle):
    ok = needle in (got or "")
    if not ok:
        fails.append(label)
    print(f"   {'ok  ' if ok else 'FAIL'} {label}" + ("" if ok else f"  {needle!r} not in {got!r}"))


def silent(label, got):
    check(label, got, None)


def stage(tmp: Path, installed: str | None, claude_md: str | None) -> Path:
    """A throwaway CLAUDE_CONFIG_DIR with the two files the checks read."""
    config = tmp / ".claude"
    (config / "plugins").mkdir(parents=True, exist_ok=True)
    if installed is not None:
        (config / "plugins" / "installed_plugins.json").write_text(json.dumps(
            {"plugins": {"cairn@superbole": [{"version": installed}]}}), encoding="utf-8")
    if claude_md is not None:
        (config / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
    os.environ["CLAUDE_CONFIG_DIR"] = str(config)
    return config


BLOCK = ("<!-- reentry:begin v{v} — managed by the reentry plugin. -->\n"
         "some rules\n<!-- reentry:end -->\n")


def main() -> int:
    original = os.environ.get("CLAUDE_CONFIG_DIR")
    try:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)

            print("\nrules_state() — three states, never two")
            stage(tmp / "a", "1.31.0", BLOCK.format(v="1.31.0"))
            check("marker present -> ('ok', version)", vd.rules_state(), ("ok", "1.31.0"))
            stage(tmp / "b", "1.31.0", "hand-written notes, no plugin block\n")
            check("no marker -> ('no-marker', None)", vd.rules_state(), ("no-marker", None))
            stage(tmp / "c", "1.31.0", None)
            check("no file -> ('missing', None)", vd.rules_state(), ("missing", None))

            print("\nthe rules check — a mismatch is reported, agreement is silent")
            stage(tmp / "d", "1.32.0", BLOCK.format(v="1.32.0"))
            silent("installed == rules -> silent", vd._rules_drift("1.32.0"))
            stage(tmp / "e", "1.32.0", BLOCK.format(v="1.31.0"))
            contains("installed > rules -> names both", vd._rules_drift("1.32.0"), "v1.31.0")
            contains("...and says NEW code, OLD rules", vd._rules_drift("1.32.0"), "OLD rules")

            print("\nB66: rules NEWER than installed -- the plugin is the old side, a restart will")
            print("     NOT resync (D33/B63 keep-newer). Opposite wording from the case just above.")
            stage(tmp / "e2", "1.31.0", BLOCK.format(v="1.32.0"))
            newer_msg = vd._rules_drift("1.31.0")
            contains("names both versions", newer_msg, "v1.32.0")
            contains("names both versions", newer_msg, "v1.31.0")
            contains("says NEWER than the installed plugin", newer_msg, "NEWER than the installed")
            contains("says a restart will NOT resync", newer_msg, "will NOT resync")
            contains("names the marketplace-then-plugin remedy",
                     newer_msg, "claude plugin marketplace update superbole")
            contains("names the plugin-update remedy", newer_msg, "claude plugin update cairn@superbole")
            check("does NOT use the other direction's wording (OLD rules)",
                  "OLD rules" in newer_msg, False)

            print("\nB66: an installed version that does not parse is NO EVIDENCE of direction --")
            print("     must fall through to the older, direction-agnostic wording, never the NEWER")
            print("     branch on a guess.")
            stage(tmp / "e3", None, BLOCK.format(v="1.32.0"))
            unparseable_msg = vd._rules_drift("weird-1.2.3")
            contains("falls through to the OLD-rules default wording", unparseable_msg, "OLD rules")
            check("does NOT land in the NEWER branch", "NEWER than the installed" in unparseable_msg, False)

            print("\nB66: equal versions stay silent (unchanged by the new branch)")
            stage(tmp / "e4", "1.32.0", BLOCK.format(v="1.32.0"))
            silent("installed == rules -> still silent", vd._rules_drift("1.32.0"))

            print("\nan absent record must not read as a satisfied one (B30/B35/B37 family)")
            stage(tmp / "f", "1.32.0", "no block here\n")
            contains("no marker -> warns", vd._rules_drift("1.32.0"), "never installed")
            check("...and is NOT the equal-version silence", vd._rules_drift("1.32.0") is None, False)
            stage(tmp / "g", "1.32.0", None)
            contains("no file -> warns", vd._rules_drift("1.32.0"), "could not be read")

            print("\nnothing to compare against is silence, not a manufactured warning")
            stage(tmp / "h", None, BLOCK.format(v="1.31.0"))
            silent("no installed version -> silent", vd._rules_drift(None))

            print("\nSCOPE: the rules check fires OUTSIDE agent-reentry; the repo check does not")
            stage(tmp / "i", "1.32.0", BLOCK.format(v="1.31.0"))
            not_a_plugin_repo = tmp / "some-other-project"
            not_a_plugin_repo.mkdir(parents=True, exist_ok=True)
            out = vd.check(not_a_plugin_repo)
            contains("rules warning present in a foreign repo", out, "OLD rules")
            check("repo warning absent there", "plugin.json is v" in (out or ""), False)

            print("\nB97: installed vs the marketplace clone on disk (no network)")
            day = 86400
            now = 1_800_000_000.0

            def clone(config: Path, version: str | None, fetched_days_ago: float | None = 0,
                      logs_days_ago: float | None = None, marketplace: str = "superbole",
                      source: str | None = "./plugins/cairn") -> Path:
                root = config / "plugins" / "marketplaces" / marketplace
                (root / ".git" / "logs").mkdir(parents=True, exist_ok=True)
                if source is not None:
                    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
                    (root / ".claude-plugin" / "marketplace.json").write_text(json.dumps(
                        {"name": marketplace, "plugins": [{"name": "cairn", "source": source}]}),
                        encoding="utf-8")
                if version is not None:
                    rel = (source or "./plugins/cairn")
                    manifest = root / rel / ".claude-plugin" / "plugin.json"
                    manifest.parent.mkdir(parents=True, exist_ok=True)
                    manifest.write_text(json.dumps({"name": "cairn", "version": version}),
                                        encoding="utf-8")
                for rel, ago in (("FETCH_HEAD", fetched_days_ago), ("logs/HEAD", logs_days_ago)):
                    if ago is not None:
                        p = root / ".git" / rel
                        p.write_text("x\n", encoding="utf-8")
                        os.utime(p, (now - ago * day, now - ago * day))
                return root

            cfg = stage(tmp / "m1", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.66.0", fetched_days_ago=1)
            check("same version, fetched yesterday -> silent",
                  vd._marketplace_drift("superbole", "1.66.0", now), [])

            cfg = stage(tmp / "m2", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.67.0", fetched_days_ago=1)
            found = vd._marketplace_drift("superbole", "1.66.0", now)
            check("clone NEWER than installed -> exactly one finding", len(found), 1)
            contains("...names the installed version", found[0] if found else "", "v1.66.0")
            contains("...names the published version", found[0] if found else "", "v1.67.0")
            contains("...names the update command for THAT marketplace", found[0] if found else "",
                     "claude plugin update cairn@superbole")

            cfg = stage(tmp / "m3", "1.67.0", BLOCK.format(v="1.67.0"))
            clone(cfg, "1.66.0", fetched_days_ago=1)
            check("installed NEWER than clone -> silent (a stale clone, the fetch check's job)",
                  vd._marketplace_drift("superbole", "1.67.0", now), [])

            cfg = stage(tmp / "m4", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.67.0-rc1", fetched_days_ago=1)
            check("a version that does not parse -> silent, never a guessed direction",
                  vd._marketplace_drift("superbole", "1.66.0", now), [])

            stage(tmp / "m5", "1.66.0", BLOCK.format(v="1.66.0"))
            check("no marketplace clone at all -> silent",
                  vd._marketplace_drift("superbole", "1.66.0", now), [])
            check("no marketplace name -> silent", vd._marketplace_drift(None, "1.66.0", now), [])
            check("a marketplace name with a path separator -> silent",
                  vd._marketplace_drift("../x", "1.66.0", now), [])
            check("no installed version -> silent", vd._marketplace_drift("superbole", None, now), [])

            cfg = stage(tmp / "m6", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.66.0", fetched_days_ago=10)
            found = vd._marketplace_drift("superbole", "1.66.0", now)
            check("fetched 10 days ago -> one stale-clone finding", len(found), 1)
            contains("...says how many days", found[0] if found else "", "10 days ago")
            contains("...names the marketplace refresh", found[0] if found else "",
                     "claude plugin marketplace update superbole")

            cfg = stage(tmp / "m7", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.66.0", fetched_days_ago=vd.STALE_FETCH_DAYS - 0.5)
            check("just under the threshold -> silent",
                  vd._marketplace_drift("superbole", "1.66.0", now), [])

            cfg = stage(tmp / "m8", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.66.0", fetched_days_ago=None, logs_days_ago=2)
            check("fresh clone with no FETCH_HEAD: reflog mtime counts -> silent",
                  vd._marketplace_drift("superbole", "1.66.0", now), [])
            cfg = stage(tmp / "m9", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.66.0", fetched_days_ago=30, logs_days_ago=1)
            check("the NEWER of FETCH_HEAD and the reflog wins -> silent",
                  vd._marketplace_drift("superbole", "1.66.0", now), [])
            cfg = stage(tmp / "m10", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.66.0", fetched_days_ago=None, logs_days_ago=None)
            check("neither file -> no fetch time -> silent",
                  vd._marketplace_drift("superbole", "1.66.0", now), [])

            cfg = stage(tmp / "m11", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.67.0", fetched_days_ago=12)
            check("newer AND stale -> both findings",
                  len(vd._marketplace_drift("superbole", "1.66.0", now)), 2)

            cfg = stage(tmp / "m12", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.67.0", fetched_days_ago=1, source="./elsewhere/cairn")
            contains("the plugin path comes from the clone's marketplace.json",
                     " ".join(vd._marketplace_drift("superbole", "1.66.0", now)), "v1.67.0")
            cfg = stage(tmp / "m13", "1.66.0", BLOCK.format(v="1.66.0"))
            clone(cfg, "1.67.0", fetched_days_ago=1, source=None)
            contains("no marketplace.json -> falls back to plugins/cairn",
                     " ".join(vd._marketplace_drift("superbole", "1.66.0", now)), "v1.67.0")
            cfg = stage(tmp / "m14", "1.66.0", BLOCK.format(v="1.66.0"))
            outside = cfg / "plugins" / "marketplaces" / "evil-target"
            (outside / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (outside / ".claude-plugin" / "plugin.json").write_text(
                json.dumps({"version": "9.9.9"}), encoding="utf-8")
            clone(cfg, None, fetched_days_ago=1, source="../evil-target")
            check("a source that climbs out of the clone is ignored -> silent",
                  vd._marketplace_drift("superbole", "1.66.0", now), [])

            print("\nB97: the marketplace name is read from the installed `cairn@<name>` key")
            cfg = stage(tmp / "m15", None, BLOCK.format(v="1.66.0"))
            (cfg / "plugins" / "installed_plugins.json").write_text(json.dumps(
                {"plugins": {"cairn@other-mkt": [{"version": "1.66.0"}]}}), encoding="utf-8")
            check("_installed_entry() -> (marketplace, version)", vd._installed_entry(),
                  ("other-mkt", "1.66.0"))
            check("_installed_version() unchanged", vd._installed_version(), "1.66.0")
            clone(cfg, "1.70.0", fetched_days_ago=0, marketplace="other-mkt")
            out = vd.check(tmp / "some-other-project")
            contains("check() reports it OUTSIDE the plugin repo (not scope-guarded)", out,
                     "cairn@other-mkt")
            check("...and the rules check stays silent alongside it", "OLD rules" in (out or ""),
                  False)

            print("\nEND-TO-END: a healthy machine stays silent")
            stage(tmp / "j", "1.31.0", BLOCK.format(v="1.31.0"))
            healthy = vd.check(tmp / "some-other-project")
            silent("all three agree -> check() returns None", healthy)

            repo = tmp / "repo"
            (repo / ".claude").mkdir(parents=True, exist_ok=True)
            (repo / "NEXT.md").write_text("# NEXT\n\n## Queue\n\n## Watching\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=repo, **NW)

            def run_hook() -> str:
                env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
                return subprocess.run(
                    [sys.executable, str(HOOKS / "session_orientation.py")],
                    cwd=repo, env=env, capture_output=True, text=True, **NW).stdout

            # The hook calls install_rules FIRST, and that writes THIS checkout's rules into the
            # staged config dir. So "healthy" means the staged installed version equals the version
            # about to be installed -- READ IT, never hardcode it. The first cut of this test staged
            # a literal "1.31.0" and passed; the very next commit bumped to 1.32.0 and it started
            # asserting that a genuine mismatch was healthy.
            live = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8"))["version"]

            stage(tmp / "k", live, BLOCK.format(v=live))
            check("real hook: silent when installed matches what installs",
                  "OLD rules" in run_hook(), False)

            # install_rules runs FIRST and upgrades the staged v0.0.1 block to `live` (0.0.1 is
            # older, so that is an ordinary write, not the B63 keep-newer refusal) -- so by the time
            # version_drift looks, the staged installed_plugins.json is still "0.0.1" but the rules
            # block it reads is now `live`. That is the RULES-NEWER shape (B66), not "OLD rules".
            stage(tmp / "l", "0.0.1", BLOCK.format(v="0.0.1"))
            contains("real hook: warns when they diverge", run_hook(), "NEWER than the installed")
    finally:
        if original is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = original

    print()
    if fails:
        print(f"{len(fails)} FAILED: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
