#!/usr/bin/env python3
"""Extracts frames from videos (ffmpeg), drops near-duplicate frames (dHash), takes images as they are.

Output: frames/<code>/<name>_NNNN.jpg + post['frames']. Contact sheet for review: frames/<code>/_sheet.jpg
"""
from __future__ import annotations

import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

from ig_common import Saver, base_parser, cache_dir, load_config, load_state, need_tool, workers

VIDEO = {".mp4", ".mov", ".webm", ".mkv"}
IMAGE = {".jpg", ".jpeg", ".png", ".webp"}


def dhash(img: Image.Image, size: int = 8) -> int:
    g = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            bits = (bits << 1) | (px[row * (size + 1) + col] > px[row * (size + 1) + col + 1])
    return bits


def dedupe(files: list, max_dist: int) -> list:
    kept, hashes = [], []
    for f in files:
        h = dhash(Image.open(f))
        if all(bin(h ^ k).count("1") > max_dist for k in hashes):
            kept.append(f)
            hashes.append(h)
    return kept


def make_sheet(files: list, out: Path, thumb: int = 360, cols: int = 3) -> None:
    if not files:
        return
    imgs = []
    step = max(len(files) / 12, 1)  # 12 evenly spaced frames covering the whole duration
    for f in [files[int(i * step)] for i in range(min(12, len(files)))]:
        im = Image.open(f).convert("RGB")
        im.thumbnail((thumb, thumb * 2))
        imgs.append(im)
    w = max(i.width for i in imgs)
    h = max(i.height for i in imgs)
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "white")
    for n, im in enumerate(imgs):
        sheet.paste(im, ((n % cols) * w, (n // cols) * h))
    sheet.save(out, quality=85)


def build_frames(code: str, media: list, cd: str, ffmpeg: str, fps, dedupe_dist: int, cap: int, duration: float = 0, long_s: float = 0, fps_long=None):
    """Extracts the frames of one post (runs in a worker process). Returns (code, frame paths, contact sheet path)."""
    cd_p = Path(cd)
    fdir = cd_p / "frames" / code
    fdir.mkdir(parents=True, exist_ok=True)
    frames = []
    for rel in media:
        src = cd_p / rel
        if src.suffix.lower() in VIDEO:
            if long_s and fps_long and duration and duration > long_s:
                fps = fps_long  # half rate for long videos: on-screen text stays for seconds, OCR load is halved
            pattern = fdir / f"{src.stem}_%04d.jpg"
            subprocess.run([ffmpeg, "-v", "error", "-y", "-threads", "2", "-i", str(src), "-vf", f"fps={fps}",
                            "-q:v", "2", str(pattern)], check=False)
            frames += sorted(fdir.glob(f"{src.stem}_*.jpg"))
        elif src.suffix.lower() in IMAGE:
            frames.append(src)
    has_video = any((cd_p / r).suffix.lower() in VIDEO for r in media)
    if has_video:  # carousel/photo: every slide is separate content, no dedupe and no cap
        frames = dedupe(frames, dedupe_dist)
        if len(frames) > cap:  # sample evenly
            frames = [frames[int(i * len(frames) / cap)] for i in range(cap)]
    make_sheet(frames, fdir / "_sheet.jpg")
    return code, [str(f.relative_to(cd_p)) for f in frames], str((fdir / "_sheet.jpg").relative_to(cd_p))


def main() -> None:
    p = base_parser(__doc__)
    args = p.parse_args()
    wd = Path(args.workdir)
    cfg, state = load_config(wd), load_state(wd)
    cd = cache_dir(args, wd, cfg)
    ffmpeg = need_tool("ffmpeg")

    todo = [(c, v) for c, v in state["posts"].items() if v.get("media") and not v.get("frames")]
    with ProcessPoolExecutor(max_workers=max(workers(cfg) // 2, 2)) as pool, Saver(wd, state) as sv:  # ffmpeg is multi-threaded already
        futs = [pool.submit(build_frames, c, v["media"], str(cd), ffmpeg, cfg["frame_fps"],
                            cfg["frame_dedupe_distance"], cfg["max_frames"], v.get("duration") or 0,
                            cfg.get("long_video_seconds", 0), cfg.get("frame_fps_long")) for c, v in todo]
        for f in as_completed(futs):
            code, rels, sheet = f.result()
            post = state["posts"][code]
            post["frames"], post["sheet"] = rels, sheet
            sv.tick()
            print(code, len(rels), "frames", flush=True)


if __name__ == "__main__":
    main()
