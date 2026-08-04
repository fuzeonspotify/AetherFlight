"""Single entry point for the final Stage 13 river-environment grounding repair."""

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "RepairAetherVideoRiverEnvironmentPreviewGrounding_UE58_v2.py"

if not TARGET.is_file():
    raise RuntimeError(f"Final grounding repair is missing: {TARGET}")

namespace = {
    "__file__": str(TARGET),
    "__name__": "__main__",
}
source = TARGET.read_text(encoding="utf-8")
exec(compile(source, str(TARGET), "exec"), namespace, namespace)
