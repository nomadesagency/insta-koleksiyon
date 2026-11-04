#!/usr/bin/env python3
"""state.json yönetimi.

Alt komutlar:
  add-list  --file urls.json        Chrome'dan toplanan URL listesini ekler (JSON dizi, Instagram sırasıyla)
  set       --code X --json '{...}' Bir postun alanlarını günceller (meta, kategori, düzeltilmiş metin...)
  show      [--code X]              Özet veya tek post
  review    Gözden geçirilecek postları listeler (kare kontak sayfası yoluyla)
"""
from __future__ import annotations

import json
from pathlib import Path

from ig_common import advance, base_parser, load_state, save_state, shortcode


def main() -> None:
    p = base_parser(__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add-list")
    a.add_argument("--file", help="URL listesi JSON (dizi)")
    a.add_argument("--feed", help="Besleme dökümü JSON (saved-feed.json); URL'ler kodlardan üretilir")
    a.add_argument("--limit", type=int, default=0, help="Yalnız ilk N (pilot); --append-new ile: eklenecek en çok N YENİ post")
    a.add_argument("--append-new", action="store_true",
                   help="Yalnız state'te olmayan kodları ekle, sırayı mevcut en büyük order'dan sürdür; mevcut hiçbir order değişmez")
    s = sub.add_parser("set")
    s.add_argument("--code", required=True)
    s.add_argument("--json", required=True)
    sh = sub.add_parser("show")
    sh.add_argument("--code")
    sub.add_parser("review")
    args = p.parse_args()

    wd = Path(args.workdir)
    wd.mkdir(parents=True, exist_ok=True)
    state = load_state(wd)
    posts = state["posts"]

    if args.cmd == "add-list":
        if args.feed:
            urls = [f"https://www.instagram.com/p/{r['c']}/" for r in json.loads(Path(args.feed).read_text(encoding="utf-8"))]
        elif args.file:
            urls = json.loads(Path(args.file).read_text(encoding="utf-8"))
        else:
            raise SystemExit("--file veya --feed gerekli")
        if args.append_new:
            top = max((v.get("order", 0) for v in posts.values()), default=0)
            fresh = [u for u in urls if shortcode(u) not in posts]
            fresh = list(dict.fromkeys(fresh))[: args.limit or None]
            for k, url in enumerate(fresh, 1):
                posts[shortcode(url)] = {"url": url.split("?")[0], "order": top + k, "stage": "listed"}
            save_state(wd, state)
            print(f"{len(fresh)} yeni post eklendi (order {top + 1}-{top + len(fresh)}), toplam {len(posts)}")
            return
        if args.limit:
            urls = urls[: args.limit]
        added = 0
        for i, url in enumerate(urls, 1):
            code = shortcode(url)
            if code not in posts:
                posts[code] = {"url": url.split("?")[0], "order": i, "stage": "listed"}
                added += 1
            else:
                posts[code]["order"] = i  # liste sırası değişmiş olabilir (yeni kaydedilenler başa gelir)
        save_state(wd, state)
        print(f"{added} yeni post eklendi, toplam {len(posts)}")

    elif args.cmd == "set":
        post = posts[args.code]
        patch = json.loads(args.json)
        stage = patch.pop("_stage", None)
        post.update(patch)
        if stage:
            advance(post, stage)
        save_state(wd, state)
        print("güncellendi:", args.code)

    elif args.cmd == "show":
        if args.code:
            print(json.dumps(posts[args.code], ensure_ascii=False, indent=1))
        else:
            counts: dict = {}
            for v in posts.values():
                counts[v.get("stage", "?")] = counts.get(v.get("stage", "?"), 0) + 1
            print(json.dumps(counts, ensure_ascii=False), f"toplam={len(posts)}")

    elif args.cmd == "review":
        for code, v in posts.items():
            if v.get("text_status") == "GÖZDEN GEÇİR":
                print(code, v.get("sheet", ""), v.get("review_reason", ""))


if __name__ == "__main__":
    main()
