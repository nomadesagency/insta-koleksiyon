#!/usr/bin/env python3
"""Review board: 8 frames in one image (first 2 + 6 evenly spaced) + a text summary, for posts that need review.

Titles usually appear at the start of a video, so the first two frames are always included.
Usage: ig_board.py --workdir W --pending   (ALL pending posts: flagged + AUTO, in one go)   |   --batch 0 --size 5 (flagged only)   |   --codes A,B
Output: frames/<code>/_board.jpg + an OCR/subtitle/speech summary in the terminal. The reviewer (you or an agent) reads the boards visually.
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
    p.add_argument("--pending", action="store_true", help="All posts whose review is not finished (stage != done); AUTO included")
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
        print(f"pending review: {len(codes)} posts")
    else:
        todo = [c for c, v in sorted(posts.items(), key=lambda kv: kv[1].get("order", 0))
                if v.get("text_status") == "REVIEW" and v.get("frames")]
        codes = todo[args.batch * args.size:(args.batch + 1) * args.size]
        print(f"REVIEW remaining: {len(todo)}  this batch: {len(codes)}")
    for c in codes:
        v = posts[c]
        if not v.get("frames"):
            print("=====", c, "no frames")
            continue
        print(f"===== {c} @{v.get('account')} {v.get('type')} {round(v.get('duration') or 0)}s")
        if v.get("type") in ("Carousel", "Photo"):
            # carousel: every slide must be read, 6 slides per board, larger
            fr = v["frames"]
            for k in range(0, len(fr), 6):
                print("BOARD:", make_board(cd, c, fr[k:k + 6], cols=3, w=400, pick_all=True, name=f"_slides_{k // 6 + 1}.jpg"))
        else:
            print("BOARD:", make_board(cd, c, v["frames"]))
        print("CAPTION:", (v.get("caption") or "")[:160].replace("\n", " / "))
        print("OCR LEFT:", (v.get("screen_text") or "(empty)")[:500].replace("\n", " | "))
        print("COUNTED AS SUBTITLE:", " | ".join(v.get("subtitle_lines", []))[:200])
        flag = ""
        if v.get("speech_suspect"):
            flag = f"  [SUSPECT: may be song lyrics; audio={v.get('audio_type') or '?'} {v.get('music_title') or ''}]"
        print("SPEECH:", (v.get("speech_text") or "(none)")[:160].replace("\n", " ") + flag)


if __name__ == "__main__":
    main()
