# Brief — model labels name the tier (family), not a version (B76)

`Opus 5` · effort `high` · `AFK/Auto` · from `BACKLOG.md` B76. Written 2026-09-26 at B70's wrap.

**Commit locally, then stop. The push and `tools/sync_backlog.py` wait for the user.**

## Read first
- The entry: `sed -n '/^## B76\./,/^## B[0-9]/p' BACKLOG.md`. It holds the defect (`hooks/backlog_file.py`
  `_MODEL_RE` is a fixed list of version strings), both options, and the recommendation.
- `grep -rn "Opus 5\|Sonnet 5\|Haiku 4.5\|Fable 5" plugins/` gives the full blast radius: the rules
  template, both skills, the orientation, `validate_next.py` and the tests.

## Decide, then do
1. Take option (a) unless the code shows it can't work: the label is the family, with an optional version.
   The regex accepts `Opus`, `Opus 5` and `Opus 5.5` alike. Existing `Opus 5` labels must keep parsing.
2. Write down the tier order that a mismatch check uses: Haiku < Sonnet < Opus, **and where Fable sits**.
   Stating that is a judgement. Make it, record it in a `docs/decisions.md` row with the rejected option
   (b), and say in the report that it was decided on the user's behalf.
3. Update the templates and examples in `rules/CLAUDE.md` and both `SKILL.md` files so new items write the
   family. Don't mass-rewrite existing `NEXT.md` or `BACKLOG.md` labels; they still parse.
4. Tests: `Opus 5.5`, `Fable 5.1` and a bare `Opus` all parse, and an unknown family is still refused.

## Verification
`python plugins/cairn/tools/run_tests.py --timeout=300`, with the output pasted in full. Version bump,
CHANGELOG entry, and close B76.

## Report, then stop
Changed files, the test output, and the tier order you chose. End the turn. The push waits for the user.
