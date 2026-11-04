#!/usr/bin/env python3
"""Turu bitirir: Excel'i üret -> state ile doğrula -> BAŞARILIYSA media/ ve frames/ klasörlerini sil.

Başarısız olursa hiçbir şey silinmez (inceleme eksik, Excel state ile tutmuyor, kategori liste dışı...). Silinen post
`media_purged: true` alır; yeniden indirilmez. Yalnız aşaması `done` olan postlar silinir.

Kullanım:  ig_finish_batch.py --workdir W
Önbellek konumu: --cachedir > config cache_dir > ~/Desktop/insta-koleksiyon-cache (çalışma alanı dışında).
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
        sys.exit(f"DURDU: {label} başarısız, hiçbir şey silinmedi.")


def main() -> None:
    p = base_parser(__doc__)
    args = p.parse_args()
    wd = Path(args.workdir)
    cd = cache_dir(args, wd, load_config(wd))
    w = ["--workdir", args.workdir, "--cachedir", str(cd)]

    posts = load_state(wd)["posts"]
    pending = [c for c, v in posts.items() if v.get("stage") != "done"]
    if pending:
        sys.exit(f"DURDU: {len(pending)} post henüz `done` değil (inceleme/kategori eksik): {pending[:5]}. Hiçbir şey silinmedi.")

    sh("Excel üret", [str(HERE / "build_xlsx.py"), "--workdir", args.workdir])
    sh("Excel ↔ state doğrula", [str(HERE / "verify_xlsx.py"), "--workdir", args.workdir])
    sh("medya + kare temizliği", [str(HERE / "ig_cleanup.py"), *w, "--apply"])
    print(f"önbellek ({cd}) boşaltıldı; kalıcı çıktı yalnız Excel + state.json.")


if __name__ == "__main__":
    main()
