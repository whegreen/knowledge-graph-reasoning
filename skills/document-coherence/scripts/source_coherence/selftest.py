#!/usr/bin/env python3
"""selftest.py — eval portabel: berjalan tanpa repo, KG, atau jaringan."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# jalan langsung sebagai skrip maupun sebagai modul paket.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from source_coherence.compare import classify, pair, topics  # noqa: E402
from source_coherence.extract import build, facts_in_line  # noqa: E402

CFG = {
    "schema": 1,
    "units": {"tahun": {"factor": 12, "label": "tahun"},
              "bulan": {"factor": 1, "label": "bulan"}},
    "token_aliases": {},
    "skip_patterns": {"freq": "menetap|\\d+\\s*[×x]\\s*/\\s*(mgg|minggu)"},
    "skip_sections": "changelog|history",
    "facts": [
        {"id": "age", "emit": "age",
         "pattern": "\\b(Alpha|Beta)\\b[^.\\n]{0,20}?(\\d+)\\s*(tahun|bulan)\\b",
         "flags": "i", "compare": "interval"},
        {"id": "framework", "emit": "term",
         "pattern": "(Montessori|Little\\s*House|Littlehouse)", "flags": "i",
         "terms": {"montessori": "montessori", "little": "littlehouse"},
         "compare": "term_variant"},
    ],
    "one_sided": [],
    "aliases": {"age:beta": "age:alpha"},
    "term_topics": ["framework"],
    "shared_topics": ["framework"],
    "canon_terms": {"framework": {"montessori": "montessori", "little": "littlehouse"}},
    "topics": [
        {"name": "framework", "pattern": "montessori|little\\s*house|littlehouse"},
        {"name": "inklusi", "pattern": "inklus"},
    ],
    "version_labels": {},
}


def self_test() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.md").write_text(
            "# Alpha\nAlpha 3 tahun. Montessori Practical Life. LittleHouse Homeschool. Inklusi.\n",
            encoding="utf-8")
        (root / "b.md").write_text(
            "# Alpha\nAlpha 36 bulan. Beta 2 tahun. Little House. Montessori Practical Life.\n", encoding="utf-8")
        cfg = {**CFG, "docs": [{"id": "a", "path": "a.md", "version": "1.0"},
                               {"id": "b", "path": "b.md", "version": "1.0"}],
               "root": str(root)}
        idx = build(cfg["docs"], cfg, root)
        assert idx["stats"]["docs"] == 2
        a = dict(facts_in_line("Alpha 36 bulan. Montessori", cfg))
        assert a["age:alpha"] == "3 tahun", a
        assert a["framework:montessori"] == "Montessori"
        assert classify(["3 tahun"], ["36 bulan"], cfg) == "SUB-TAHAP"
        assert classify(["3-4 tahun"], ["1-2 tahun"], cfg) == "BEDA"
        pr = pair(idx, "a", "b", cfg)
        fw = next(f for f in pr["findings"] if f["key"] == "framework:littlehouse")
        assert fw["label"] == "ISTILAH BEDA", fw
        # aliases compare values instead of merely relabelling one-sided facts.
        beta = next(f for f in pr["findings"] if f["key"] == "age:beta")
        assert beta["label"] == "ALIAS/BEDA", beta
        tr = topics(idx, "a", "b", cfg)
        labels = {f["topic"]: f["label"] for f in tr["findings"]}
        assert labels["framework"] == "ISTILAH BEDA", labels
        assert labels["inklusi"] == "SATU-SISI", labels
        assert all("route" not in e for e in tr["escalations"])
        # one-sided outside shared_topics is information, not an escalation.
        assert any(n["topic"] == "inklusi" for n in tr["notes"]), tr
        assert not any(e["topic"] == "inklusi" for e in tr["escalations"]), tr
        # escalations are sorted by severity and never truncated in JSON data.
        assert tr["escalations"][0]["label"] in {"REFERENSI BASI", "KONFLIK", "ISTILAH BEDA"}, tr

    # batas paket: hanya stdlib, tanpa dependency eksternal.
    for p in Path(__file__).resolve().parent.glob("*.py"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith(("import ", "from ")):
                assert not any(dep in line for dep in ("yaml", "requests", "numpy", "pandas")), p.name
    print("source_coherence selftest PASS (extract/classify/pair/topics)")
    return 0


if __name__ == "__main__":
    sys.exit(self_test())
