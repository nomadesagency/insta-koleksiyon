#!/usr/bin/env python3
"""Saves the image URLs from ig_images_<code>.json files (taken from Chrome) as media/<code>/NN.jpg.

For carousel/photo posts (yt-dlp cannot download image posts). The JSON comes from the page via the clipboard
(SKILL.md step 3b: a button injected into the page, a real mouse click, then `pbpaste > <workdir>/ig_images_<code>.json`).
The URLs are signed, no cookies needed. Each processed JSON file is deleted.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from ig_common import advance, base_parser, cache_dir, load_state, save_state


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--downloads", help="Folder holding the ig_images_*.json files (default: the working folder)")
    args = p.parse_args()
    wd = Path(args.workdir)
    state = load_state(wd)
    cd = cache_dir(args, wd)

    for jf in sorted(Path(args.downloads or wd).expanduser().glob("ig_images_*.json")):
        data = json.loads(jf.read_text(encoding="utf-8"))
        code = data["code"]
        post = state["posts"].get(code)
        if not post:
            print("not in state, skipped:", code)
            continue
        out = cd / "media" / code
        out.mkdir(parents=True, exist_ok=True)
        files = []
        for i, url in enumerate(data["urls"], 1):
            dest = out / f"{i:02d}.jpg"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            dest.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            files.append(str(dest.relative_to(cd)))
        post["media"] = files
        for src, dst in (("caption", "caption"), ("handle", "account"), ("date_text", "date_text")):
            if data.get(src) and not post.get(dst):
                post[dst] = data[src]
        post["type"] = post.get("type") or ("Carousel" if len(files) > 1 else "Photo")
        post.pop("error", None)
        advance(post, "media")
        save_state(wd, state)
        jf.unlink()
        print(code, len(files), "images")


if __name__ == "__main__":
    main()
