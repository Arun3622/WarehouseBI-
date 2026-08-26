"""Inject aggregates.json into template.html -> index.html"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
template = (BASE / "dashboard" / "template.html").read_text(encoding="utf-8")
data = (BASE / "data" / "aggregates.json").read_text(encoding="utf-8")
out = BASE / "dashboard" / "index.html"
out.write_text(template.replace("__DATA_JSON__", data), encoding="utf-8")
print(f"[done] dashboard -> {out}")
