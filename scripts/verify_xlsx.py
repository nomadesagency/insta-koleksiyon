#!/usr/bin/env python3
"""Excel'i state.json ile hücre hücre karşılaştırır (kalite kapısı). Fark varsa çıkış kodu 1.

Kontroller: satır sayısı = post sayısı · URL'ler tekil · 13 içerik sütunu state ile birebir · kategori/etiket taksonomide ·
tarih boş değil. Silme adımlarından (ig_cleanup) ÖNCE çalıştırılır.
"""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl

from ig_common import base_parser, load_state, load_taxonomy

# build_xlsx.COLUMNS sırası: 0 Sıra 1 URL 2 Hesap 3 Tür 4 Tarih 5 Koleksiyon 6 Açıklama 7 Ekran metni 8 Konuşma
# 9 Konuşma var 10 Metin durumu 11 Ana kategori 12 Etiketler
def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--xlsx", default="kaydedilenler.xlsx")
    args = p.parse_args()
    wd = Path(args.workdir)
    posts = load_state(wd)["posts"]
    cats = set(load_taxonomy(wd)["categories"])
    ws = openpyxl.load_workbook(wd / args.xlsx)["Kaydedilenler"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    by_url = {p_["url"]: p_ for p_ in posts.values()}
    s = lambda v: "" if v is None else str(v)  # noqa: E731
    errors = []
    if len(rows) != len(posts):
        errors.append(f"satır {len(rows)} ≠ state {len(posts)}")
    if len({r[1] for r in rows}) != len(rows):
        errors.append("URL'ler tekil değil")
    for r in rows:
        post = by_url.get(r[1])
        if not post:
            errors.append(f"state'te yok: {r[1]}")
            continue
        exp = [post.get("order"), post["url"], post.get("account"), post.get("type"), None, post.get("collection"),
               post.get("caption"), post.get("screen_text", ""), post.get("speech_text"),
               "Evet" if post.get("has_speech") else "Hayır", post.get("text_status"), post.get("category"),
               ", ".join(post.get("tags", []))]
        for i, e in enumerate(exp):
            if i != 4 and s(e) != s(r[i]):
                errors.append(f"{r[1][-14:]} sütun {i}: state≠Excel")
        # etiket adlarında virgül var ("Satış, Teklif & ..."): virgülden bölme, state'teki listeyi kontrol et (Excel sütunu zaten eşleşti)
        if r[11] not in cats or any(t not in cats for t in post.get("tags", [])):
            errors.append(f"{r[1][-14:]}: kategori/etiket taksonomide yok")
        if not r[4]:
            errors.append(f"{r[1][-14:]}: tarih boş")
    if errors:
        print("EXCEL DOĞRULAMA BAŞARISIZ:\n  " + "\n  ".join(errors[:30]) + (f"\n  ... +{len(errors) - 30}" if len(errors) > 30 else ""))
        sys.exit(1)
    print(f"Excel doğrulandı: {len(rows)} satır = state, URL'ler tekil, hücre farkı 0, taksonomi uyumlu")


if __name__ == "__main__":
    main()
