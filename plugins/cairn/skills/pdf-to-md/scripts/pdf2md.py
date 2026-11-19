#!/usr/bin/env python3
"""pdf2md.py - convert any PDF to lean Markdown for LLM consumption.

Usage:
    python pdf2md.py doc.pdf [-o doc.md] [--skip-pages 1-3,40-45] [--outline]
                     [--keep-images] [--keep-markup] [--no-strip] [--ask-password]

Runs fully locally (no network). Requires: pip install pymupdf4llm
Falls back to `pdftotext -layout` if pymupdf4llm is not importable (tables get flattened).
Do not run it with `python -I` or `-s`: that hides a user-site install and silently
falls back to pdftotext. Use `python -P` if you want the script's folder kept off sys.path.

Exit codes: 0 ok, 2 bad arguments, 3 password-protected (see message), 4 wrong password.
"""
import argparse, collections, getpass, os, re, shutil, subprocess, sys
from pathlib import Path

try:  # Windows consoles default to a legacy code page; never crash on a stray glyph
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass


def parse_ranges(spec, n):
    skip = set()
    for part in filter(None, (spec or "").split(",")):
        a, _, b = part.strip().partition("-")
        skip.update(range(int(a), int(b or a) + 1))
    return {p for p in skip if 1 <= p <= n}


def open_doc(pdf, ask_password):
    """Open with PyMuPDF, authenticating if needed. Returns None if PyMuPDF is missing."""
    try:
        import pymupdf
    except ImportError:
        return None
    doc = pymupdf.open(str(pdf))
    if doc.needs_pass:
        if not ask_password:
            _exit_protected(pdf)
        if not interactive():
            sys.exit("--ask-password needs an interactive terminal. "
                     "Run it in your own terminal, not through an agent's shell tool.")
        if not doc.authenticate(getpass.getpass(f"Password for {pdf.name}: ")):
            print("Wrong password.", file=sys.stderr)
            sys.exit(4)
    return doc


def interactive():
    """True only for a real console. On Windows the NUL device an agent shell gives as
    stdin reports isatty() True, and getpass then blocks forever reading the console."""
    if not sys.stdin.isatty():
        return False
    if os.name == "nt":
        try:
            import ctypes, msvcrt
            h = msvcrt.get_osfhandle(sys.stdin.fileno())
            return bool(ctypes.windll.kernel32.GetConsoleMode(h, ctypes.byref(ctypes.c_ulong())))
        except Exception:
            return False
    return True


def _exit_protected(pdf):
    print(f"{pdf.name} is password-protected. Never put the password in a command line, "
          "env var or chat. The user runs this themself in their own terminal and types it "
          "at the hidden prompt:\n"
          f'    python "{Path(__file__).resolve()}" "{pdf}" --ask-password', file=sys.stderr)
    sys.exit(3)


def extract_pages(pdf, doc):
    if doc is not None:
        try:
            import pymupdf4llm
            kw = dict(page_chunks=True, show_progress=False)
            try:  # no OCR; headers/footers removed by our own repetition check
                chunks = pymupdf4llm.to_markdown(doc, use_ocr=False, **kw)
            except TypeError:
                chunks = pymupdf4llm.to_markdown(doc, **kw)
            return [c["text"] for c in chunks], "pymupdf4llm"
        except ImportError:
            # PyMuPDF without pymupdf4llm: plain text per page, still decrypted
            return [p.get_text() for p in doc], "pymupdf-text"
    if not shutil.which("pdftotext"):
        sys.exit("Install pymupdf4llm (pip install pymupdf4llm) or poppler's pdftotext.")
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        if "password" in (out.stderr or "").lower() or "encrypt" in (out.stderr or "").lower():
            sys.exit("Password-protected, and the pdftotext fallback cannot take a password "
                     "safely. Install pymupdf4llm, then run with --ask-password.")
        sys.exit(f"pdftotext failed: {out.stderr.strip()}")
    return out.stdout.rstrip("\f\n").split("\f"), "pdftotext"


def textless_pages(doc):
    """1-based numbers of pages with (almost) no text layer: scanned images, needs OCR."""
    if doc is None:
        return []
    return [i for i, p in enumerate(doc, 1) if len(p.get_text().strip()) < 30]


MARKUP = [  # <br> first: the tag list below must not see it as "<b" + "r>"
    (re.compile(r"<br\s*/?>", re.I), " "),
    (re.compile(r"</?(u|b|i|em|strong|sup|sub|span|mark|font)\b[^>]*>", re.I), ""),
    (re.compile(r"\*\*"), ""),
]


def demarkup(s):
    for rx, rep in MARKUP:
        s = rx.sub(rep, s)
    return s


def norm(line):
    # Compare without bold/underline noise. Digits are normalised only on lines that
    # look like running footers with page numbers ("ACME | Page 3 of 40"); never on other
    # lines, so "Finding 3: ..." and "Finding 4: ..." stay distinct.
    s = re.sub(r"\s+", " ", demarkup(line)).strip().lower()
    # "page" may be glued to its number once bold markers are gone ("Page1of87")
    return re.sub(r"\d+", "#", s) if re.search(r"\bpage(\b|\d)|^\d+$|^\d+\s*/\s*\d+$", s) else s


IMG_RE = re.compile(r"^\*\*==>.*(picture|image).*<==\*\*$|^!\[.*\]\(.*\)$", re.I)
PAGENUM_RE = re.compile(r"^(page\s*)?#+(\s*(of|/)\s*#+)?$")
SEP_RE = re.compile(r"^\|?(\s*:?-{3,}:?\s*\|)+\s*:?-*:?\s*$")
HEAD, TAIL = 3, 4  # lines from the top/bottom of each page that vote on boilerplate


def find_boilerplate(pages):
    # A line in the top/bottom band of a full page that repeats on >=40% of pages is a
    # running header/footer/classification banner/copyright notice. Short pages don't
    # vote, so real content on sparse pages is never mistaken for a footer. Table
    # separators never count. In the top band a table row counts only if it carries a
    # page number ("|Report no: X|Page 3 of 87|"): a repeated table HEADER continuing a
    # findings table across pages is content, not a running header.
    counts, voters = collections.Counter(), 0
    for p in pages:
        ls = [l for l in p.splitlines() if l.strip()]
        if sum(map(len, ls)) < 600 or len(ls) < HEAD + TAIL:
            continue
        voters += 1
        band = {n for n in map(norm, ls[:HEAD])
                if not n.startswith("|") or re.search(r"\bpage\s*#", n)}
        band |= {norm(l) for l in ls[-TAIL:] if not SEP_RE.match(l.strip())}
        counts.update(band)
    threshold = max(3, int(voters * 0.4))
    return {k for k, c in counts.items() if c >= threshold and k}


def clean(pages, pagenos, keep_images, keep_markup, strip=True):
    boiler = find_boilerplate(pages) if strip else set()
    out, images = [], 0
    for pno, p in zip(pagenos, pages):
        kept = [f"[p{pno}]"]  # ~3 tokens; lets you jump back to the PDF page
        for line in p.splitlines():
            s = line.rstrip()
            n = norm(s)
            if n in boiler or PAGENUM_RE.match(n):
                continue
            if IMG_RE.match(s.strip()):
                images += 1
                if keep_images:
                    kept.append("[image omitted]")
                continue
            if re.fullmatch(r"[-_=.\s]{4,}", s):       # rule lines / TOC dot leaders
                continue
            s = re.sub(r"\.{4,}\s*\d*$", "", s)        # TOC dot leaders
            s = re.sub(r"[ \t]{3,}", "  ", s)          # layout padding
            if not keep_markup:
                s = demarkup(s)
            # a table separator whose header row was stripped as boilerplate is orphaned
            if SEP_RE.match(s.strip()) and not (kept and kept[-1].lstrip().startswith("|")):
                continue
            kept.append(s)
        out.append("\n".join(kept))
    text = "\n\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # dedupe identical consecutive paragraphs (repeated remediation/legal boilerplate)
    paras, last = [], None
    for para in text.split("\n\n"):
        key = para.strip()
        if key and key == last:
            continue
        paras.append(para); last = key
    return "\n\n".join(paras).strip() + "\n", images, sorted(boiler)


def outline(md, limit=80):
    rows, page = [], "?"
    for line in md.splitlines():
        m = re.match(r"^\[p(\d+)\]$", line)
        if m:
            page = m.group(1)
        elif re.match(r"^#{1,4} \S", line):
            rows.append(f"  p{page:<4} {line[:100]}")
    for r in rows[:limit]:
        print(r)
    if len(rows) > limit:
        print(f"  ... {len(rows) - limit} more headings (grep '^#' in the .md)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--skip-pages", help="1-based ranges to drop, e.g. 1-3,40-45 (cover, TOC, appendices)")
    ap.add_argument("--outline", action="store_true", help="also print the heading map with page numbers")
    ap.add_argument("--no-strip", action="store_true",
                    help="don't strip repeating header/footer lines (use if real content was stripped)")
    ap.add_argument("--keep-images", action="store_true", help="leave [image omitted] markers")
    ap.add_argument("--keep-markup", action="store_true", help="keep **bold**, <u>, <br> etc.")
    ap.add_argument("--ask-password", action="store_true",
                    help="prompt (hidden) for the password; interactive terminals only")
    a = ap.parse_args()
    if not a.pdf.is_file():
        ap.error(f"no such file: {a.pdf}")

    doc = open_doc(a.pdf, a.ask_password)
    pages, engine = extract_pages(a.pdf, doc)
    raw_chars = sum(len(p) for p in pages)
    skip = parse_ranges(a.skip_pages, len(pages))
    pagenos = [i for i in range(1, len(pages) + 1) if i not in skip]
    md, images, boiler = clean([pages[i - 1] for i in pagenos], pagenos,
                               a.keep_images, a.keep_markup, not a.no_strip)

    out = a.out or a.pdf.with_suffix(".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"engine={engine} pages={len(pages)} skipped={len(skip)} images_dropped={images}")
    if engine == "pdftotext":
        print("WARNING: pdftotext fallback - tables are flattened to text columns. "
              "Install pymupdf4llm (and don't run with python -I/-s) for proper tables.")
    for b in boiler:
        print(f"  stripped repeating header/footer: {b[:80]!r}")
    print(f"~tokens raw={raw_chars // 4:,} -> clean={len(md) // 4:,}  ->  {out}")
    if images:
        print(f"NOTE: {images} images are not in the Markdown. "
              "Open specific PDF pages if a figure or screenshot matters.")
    blank = [p for p in textless_pages(doc) if p not in skip]
    if blank:
        shown = ",".join(map(str, blank[:20])) + (" ..." if len(blank) > 20 else "")
        print(f"NOTE: {len(blank)} page(s) have no text layer (scanned?): {shown}. "
              "This script does not OCR; their content is missing from the Markdown.")
    if a.outline:
        outline(md)


if __name__ == "__main__":
    main()
