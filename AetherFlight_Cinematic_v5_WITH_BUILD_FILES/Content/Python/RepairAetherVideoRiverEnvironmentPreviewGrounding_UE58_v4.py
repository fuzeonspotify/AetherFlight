"""Stage 13.3 V4: accept Geometry Script FOUND outcomes and proven river ray distances."""

from pathlib import Path
import sys
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

V3 = SCRIPT_DIR / "RepairAetherVideoRiverEnvironmentPreviewGrounding_UE58_v3.py"
if not V3.is_file():
    raise RuntimeError(f"Stage 13.3 V3 repair is missing: {V3}")

source = V3.read_text(encoding="utf-8")
marker = '\ntry:\n    base["main"]()'
if marker not in source:
    raise RuntimeError("Stage 13.3 V3 entry marker was not found")

ns = {"__file__": str(V3), "__name__": "AetherPreviewGroundingV4Base"}
exec(compile(source.split(marker, 1)[0], str(V3), "exec"), ns, ns)

base = ns["base"]


def geometry_query_success(value):
    text = str(value).upper()
    if "NOT_FOUND" in text or "FAIL" in text or "ERROR" in text:
        return False
    return "SUCCESS" in text or ".FOUND" in text or text.endswith("FOUND")


# Geometry Script copy calls return SUCCESS, while spatial queries return FOUND.
base["success"] = geometry_query_success

# The read-only diagnostic proved a valid river-tile ray hit at 147,869 cm.
# Use a conservative range that still remains local to the loaded river tiles.
base["RAY_LIFT"] = 120000.0
base["RAY_MAX"] = 250000.0

try:
    base["log"]("V4_GEOMETRY_QUERY_OUTCOME_FIX=TRUE")
    base["log"]("V4_RAY_LIFT_CM=120000.0")
    base["log"]("V4_RAY_MAX_CM=250000.0")
    base["main"]()
except Exception as exc:
    base["log"]("")
    base["log"]("PREVIEW_GROUNDING_RESULT=FAIL")
    base["log"](f"ERROR={type(exc).__name__}: {exc}")
    base["log"]("SAVED_ENVIRONMENT_ACTOR_WAS_NOT_REPLACED=TRUE")
    base["log"]("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    base["report"]()
    unreal.log_error(f"AETHER_PREVIEW_GROUNDING_V4_FAILED={type(exc).__name__}: {exc}")
    raise
