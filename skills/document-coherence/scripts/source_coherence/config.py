"""config.py — konfigurasi deklaratif untuk document coherence.

Tidak ada nama dokumen, path, atau tool spesifik proyek di modul ini.
Nilai KT ada di ops/kg/coherence.config.json, bukan di sini.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def load(path: str | Path) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if cfg.get("schema") != 1:
        raise ValueError(f"config schema tidak didukung: {cfg.get('schema')}")
    for key in ("facts", "units", "topics", "aliases"):
        if key not in cfg:
            raise ValueError(f"config kehilangan kunci wajib: {key}")
    return cfg


def compile_specs(cfg: dict) -> list[dict]:
    out = []
    for spec in cfg["facts"]:
        flags = re.I if "i" in spec.get("flags", "") else 0
        out.append({**spec, "regex": re.compile(spec["pattern"], flags)})
    return out


def canon(text: str, aliases: dict[str, str]) -> str:
    s = re.sub(r"\s+", " ", text.strip().lower())
    for raw, canonical in aliases.items():
        s = s.replace(raw, canonical)
    return s


def unit_label(cfg: dict, factor: int) -> str:
    for name, meta in cfg["units"].items():
        if meta.get("factor") == factor:
            return meta.get("label", name)
    return "year" if factor == 12 else "month"
