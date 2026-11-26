"""extract.py — ekstraksi fakta deterministik dari sekumpulan dokumen.

Input: daftar dokumen {id, path, version} + config. Tidak membaca registry,
tidak tahu soal git, KG, atau skill agent. Ini bagian yang bisa dipublikasikan.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from .config import canon, compile_specs, unit_label

MD_HEADING = re.compile(r"^#{1,6}\s+(.+)$")
HTML_HEADING = re.compile(r"^<h[1-6][^>]*>(.*?)</h[1-6]>", re.I)

MAX_PER_DOC = 12  # ponytail: simpan contoh, bukan seluruh kemunculan
_SPEC_CACHE: dict[int, list] = {}


def _specs(cfg: dict) -> list:
    key = id(cfg)
    if key not in _SPEC_CACHE:
        _SPEC_CACHE[key] = compile_specs(cfg)
    return _SPEC_CACHE[key]


def norm_age(number: str, unit: str, cfg: dict) -> str:
    num = re.sub(r"\s*", "", number.replace("–", "-").replace("—", "-"))
    meta = cfg["units"].get(unit.lower(), {"factor": 1})
    # ponytail: bulan hanya dikonversi bila semua endpoint habis dibagi 12.
    if meta.get("factor") == 1 and all(p.isdigit() and int(p) % 12 == 0 for p in num.split("-")):
        num = "-".join(str(int(p) // 12) for p in num.split("-"))
        return f"{num} {unit_label(cfg, 12)}"
    return f"{num} {unit_label(cfg, meta.get('factor', 1))}"


def heading_level(match, is_html: bool) -> int:
    if is_html:
        m = re.search(r"<h([1-6])", match.group(0), re.I)
        return int(m.group(1)) if m else 0
    return len(match.group(0)) - len(match.group(0).lstrip("#"))


def clean_heading(raw: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
    return re.sub(r"\s+", " ", text)[:100]


def _emit(spec: dict, match: re.Match, cfg: dict) -> tuple[str, str] | None:
    fid, kind = spec["id"], spec["emit"]
    g = [match.group(i) if i <= match.re.groups else "" for i in range(1, 5)]
    skip = spec.get("skip_if")
    if skip == "rf" and "-RF" in g[0]:
        return None
    if skip and skip != "rf":
        pat = cfg.get("skip_patterns", {}).get(skip)
        if pat and re.search(pat, match.group(0), re.I):
            return None
    if kind == "code":
        return f"{fid}:{g[0]}-RF{g[1]}", ""
    if kind == "session":
        return f"{fid}:{g[0]}", ""
    if kind == "age":
        key = canon(g[0], cfg["token_aliases"])
        return f"{fid}:{key}", norm_age(g[1], g[2], cfg)
    if kind == "keyword":
        return f"{fid}:{g[0].upper()}", ""
    if kind == "label":
        return f"{fid}:{re.sub(r'\s+', '', g[0]).lower()}", ""
    if kind == "count":
        return f"{fid}:{g[1].lower()}", g[0]
    if kind == "db":
        return f"{fid}:{g[0]}", ""
    if kind == "term":
        surface = re.sub(r"\s+", " ", match.group(0)).strip()
        for needle, canonical in spec.get("terms", {}).items():
            if needle in surface.lower():
                return f"{fid}:{canonical}", surface
        return None
    return None


def facts_in_line(line: str, cfg: dict) -> list[tuple[str, str]]:
    """(key, value) dari satu baris; value sudah ternormalisasi."""
    out: list[tuple[str, str]] = []
    for spec in _specs(cfg):
        for m in spec["regex"].finditer(line):
            item = _emit(spec, m, cfg)
            if item:
                out.append(item)
    return out


def build(docs: list[dict], cfg: dict, root, max_per_doc: int = MAX_PER_DOC) -> dict:
    """docs = [{"id","path","version"}]; root = Path dasar path tersebut."""
    collected: dict[str, dict[str, dict]] = {}
    sources: list[dict] = []
    sections: list[dict] = []
    total_lines = 0

    for doc in docs:
        path = root / doc["path"]
        if not path.is_file():
            continue
        doc_id = doc["id"]
        is_html = path.suffix.lower() == ".html"
        section = ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        doc_sections: list[dict] = []
        current: dict | None = None
        sources.append({"id": doc_id, "path": doc["path"], "version": doc.get("version", "")})

        for lineno, line in enumerate(lines, 1):
            total_lines += 1
            head = HTML_HEADING.match(line.strip()) if is_html else MD_HEADING.match(line)
            if head:
                if current:
                    current["end"] = lineno - 1
                current = {"doc": doc_id, "line": lineno,
                           "level": heading_level(head, is_html),
                           "title": clean_heading(head.group(1)), "end": len(lines)}
                doc_sections.append(current)
                section = current["title"]
            # heading tetap diproses: fakta kanonik sering ada di judul.
            for key, value in facts_in_line(line, cfg):
                bucket = collected.setdefault(key, {}).setdefault(doc_id, {"n": 0, "items": []})
                bucket["n"] += 1
                if len(bucket["items"]) < max_per_doc:
                    bucket["items"].append({"doc": doc_id, "path": doc["path"],
                                            "line": lineno, "section": section, "value": value})
        sections.extend(doc_sections)

    facts: dict[str, list[dict]] = {}
    for key, by_doc in sorted(collected.items()):
        entries = []
        for by in by_doc.values():
            for item in by["items"]:
                item["mentions"] = by["n"]
                entries.append(item)
        facts[key] = entries

    return {
        "schema": 2,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": sources,
        "sections": sections,
        "facts": facts,
        "stats": {
            "docs": len(sources),
            "lines": total_lines,
            "fact_keys": len(facts),
            "mentions": sum(e["mentions"] for entries in facts.values() for e in entries),
        },
    }


def payload(data: dict) -> dict:
    """Bagian yang dibandingkan --check (timestamp diabaikan)."""
    return {k: data[k] for k in ("schema", "sources", "sections", "facts", "stats")}
