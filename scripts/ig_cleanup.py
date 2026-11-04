#!/usr/bin/env python3
"""Biten postların media/ ve frames/ klasörlerini siler; Excel + state.json yeterlidir (URL'ler duruyor).

Yalnız aşaması 'done' olan postlar silinir (varsayılan: kuru çalıştırma, --apply ile gerçekten siler).
Silinen post state'te `media_purged: true` alır; ig_download.py onu yeniden indirmez.
Hem --cachedir hem (eski kurulumdan kalan) --workdir altındaki media/frames temizlenir.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ig_common import base_parser, cache_dir, load_state, save_state


def tree_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.exists() else 0


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--apply", action="store_true", help="Gerçekten sil (yoksa yalnız rapor)")
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
            for k in ("frames", "sheet", "media"):  # state şişmesin: yolların işi bitti (5000 post ≈ MB düzeyi fark)
                post.pop(k, None)
    if args.apply:
        save_state(wd, state)
        for root in {cd, wd}:  # boşalan üst klasörleri toparla
            for sub in ("media", "frames"):
                d = root / sub
                if d.exists() and not any(d.iterdir()):
                    d.rmdir()
    print(f"{'silindi' if args.apply else 'silinecek (kuru çalıştırma)'}: {count} post, {total / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
