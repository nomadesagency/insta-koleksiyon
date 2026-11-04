#!/usr/bin/env python3
"""Yanık altyazıyı ayıklar: konuşma transkriptiyle büyük ölçüde örtüşen OCR satırları 'altyazı' sayılır.

Kapsam kararı: görsel üstü metin dökümü altyazıyı İÇERMEZ (konuşma ayrı sütundadır). Yalnız kısa (en fazla MAX_SUBTITLE_WORDS kelime) satırlar altyazı sayılır. Heuristiktir
(Whisper hataları örtüşmeyi düşürür), bu yüzden satır atılan her post 'GÖZDEN GEÇİR' olur.
ig_speech.py'den SONRA çalıştırılır. İdempotent.
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

from ig_common import base_parser, load_state, save_state

WORD_MATCH = 0.8
LINE_MATCH = 0.6
MAX_SUBTITLE_WORDS = 4  # yanık altyazı kısa ve hızlı değişir; uzun cümle tasarlanmış ekran metnidir


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
            post["text_status"] = "GÖZDEN GEÇİR"
            post["review_reason"] = f"{len(subs)} satır altyazı sayıldı, doğrula"
        elif not keep and post.get("text_status") == "OTO":
            post["text_status"], post["review_reason"] = "GÖZDEN GEÇİR", "OCR boş"
        save_state(wd, state)
        print(code, f"altyazı={len(subs)} kalan={len(keep)}")


if __name__ == "__main__":
    main()
