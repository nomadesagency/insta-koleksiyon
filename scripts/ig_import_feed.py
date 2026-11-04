#!/usr/bin/env python3
"""Imports meta + media (in parallel) from the Saved feed dump taken in Chrome (saved-feed.json).

Why: the feed API already returns each post's caption, account, date, audio type, direct video URL and carousel/photo
image URLs. Reel videos can be downloaded without yt-dlp, cookies or Keychain prompts, and in parallel (no 3-6 s wait per
post); image posts are not visited one by one. Fallback: ig_download.py (yt-dlp) for posts with no URL or an expired one.

File format (JSON array), output of the "Feed dump" snippet in chrome-snippets.md:
  {c: code, t: 1 photo | 2 video | 8 carousel, at: unix, u: account, cap: caption, d: duration, v: video URL, ha: has audio,
   au: audio type (original_sounds | licensed_music), mu: song title, s: [{t: slide type, i: image URL, v: slide video URL}]}
URLs are signed and expire (hours): take the dump shortly before downloading.

Usage: ig_import_feed.py --workdir W [--file saved-feed.json] [--codes A,B] [--no-media]   (default file: W/saved-feed.json)
Works only on posts that are in state and whose media is not downloaded yet. Idempotent.
"""
from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from ig_common import advance, base_parser, cache_dir, feed_path, load_config, load_state, save_state, workers

TYPE_NAME = {1: "Photo", 2: "Reel", 8: "Carousel"}


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    if tmp.stat().st_size == 0:
        raise OSError("empty file")
    tmp.replace(dest)


def fetch_post(code: str, row: dict, cd: Path):
    """Downloads the media of one post (in a thread). Returns (code, file list | None, error | None)."""
    out = cd / "media" / code
    out.mkdir(parents=True, exist_ok=True)
    t = row.get("t")
    items = []  # (URL, file name)
    if t == 2 and row.get("v"):
        items = [(row["v"], "01.mp4")]
    elif t in (1, 8):
        for i, s in enumerate(row.get("s") or [], 1):
            if s.get("t") == 2 and s.get("v"):
                items.append((s["v"], f"{i:02d}.mp4"))
            elif s.get("i"):
                items.append((s["i"], f"{i:02d}.jpg"))
    if not items:
        return code, None, "no downloadable URL in the dump"
    files = []
    for url, name in items:
        dest = out / name
        try:
            if not dest.exists() or dest.stat().st_size == 0:
                download(url, dest)
        except Exception as e:  # noqa: BLE001 - one failure must not stop the whole batch
            return code, None, f"download failed ({name}): {str(e)[:100]} (the URL may have expired: take a new dump)"
        files.append(str(dest.relative_to(cd)))
    return code, files, None


def apply_meta(post: dict, r: dict) -> None:
    if not post.get("caption") and r.get("cap"):
        post["caption"] = r["cap"]
    if not post.get("account") and r.get("u"):
        post["account"] = r["u"]
    if not post.get("date") and r.get("at"):
        post["date"] = datetime.fromtimestamp(r["at"], timezone.utc).strftime("%Y-%m-%d")
    post["type"] = post.get("type") or TYPE_NAME.get(r.get("t"), "")
    if r.get("d") and not post.get("duration"):
        post["duration"] = r["d"]
    if r.get("au"):
        post["audio_type"] = r["au"]
    if r.get("mu"):
        post["music_title"] = r["mu"]
    if r.get("ha") is not None:
        post["has_audio"] = bool(r["ha"])


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--file", help="Feed dump JSON (default: <workdir>/saved-feed.json)")
    p.add_argument("--codes", help="Only these codes (comma separated)")
    p.add_argument("--no-media", action="store_true", help="Meta only; do not download media")
    args = p.parse_args()
    wd = Path(args.workdir)
    cfg = load_config(wd)
    cd = cache_dir(args, wd, cfg)
    state = load_state(wd)
    feed = {r["c"]: r for r in json.loads(feed_path(wd, args.file).read_text(encoding="utf-8"))}
    only = set(args.codes.split(",")) if args.codes else None

    todo = []
    meta = 0
    for code, post in state["posts"].items():
        r = feed.get(code)
        if not r or (only and code not in only) or post.get("media_purged"):
            continue
        apply_meta(post, r)
        meta += 1
        if not args.no_media and not post.get("media"):
            todo.append((code, r))
    save_state(wd, state)

    ok = failed = 0
    with ThreadPoolExecutor(max_workers=min(workers(cfg) * 2, 12)) as pool:  # network-bound work: more threads than cores
        futs = [pool.submit(fetch_post, c, r, cd) for c, r in todo]
        for f in as_completed(futs):
            code, files, err = f.result()
            post = state["posts"][code]
            if files:
                post["media"] = sorted(files)
                post.pop("error", None)
                advance(post, "media")
                ok += 1
            else:
                post["error"] = err
                failed += 1
            save_state(wd, state)
    print(f"meta={meta} media_downloaded={ok} errors={failed}" + ("  (use ig_download.py as the fallback for failures)" if failed else ""))


if __name__ == "__main__":
    main()
