"""Structured JSONL logging. One helper, used by llm wrapper + smoke tests."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def jsonl_append(log_dir: str | Path, filename: str, record: dict[str, Any]) -> Path:
    d = Path(log_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    rec = {"ts": time.time(), **record}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return p
