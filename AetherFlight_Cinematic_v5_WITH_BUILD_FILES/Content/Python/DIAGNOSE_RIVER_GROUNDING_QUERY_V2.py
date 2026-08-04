"""V2 read-only river grounding query diagnostic.

Runs the original diagnostic while treating Mesh Partition preview-component
transforms as optional. Some UE 5.8 StaticMeshPreviewComponent objects expose
neither get_component_transform() nor component_to_world to Python.
"""

from pathlib import Path
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
ORIGINAL = SCRIPT_DIR / "DIAGNOSE_RIVER_GROUNDING_QUERY.py"

if not ORIGINAL.is_file():
    raise RuntimeError(f"Original query diagnostic is missing: {ORIGINAL}")

source = ORIGINAL.read_text(encoding="utf-8")
marker = "\ntry:\n    main()"
if marker not in source:
    raise RuntimeError("Original diagnostic entry marker was not found")

ns = {
    "__file__": str(ORIGINAL),
    "__name__": "AetherRiverGroundingQueryDiagnosticV2Base",
}
exec(compile(source.split(marker, 1)[0], str(ORIGINAL), "exec"), ns, ns)


def component_transform_v2(component):
    for method_name in (
        "get_component_transform",
        "get_world_transform",
        "get_relative_transform",
    ):
        method = getattr(component, method_name, None)
        if not callable(method):
            continue
        try:
            return method()
        except Exception:
            pass

    for property_name in (
        "component_to_world",
        "world_transform",
        "relative_transform",
    ):
        try:
            return component.get_editor_property(property_name)
        except Exception:
            pass
    return None


def transform_bounds_v2(component, mesh):
    transform = component_transform_v2(component)
    if transform is None:
        return None
    try:
        bounds = mesh.get_bounds()
        points = []
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                for sz in (-1.0, 1.0):
                    local = unreal.Vector(
                        float(bounds.origin.x) + sx * float(bounds.box_extent.x),
                        float(bounds.origin.y) + sy * float(bounds.box_extent.y),
                        float(bounds.origin.z) + sz * float(bounds.box_extent.z),
                    )
                    points.append(unreal.MathLibrary.transform_location(transform, local))
        return (
            min(float(point.x) for point in points),
            max(float(point.x) for point in points),
            min(float(point.y) for point in points),
            max(float(point.y) for point in points),
            min(float(point.z) for point in points),
            max(float(point.z) for point in points),
        )
    except Exception:
        return None


ns["component_transform"] = component_transform_v2
ns["transform_bounds"] = transform_bounds_v2

try:
    ns["main"]()
except Exception as exc:
    ns["log"]("")
    ns["log"]("DIAGNOSTIC_RESULT=FAIL")
    ns["log"](f"ERROR={type(exc).__name__}: {exc}")
    ns["log"]("NO_ACTORS_SPAWNED_OR_DESTROYED=TRUE")
    ns["log"]("NO_PACKAGES_SAVED=TRUE")
    ns["log"]("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    ns["save_report"]()
    unreal.log_error(f"AETHER_RIVER_GROUNDING_QUERY_DIAGNOSTIC_V2_FAILED={type(exc).__name__}: {exc}")
    raise
