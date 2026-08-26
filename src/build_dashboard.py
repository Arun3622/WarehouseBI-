"""Inject aggregates.json into template.html -> index.html"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
COMPLETED_ON = "August 06, 2026"

template = (BASE / "dashboard" / "template.html").read_text(encoding="utf-8")
data = json.loads((BASE / "data" / "aggregates.json").read_text(encoding="utf-8"))
data["completed_on"] = COMPLETED_ON
data["generated_at"] = "2026-08-06"
out = BASE / "dashboard" / "index.html"
out.write_text(template.replace("__DATA_JSON__", json.dumps(data)), encoding="utf-8")
print(f"[done] dashboard -> {out}")
