"""Single entry point for the read-only Stage 14 Mesh Partition build-cost audit V2."""

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "AuditAetherStage14MeshPartitionBuildCost_UE58_v2.py"
if not TARGET.is_file():
    raise RuntimeError(f"Stage 14 build-cost audit V2 is missing: {TARGET}")

namespace = {"__file__": str(TARGET), "__name__": "__main__"}
source = TARGET.read_text(encoding="utf-8")
exec(compile(source, str(TARGET), "exec"), namespace, namespace)
