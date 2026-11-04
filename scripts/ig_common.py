"""Shared helpers: config, state.json (atomic write + verification), taxonomy, PATH.

Holds no personal data. Every file (state.json, config, JSON dumps, spreadsheet, media/, frames/) is written to the
working folder given with --workdir. --cachedir is an optional override for the heavy media/ and frames/ folders only.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import json
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
_MISSING = object()
STAGES = ["listed", "meta", "media", "ocr", "reviewed", "done"]
# Homebrew may be missing from PATH in cron/non-login shells
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")


def base_parser(desc: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--workdir", required=True, help="Private working folder (state.json, config.json, spreadsheet)")
    p.add_argument("--cachedir", help="Optional: put media/ and frames/ somewhere else (default: config cache_dir, "
                   "otherwise the working folder)")
    return p


def cache_dir(args, workdir: Path, cfg: dict | None = None) -> Path:
    """Root of the heavy files (media/, frames/). Priority: --cachedir > config cache_dir > the working folder."""
    cfg = cfg if cfg is not None else load_config(workdir)
    raw = args.cachedir or cfg.get("cache_dir") or str(workdir)
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(workdir: Path) -> dict:
    cfg = load_json(SKILL_DIR / "config.example.json", {})
    cfg.update(load_json(workdir / "config.json", {}) or {})
    return cfg


def load_taxonomy(workdir: Path) -> dict:
    """A taxonomy.json in the working folder overrides the default."""
    custom = workdir / "taxonomy.json"
    return load_json(custom if custom.exists() else SKILL_DIR / "taxonomy.default.json")


def feed_path(workdir: Path, given: str | None) -> Path:
    """The feed dump: the given path, otherwise <workdir>/saved-feed.json."""
    return Path(given).expanduser() if given else workdir / "saved-feed.json"


def state_path(workdir: Path) -> Path:
    return workdir / "state.json"


class State(dict):
    """Contents of state.json + a snapshot taken at load time (save_state writes only what CHANGED)."""
    _snap: dict = {}


def _read_state(workdir: Path) -> dict:
    return load_json(state_path(workdir), {"posts": {}})


def load_state(workdir: Path) -> State:
    st = State(_read_state(workdir))
    st._snap = copy.deepcopy(dict(st))
    return st


def save_state(workdir: Path, state: dict) -> None:
    """Merging, locked, atomic write.

    Under a file lock the current state on disk is read; only the fields CHANGED by this process (relative to load time)
    are written on top of it. Two scripts running at the same time (e.g. OCR + speech) therefore never overwrite each
    other's fields (e.g. a field written by hand while a chain is running is not lost). The file is read back and checked.
    """
    snap = getattr(state, "_snap", {}).get("posts", {})
    path = state_path(workdir)
    lock = path.with_suffix(".lock")
    with open(lock, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        disk = _read_state(workdir)
        dposts = disk.setdefault("posts", {})
        for code, post in state["posts"].items():
            base = snap.get(code)
            if base is None:  # post added by this process
                dposts[code] = copy.deepcopy(post)
                continue
            target = dposts.setdefault(code, {})
            for k, v in post.items():
                if base.get(k, _MISSING) != v:
                    target[k] = copy.deepcopy(v)
            for k in base:
                if k not in post:
                    target.pop(k, None)
        for k, v in state.items():
            if k != "posts":
                disk[k] = v
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(disk, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        back = json.loads(path.read_text(encoding="utf-8"))
        if len(back.get("posts", {})) != len(disk["posts"]):
            raise RuntimeError("state.json write check failed (record count does not match)")
        state._snap = copy.deepcopy({"posts": {c: copy.deepcopy(p) for c, p in state["posts"].items()}})
        # fields added on disk by others are not in memory; keep the snapshot consistent with the in-memory state
        for c, p in back["posts"].items():
            if c not in state["posts"]:
                state["posts"][c] = copy.deepcopy(p)
                state._snap["posts"][c] = copy.deepcopy(p)


class Saver:
    """Throttled save_state: writes at most every `every` seconds, and always on exit (also after an error).

    Saving the whole state.json after every post is slow on big archives (≈0.3 s per save at 5000 posts, ≈12 min
    per 500-post batch). Use:  with Saver(wd, state) as sv: ... sv.tick()  (env IG_SAVE_EVERY overrides the interval).
    """

    def __init__(self, workdir: Path, state: dict, every: float | None = None):
        self.wd, self.state = workdir, state
        self.every = float(os.environ.get("IG_SAVE_EVERY", 20)) if every is None else every
        self.last, self.dirty = time.time(), False

    def tick(self) -> None:
        self.dirty = True
        if time.time() - self.last >= self.every:
            self.flush()

    def flush(self) -> None:
        if self.dirty:
            save_state(self.wd, self.state)
            self.dirty = False
        self.last = time.time()

    def __enter__(self) -> "Saver":
        return self

    def __exit__(self, *exc) -> None:
        self.flush()


def shortcode(url: str) -> str:
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", url)
    if not m:
        raise ValueError(f"Post URL not recognised: {url}")
    return m.group(1)


def polite_sleep(cfg: dict) -> None:
    lo, hi = cfg.get("delay_seconds", [3, 6])
    time.sleep(random.uniform(lo, hi))


def need_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"ERROR: '{name}' is not installed (see README -> Requirements).")
    return path


def advance(post: dict, stage: str) -> None:
    """Moves the stage forward only, never back."""
    if STAGES.index(stage) > STAGES.index(post.get("stage", "listed")):
        post["stage"] = stage


def workers(cfg: dict | None = None) -> int:
    """Number of parallel workers: config 'workers' or (CPU cores - 2), at least 2."""
    n = (cfg or {}).get("workers") or max((os.cpu_count() or 4) - 2, 2)
    return int(n)
