#!/usr/bin/env python3
"""Reads on-screen text from frames with tesseract (bulk pass).

Each frame is read plain and, if needed, inverted (light text on dark background); the more confident result wins.
Lines repeated across frames are merged. If confidence is below the threshold or no text is found, the post is marked
'REVIEW': the reviewer (you or an agent) reads the contact sheet (post['sheet']) and corrects it with `ig_state.py set`.
"""
from __future__ import annotations

import csv
import difflib
import io
import re
import os
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

from ig_common import advance, base_parser, cache_dir, load_config, load_state, need_tool, save_state, workers

MIN_WORD_CONF = 30
UPSCALE_BELOW = int(os.environ.get("IG_OCR_UPSCALE_BELOW", 600))


def run_tsv(tess: str, img: Image.Image, lang: str):
    """Returns [(line_text, mean_line_confidence)]."""
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        img.save(tmp.name)
        r = subprocess.run([tess, tmp.name, "stdout", "-l", lang, "--psm", "6", "tsv"],
                           capture_output=True, text=True, env={**os.environ, "OMP_THREAD_LIMIT": "1"})
    rows = list(csv.DictReader(io.StringIO(r.stdout), delimiter="\t", quoting=csv.QUOTE_NONE))
    lines: dict = {}
    for row in rows:
        word = (row.get("text") or "").strip()
        try:
            conf = float(row.get("conf", -1))
        except ValueError:
            continue
        if not word or conf < 0:
            continue
        key = (row["block_num"], row["par_num"], row["line_num"])
        lines.setdefault(key, []).append((word, conf))
    out = []
    for ws in lines.values():
        text = " ".join(w for w, _ in ws)
        out.append((text, sum(c for _, c in ws) / len(ws)))
    return out


def looks_like_text(text: str, conf: float, min_conf: float) -> bool:
    """Filter noise: low confidence, few letters, single-character fragments."""
    letters = sum(ch.isalpha() for ch in text)
    words = [w for w in text.split() if sum(ch.isalpha() for ch in w) >= 2]
    return conf >= min_conf and letters >= 3 and letters / max(len(text.replace(" ", "")), 1) >= 0.6 and len(words) >= 1


def ocr_frame(tess: str, path: Path, lang: str, min_conf: float):
    """The plain frame is read first; the inverted one (light text on dark) only if the plain read is weak (roughly halves the work)."""
    img = Image.open(path).convert("L")
    if min(img.size) < UPSCALE_BELOW:  # 720x1280 video frames are not upscaled (2x upscaling made OCR ~3x slower)
        img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    plain = [(t, c) for t, c in run_tsv(tess, img, lang) if looks_like_text(t, c, min_conf)]
    if len(plain) >= 2 and sum(c for _, c in plain) / len(plain) >= 80:
        return plain  # strong enough: no need for the inverted pass
    inv = [(t, c) for t, c in run_tsv(tess, ImageOps.invert(img), lang) if looks_like_text(t, c, min_conf)]
    return max((plain, inv), key=lambda g: sum(c for _, c in g))


def _ocr_job(args):
    return ocr_frame(*args)


def norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


def merge_lines(frame_lines: list, min_frames: int) -> list:
    """frame_lines: [(text, confidence)] per frame. Similar lines are clustered; a cluster must appear in at least
    min_frames frames (on-screen text stays for a few seconds, texture noise stays in a single frame)."""
    clusters = []  # {"text","key","frames":set,"conf"}
    for fi, lines in enumerate(frame_lines):
        for text, conf in lines:
            k = norm(text)
            if len(k) < 3:
                continue
            for c in clusters:
                if k == c["key"] or difflib.SequenceMatcher(None, k, c["key"]).ratio() > 0.8:
                    c["frames"].add(fi)
                    if conf > c["conf"]:
                        c["text"], c["key"], c["conf"] = text, k, conf
                    break
            else:
                clusters.append({"text": text, "key": k, "frames": {fi}, "conf": conf})
    kept = [c for c in clusters if len(c["frames"]) >= min_frames]
    return kept


def main() -> None:
    p = base_parser(__doc__)
    args = p.parse_args()
    wd = Path(args.workdir)
    cfg, state = load_config(wd), load_state(wd)
    cd = cache_dir(args, wd, cfg)
    tess = need_tool("tesseract")
    min_conf = cfg["ocr_line_min_confidence"]

    with ProcessPoolExecutor(max_workers=workers(cfg)) as pool:  # frames in parallel; tesseract is single-threaded
        for code, post in state["posts"].items():
            if not post.get("frames") or "ocr_text" in post:
                continue
            jobs = [(tess, cd / rel, cfg["ocr_languages"], min_conf) for rel in post["frames"]]
            frame_lines = list(pool.map(_ocr_job, jobs, chunksize=4))
            kept = merge_lines(frame_lines, 2 if len(frame_lines) > cfg["ocr_persistence_above_frames"] else 1)
            merged = [c["text"] for c in kept]
            confs = [c["conf"] for c in kept]
            mean = round(sum(confs) / len(confs), 1) if confs else 0.0
            post["ocr_text"] = "\n".join(merged)
            post["ocr_confidence"] = mean
            if not merged:
                post["text_status"], post["review_reason"] = "REVIEW", "OCR empty: confirm there is really no text"
            elif mean < cfg["ocr_review_confidence"]:
                post["text_status"], post["review_reason"] = "REVIEW", f"low confidence {mean}"
            else:
                post["text_status"] = "AUTO"
            if post["text_status"] == "AUTO":
                post["screen_text"] = post["ocr_text"]
            advance(post, "ocr")
            save_state(wd, state)
            print(code, post["text_status"], mean, f"{len(merged)} lines", flush=True)


if __name__ == "__main__":
    main()
