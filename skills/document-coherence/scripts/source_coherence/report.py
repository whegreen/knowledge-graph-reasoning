"""report.py — serialisasi output. JSON adalah kontrak dengan pemanggil luar."""
from __future__ import annotations

import json
from datetime import datetime, timezone


def to_json(report: dict) -> dict:
    if "escalations" in report:
        mode = "topics"
    elif "refs" in report:
        mode = "pair"
    else:
        mode = "audit"
    return {
        "schema": 1,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": report.get("coverage", ""),
        "data": report,
    }


def dump(report: dict) -> str:
    return json.dumps(to_json(report), ensure_ascii=False, indent=2, sort_keys=True)
