#!/usr/bin/env python3
"""Audio track + speech detection; a Whisper (faster-whisper) transcript when there is speech.

Music-only videos: if the VAD filter finds no speech segment, the post counts as 'no speech'.
Only posts with video media are processed.
"""
from __future__ import annotations

import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from ig_common import base_parser, cache_dir, load_config, load_state, need_tool, save_state, workers

VIDEO = {".mp4", ".mov", ".webm", ".mkv"}


def mean_volume_db(ffmpeg: str, path: Path):
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"],
                       capture_output=True, text=True)
    if "Audio:" not in r.stderr:
        return None
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


_MODEL = None


def _init_worker(model_name: str, threads: int) -> None:
    global _MODEL
    from faster_whisper import WhisperModel  # late import: fails only here if not installed
    _MODEL = WhisperModel(model_name, compute_type="int8", cpu_threads=threads)


def analyze(code: str, video: str, ffmpeg: str, cfg: dict, duration: float, audio_type):
    """Analyses the audio of one post (in a worker process). Returns (code, fields dict, mean volume dB)."""
    path = Path(video)
    vol = mean_volume_db(ffmpeg, path)
    if vol is None or vol < cfg["audio_min_mean_volume_db"]:
        return code, {"has_speech": False, "speech_text": ""}, vol
    segs, info = _MODEL.transcribe(str(path), vad_filter=True, beam_size=cfg.get("speech_beam_size", 1),
                                   condition_on_previous_text=False)
    segs = list(segs)
    text = " ".join(s.text.strip() for s in segs).strip()
    has = len(text) >= cfg["speech_min_chars"]
    # Song-lyrics false alarm (14 of 57 posts in a test run): flagged 'suspect' if the audio type is licensed music,
    # language confidence is low, or speech covers only a small part of the video; the review board shows the flag.
    # (The licensed-music label alone is NOT a reason to drop speech: some posts have real voice-over on top of music.)
    spoken = sum(s.end - s.start for s in segs)
    suspect = bool(has and (audio_type == "licensed_music" or info.language_probability < 0.6
                            or (duration and spoken / duration < 0.3)))
    return code, {"has_speech": has, "speech_text": text if has else "", "speech_suspect": suspect}, vol


def main() -> None:
    p = base_parser(__doc__)
    args = p.parse_args()
    wd = Path(args.workdir)
    cfg, state = load_config(wd), load_state(wd)
    cd = cache_dir(args, wd, cfg)
    ffmpeg = need_tool("ffmpeg")

    jobs = []
    for code, post in state["posts"].items():
        if "speech_text" in post:
            continue
        videos = [cd / r for r in post.get("media", []) if (cd / r).suffix.lower() in VIDEO]
        if not videos:
            post["has_speech"], post["speech_text"] = False, ""
            continue
        jobs.append((code, str(videos[0]), post.get("duration") or 0, post.get("audio_type")))
    save_state(wd, state)

    # Whisper does not scale with more threads: a few processes x few threads is faster
    n = max(min(cfg.get("speech_workers", 3), len(jobs)), 1)
    threads = max((workers(cfg) + 2) // n, 2)
    with ProcessPoolExecutor(max_workers=n, initializer=_init_worker, initargs=(cfg["speech_model"], threads)) as pool:
        futs = [pool.submit(analyze, c, v, ffmpeg, cfg, d, au) for c, v, d, au in jobs]
        for f in as_completed(futs):
            code, fields, vol = f.result()
            state["posts"][code].update(fields)
            save_state(wd, state)
            print(code, "speech" if fields["has_speech"] else "no speech", vol, flush=True)


if __name__ == "__main__":
    main()
