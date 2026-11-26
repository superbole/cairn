#!/usr/bin/env python3
"""Move accepted review dossiers to `docs/review/archive/` and repoint every link to them.

    python plugins/cairn/tools/archive_reviews.py                  # dry run, the default
    python plugins/cairn/tools/archive_reviews.py --apply
    python plugins/cairn/tools/archive_reviews.py --accepted SHA [SHA ...] [--apply]
    (--root DIR to point at another checkout; default is the current directory's repo)

WHY (B51). `docs/review/` is an inbox (`docs/running-a-batch.md`). Moving a dossier by hand
means repointing the queue, backlog, changelog, docs and incident logs in the same commit; a
missed one is a dangling pointer made by hand.

ACCEPTED means, never mtimes: with no `--accepted`, HEAD must be 0 commits ahead of `--upstream`
(default `origin/main`) and every committed dossier is accepted. With `--accepted`, only a
dossier whose LAST commit is one of those shas (a merge counts for what it brought in against
its first parent). Either way an untracked or locally modified dossier stays.

Pointers are rewritten in every tracked or untracked-not-ignored UTF-8 file: the literal
`docs/review/<name>`, plus relative markdown links `](...)` in `.md` files (including the moved
dossiers' own links, which are one directory deeper afterwards). What still resolves to nothing
is REPORTED, never guessed at. `test_*.py` files are skipped both ways: the paths in them are
fixtures, not pointers. Does not commit.
"""
import argparse
import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path

INBOX = "docs/review"
ARCHIVE = INBOX + "/archive"
REFERENCE = {"readme.md", "user-guide.md"}      # standing references, not one run's dossier
PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{4}-")
DATE = re.compile(r"-?(\d{4}-\d{2}-\d{2})-?")
LINK = re.compile(r"(\]\()([^)\s]+)")
# Stops at whitespace and the punctuation that closes a pointer in prose or markdown.
MENTION = re.compile(r"docs/review/[^\s`'\"()\[\]<>|;:#]*")


class Refused(Exception):
    pass


def git(root, *args):
    p = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=false", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if p.returncode:
        raise Refused(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def listed(root, *args):
    return [f for f in git(root, "ls-files", "-z", *args).split("\0") if f]


def accepted_dossiers(root, shas, upstream):
    """(accepted paths, [(path, why it stays)])."""
    if shas:
        full = {git(root, "rev-parse", "--verify", s + "^{commit}").strip() for s in shas}
        brought = set()
        for s in full:
            brought |= set(git(root, "show", "--pretty=format:", "--name-only", "--no-renames",
                               "--diff-merges=first-parent", s).split("\n"))
    else:
        ahead = int(git(root, "rev-list", "--count", f"{upstream}..HEAD").strip())
        if ahead:
            raise Refused(f"HEAD is {ahead} commit(s) ahead of {upstream}: nothing is accepted "
                          f"until it is pushed. Push first, or name shas with --accepted.")
    dirty = set(git(root, "diff", "--name-only", "--no-renames", "HEAD").split("\n"))
    tracked = set(listed(root, "--", INBOX))
    yes, no = [], []
    on_disk = sorted(p.name for p in (root / INBOX).glob("*.md") if p.is_file())
    for name in on_disk:
        path = f"{INBOX}/{name}"
        if name.lower() in REFERENCE:
            no.append((path, "standing reference"))
        elif path not in tracked:
            no.append((path, "untracked"))
        elif path in dirty:
            no.append((path, "uncommitted changes"))
        elif shas and not (
                git(root, "log", "-1", "--format=%H", "--", path).strip() in full
                # `log` names the branch commit, not the merge that brought it in.
                or (path in brought and any(
                    not git(root, "diff", "--name-only", s, "HEAD", "--", path).strip()
                    for s in full))):
            no.append((path, "last change is not in the accepted shas"))
        else:
            yes.append(path)
    return yes, no


def archived_name(root, path):
    """Keep a `YYYY-MM-DD-HHMM-` prefix, else derive it from the commit that added the file."""
    name = posixpath.basename(path)
    if PREFIX.match(name):
        return name
    # ponytail: HHMM is the first commit's time, not the run's start (git does not record that).
    added = git(root, "log", "--diff-filter=A", "--format=%ad",
                "--date=format:%Y-%m-%d %H%M", "--", path).split("\n")
    added = [a for a in added if a]
    if not added:
        raise Refused(f"{path}: no commit adds it, so no prefix can be derived")
    day, hhmm = added[-1].split()
    stem = name[:-len(".md")]
    m = DATE.search(stem)
    if m:                                       # a date already in the name beats the commit's
        day = m.group(1)
        stem = "-".join(x for x in (stem[:m.start()], stem[m.end():]) if x)
    return f"{day}-{hhmm}-{stem or 'dossier'}.md"


def plan(root, shas=None, upstream="origin/main"):
    """(moves {old: new}, kept, edits {new-path: (text, count)}, dangling lines)."""
    yes, kept = accepted_dossiers(root, shas, upstream)
    moves = {p: f"{ARCHIVE}/{archived_name(root, p)}" for p in yes}
    targets = list(moves.values())
    for new in targets:
        if targets.count(new) > 1 or (root / new).exists():
            raise Refused(f"{new} would be overwritten; rename one of the dossiers first")

    files = sorted(set(listed(root, "--cached", "--others", "--exclude-standard")))
    after = {moves.get(f, f) for f in files if (root / f).is_file()}
    after_dirs = {posixpath.dirname(f) for f in after}

    def exists(rel):
        return rel in after or rel in after_dirs or (
            rel not in moves and (root / rel).exists())

    edits, dangling = {}, []
    for old in files:
        if not (root / old).is_file() or re.fullmatch(r"test_.*\.py", posixpath.basename(old)):
            continue
        try:
            text = (root / old).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        new = moves.get(old, old)
        count = 0

        def relink(m):
            nonlocal count
            target, hash_, frag = m.group(2).partition("#")
            if not target or target.startswith("/") or re.match(r"[a-z][a-z0-9+.-]*:", target, re.I):
                return m.group(0)
            was = posixpath.normpath(posixpath.join(posixpath.dirname(old), target))
            now = moves.get(was, was)
            if old not in moves and was not in moves:
                if was.startswith(INBOX + "/") and not exists(was):
                    dangling.append(f"{new}: link ({target}) points at nothing")
                return m.group(0)
            if not exists(now):
                dangling.append(f"{new}: link ({target}) points at nothing")
                return m.group(0)
            if posixpath.normpath(posixpath.join(posixpath.dirname(new), target)) == now:
                return m.group(0)
            count += 1
            return m.group(1) + posixpath.relpath(now, posixpath.dirname(new) or ".") + hash_ + frag

        out = LINK.sub(relink, text) if old.endswith(".md") else text
        for src, dst in moves.items():
            out, n = re.subn(re.escape(src) + r"(?![\w-])", lambda _: dst, out)
            count += n
        if count:
            edits[new] = (out, count)

        renamed = {posixpath.basename(s): posixpath.basename(d) for s, d in moves.items()
                   if posixpath.basename(s) != posixpath.basename(d)}
        for i, line in enumerate(out.split("\n"), 1):
            for m in MENTION.finditer(line):
                if line[m.end():m.end() + 1] == "<" or m.group(0).endswith("*"):
                    continue                    # a placeholder or a glob, not a pointer
                ref = m.group(0).rstrip(".,!?")
                if ref.rstrip("/") not in (INBOX, ARCHIVE) and not exists(ref):
                    dangling.append(f"{new}:{i}: {ref}")
            for was, now in renamed.items():
                # the old bare name, not as the tail of a longer name or of a path
                if re.search(r"(?<![\w/-])" + re.escape(was) + r"(?![\w-])", line) \
                        and f"]({was}" not in line:
                    dangling.append(f"{new}:{i}: bare old name {was} (now {now})")
    return moves, kept, edits, dangling


def apply(root, moves, edits):
    if moves:
        (root / ARCHIVE).mkdir(parents=True, exist_ok=True)
    for old, new in moves.items():
        git(root, "mv", "--", old, new)
    for path, (text, _) in edits.items():
        (root / path).write_bytes(text.encode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--upstream", default="origin/main")
    ap.add_argument("--accepted", nargs="+", metavar="SHA")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true", help="the default")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        root = Path(git(a.root, "rev-parse", "--show-toplevel").strip())
        moves, kept, edits, dangling = plan(root, a.accepted, a.upstream)
        if a.apply:
            apply(root, moves, edits)
    except Refused as e:
        print(f"archive_reviews: refused - {e}", file=sys.stderr)
        return 1
    print(f"{'moved' if a.apply else 'would move'}: {len(moves)} dossier(s)")
    for old, new in moves.items():
        print(f"  {old} -> {new}")
    for path, why in kept:
        print(f"  stays: {path} ({why})")
    print(f"{'repointed' if a.apply else 'would repoint'}: "
          f"{sum(n for _, n in edits.values())} pointer(s) in {len(edits)} file(s)")
    for path, (_, n) in sorted(edits.items()):
        print(f"  {path}: {n}")
    print(f"pointing at nothing, fix by hand: {len(dangling)}")
    for line in dangling:
        print(f"  {line}")
    if not a.apply:
        print("dry run: nothing changed. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
