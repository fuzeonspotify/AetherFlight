"""Single entry point for the strict Stage 14 river-rock collision installer."""

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "InstallAetherStage14RockCollision_UE58_v2.py"
if not TARGET.is_file():
    raise RuntimeError(f"Stage 14 rock collision installer is missing: {TARGET}")

namespace = {"__file__": str(TARGET), "__name__": "__main__"}
source = TARGET.read_text(encoding="utf-8")
exec(compile(source, str(TARGET), "exec"), namespace, namespace)
