#!/usr/bin/env python3
"""state.json -> saved-posts.xlsx. Category values are VALIDATED against the taxonomy; a value outside it stops the build.

Sheets: Saved · Errors-Missing · Category Distribution
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ig_common import base_parser, load_state, load_taxonomy

COLUMNS = [
    ("No", 6), ("URL", 38), ("Account", 18), ("Type", 10), ("Published", 13), ("Collection", 16),
    ("Caption", 60), ("On-screen text", 60), ("Speech transcript", 60), ("Has speech", 12),
    ("Text status", 14), ("Category", 28), ("Tags", 34), ("Media folder", 24), ("Note", 30),
]
CELL_LIMIT = 32000


def post_date(v: dict) -> str:
    """ISO date; otherwise a date_text such as 'October 22, 2026' is converted to ISO."""
    if v.get("date"):
        return v["date"]
    try:
        return datetime.strptime(v.get("date_text", ""), "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return v.get("date_text", "") or ""


def clean(v) -> str:
    s = ILLEGAL_CHARACTERS_RE.sub("", str(v or ""))
    return s if len(s) <= CELL_LIMIT else s[:CELL_LIMIT] + " …[truncated]"


def validate(posts: dict, tax: dict, partial: bool) -> list:
    cats, errors = set(tax["categories"]), []
    for code, p in posts.items():
        main, tags = p.get("category"), p.get("tags", [])
        if not main:
            if not partial:
                errors.append(f"{code}: no category")
            continue
        if main not in cats:
            errors.append(f"{code}: category not in the list -> {main!r}")
        bad = [t for t in tags if t not in cats]
        if bad:
            errors.append(f"{code}: tag not in the list -> {bad}")
        if len(tags) > tax["max_secondary"]:
            errors.append(f"{code}: at most {tax['max_secondary']} secondary tags, {len(tags)} given")
        if main in tags:
            errors.append(f"{code}: category repeated in tags")
    return errors


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--partial", action="store_true", help="Allow uncategorised posts (intermediate output)")
    p.add_argument("--out", default="saved-posts.xlsx")
    args = p.parse_args()
    wd = Path(args.workdir)
    posts = load_state(wd)["posts"]
    tax = load_taxonomy(wd)

    errors = validate(posts, tax, args.partial)
    if errors:
        sys.exit("VALIDATION ERROR, spreadsheet not written:\n  " + "\n  ".join(errors))

    wb = Workbook()
    ws = wb.active
    ws.title = "Saved"
    ws.append([c for c, _ in COLUMNS])
    for i, (_, w) in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="333333")
    problems = []
    for code, v in sorted(posts.items(), key=lambda kv: kv[1].get("order", 0)):
        screen = v.get("screen_text", v.get("ocr_text", ""))
        row = [v.get("order"), v["url"], v.get("account"), v.get("type"), post_date(v), v.get("collection"),
               v.get("caption"), screen, v.get("speech_text"),
               "Yes" if v.get("has_speech") else "No", v.get("text_status", ""),
               v.get("category", ""), ", ".join(v.get("tags", [])),
               str(Path("media") / code) if v.get("media") and not v.get("media_purged") else "", v.get("note", "")]
        ws.append([clean(x) for x in row])
        if v.get("error") or v.get("text_status") == "REVIEW" or not v.get("caption"):
            problems.append((code, v))
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    for r in ws.iter_rows(min_row=2):
        for c in r:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        r[1].hyperlink = r[1].value

    ws2 = wb.create_sheet("Errors-Missing")
    ws2.append(["No", "URL", "Problem"])
    for code, v in problems:
        reason = v.get("error") or (v.get("review_reason") if v.get("text_status") == "REVIEW" else "") or ("empty caption" if not v.get("caption") else "")
        ws2.append([v.get("order"), v["url"], clean(reason)])
    ws2.column_dimensions["B"].width = 40
    ws2.column_dimensions["C"].width = 60

    ws3 = wb.create_sheet("Category Distribution")
    ws3.append(["Category", "As category (posts)", "As tag"])
    mains = Counter(v.get("category") for v in posts.values() if v.get("category"))
    tagc = Counter(t for v in posts.values() for t in v.get("tags", []))
    for cat in tax["categories"]:
        ws3.append([cat, mains.get(cat, 0), tagc.get(cat, 0)])
    ws3.column_dimensions["A"].width = 36

    out = wd / args.out
    wb.save(out)
    total = len(posts)
    fb = mains.get(tax["fallback"], 0)
    print(f"written: {out}  rows={total}  errors/missing={len(problems)}  '{tax['fallback']}' share={fb}/{total}")


if __name__ == "__main__":
    main()
