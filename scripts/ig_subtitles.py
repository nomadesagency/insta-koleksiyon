#!/usr/bin/env python3
"""Removes burned-in subtitles: OCR lines that largely overlap the speech transcript count as 'subtitles'.

Scope rule: the on-screen text does NOT include subtitles (speech has its own column). Only short lines (at most
MAX_SUBTITLE_WORDS words) can count as subtitles. It is a heuristic (Whisper errors lower the overlap), so every post
that loses a line is marked 'REVIEW'.
Run AFTER ig_speech.py. Idempotent.
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

from ig_common import base_parser, load_state, save_state

WORD_MATCH = 0.8
LINE_MATCH = 0.6
MAX_SUBTITLE_WORDS = 4  # burned-in subtitles are short and change fast; a long sentence is designed on-screen text


def words(s: str) -> list:
    return [w for w in re.findall(r"\w+", s.lower()) if len(w) >= 2]


def is_subtitle(line: str, speech_words: set) -> bool:
    ws = words(line)
    if not ws or not speech_words or len(ws) > MAX_SUBTITLE_WORDS:
        return False
    hit = sum(1 for w in ws if w in speech_words or difflib.get_close_matches(w, speech_words, 1, WORD_MATCH))
    return hit / len(ws) >= LINE_MATCH


def main() -> None:
    p = base_parser(__doc__)
    args = p.parse_args()
    wd = Path(args.workdir)
    state = load_state(wd)

    changed = 0
    for code, post in state["posts"].items():
        if "ocr_text" not in post or "speech_text" not in post or "subtitle_lines" in post:
            continue
        speech_words = set(words(post.get("speech_text", "")))
        lines = [l for l in post["ocr_text"].split("\n") if l.strip()]
        subs = [l for l in lines if is_subtitle(l, speech_words)]
        keep = [l for l in lines if l not in subs]
        post["subtitle_lines"] = subs
        post["screen_text"] = "\n".join(keep)
        if subs:
            post["text_status"] = "REVIEW"
            post["review_reason"] = f"{len(subs)} lines counted as subtitles, check"
        elif not keep and post.get("text_status") == "AUTO":
            post["text_status"], post["review_reason"] = "REVIEW", "OCR empty"
        changed += 1
        print(code, f"subtitles={len(subs)} kept={len(keep)}")
    if changed:  # pure computation, no slow step: one save at the end is enough
        save_state(wd, state)


if __name__ == "__main__":
    main()
