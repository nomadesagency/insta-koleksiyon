#!/usr/bin/env python3
"""Compares the spreadsheet with state.json cell by cell (quality gate). Exit code 1 on any difference.

Checks: row count = post count · URLs unique · 13 content columns + Review identical to state · category/tags in taxonomy ·
date not empty. Run BEFORE any deletion step (ig_cleanup).
"""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

from ig_common import base_parser, load_state, load_taxonomy

# build_xlsx.COLUMNS order: 0 No 1 URL 2 Account 3 Type 4 Published 5 Collection 6 Caption 7 On-screen text 8 Speech
# 9 Has speech 10 Text status 11 Category 12 Tags 13 Media folder 14 Note 15 Review
def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--xlsx", default="saved-posts.xlsx")
    args = p.parse_args()
    wd = Path(args.workdir)
    posts = load_state(wd)["posts"]
    cats = set(load_taxonomy(wd)["categories"])
    ws = openpyxl.load_workbook(wd / args.xlsx)["Saved"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    by_url = {p_["url"]: p_ for p_ in posts.values()}
    s = lambda v: "" if v is None else str(v)  # noqa: E731
    errors = []
    if len(rows) != len(posts):
        errors.append(f"rows {len(rows)} ≠ state {len(posts)}")
    if len({r[1] for r in rows}) != len(rows):
        errors.append("URLs are not unique")
    for r in rows:
        post = by_url.get(r[1])
        if not post:
            errors.append(f"not in state: {r[1]}")
            continue
        exp = [post.get("order"), post["url"], post.get("account"), post.get("type"), None, post.get("collection"),
               post.get("caption"), post.get("screen_text", ""), post.get("speech_text"),
               "Yes" if post.get("has_speech") else "No", post.get("text_status"), post.get("category"),
               ", ".join(post.get("tags", []))]
        for i, e in enumerate(exp):
            if i != 4 and s(e) != s(r[i]):
                errors.append(f"{r[1][-14:]} column {i}: state≠spreadsheet")
        # category names may contain commas: do not split the column on commas, check the list in state (the column already matched)
        if r[11] not in cats or any(t not in cats for t in post.get("tags", [])):
            errors.append(f"{r[1][-14:]}: category/tag not in taxonomy")
        if s(post.get("review", "")) != s(r[15] if len(r) > 15 else ""):
            errors.append(f"{r[1][-14:]} column 15 (Review): state≠spreadsheet")
        if not r[4]:
            errors.append(f"{r[1][-14:]}: empty date")
    if errors:
        print("SPREADSHEET CHECK FAILED:\n  " + "\n  ".join(errors[:30]) + (f"\n  ... +{len(errors) - 30}" if len(errors) > 30 else ""))
        sys.exit(1)
    print(f"Spreadsheet verified: {len(rows)} rows = state, URLs unique, 0 cell differences, taxonomy consistent")


if __name__ == "__main__":
    main()
