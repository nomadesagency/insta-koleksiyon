#!/usr/bin/env python3
"""İnceleme sonuçlarını state'e yazar (ekran metni, kategori, etiket, not). stdin'den JSON okur.

Kullanım:  ig_apply.py --workdir W < sonuc.json      |      ig_apply.py --workdir W --letters   (harf kodlarını göster)
Girdi: {"<kod>": {"screen_text": "...", "category": "G", "tags": ["H"], "note": "...", "has_speech": false, ...}, ...}
Kategori/etiket tam adla ya da taksonomi sırasına göre A..M harf kodlarıyla yazılabilir (A = 1. kategori ... M = 13.).
Kategori verilen post `done` aşamasına geçer. Liste dışı kategori, aynı etiketin ana kategoriyle tekrarı, 2'den fazla etiket reddedilir.
Varsayılan metin durumu DÜZELTİLDİ (görsel inceleme yapıldı); değiştirmek için "text_status" ver.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ig_common import advance, base_parser, load_state, load_taxonomy, save_state


def main() -> None:
    p = base_parser(__doc__)
    p.add_argument("--letters", action="store_true", help="Harf kodlarını göster ve çık")
    args = p.parse_args()
    wd = Path(args.workdir)
    tax = load_taxonomy(wd)
    cats = tax["categories"]
    letters = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", cats))
    if args.letters:
        for k, v in letters.items():
            print(k, v)
        return

    full = lambda x: letters.get(x, x)  # noqa: E731
    data = json.load(sys.stdin)
    state = load_state(wd)
    errors = []
    for code, f in data.items():
        if code not in state["posts"]:
            errors.append(f"{code}: state'te yok")
            continue
        if "category" in f:
            f["category"] = full(f["category"])
            f["tags"] = [full(x) for x in f.get("tags", [])]
            if f["category"] not in cats or any(t not in cats for t in f["tags"]):
                errors.append(f"{code}: kategori/etiket listede yok")
            elif f["category"] in f["tags"] or len(f["tags"]) > tax["max_secondary"]:
                errors.append(f"{code}: etiket kuralı (tekrar ya da en fazla {tax['max_secondary']})")
    if errors:
        sys.exit("DOĞRULAMA HATASI, hiçbir şey yazılmadı:\n  " + "\n  ".join(errors))
    for code, f in data.items():
        post = state["posts"][code]
        f.setdefault("text_status", "DÜZELTİLDİ")
        post.pop("review_reason", None)
        if f.get("has_speech") is False:
            f.setdefault("speech_text", "")
            f["speech_suspect"] = False
        if "category" in f:
            advance(post, "done")
        post.update(f)
    save_state(wd, state)
    print("uygulandı:", len(data))


if __name__ == "__main__":
    main()
