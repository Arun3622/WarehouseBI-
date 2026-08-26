"""One-command runner: generate -> warehouse build -> dashboard."""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
for step in ["src/generate_data.py", "src/pipeline.py", "src/build_dashboard.py"]:
    print(f"\n{'='*60}\n>>> {step}\n{'='*60}")
    if subprocess.run([sys.executable, str(BASE / step)]).returncode != 0:
        sys.exit(f"FAILED at {step}")
print("\nALL DONE -> open dashboard/index.html in your browser!")
