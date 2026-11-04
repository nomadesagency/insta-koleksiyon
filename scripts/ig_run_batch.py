#!/usr/bin/env python3
"""Prepares a batch with one command: add new posts -> meta + media (parallel) -> frames (parallel) -> OCR || speech -> strip subtitles.

At the end it prints how many posts await review; next step (review): read the `ig_board.py --pending` boards and write the results with `ig_apply.py`.

Usage:
  ig_run_batch.py --workdir W --new 50          (the feed dump is read from W/saved-feed.json; --feed for another path)
  (--new 0 or omitted: adds nothing, processes posts already pending in state)

Each stage is idempotent; if interrupted, run the same command again. OCR and speech run at the same time
(state writes are locked and merging, they do not overwrite each other). Reels whose URL is missing or expired fall back to yt-dlp.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd: list, label: str, log: Path | None = None) -> float:
    t0 = time.time()
    print(f"== {label}", flush=True)
    r = subprocess.run([sys.executable, *cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = [ln for ln in r.stdout.splitlines() if "Warning" not in ln and "mel_spec" not in ln]
    print("\n".join(out[-4:]), flush=True)
    if log:
        log.write_text(r.stdout, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"ERROR: {label} failed (exit {r.returncode})")
    return time.time() - t0


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workdir", required=True)
    p.add_argument("--cachedir")
    p.add_argument("--feed", help="Feed dump (default: <workdir>/saved-feed.json)")
    p.add_argument("--new", type=int, default=0, help="Number of new posts to add to state (0 = none)")
    args = p.parse_args()
    feed = str(Path(args.feed).expanduser()) if args.feed else str(Path(args.workdir) / "saved-feed.json")
    if not Path(feed).exists():
        sys.exit(f"ERROR: feed dump not found: {feed} (chrome-snippets.md snippets 1 + 2)")
    w = ["--workdir", args.workdir] + (["--cachedir", args.cachedir] if args.cachedir else [])
    t_all = time.time()
    times = {}

    if args.new:
        times["list"] = run([str(HERE / "ig_state.py"), *w, "add-list", "--feed", feed, "--append-new", "--limit", str(args.new)], "list")
    times["media"] = run([str(HERE / "ig_import_feed.py"), *w, "--file", feed], "meta + media (parallel)")
    times["yt-dlp fallback"] = run([str(HERE / "ig_download.py"), *w], "yt-dlp fallback (reels without media only)")
    times["frames"] = run([str(HERE / "ig_frames.py"), *w], "frames (parallel)")

    t0 = time.time()
    print("== OCR || speech (at the same time)", flush=True)
    procs = [subprocess.Popen([sys.executable, str(HERE / s), *w], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
             for s in ("ig_ocr.py", "ig_speech.py")]
    for pr in procs:
        out, _ = pr.communicate()
        if pr.returncode != 0:
            sys.exit(f"ERROR: {pr.args[1]} failed:\n{out[-600:]}")
    times["OCR||speech"] = time.time() - t0
    times["subtitles"] = run([str(HERE / "ig_subtitles.py"), *w], "strip subtitles")

    sys.path.insert(0, str(HERE))
    from ig_common import load_state  # noqa: E402
    posts = load_state(Path(args.workdir))["posts"]
    pend = [c for c, v in posts.items() if v.get("frames") and v.get("stage") != "done"]
    flagged = sum(1 for c in pend if posts[c].get("text_status") == "REVIEW")
    errs = [c for c, v in posts.items() if v.get("error") and not v.get("media")]
    print("\n--- durations (s): " + ", ".join(f"{k} {v:.0f}" for k, v in times.items()) + f", total {time.time() - t_all:.0f}")
    print(f"pending review: {len(pend)} (flagged {flagged}, AUTO {len(pend) - flagged}) | errors without media: {len(errs)} {errs[:5]}")
    print("next step: ig_board.py --workdir W --pending  ->  read the boards  ->  ig_apply.py")


if __name__ == "__main__":
    main()
