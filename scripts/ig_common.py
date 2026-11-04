"""Ortak yardımcılar: config, state.json (atomik yazım + doğrulama), taksonomi, PATH.

Özel veri taşımaz. Yollar --workdir (state.json, config, Excel: küçük dosyalar) ve
--cachedir (media/, frames/: ağır dosyalar, çalışma alanı dışında) argümanlarından gelir.
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
# cron/non-login shell'lerde Homebrew PATH'te olmayabilir
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")


def base_parser(desc: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--workdir", required=True, help="Özel çalışma alanı klasörü (state.json, config.json, Excel)")
    p.add_argument("--cachedir", help="media/ ve frames/ klasörlerinin yeri (varsayılan: config cache_dir veya "
                   "~/Desktop/insta-koleksiyon-cache). Bulut senkron yükünden kaçınmak için çalışma alanı dışında tutulur")
    return p


def cache_dir(args, workdir: Path, cfg: dict | None = None) -> Path:
    """Ağır dosyaların (media/, frames/) kökü. Öncelik: --cachedir > config cache_dir > masaüstü varsayılanı."""
    cfg = cfg if cfg is not None else load_config(workdir)
    raw = args.cachedir or cfg.get("cache_dir") or "~/Desktop/insta-koleksiyon-cache"
    path = Path(raw).expanduser().resolve()
    if path == workdir.resolve() or workdir.resolve() in path.parents:
        sys.exit("HATA: cachedir çalışma alanının içinde olamaz (amaç ağır dosyaları çalışma alanından ayırmak).")
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
    """Çalışma alanındaki taxonomy.json varsa varsayılanı ezer."""
    custom = workdir / "taxonomy.json"
    return load_json(custom if custom.exists() else SKILL_DIR / "taxonomy.default.json")


def state_path(workdir: Path) -> Path:
    return workdir / "state.json"


class State(dict):
    """state.json içeriği + yüklendiği andaki anlık görüntü (save_state yalnız DEĞİŞENLERİ yazar)."""
    _snap: dict = {}


def _read_state(workdir: Path) -> dict:
    return load_json(state_path(workdir), {"posts": {}})


def load_state(workdir: Path) -> State:
    st = State(_read_state(workdir))
    st._snap = copy.deepcopy(dict(st))
    return st


def save_state(workdir: Path, state: dict) -> None:
    """Birleştirmeli, kilitli, atomik yazım.

    Dosya kilidi altında diskteki güncel state okunur; yalnız bu süreçte DEĞİŞEN alanlar (yüklenme anına göre fark) üstüne
    yazılır. Böylece aynı anda çalışan iki betik (ör. OCR + konuşma) birbirinin alanını ezmez (ör. zincir
    çalışırken elle yazılan bir alan kaybolmaz). Yazımdan sonra geri okunup doğrulanır.
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
            if base is None:  # bu süreçte eklenen yeni post
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
            raise RuntimeError("state.json yazım doğrulaması başarısız (kayıt sayısı tutmuyor)")
        state._snap = copy.deepcopy({"posts": {c: copy.deepcopy(p) for c, p in state["posts"].items()}})
        # diskte başkalarının eklediği alanlar bellekte yok; snapshot'ı da bellek durumuyla tutarlı bırak
        for c, p in back["posts"].items():
            if c not in state["posts"]:
                state["posts"][c] = copy.deepcopy(p)
                state._snap["posts"][c] = copy.deepcopy(p)


def shortcode(url: str) -> str:
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", url)
    if not m:
        raise ValueError(f"Gönderi URL'si tanınmadı: {url}")
    return m.group(1)


def polite_sleep(cfg: dict) -> None:
    lo, hi = cfg.get("delay_seconds", [3, 6])
    time.sleep(random.uniform(lo, hi))


def need_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"HATA: '{name}' kurulu değil (README -> Kurulum).")
    return path


def advance(post: dict, stage: str) -> None:
    """Aşamayı yalnız ileri taşır, asla geri almaz."""
    if STAGES.index(stage) > STAGES.index(post.get("stage", "listed")):
        post["stage"] = stage


def workers(cfg: dict | None = None) -> int:
    """Paralel işçi sayısı: config 'workers' veya (CPU çekirdeği - 2), en az 2."""
    n = (cfg or {}).get("workers") or max((os.cpu_count() or 4) - 2, 2)
    return int(n)
