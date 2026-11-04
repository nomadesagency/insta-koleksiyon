#!/usr/bin/env python3
"""Postların medyasını yt-dlp ile indirir (tarayıcı çerezleriyle). İdempotent: media/<kod>/ doluysa atlar.

İndiremeyen post `error` alanıyla işaretlenir; yedek yol: Chrome'da ekran görüntüsü (SKILL.md).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ig_common import advance, base_parser, cache_dir, load_config, load_state, need_tool, polite_sleep, save_state

MEDIA_EXT = {".mp4", ".mov", ".webm", ".mkv", ".jpg", ".jpeg", ".png", ".webp"}


def fill_meta(post: dict, out_dir: Path) -> None:
    """yt-dlp bilgi dosyasından açıklama/hesap/tarih/süre; Chrome'dan gelen değerleri ezmez."""
    infos = sorted(out_dir.glob("*.info.json"))
    if not infos:
        return
    info = json.loads(infos[0].read_text(encoding="utf-8"))
    d = info.get("upload_date") or ""
    fields = {
        "caption": info.get("description"),
        "account": info.get("channel") or info.get("uploader"),  # uploader_id sayısal ID'dir, kullanılmaz
        "date": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else None,
        "type": "Reel" if info.get("duration") else None,
        "duration": info.get("duration"),
    }
    for k, v in fields.items():
        if v and not post.get(k):
            post[k] = v


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--code", help="Yalnız bu post")
    p.add_argument("--force", action="store_true", help="Carousel/foto postları da yt-dlp ile dene")
    args = p.parse_args()
    wd = Path(args.workdir)
    cfg, state = load_config(wd), load_state(wd)
    cd = cache_dir(args, wd, cfg)
    ytdlp = need_tool("yt-dlp")

    done = failed = 0
    for code, post in state["posts"].items():
        if args.code and code != args.code:
            continue
        if post.get("media_purged"):  # ig_cleanup.py ile bilerek silindi, yeniden indirilmez
            continue
        if post.get("type") in ("Carousel", "Foto") and not args.force:  # yt-dlp resimli postu indiremez (ig_import_feed.py)
            continue
        out_dir = cd / "media" / code
        existing = [f for f in out_dir.glob("*") if f.suffix.lower() in MEDIA_EXT] if out_dir.exists() else []
        if existing:
            fill_meta(post, out_dir)
            post["media"] = sorted(str(f.relative_to(cd)) for f in existing)
            advance(post, "media")
            save_state(wd, state)
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [ytdlp, "--cookies-from-browser", cfg["browser_for_cookies"], "--no-progress", "--write-info-json",
               "-o", str(out_dir / "%(autonumber)02d.%(ext)s"), post["url"]]
        r = subprocess.run(cmd, capture_output=True, text=True)
        files = [f for f in out_dir.glob("*") if f.suffix.lower() in MEDIA_EXT]
        if r.returncode != 0 or not files:
            post["error"] = (r.stderr.strip().splitlines() or ["indirilemedi"])[-1][:300]
            failed += 1
        else:
            post.pop("error", None)
            fill_meta(post, out_dir)
            post["media"] = sorted(str(f.relative_to(cd)) for f in files)
            advance(post, "media")
            done += 1
        save_state(wd, state)
        polite_sleep(cfg)
    print(f"indirildi={done} hata={failed}")


if __name__ == "__main__":
    main()
