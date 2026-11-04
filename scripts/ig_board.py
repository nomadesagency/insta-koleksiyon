#!/usr/bin/env python3
"""İnceleme panosu: 'GÖZDEN GEÇİR' postlar için tek görselde 8 kare (ilk 2 + eşit aralıklı 6) + metin özeti.

Başlıklar çoğunlukla videonun başında çıktığı için ilk iki kare her zaman dahildir.
Kullanım: ig_board.py --workdir W --pending   (bekleyen TÜM postlar: işaretli + OTO, tek seferde)   |   --batch 0 --size 5 (yalnız işaretliler)   |   --codes A,B
Çıktı: frames/<kod>/_board.jpg + terminalde OCR/altyazı/konuşma özeti. Panoları inceleyen kişi ya da ajan görsel olarak okur.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from ig_common import base_parser, cache_dir, load_state


def pick(frames: list, n: int = 8) -> list:
    if len(frames) <= n:
        return frames
    head = frames[:2]
    rest = frames[2:]
    step = len(rest) / (n - 2)
    return head + [rest[int(i * step)] for i in range(n - 2)]


def make_board(wd: Path, code: str, frames: list, cols: int = 4, w: int = 300, pick_all: bool = False,
               name: str = "_board.jpg") -> Path:
    ims = []
    for rel in (frames if pick_all else pick(frames)):
        im = Image.open(wd / rel).convert("RGB")
        im.thumbnail((w, int(w * 2)))
        ims.append(im)
    h = max(i.height for i in ims)
    rows = (len(ims) + cols - 1) // cols
    board = Image.new("RGB", (cols * w, rows * h), "white")
    for n, im in enumerate(ims):
        board.paste(im, ((n % cols) * w, (n // cols) * h))
    out = wd / "frames" / code / name
    board.save(out, quality=85)
    return out


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--codes")
    p.add_argument("--pending", action="store_true", help="İncelemesi bitmemiş (stage != done) tüm postlar; OTO dahil")
    p.add_argument("--batch", type=int, default=0)
    p.add_argument("--size", type=int, default=5)
    args = p.parse_args()
    wd = Path(args.workdir)
    cd = cache_dir(args, wd)
    posts = load_state(wd)["posts"]
    if args.codes:
        codes = args.codes.split(",")
    elif args.pending:
        codes = [c for c, v in sorted(posts.items(), key=lambda kv: kv[1].get("order", 0))
                 if v.get("frames") and v.get("stage") != "done"]
        print(f"inceleme bekleyen: {len(codes)} post")
    else:
        todo = [c for c, v in sorted(posts.items(), key=lambda kv: kv[1].get("order", 0))
                if v.get("text_status") == "GÖZDEN GEÇİR" and v.get("frames")]
        codes = todo[args.batch * args.size:(args.batch + 1) * args.size]
        print(f"kalan GÖZDEN GEÇİR: {len(todo)}  bu parti: {len(codes)}")
    for c in codes:
        v = posts[c]
        if not v.get("frames"):
            print("=====", c, "kare yok")
            continue
        print(f"===== {c} @{v.get('account')} {v.get('type')} {round(v.get('duration') or 0)}s")
        if v.get("type") in ("Carousel", "Foto"):
            # carousel: her slayt okunmalı, 6'şar slayt, büyük
            fr = v["frames"]
            for k in range(0, len(fr), 6):
                print("BOARD:", make_board(cd, c, fr[k:k + 6], cols=3, w=400, pick_all=True, name=f"_slides_{k // 6 + 1}.jpg"))
        else:
            print("BOARD:", make_board(cd, c, v["frames"]))
        print("AÇIKLAMA:", (v.get("caption") or "")[:160].replace("\n", " / "))
        print("KALAN OCR:", (v.get("screen_text") or "(boş)")[:500].replace("\n", " | "))
        print("ALTYAZI SAYILAN:", " | ".join(v.get("subtitle_lines", []))[:200])
        flag = ""
        if v.get("speech_suspect"):
            flag = f"  [ŞÜPHELİ: şarkı sözü olabilir; ses={v.get('audio_type') or '?'} {v.get('music_title') or ''}]"
        print("KONUŞMA:", (v.get("speech_text") or "(yok)")[:160].replace("\n", " ") + flag)


if __name__ == "__main__":
    main()
