#!/usr/bin/env python3
"""Writes review results to state (on-screen text, category, tags, note). Reads JSON from stdin.

Usage:  ig_apply.py --workdir W < results.json      |      ig_apply.py --workdir W --letters   (show letter codes)
Input: {"<code>": {"screen_text": "...", "category": "G", "tags": ["H"], "note": "...", "has_speech": false, ...}, ...}
Category/tags may be given by full name or by letter code in taxonomy order (A = 1st category ... M = 13th).
A post that gets a category moves to the `done` stage. Categories outside the list, a tag repeating the category and
more than the allowed number of tags are rejected.
Default text status is CORRECTED; pass "text_status" to change it.
--mode visual|text records HOW the posts were reviewed (default visual = boards/slides were looked at; text = decided from
caption + OCR + speech only). It is shown in the spreadsheet's Review column, so text-only posts can be revisited later.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ig_common import advance, base_parser, load_state, load_taxonomy, save_state


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--letters", action="store_true", help="Show letter codes and exit")
    p.add_argument("--mode", choices=["visual", "text"], default="visual", help="How these posts were reviewed")
    args = p.parse_args()
    wd = Path(args.workdir)
    tax = load_taxonomy(wd)
    cats = tax["categories"]
    letters = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", cats))
    if args.letters:
        for k, v in letters.items():
            print(k, v)
        return

    full = lambda x: letters.get(x, x)  # noqa: E731
    data = json.load(sys.stdin)
    state = load_state(wd)
    errors = []
    for code, f in data.items():
        if code not in state["posts"]:
            errors.append(f"{code}: not in state")
            continue
        if "category" in f:
            f["category"] = full(f["category"])
            f["tags"] = [full(x) for x in f.get("tags", [])]
            if f["category"] not in cats or any(t not in cats for t in f["tags"]):
                errors.append(f"{code}: category/tag not in the list")
            elif f["category"] in f["tags"] or len(f["tags"]) > tax["max_secondary"]:
                errors.append(f"{code}: tag rule (repeat, or more than {tax['max_secondary']})")
    if errors:
        sys.exit("VALIDATION ERROR, nothing written:\n  " + "\n  ".join(errors))
    for code, f in data.items():
        post = state["posts"][code]
        f.setdefault("text_status", "CORRECTED")
        f.setdefault("review", args.mode)
        post.pop("review_reason", None)
        if f.get("has_speech") is False:
            f.setdefault("speech_text", "")
            f["speech_suspect"] = False
        if "category" in f:
            advance(post, "done")
        post.update(f)
    save_state(wd, state)
    print("applied:", len(data))


if __name__ == "__main__":
    main()
