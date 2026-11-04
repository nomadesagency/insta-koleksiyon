#!/usr/bin/env python3
"""Bir partiyi tek komutla hazırlar: yeni postları ekle -> meta + medya (paralel) -> kareler (paralel) -> OCR || konuşma -> altyazı ayıkla.

Sonunda inceleme bekleyen post sayısını yazar; sıradaki adım (inceleme): `ig_board.py --pending` panolarını okuyup `ig_apply.py` ile yazmak.

Kullanım:
  ig_run_batch.py --workdir W --feed ~/Desktop/insta-koleksiyon-cache/saved-feed.json --new 50
  (--new 0 ya da verilmezse: yeni eklemez, state'te bekleyen postları işler)

Aşamalar kendi içinde idempotenttir; yarıda kalırsa aynı komutu tekrar çalıştır. OCR ile konuşma aynı anda koşar
(state yazımı kilitli ve birleştirmelidir, birbirini ezmez). Medya süresi dolmuş/adresi olmayan reel'ler yt-dlp'ye düşer.
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
        sys.exit(f"HATA: {label} başarısız (çıkış {r.returncode})")
    return time.time() - t0


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workdir", required=True)
    p.add_argument("--cachedir")
    p.add_argument("--feed", required=True, help="Besleme dökümü (saved-feed.json)")
    p.add_argument("--new", type=int, default=0, help="State'e eklenecek yeni post sayısı (0 = ekleme)")
    args = p.parse_args()
    w = ["--workdir", args.workdir] + (["--cachedir", args.cachedir] if args.cachedir else [])
    t_all = time.time()
    times = {}

    if args.new:
        times["liste"] = run([str(HERE / "ig_state.py"), *w, "add-list", "--feed", args.feed, "--append-new", "--limit", str(args.new)], "liste")
    times["medya"] = run([str(HERE / "ig_import_feed.py"), *w, "--file", args.feed], "meta + medya (paralel)")
    times["yt-dlp yedek"] = run([str(HERE / "ig_download.py"), *w], "yt-dlp yedek (yalnız medyasız reel)")
    times["kareler"] = run([str(HERE / "ig_frames.py"), *w], "kareler (paralel)")

    t0 = time.time()
    print("== OCR || konuşma (aynı anda)", flush=True)
    procs = [subprocess.Popen([sys.executable, str(HERE / s), *w], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
             for s in ("ig_ocr.py", "ig_speech.py")]
    for pr in procs:
        out, _ = pr.communicate()
        if pr.returncode != 0:
            sys.exit(f"HATA: {pr.args[1]} başarısız:\n{out[-600:]}")
    times["OCR||konuşma"] = time.time() - t0
    times["altyazı"] = run([str(HERE / "ig_subtitles.py"), *w], "altyazı ayıkla")

    sys.path.insert(0, str(HERE))
    from ig_common import load_state  # noqa: E402
    posts = load_state(Path(args.workdir))["posts"]
    pend = [c for c, v in posts.items() if v.get("frames") and v.get("stage") != "done"]
    flagged = sum(1 for c in pend if posts[c].get("text_status") == "GÖZDEN GEÇİR")
    errs = [c for c, v in posts.items() if v.get("error") and not v.get("media")]
    print("\n--- süreler (sn): " + ", ".join(f"{k} {v:.0f}" for k, v in times.items()) + f", toplam {time.time() - t_all:.0f}")
    print(f"inceleme bekleyen: {len(pend)} (işaretli {flagged}, OTO {len(pend) - flagged}) | medyasız hata: {len(errs)} {errs[:5]}")
    print("sıradaki adım: ig_board.py --workdir W --pending  ->  panoları oku  ->  ig_apply.py")


if __name__ == "__main__":
    main()
