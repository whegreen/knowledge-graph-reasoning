#!/usr/bin/env python3
"""document-coherence — deterministic source consistency check.

Reads a declarative config, indexes facts in a document set, then compares
documents. No knowledge graph, model call, or network access is involved.

    python3 coherence.py --config coherence.json --root . --mode index
    python3 coherence.py --config coherence.json --root . --mode pair --docs handbook curriculum
    python3 coherence.py --config coherence.json --root . --mode topics --docs handbook curriculum --json
    python3 coherence.py --config coherence.json --root . --mode audit --strict
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_coherence import compare, config, extract, report  # noqa: E402


def render(report_obj: dict, mode: str) -> str:
    out = []
    if mode in ("pair", "topics"):
        out.append(f"{mode.title()} — {report_obj['a']} ↔ {report_obj['b']}")
        if mode == "pair":
            for r in report_obj["refs"]:
                out.append(f"  STALE {r['from']}:{r['line']} v{r['version']} "
                           f"→ {r['target']} = {r['expected']}")
        for f in report_obj["findings"]:
            label = f.get("label", "")
            if label in ("SAMA", "KOHEREN"):
                continue
            name = f.get("key", f.get("topic"))
            out.append(f"  [{label}] {name}")
        out.append("  " + report_obj.get("coverage", ""))
    else:
        out.append(f"Audit — {report_obj['docs']} docs, {report_obj['facts']} facts, "
                   f"{report_obj['conflicts']} conflicts")
        for f in report_obj["findings"]:
            if f["conflict"]:
                out.append(f"  CONFLICT {f['key']}: {', '.join(f['values'])}")
        out.append("  " + report_obj.get("coverage", ""))
    return "\n".join(out)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="document-coherence quick check")
    p.add_argument("--config", required=True)
    p.add_argument("--root", default=".")
    p.add_argument("--mode", choices=["index", "pair", "topics", "audit"], default="index")
    p.add_argument("--docs", nargs=2, metavar=("A", "B"))
    p.add_argument("--json", action="store_true")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)

    cfg = config.load(args.config)
    root = Path(args.root).resolve()
    cfg["root"] = str(root)
    docs = cfg.get("docs") or []
    if not docs:
        print("config needs a non-empty 'docs' list", file=sys.stderr)
        return 1
    index = extract.build(docs, cfg, root)

    if args.mode == "index":
        print(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) if args.json
              else f"index: {index['stats']['docs']} docs · {index['stats']['lines']} lines · "
                   f"{index['stats']['fact_keys']} facts · {index['stats']['mentions']} mentions")
        return 0

    if args.mode in ("pair", "topics") and not args.docs:
        print("--docs <A> <B> is required for pair/topics", file=sys.stderr)
        return 1
    known = {s["id"] for s in index["sources"]}
    if args.docs and not set(args.docs) <= known:
        print(f"unknown document id; choose from {sorted(known)}", file=sys.stderr)
        return 1

    if args.mode == "pair":
        obj = compare.pair(index, *args.docs, cfg)
    elif args.mode == "topics":
        obj = compare.topics(index, *args.docs, cfg)
    else:
        obj = compare.audit(index, cfg.get("owners", {}), cfg)

    print(report.dump(obj) if args.json else render(obj, args.mode))
    if args.strict:
        hard = [f for f in obj["findings"]
                if f.get("label") in {"BEDA", "KONFLIK"} or f.get("conflict")]
        if hard or obj.get("refs"):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
