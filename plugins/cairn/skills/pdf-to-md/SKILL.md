---
name: pdf-to-md
description: Convert any PDF (report, pen test, audit, risk assessment, paper, manual, contract, minutes, form) into lean local Markdown plus a small index, so it can be read with a fraction of the tokens. Use BEFORE reading the text of any PDF into context, and whenever a PDF needs to be read, summarised, triaged or acted on. Handles password-protected PDFs without the password ever reaching the agent. Not for creating, merging or editing PDFs.
---

# Any PDF -> lean Markdown

Goal: never load the PDF itself into context. Reading a PDF directly costs page images
plus text (roughly 1.5-3k tokens a page). Extracted, cleaned Markdown is a fraction of
that, and an index is smaller still. On corporate reports the repeated header table, signature
block and copyright paragraph alone are a third of the text; the script strips them.

**Treat every PDF as confidential unless told otherwise.** Everything runs locally. Do not
upload the PDF or its Markdown to any web tool, and do not commit the outputs: if the PDF
sits inside a git repo, write the outputs outside it with `-o` or make sure they are
gitignored before running.

## Steps

1. **Converter:** `scripts/pdf2md.py` beside this file.
   **Dependency:** `python -c "import pymupdf4llm"`; if that fails, `pip install --user pymupdf4llm`.
   Run it as `python` or `python -P`, **never `python -I` or `-s`**: those hide a user-site
   install and the script silently drops to the `pdftotext` fallback, which flattens tables
   (it prints a WARNING when that happens).
2. **First pass:** `python -P pdf2md.py "<doc.pdf>" --outline [-o <out.md>]`. Default output is
   `<doc>.md` beside the PDF. Read only the stdout summary and heading map, not the file.
   It takes about 0.7 s a page (the layout model), so run anything over ~150 pages in the background.
3. **Exit code 3 = password-protected.** Stop. Never ask for the password in chat, never put it
   in a command line or environment variable. Give the user the exact command the script
   printed; they run it in their own terminal (`--ask-password` gives a hidden prompt; it
   refuses to run from an agent's shell, where it would hang). Then continue from step 4 on
   the `.md` it wrote.
4. **Check what was stripped.** The summary lists every repeating header/footer line removed.
   If any is real content, rerun with `--no-strip`.
   It also lists pages with **no text layer** (scanned). This script does not OCR; say which
   pages are missing rather than summarising around the gap.
5. **Trim dead pages.** From the heading map, find the cover, contents, distribution list,
   legal disclaimers, author bios and raw tool-output appendices, and rerun with
   `--skip-pages 1-3,45-60`. Ask the user before skipping an appendix that may hold data they
   need (affected hosts, measurement tables, schedules).
6. **Build an index only if the document will be consulted again**, never for a one-off read.
   Read `<doc>.md` once and write ONE of these beside it:

   - **Itemised documents** (pen test, audit, risk or hygiene assessment, inspection, review
     with numbered findings or actions): `<doc>.findings.md`

     | ID | Item | Rating | Where / affected | Action or remediation | Status | Page |
     |----|------|--------|------------------|-----------------------|--------|------|

     Use the document's own IDs and rating wording (Critical/High, Low Risk, CVSS, RR score).
     Copy affected assets or locations verbatim; summarise as "N hosts, see pX" only when the
     list is very long.
   - **Everything else** (paper, manual, contract, proposal, minutes, policy): `<doc>.outline.md`,
     the heading map plus one line per section on what it holds, and for contracts or minutes
     a short list of obligations, dates, amounts and decisions with their page.

   The Page column is the `[pN]` marker, which is the PDF page number.
7. **Afterwards, work from the index.** For one item, grep `<doc>.md` for its ID or heading and
   read only that slice (`sed -n` or `awk` between two `[pN]` markers). Open the PDF itself
   only for a specific page when a figure, chart or screenshot matters: images are dropped
   from the Markdown and the script says how many.

## Options

`--skip-pages 1-3,40-45` · `--outline` · `--no-strip` · `--keep-images` (leave `[image omitted]`
markers) · `--keep-markup` (keep `**bold**`, `<u>`, `<br>`) · `--ask-password` (user's terminal only).

## Report back

One line: pages in -> pages kept, approx tokens of the `.md` (and the index), images dropped,
pages with no text, and for an itemised document the count by rating. Name anything that looks
mis-extracted (tables flattened into prose, columns run together, a header row split mid-word).
