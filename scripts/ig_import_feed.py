#!/usr/bin/env python3
"""Chrome'dan alınan kaydedilenler akışı dökümünden (saved-feed.json) meta + medya içe aktarır (paralel).

Neden: akış API'si her postun açıklamasını, hesabını, tarihini, ses türünü, doğrudan video adresini ve carousel/foto görsel
adreslerini zaten verir. Reel videoları yt-dlp'siz, çerezsiz, Anahtar Zinciri izinsiz ve paralel inebilir (post başı 3-6 sn bekleme
yok); resimli postlar tek tek gezilmez. Yedek yol: ig_download.py (yt-dlp), dökümde adresi olmayan/süresi dolan postlar için.

Dosya biçimi (JSON dizi), chrome-snippets.md "Besleme dökümü" parçasının çıktısı:
  {c: kod, t: 1 foto | 2 video | 8 carousel, at: unix, u: hesap, cap: açıklama, d: süre, v: video URL, ha: ses var mı,
   au: ses türü (original_sounds | licensed_music), mu: şarkı adı, s: [{t: slayt türü, i: görsel URL, v: slayt video URL}]}
Adresler imzalıdır ve süresi dolar (saatler): dökümü indirmeden kısa süre önce al.

Kullanım: ig_import_feed.py --workdir W --file saved-feed.json [--codes A,B] [--no-media]
Yalnız state'te olan, medyası henüz inmemiş postlar için çalışır. İdempotenttir.
"""
from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from ig_common import advance, base_parser, cache_dir, load_config, load_state, save_state, workers

TYPE_NAME = {1: "Foto", 2: "Reel", 8: "Carousel"}


def download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    if tmp.stat().st_size == 0:
        raise OSError("boş dosya")
    tmp.replace(dest)


def fetch_post(code: str, row: dict, cd: Path):
    """Bir postun medyasını indirir (iş parçacığında). (kod, dosya listesi | None, hata | None) döndürür."""
    out = cd / "media" / code
    out.mkdir(parents=True, exist_ok=True)
    t = row.get("t")
    items = []  # (URL, dosya adı)
    if t == 2 and row.get("v"):
        items = [(row["v"], "01.mp4")]
    elif t in (1, 8):
        for i, s in enumerate(row.get("s") or [], 1):
            if s.get("t") == 2 and s.get("v"):
                items.append((s["v"], f"{i:02d}.mp4"))
            elif s.get("i"):
                items.append((s["i"], f"{i:02d}.jpg"))
    if not items:
        return code, None, "dökümde indirilebilir adres yok"
    files = []
    for url, name in items:
        dest = out / name
        try:
            if not dest.exists() or dest.stat().st_size == 0:
                download(url, dest)
        except Exception as e:  # noqa: BLE001 - tek hata tüm partiyi durdurmasın
            return code, None, f"indirilemedi ({name}): {str(e)[:100]} (adres süresi dolmuş olabilir: yeni döküm al)"
        files.append(str(dest.relative_to(cd)))
    return code, files, None


def apply_meta(post: dict, r: dict) -> None:
    if not post.get("caption") and r.get("cap"):
        post["caption"] = r["cap"]
    if not post.get("account") and r.get("u"):
        post["account"] = r["u"]
    if not post.get("date") and r.get("at"):
        post["date"] = datetime.fromtimestamp(r["at"], timezone.utc).strftime("%Y-%m-%d")
    post["type"] = post.get("type") or TYPE_NAME.get(r.get("t"), "")
    if r.get("d") and not post.get("duration"):
        post["duration"] = r["d"]
    if r.get("au"):
        post["audio_type"] = r["au"]
    if r.get("mu"):
        post["music_title"] = r["mu"]
    if r.get("ha") is not None:
        post["has_audio"] = bool(r["ha"])


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--file", required=True, help="Akış dökümü JSON")
    p.add_argument("--codes", help="Yalnız bu kodlar (virgülle)")
    p.add_argument("--no-media", action="store_true", help="Yalnız meta; medya indirme")
    args = p.parse_args()
    wd = Path(args.workdir)
    cfg = load_config(wd)
    cd = cache_dir(args, wd, cfg)
    state = load_state(wd)
    feed = {r["c"]: r for r in json.loads(Path(args.file).read_text(encoding="utf-8"))}
    only = set(args.codes.split(",")) if args.codes else None

    todo = []
    meta = 0
    for code, post in state["posts"].items():
        r = feed.get(code)
        if not r or (only and code not in only) or post.get("media_purged"):
            continue
        apply_meta(post, r)
        meta += 1
        if not args.no_media and not post.get("media"):
            todo.append((code, r))
    save_state(wd, state)

    ok = failed = 0
    with ThreadPoolExecutor(max_workers=min(workers(cfg) * 2, 12)) as pool:  # ağ bekleyen iş: çekirdekten fazla iş parçacığı
        futs = [pool.submit(fetch_post, c, r, cd) for c, r in todo]
        for f in as_completed(futs):
            code, files, err = f.result()
            post = state["posts"][code]
            if files:
                post["media"] = sorted(files)
                post.pop("error", None)
                advance(post, "media")
                ok += 1
            else:
                post["error"] = err
                failed += 1
            save_state(wd, state)
    print(f"meta={meta} medya_indirilen={ok} hata={failed}" + ("  (hatalılar için ig_download.py yedek yolu)" if failed else ""))


if __name__ == "__main__":
    main()
