"""Stage 15B bounded Mesh Terrain preview/cache build through the editor C++ bridge.

The underlying UMeshPartitionEditorComponent::BuildMegaMeshPreviewSections API is
public C++ but is not a reflected UFUNCTION, so Unreal Python cannot call it
directly. AetherFlightEditor exposes only that bounded call to Python.

This script requests one synchronous preview build for the existing 300 m x 200 m
x 1000 m probe box, then verifies that preview section actors and PCGDataComponent
caches exist in that box. It does not save packages, generate PCG, or build
compiled/runtime Mesh Partition sections.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BBoundedPCGPreviewCacheBuildCPP.txt"
MAP_PREFIX = "/Game/Maps/AetherWorld"
MESH_PARTITION_LABEL = "MeshTerrain_AetherWorld"
ADAPTER_ACTOR_LABEL = "Aether_Stage15B_MeshTerrainPCGAdapter"
DATA_CLASS_PATH = "/Script/PCGMeshPartitionInterop.PCGDataComponent"
PROBE_CENTER = (-720281.762624, -777396.263126, 360041.204628)
PROBE_EXTENT = (15000.0, 10000.0, 50000.0)

LINES = []


def log(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES).rstrip() + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_STAGE15B_BOUNDED_PCG_PREVIEW_CPP_REPORT={REPORT_PATH}")


def safe_call(fn, fallback=None):
    try:
        return fn()
    except Exception:
        return fallback


def object_path(obj):
    if obj is None:
        return "NONE"
    for fn in (lambda: obj.get_path_name(), lambda: obj.get_full_name(), lambda: str(obj)):
        value = safe_call(fn)
        if value:
            return str(value)
    return "UNKNOWN"


def class_path(obj):
    cls = safe_call(lambda: obj.get_class())
    if cls is not None:
        value = safe_call(lambda: cls.get_path_name())
        if value:
            return str(value)
    return type(obj).__name__ if obj is not None else "NONE"


def actor_label(actor):
    return str(safe_call(lambda: actor.get_actor_label(), safe_call(lambda: actor.get_name(), "UNKNOWN")))


def current_world():
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if subsystem_class is None:
        return None
    subsystem = unreal.get_editor_subsystem(subsystem_class)
    return safe_call(lambda: subsystem.get_editor_world())


def all_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return list(subsystem.get_all_level_actors())


def find_exact_actor(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one actor labelled {label}; found {len(matches)}")
    return matches[0]


def is_section_actor(actor):
    text = f"{class_path(actor)} {actor_label(actor)} {safe_call(lambda: actor.get_name(), '')}".lower()
    return any(token in text for token in ("previewsection", "interactivesection", "compiledsection"))


def section_kind(actor):
    text = f"{class_path(actor)} {actor_label(actor)}".lower()
    if "compiled" in text:
        return "COMPILED"
    if "interactive" in text:
        return "INTERACTIVE"
    return "PREVIEW"


def actor_bounds(actor):
    value = safe_call(lambda: actor.get_actor_bounds(False))
    if not isinstance(value, tuple) or len(value) < 2:
        return None
    origin, extent = value[0], value[1]
    try:
        return (
            float(origin.x) - float(extent.x),
            float(origin.x) + float(extent.x),
            float(origin.y) - float(extent.y),
            float(origin.y) + float(extent.y),
            float(origin.z) - float(extent.z),
            float(origin.z) + float(extent.z),
        )
    except Exception:
        return None


def probe_bounds():
    cx, cy, cz = PROBE_CENTER
    ex, ey, ez = PROBE_EXTENT
    return (cx - ex, cx + ex, cy - ey, cy + ey, cz - ez, cz + ez)


def overlaps(a, b):
    if a is None or b is None:
        return False
    return not (
        a[1] < b[0] or a[0] > b[1]
        or a[3] < b[2] or a[2] > b[3]
        or a[5] < b[4] or a[4] > b[5]
    )


def count_state(actors, data_class):
    sections = [actor for actor in actors if is_section_actor(actor)]
    kinds = {"PREVIEW": 0, "INTERACTIVE": 0, "COMPILED": 0}
    data_rows = []
    overlapping_data_rows = []
    target_bounds = probe_bounds()

    for section in sections:
        kinds[section_kind(section)] += 1
        components = list(safe_call(
            lambda section=section: section.get_components_by_class(data_class),
            [],
        ) or [])
        bounds = actor_bounds(section)
        for component in components:
            row = (section, component, bounds)
            data_rows.append(row)
            if overlaps(bounds, target_bounds):
                overlapping_data_rows.append(row)

    return sections, kinds, data_rows, overlapping_data_rows


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before building the bounded preview cache")
    except AttributeError:
        pass

    log("AETHER STAGE 15B - BOUNDED MESH TERRAIN PCG PREVIEW CACHE BUILD (C++ BRIDGE)")
    log("=" * 108)
    log("BOUNDED_PREVIEW_BUILD_ONLY=TRUE")
    log("WHOLE_WORLD_BUILD=FALSE")
    log("COMPILED_MESH_PARTITION_BUILD_STARTED=FALSE")
    log("PCG_GENERATION_STARTED=FALSE")
    log("GRAPH_MODIFIED=FALSE")
    log("LEVEL_PACKAGE_SAVED=FALSE")
    log("BRIDGE_ROUTE=AetherFlightEditor C++ UFUNCTION -> UMeshPartitionEditorComponent::BuildMegaMeshPreviewSections")

    world = current_world()
    if world is None or not object_path(world).startswith(MAP_PREFIX):
        raise RuntimeError(f"Open /Game/Maps/AetherWorld first. Current world={object_path(world)}")
    log(f"WORLD={object_path(world)}")

    bridge = getattr(unreal, "AetherMeshTerrainEditorLibrary", None)
    if bridge is None:
        raise RuntimeError(
            "AetherMeshTerrainEditorLibrary is unavailable. Close Unreal and run Build_AetherFlight.bat before reopening."
        )
    build_function = getattr(bridge, "build_bounded_preview_sections", None)
    if not callable(build_function):
        raise RuntimeError("The C++ bridge class loaded but build_bounded_preview_sections is unavailable")

    data_class = unreal.load_class(None, DATA_CLASS_PATH)
    if data_class is None:
        raise RuntimeError(f"Could not load required class {DATA_CLASS_PATH}")

    actors_before = all_actors()
    mesh_partition = find_exact_actor(actors_before, MESH_PARTITION_LABEL)
    adapter_actor = find_exact_actor(actors_before, ADAPTER_ACTOR_LABEL)
    log(f"MESH_PARTITION={object_path(mesh_partition)}")
    log(f"ADAPTER_ACTOR={object_path(adapter_actor)}")
    log(f"PROBE_CENTER={PROBE_CENTER}")
    log(f"PROBE_EXTENT={PROBE_EXTENT}")

    sections_before, kinds_before, data_before, overlap_before = count_state(actors_before, data_class)
    log(f"PREVIEW_SECTION_COUNT_BEFORE={kinds_before['PREVIEW']}")
    log(f"INTERACTIVE_SECTION_COUNT_BEFORE={kinds_before['INTERACTIVE']}")
    log(f"COMPILED_SECTION_COUNT_BEFORE={kinds_before['COMPILED']}")
    log(f"PCG_DATA_COMPONENT_COUNT_BEFORE={len(data_before)}")
    log(f"PROBE_OVERLAPPING_PCG_DATA_COMPONENT_COUNT_BEFORE={len(overlap_before)}")

    result = bool(build_function(
        MESH_PARTITION_LABEL,
        unreal.Vector(*PROBE_CENTER),
        unreal.Vector(*PROBE_EXTENT),
        True,
    ))
    log(f"CPP_BRIDGE_CALL_RETURN={result}")
    if not result:
        raise RuntimeError("The C++ bounded preview build bridge returned false; inspect LogAetherMeshTerrainEditor")

    actors_after = all_actors()
    sections_after, kinds_after, data_after, overlap_after = count_state(actors_after, data_class)
    log(f"PREVIEW_SECTION_COUNT_AFTER={kinds_after['PREVIEW']}")
    log(f"INTERACTIVE_SECTION_COUNT_AFTER={kinds_after['INTERACTIVE']}")
    log(f"COMPILED_SECTION_COUNT_AFTER={kinds_after['COMPILED']}")
    log(f"PCG_DATA_COMPONENT_COUNT_AFTER={len(data_after)}")
    log(f"PROBE_OVERLAPPING_PCG_DATA_COMPONENT_COUNT_AFTER={len(overlap_after)}")

    for index, (section, component, bounds) in enumerate(overlap_after):
        log(
            f"OVERLAPPING_PCG_DATA_{index:02d}=section:{actor_label(section)} "
            f"section_class:{class_path(section)} component:{object_path(component)} bounds:{bounds}"
        )

    cache_ready = bool(sections_after and data_after and overlap_after)
    log(f"PCG_CACHE_READY={cache_ready}")
    if not cache_ready:
        raise RuntimeError(
            "The native bounded preview call completed but did not produce an overlapping PCGDataComponent cache"
        )

    log("BOUNDED_PREVIEW_CACHE_BUILD_CPP_RESULT=PASS")
    log("NEXT=Run RUN_THIS_STAGE15B_VALIDATE_MESH_TERRAIN_PCG_ADAPTER.py without restarting Unreal.")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PCG_GENERATION_STARTED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()


try:
    main()
except Exception as exc:
    log("BOUNDED_PREVIEW_CACHE_BUILD_CPP_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PCG_GENERATION_STARTED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE15B_BOUNDED_PCG_PREVIEW_CPP_FAILED={type(exc).__name__}: {exc}")
    raise
