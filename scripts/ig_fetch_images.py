#!/usr/bin/env python3
"""Chrome'dan indirilen ig_images_<kod>.json dosyalarındaki görsel URL'lerini media/<kod>/NN.jpg olarak kaydeder.

Carousel/foto postlar için (yt-dlp resimli postu indiremez). JSON'u Chrome sayfa içinden bir Blob olarak indirir
(SKILL.md adım 3b; Blob indirmesi engelliyse sayfadaki bir düğmeyi gerçek tıklamayla çalıştırıp JSON'u panoya yazdır, `pbpaste > ~/Downloads/ig_images_<kod>.json`); URL'ler imzalıdır, çerez gerekmez. İşlenen JSON dosyası silinir.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from ig_common import advance, base_parser, cache_dir, load_state, save_state


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--downloads", default=str(Path.home() / "Downloads"))
    args = p.parse_args()
    wd = Path(args.workdir)
    state = load_state(wd)
    cd = cache_dir(args, wd)

    for jf in sorted(Path(args.downloads).glob("ig_images_*.json")):
        data = json.loads(jf.read_text(encoding="utf-8"))
        code = data["code"]
        post = state["posts"].get(code)
        if not post:
            print("state'te yok, atlandı:", code)
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
        post["type"] = post.get("type") or ("Carousel" if len(files) > 1 else "Foto")
        post.pop("error", None)
        advance(post, "media")
        save_state(wd, state)
        jf.unlink()
        print(code, len(files), "görsel")


if __name__ == "__main__":
    main()
