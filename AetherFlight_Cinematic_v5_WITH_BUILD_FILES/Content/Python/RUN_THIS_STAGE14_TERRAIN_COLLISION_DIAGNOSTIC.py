"""Single entry point for the read-only Stage 14 terrain collision diagnostic."""

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "DiagnoseAetherStage14TerrainCollisionPath_UE58.py"
if not TARGET.is_file():
    raise RuntimeError(f"Stage 14 terrain collision diagnostic is missing: {TARGET}")

namespace = {"__file__": str(TARGET), "__name__": "__main__"}
source = TARGET.read_text(encoding="utf-8")
exec(compile(source, str(TARGET), "exec"), namespace, namespace)
