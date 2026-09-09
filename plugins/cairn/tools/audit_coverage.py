#!/usr/bin/env python3
"""Both-ways audit for a trim: prove every rule the OLD file had still exists somewhere.

WHY THIS EXISTS
---------------
Trimming an always-loaded file is the one edit where the failure is invisible. A rewrite that
drops a rule looks *better* than the original — shorter, cleaner, every remaining sentence
correct — and the loss only surfaces months later as an agent doing the thing the deleted rule
forbade. Reading the diff does not catch it either: a diff shows what changed, not whether what
left is recoverable.

So the test is not "is the new file good?" but **"is every sentence of the old file still covered,
here or somewhere an agent will actually reach?"** That is what this script answers. It has been
rebuilt by hand for each trim in this system (`skills/next`, then `rules/CLAUDE.md`); shipping it
stops the next one from re-deriving it, and stops the threshold drifting between trims.

HOW IT WORKS
------------
Split the old file into sentences, reduce each to a keyword set (stopwords dropped), and score it
against every sentence of every target file. The score is the fraction of the old sentence's
keywords present in the best-matching target sentence. Below `--threshold`, it is flagged.

**The flags are the START of the audit, not the result.** Hand-check every one. In practice they
sort into four kinds, and only the last is a bug:

  - **markdown / line-wrap artefacts** — sentence splitting merges a paragraph with a following
    heading, or a table row with its neighbour. Both halves are usually present verbatim.
  - **rewording** — the rule survives, condensed or rephrased, so the keywords moved.
  - **deliberate history cuts** — evidence removed on purpose because it lives in a
    `references/incidents.md` that the agent can reach. Confirm it is genuinely there.
  - **a real loss** — a rule that exists nowhere. Restore it.

Roughly 5% of flags are artefacts of the first kind. A run with zero flags means the threshold is
too low, not that the trim was perfect.

USAGE
-----
    python audit_coverage.py --old HEAD:path/to/file.md \\
        --against new.md other/SKILL.md other/references/incidents.md

`--old` is any `git show` ref (`HEAD:path`, `abc123:path`) or a plain path to a file on disk.
Run it from inside the repo the ref belongs to.
"""
import argparse
import pathlib
import re
import subprocess
import sys

# Words that carry no signal about WHICH rule a sentence states. Kept deliberately short: an
# aggressive stoplist inflates every score and hides real losses.
STOP = set("""a an the and or but if of to in on at by for with as is are was were be been being
it its this that these those they them their you your yours we us our they them their not no so than
then there here what which who whom when where why how all any both each few more most other some
such only own same too very can will just don't should now into from about over under again""".split())


def words(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9_.]+", s.lower()) if w not in STOP and len(w) > 2}


def sentences(text: str, min_words: int = 4) -> list:
    """Split into sentences, dropping fragments too short to carry a rule.

    Markdown is not prose, so this is approximate by design — see the artefact note above.
    """
    text = re.sub(r"\s+", " ", text)
    return [c.strip() for c in re.split(r"(?<=[.!?:])\s+", text)
            if len(words(c)) >= min_words]


def load_old(ref: str) -> str:
    """A `git show` ref, or a path on disk if that fails."""
    if ":" in ref:
        r = subprocess.run(["git", "show", ref], capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            return r.stdout
    return pathlib.Path(ref).read_text(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True, help="git ref (HEAD:path) or path to the pre-trim file")
    ap.add_argument("--against", required=True, nargs="+",
                    help="files that may carry the rule now — include the new file AND every "
                         "reference an agent can actually reach")
    ap.add_argument("--threshold", type=float, default=0.8)
    args = ap.parse_args()

    old = sentences(load_old(args.old))
    pools = {}
    for t in args.against:
        p = pathlib.Path(t)
        if not p.exists():
            print(f"missing target: {t}", file=sys.stderr)
            return 2
        pools[t] = [words(s) for s in sentences(p.read_text(encoding="utf-8"))]

    flags = []
    for s in old:
        sw = words(s)
        top = (0.0, None)
        for name, pool in pools.items():
            for tw in pool:
                score = len(sw & tw) / len(sw)
                if score > top[0]:
                    top = (score, name)
        if top[0] < args.threshold:
            flags.append((top[0], top[1], s))

    flags.sort()
    print(f"{len(flags)} of {len(old)} sentence(s) below {args.threshold} coverage\n")
    for score, where, s in flags:
        print(f"[{score:.2f} best={where}] {s[:200]}")
    print("\nHand-check every flag. Artefacts and rewordings are expected; a rule that exists "
          "nowhere is the bug this script is for.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
