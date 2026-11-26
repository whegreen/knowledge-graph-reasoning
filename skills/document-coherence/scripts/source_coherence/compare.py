"""compare.py — perbandingan dokumen: interval, istilah, versi, topik, cakupan.

Murni deterministik. Tidak ada KG, agent, rute, atau nama dokumen hardcoded;
semuanya dibaca dari config.
"""
from __future__ import annotations

import re
from pathlib import Path

VERSION_RE = re.compile(r"\b([A-Z][A-Za-z ]{2,44}?)\s+v(\d+(?:\.\d+)+)\b")
FILE_VERSION_RE = re.compile(r"v(\d+(?:[._]\d+)+)", re.I)


def coverage_note(index: dict) -> str:
    facts = index["facts"]
    n = sum(1 for entries in facts.values() if any(e["value"] for e in entries))
    pct = f"{100 * n / len(facts):.1f}".replace(".", ",") if facts else "0"
    return f"CAKUPAN: {n}/{len(facts)} fakta punya nilai ({pct}%)"


def parse_range(value: str, cfg: dict) -> tuple[int, int] | None:
    meta = "|".join(re.escape(u) for u in cfg["units"])
    m = re.match(rf"^(\d+)(?:-(\d+))?\s*({meta})$", value or "", re.I)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2) or m.group(1))
    f = cfg["units"][m.group(3).lower()].get("factor", 1)
    return (min(a, b) * f, max(a, b) * f)


def _union(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for r in sorted(ranges):
        if out and r[0] <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], r[1]))
        else:
            out.append(r)
    return out


def classify(values_a: list[str], values_b: list[str], cfg: dict) -> str:
    if set(values_a) == set(values_b):
        return "SAMA"
    ra = [r for v in values_a if (r := parse_range(v, cfg))]
    rb = [r for v in values_b if (r := parse_range(v, cfg))]
    if not ra or not rb:
        return "BEDA"
    ua, ub = _union(ra), _union(rb)

    def subset(x, y) -> bool:
        return all(any(a >= c and b <= d for c, d in y) for a, b in x)

    if ua == ub or subset(ua, ub) or subset(ub, ua):
        return "SUB-TAHAP"
    if any(a <= d and c <= b for a, b in ua for c, d in ub):
        return "OVERLAP"
    return "BEDA"


def version_refs(index: dict, doc_a: str, doc_b: str, cfg: dict) -> list[dict]:
    ids = {s["path"]: s["id"] for s in index["sources"]}
    versions = {d["path"]: d.get("version", "") for d in cfg.get("docs", [])}
    rows = {}
    for path, doc_id in ids.items():
        rows[doc_id] = {"path": path, "version": versions.get(path, "")}
    out: list[dict] = []
    root = Path(cfg.get("root", "."))
    for doc in (doc_a, doc_b):
        row = rows.get(doc)
        path = root / row["path"] if row else None
        if not path or not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, line in enumerate(lines, 1):
            for m in VERSION_RE.finditer(line):
                label = m.group(1).strip()
                for target in (doc_a, doc_b):
                    if target == doc or not rows.get(target):
                        continue
                    if not any(lbl.lower() in label.lower()
                               for lbl in cfg.get("version_labels", {}).get(target, ())):
                        continue
                    version = m.group(2)
                    expected = rows[target]["version"]
                    mfile = FILE_VERSION_RE.search(Path(rows[target]["path"]).stem)
                    filename_v = mfile.group(1).replace("_", ".") if mfile else ""
                    # ponytail: versi isi vs nama file boleh beda (registry mencatat keduanya).
                    if version not in (expected, filename_v):
                        out.append({"from": doc, "line": lineno, "label": label,
                                    "version": version, "target": target, "expected": expected})
    return out


def pair(index: dict, doc_a: str, doc_b: str, cfg: dict) -> dict:
    """Bandingkan dua dokumen: fakta bersama + referensi versi lintas dokumen."""
    per_doc: dict[str, dict[str, list[dict]]] = {doc_a: {}, doc_b: {}}
    skip = cfg["skip_sections"]
    for key, entries in index["facts"].items():
        for e in entries:
            if e["doc"] not in per_doc or re.search(skip, e.get("section", ""), re.I):
                continue
            per_doc[e["doc"]].setdefault(key, []).append(
                {"line": e["line"], "value": e.get("value", "")})
    findings = []
    for key in sorted(set(per_doc[doc_a]) | set(per_doc[doc_b])):
        a, b = per_doc[doc_a].get(key, []), per_doc[doc_b].get(key, [])
        av = [x["value"] for x in a if x["value"]]
        bv = [x["value"] for x in b if x["value"]]
        prefix = key.split(":", 1)[0]
        if not (a and b) and prefix in cfg["one_sided"]:
            continue
        if not av and not bv:
            label = "SAMA" if a and b else "SATU-SISI"
        elif not av or not bv:
            label = "SATU-SISI"
        else:
            label = classify(av, bv, cfg)
        if label == "BEDA" and any(f["id"] == prefix and f.get("compare") == "term_variant"
                                   for f in cfg["facts"]):
            label = "ISTILAH BEDA"
        alias = None
        alias_doc = ""
        alias_entries: list[dict] = []
        if label == "SATU-SISI" and bool(a) != bool(b):
            alias = cfg["aliases"].get(key) or next(
                (k for k, v in cfg["aliases"].items() if v == key), None)
            if alias:
                alias_doc = doc_a if not a else doc_b
                alias_entries = per_doc[alias_doc].get(alias, [])
                alt_v = [x["value"] for x in alias_entries if x["value"]]
                own_v = av or bv
                if own_v and alt_v:
                    verdict = classify(own_v, alt_v, cfg)
                    label = "ALIAS" if verdict == "SAMA" else f"ALIAS/{verdict}"
                elif alias_entries:
                    label = "ALIAS"
        finding = {"key": key, "label": label, doc_a: a, doc_b: b}
        if alias:
            finding.update({"alias": alias, "alias_doc": alias_doc,
                            "alias_entries": alias_entries})
        findings.append(finding)
    refs = version_refs(index, doc_a, doc_b, cfg)
    conflicts = sum(1 for f in findings if f["label"] == "BEDA") + len(refs)
    return {"a": doc_a, "b": doc_b, "findings": findings,
            "refs": refs, "coverage": coverage_note(index), "conflicts": conflicts}


def canon_term(name: str, matched: str, cfg: dict) -> str | None:
    for needle, canonical in cfg.get("canon_terms", {}).get(name, {}).items():
        if needle in matched.lower():
            return canonical
    return None


def topics(index: dict, doc_a: str, doc_b: str, cfg: dict) -> dict:
    """Resume topik dua dokumen. Eskalasi berisi data, bukan rute agent."""
    ids = {s["path"]: s["id"] for s in index["sources"]}
    rows = {ids.get(d["path"]): d for d in cfg.get("docs", [])}
    present: dict[str, dict[str, list[int]]] = {doc_a: {}, doc_b: {}}
    terms: dict[str, dict[str, set[str]]] = {doc_a: {}, doc_b: {}}
    lines_by_doc: dict[str, list[str]] = {}
    fact_lines: dict[str, dict[int, list[tuple[str, str]]]] = {}
    patterns = [(t["name"], re.compile(t["pattern"], re.I)) for t in cfg["topics"]]

    root = Path(cfg.get("root", "."))
    for doc in (doc_a, doc_b):
        row = rows.get(doc)
        path = root / row["path"] if row else None
        lines = (path.read_text(encoding="utf-8", errors="replace").splitlines()
                 if path and path.is_file() else [])
        lines_by_doc[doc] = lines
        for lineno, line in enumerate(lines, 1):
            for name, rx in patterns:
                m = rx.search(line)
                if m:
                    present[doc].setdefault(name, []).append(lineno)
                    canonical = canon_term(name, m.group(0), cfg)
                    if canonical:
                        terms[doc].setdefault(name, set()).add(canonical)
        fact_lines[doc] = {}
        for key, entries in index["facts"].items():
            for e in entries:
                if e["doc"] == doc and e.get("value"):
                    fact_lines[doc].setdefault(e["line"], []).append((key, e["value"]))

    def values(doc: str, linenos: list[int]) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for n in linenos:
            for k, v in fact_lines[doc].get(n, []):
                out.setdefault(k, set()).add(v)
        return out

    findings = []
    for name in sorted(set(present[doc_a]) | set(present[doc_b])):
        la, lb = present[doc_a].get(name, []), present[doc_b].get(name, [])
        if not la or not lb:
            label = "SATU-SISI"
        else:
            pa, pb = values(doc_a, la), values(doc_b, lb)
            labels = {classify(sorted(pa[k]), sorted(pb[k]), cfg) for k in set(pa) & set(pb)}
            if "BEDA" in labels:
                label = ("ISTILAH BEDA" if name in cfg["term_topics"] else "KONFLIK")
            elif labels & {"SUB-TAHAP", "OVERLAP"}:
                label = "SUB-TAHAP"
            elif name in cfg["term_topics"] and terms[doc_a].get(name, set()) != terms[doc_b].get(name, set()):
                label = "ISTILAH BEDA"
            else:
                label = "KOHEREN"
        findings.append({"topic": name, "label": label, "lines_a": la, "lines_b": lb})

    def quote(doc: str, lineno: int | None) -> str:
        if lineno is None or lineno > len(lines_by_doc[doc]):
            return "-"
        text = re.sub(r"\s+", " ", lines_by_doc[doc][lineno - 1]).strip()[:130]
        return f'{doc}:{lineno} "{text}"'

    # satu-sisi hanya perlu agent bila topiknya memang diharapkan di dua dokumen.
    shared = set(cfg.get("shared_topics", []))
    escalations: list[dict] = []
    notes: list[dict] = []
    for r in version_refs(index, doc_a, doc_b, cfg):
        escalations.append({"topic": "versi dokumen", "label": "REFERENSI BASI",
                            "a": quote(r["from"], r["line"]),
                            "b": f'{r["target"]} = {r["expected"]}', "kind": "version_reference"})
    for f in findings:
        if f["label"] not in {"KONFLIK", "ISTILAH BEDA", "SATU-SISI"}:
            continue
        item = {"topic": f["topic"], "label": f["label"],
                "a": quote(doc_a, f["lines_a"][0] if f["lines_a"] else None),
                "b": quote(doc_b, f["lines_b"][0] if f["lines_b"] else None),
                "kind": "topic"}
        if f["label"] == "SATU-SISI" and f["topic"] not in shared:
            notes.append(item)
        else:
            escalations.append(item)
    severity = {"REFERENSI BASI": 0, "KONFLIK": 1, "ISTILAH BEDA": 2, "SATU-SISI": 3}
    escalations.sort(key=lambda e: (severity.get(e["label"], 4), e["topic"]))
    return {"a": doc_a, "b": doc_b, "findings": findings,
            "present": {d: sorted(present[d]) for d in (doc_a, doc_b)},
            "escalations": escalations, "notes": notes,
            "coverage": coverage_note(index)}


def audit(index: dict, owners: dict, cfg: dict) -> dict:
    """Audit seluruh indeks tanpa git diff; konflik dihitung terhadap owner."""
    findings = []
    for key, entries in sorted(index["facts"].items()):
        prefix = key.split(":", 1)[0]
        by_value: dict[str, list[str]] = {}
        for e in entries:
            value = e.get("value", "")
            if not value or re.search(cfg["skip_sections"], e.get("section", ""), re.I):
                continue
            by_value.setdefault(value, []).append(f"{e['doc']}:{e['line']}")
        if len(by_value) < 2:
            continue
        owner = owners.get(prefix, "—")
        owner_values = {v for v, locs in by_value.items()
                        if any(loc.startswith(f"{owner}:") for loc in locs)}
        findings.append({
            "key": key, "owner": owner, "values": by_value,
            "conflict": bool(owner_values and any(v not in owner_values for v in by_value)),
        })
    return {"docs": len(index.get("sources", [])),
            "facts": index["stats"]["fact_keys"],
            "findings": findings,
            "coverage": coverage_note(index),
            "conflicts": sum(1 for f in findings if f["conflict"])}
