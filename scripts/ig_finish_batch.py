#!/usr/bin/env python3
"""Finishes a batch: build the spreadsheet -> verify it against state -> IF SUCCESSFUL delete the media/ and frames/ folders.

On failure nothing is deleted (review incomplete, spreadsheet does not match state, category outside the list...).
A deleted post gets `media_purged: true` and is not downloaded again. Only posts at stage `done` are deleted.

Usage:  ig_finish_batch.py --workdir W
Cache location: --cachedir > config cache_dir > ~/Desktop/insta-koleksiyon-cache (outside the working folder).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ig_common import base_parser, cache_dir, load_config, load_state

HERE = Path(__file__).resolve().parent


def sh(label: str, cmd: list) -> None:
    print(f"== {label}", flush=True)
    r = subprocess.run([sys.executable, *cmd], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else "", flush=True)
    if r.returncode != 0:
        print((r.stdout + r.stderr).strip(), file=sys.stderr)
        sys.exit(f"STOPPED: {label} failed, nothing was deleted.")


def main() -> None:
    p = base_parser(__doc__)
    args = p.parse_args()
    wd = Path(args.workdir)
    cd = cache_dir(args, wd, load_config(wd))
    w = ["--workdir", args.workdir, "--cachedir", str(cd)]

    posts = load_state(wd)["posts"]
    pending = [c for c, v in posts.items() if v.get("stage") != "done"]
    if pending:
        sys.exit(f"STOPPED: {len(pending)} posts are not `done` yet (review/category missing): {pending[:5]}. Nothing was deleted.")

    sh("build spreadsheet", [str(HERE / "build_xlsx.py"), "--workdir", args.workdir])
    sh("verify spreadsheet ↔ state", [str(HERE / "verify_xlsx.py"), "--workdir", args.workdir])
    sh("clean media + frames", [str(HERE / "ig_cleanup.py"), *w, "--apply"])
    print(f"cache ({cd}) emptied; the only permanent output is the spreadsheet + state.json.")


if __name__ == "__main__":
    main()
