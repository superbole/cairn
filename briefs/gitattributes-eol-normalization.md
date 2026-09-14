# Brief — `.gitattributes` and EOL normalization

Filed 2026-09-11 from `SBOLE-NB5` (WSL).

## The problem

The repo has no `.gitattributes` and `core.autocrlf` is unset. The index holds LF; the Windows
working tree at `C:\Users\SheldonBole\Projects\cairn` holds CRLF. Any session reading that
same checkout from WSL — where `autocrlf` is false — sees every tracked file as modified:

    87 files changed, 25751 insertions(+), 25751 deletions(-)

`git diff -w --ignore-cr-at-eol` is completely clean, which confirms there is no content change
at all. It is entirely line endings.

## Why it matters

A one-line fix committed from WSL would be buried under 25,751 lines of noise, and `git status`
is useless as a signal in that checkout — a real change and a clean tree look identical. It also
means the working tree cannot be trusted to answer "is there work in progress here?", which is
what `dirty_tree_warning.py` asks at `Stop` and `SessionEnd`.

This blocks any Linux-side contribution to the repo, including the fix in
[cross-platform-hook-interpreter.md](cross-platform-hook-interpreter.md).

## The fix

Add `.gitattributes` at the repo root declaring LF as canonical:

    * text=auto eol=lf

Then renormalize in one dedicated commit that touches nothing else:

    git add --renormalize .
    git commit -m "chore: normalize line endings to LF"

Do it from **Windows**, on a clean tree, and let that commit be the only thing in it so it stays
easy to skip when reading history.

## Watch for

- Anything that must stay CRLF needs its own rule (`*.bat text eol=crlf`, and `*.ps1` if the
  sync script cares — `reentry-sync.ps1` lives in `cairn-private`, not here, so check before
  assuming this repo has none).
- Confirm afterwards that a WSL session sees a clean tree: `git status --porcelain` empty from
  both sides is the test.

## Done looks like

`git status` is clean from Windows and from WSL on the same checkout, and a subsequent one-line
edit shows as a one-line diff.
