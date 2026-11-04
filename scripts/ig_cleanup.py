#!/usr/bin/env python3
"""Deletes the media/ and frames/ folders of finished posts; the spreadsheet + state.json are enough (URLs remain).

Only posts at stage 'done' are deleted (default: dry run, --apply actually deletes).
A deleted post gets `media_purged: true` in state; ig_download.py does not download it again.
media/frames under both --cachedir and (left over from an older setup) --workdir are cleaned.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ig_common import base_parser, cache_dir, load_state, save_state


def tree_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.exists() else 0


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--apply", action="store_true", help="Really delete (otherwise report only)")
    args = p.parse_args()
    wd = Path(args.workdir)
    cd = cache_dir(args, wd)
    state = load_state(wd)

    total, count = 0, 0
    for code, post in state["posts"].items():
        if post.get("stage") != "done":
            continue
        targets = [root / sub / code for root in {cd, wd} for sub in ("media", "frames")]
        existing = [t for t in targets if t.exists()]
        if not existing and post.get("media_purged"):
            if args.apply:
                for k in ("frames", "sheet", "media"):
                    post.pop(k, None)
            continue
        total += sum(tree_size(t) for t in existing)
        count += 1
        if args.apply:
            for t in existing:
                shutil.rmtree(t)
            post["media_purged"] = True
            for k in ("frames", "sheet", "media"):  # keep state small: the paths are no longer needed (MBs over 5000 posts)
                post.pop(k, None)
    if args.apply:
        save_state(wd, state)
        for root in {cd, wd}:  # remove parent folders that are now empty
            for sub in ("media", "frames"):
                d = root / sub
                if d.exists() and not any(d.iterdir()):
                    d.rmdir()
    print(f"{'deleted' if args.apply else 'would delete (dry run)'}: {count} posts, {total / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
