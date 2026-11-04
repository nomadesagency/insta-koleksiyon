#!/usr/bin/env python3
"""state.json management.

Subcommands:
  add-list  --file urls.json | --feed saved-feed.json   Adds a URL list collected in Chrome (JSON array, Instagram order)
  set       --code X --json '{...}'                      Updates the fields of one post (meta, category, corrected text...)
  show      [--code X]                                   Summary or a single post
  review    Lists posts that need review (with their contact sheet path)
  stop-codes                                             Prints a JS line for an incremental dump (chrome-snippets.md snippet 1):
                                                         the dump stops at the first page that contains a post seen in the last dump
"""
from __future__ import annotations

import json
from pathlib import Path

from ig_common import advance, base_parser, load_state, save_state, shortcode


def main() -> None:
    p = base_parser(__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add-list")
    a.add_argument("--file", help="URL list JSON (array)")
    a.add_argument("--feed", help="Feed dump JSON (saved-feed.json); URLs are built from the codes")
    a.add_argument("--limit", type=int, default=0, help="Only the first N (pilot); with --append-new: add at most N NEW posts")
    a.add_argument("--append-new", action="store_true",
                   help="Add only codes not in state, continue numbering from the current highest order; no existing order changes")
    s = sub.add_parser("set")
    s.add_argument("--code", required=True)
    s.add_argument("--json", required=True)
    sh = sub.add_parser("show")
    sh.add_argument("--code")
    sub.add_parser("review")
    sub.add_parser("stop-codes")
    args = p.parse_args()

    wd = Path(args.workdir)
    wd.mkdir(parents=True, exist_ok=True)
    state = load_state(wd)
    posts = state["posts"]

    if args.cmd == "add-list":
        if args.feed:
            rows = json.loads(Path(args.feed).read_text(encoding="utf-8"))
            urls = [f"https://www.instagram.com/p/{r['c']}/" for r in rows]
            if rows:  # the newest saved posts of this dump: the next incremental dump can stop when it reaches them
                state["feed_head"] = [r["c"] for r in rows[:30]]
        elif args.file:
            urls = json.loads(Path(args.file).read_text(encoding="utf-8"))
        else:
            raise SystemExit("--file or --feed is required")
        if args.append_new:
            top = max((v.get("order", 0) for v in posts.values()), default=0)
            fresh = [u for u in urls if shortcode(u) not in posts]
            fresh = list(dict.fromkeys(fresh))[: args.limit or None]
            for k, url in enumerate(fresh, 1):
                posts[shortcode(url)] = {"url": url.split("?")[0], "order": top + k, "stage": "listed"}
            save_state(wd, state)
            print(f"{len(fresh)} new posts added (order {top + 1}-{top + len(fresh)}), total {len(posts)}")
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
                posts[code]["order"] = i  # list order may have changed (newly saved posts go to the top)
        save_state(wd, state)
        print(f"{added} new posts added, total {len(posts)}")

    elif args.cmd == "set":
        post = posts[args.code]
        patch = json.loads(args.json)
        stage = patch.pop("_stage", None)
        post.update(patch)
        if stage:
            advance(post, stage)
        save_state(wd, state)
        print("updated:", args.code)

    elif args.cmd == "show":
        if args.code:
            print(json.dumps(posts[args.code], ensure_ascii=False, indent=1))
        else:
            counts: dict = {}
            for v in posts.values():
                counts[v.get("stage", "?")] = counts.get(v.get("stage", "?"), 0) + 1
            print(json.dumps(counts, ensure_ascii=False), f"total={len(posts)}")

    elif args.cmd == "stop-codes":
        head = state.get("feed_head")
        if not head:
            raise SystemExit("No feed_head in state yet: do one full dump + add-list --feed first.")
        print("window.__stop=new Set(" + json.dumps(head) + ");")

    elif args.cmd == "review":
        for code, v in posts.items():
            if v.get("text_status") == "REVIEW":
                print(code, v.get("sheet", ""), v.get("review_reason", ""))


if __name__ == "__main__":
    main()
