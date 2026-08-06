"""Single entry point for the corrected Stage 14 read-only API audit."""

from pathlib import Path
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR / "RUN_STAGE14_LOCAL_RUNTIME_API_AUDIT.py"
if not BASE.is_file():
    raise RuntimeError(f"Stage 14 audit implementation is missing: {BASE}")

source = BASE.read_text(encoding="utf-8")
marker = "\ntry:\n    main()"
if marker not in source:
    raise RuntimeError("Stage 14 audit entry marker was not found")

ns = {"__file__": str(BASE), "__name__": "AetherStage14AuditBase"}
exec(compile(source.split(marker, 1)[0], str(BASE), "exec"), ns, ns)


def actor_intersects_corridor_v2(actor, corridor):
    # PreviewSection actor bounds can represent the entire aggregate preview
    # world and are therefore not suitable for local river overlap tests.
    # Generated static-mesh bounds are authoritative when available.
    found_mesh_bounds = False
    for component in ns["get_components"](actor):
        mesh = ns["safe_static_mesh"](component)
        bounds = ns["raw_mesh_bounds"](mesh) if mesh else None
        if not bounds:
            continue
        found_mesh_bounds = True
        if ns["overlaps_xy"](bounds, corridor):
            return True, "RAW_STATIC_MESH_BOUNDS"
    if found_mesh_bounds:
        return False, "RAW_STATIC_MESH_BOUNDS_NO_OVERLAP"
    if ns["overlaps_xy"](ns["actor_bounds"](actor), corridor):
        return True, "ACTOR_BOUNDS_FALLBACK"
    return False, "NONE"


ns["actor_intersects_corridor"] = actor_intersects_corridor_v2

try:
    ns["main"]()
except Exception as exc:
    ns["record"]("")
    ns["record"]("AUDIT_RESULT=FAIL")
    ns["record"](f"ERROR={type(exc).__name__}: {exc}")
    ns["record"]("NO_BUILD_METHOD_CALLED=TRUE")
    ns["record"]("NO_COLLISION_SETTINGS_CHANGED=TRUE")
    ns["record"]("NO_ACTORS_SPAWNED_OR_DESTROYED=TRUE")
    ns["record"]("NO_PACKAGES_SAVED=TRUE")
    ns["record"]("NO_PIE_STARTED=TRUE")
    ns["record"]("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    ns["write_report"]()
    unreal.log_error(f"AETHER_STAGE14_LOCAL_RUNTIME_API_AUDIT_FAILED={type(exc).__name__}: {exc}")
    raise
