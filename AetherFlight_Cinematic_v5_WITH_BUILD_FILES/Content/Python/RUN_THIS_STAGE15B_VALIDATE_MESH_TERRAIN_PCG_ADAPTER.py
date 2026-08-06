"""Read-only validator for the Stage 15B Mesh Terrain PCG Adapter installation.

Run only after RUN_THIS_STAGE15B_INSTALL_MESH_TERRAIN_PCG_ADAPTER.py reports PASS
and the editor has finished Mesh Terrain preview processing. This validates the
saved adapter assignment and proves that PCGDataComponent caches now exist on the
loaded section overlapping the bounded river probe.

No actor, component, graph, package, PCG output, or Mesh Partition data is changed,
saved, generated, cleaned, invalidated, or built.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BMeshTerrainPCGAdapterValidation.txt"
MAP_PREFIX = "/Game/Maps/AetherWorld"
MESH_PARTITION_LABEL = "MeshTerrain_AetherWorld"
ADAPTER_ACTOR_LABEL = "Aether_Stage15B_MeshTerrainPCGAdapter"
ADAPTER_CLASS_PATH = "/Script/PCGMeshPartitionInteropEditor.PCGAdapterComponent"
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
    unreal.log_warning(f"AETHER_STAGE15B_PCG_ADAPTER_VALIDATION_REPORT={REPORT_PATH}")


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


def all_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return list(subsystem.get_all_level_actors())


def get_affected_partition(component):
    for method_name in ("get_affected_mesh_partition", "get_affected_mega_mesh"):
        method = getattr(component, method_name, None)
        if callable(method):
            value = safe_call(method)
            if value is not None:
                return value
    for property_name in ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"):
        value = safe_call(lambda property_name=property_name: component.get_editor_property(property_name))
        if value is not None:
            return value
    return None


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
    x, y, z = PROBE_CENTER
    ex, ey, ez = PROBE_EXTENT
    return (x - ex, x + ex, y - ey, y + ey, z - ez, z + ez)


def overlaps(a, b):
    if a is None or b is None:
        return False
    return not (
        a[1] < b[0] or a[0] > b[1]
        or a[3] < b[2] or a[2] > b[3]
        or a[5] < b[4] or a[4] > b[5]
    )


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before validating the Mesh Terrain PCG Adapter")
    except AttributeError:
        pass

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world is None or not str(world.get_path_name()).startswith(MAP_PREFIX):
        raise RuntimeError(f"Open /Game/Maps/AetherWorld first. Current={object_path(world)}")

    adapter_class = unreal.load_class(None, ADAPTER_CLASS_PATH)
    data_class = unreal.load_class(None, DATA_CLASS_PATH)
    if adapter_class is None or data_class is None:
        raise RuntimeError("Required PCG Mesh Partition Interop classes did not load")

    actors = all_actors()
    partitions = [actor for actor in actors if actor_label(actor) == MESH_PARTITION_LABEL]
    adapter_actors = [actor for actor in actors if actor_label(actor) == ADAPTER_ACTOR_LABEL]
    if len(partitions) != 1:
        raise RuntimeError(f"Expected one {MESH_PARTITION_LABEL}; found {len(partitions)}")
    if len(adapter_actors) != 1:
        raise RuntimeError(f"Expected one {ADAPTER_ACTOR_LABEL}; found {len(adapter_actors)}")

    partition = partitions[0]
    adapter_actor = adapter_actors[0]
    adapters = list(adapter_actor.get_components_by_class(adapter_class))
    if len(adapters) != 1:
        raise RuntimeError(f"Expected one PCGAdapterComponent on saved adapter actor; found {len(adapters)}")
    adapter = adapters[0]

    affected = get_affected_partition(adapter)
    registered = safe_call(lambda: adapter.is_registered(), "UNEXPOSED")
    disabled = safe_call(
        lambda: adapter.get_is_disabled_flag(),
        safe_call(lambda: adapter.get_editor_property("is_disabled"), "UNEXPOSED"),
    )
    priority_layer = safe_call(lambda: adapter.get_priority_layer(), "UNEXPOSED")
    priority = safe_call(lambda: adapter.get_priority(), safe_call(lambda: adapter.get_editor_property("priority"), "UNEXPOSED"))
    computed_bounds = safe_call(lambda: adapter.compute_bounds(), "UNEXPOSED")

    sections = [actor for actor in actors if is_section_actor(actor)]
    p_bounds = probe_bounds()
    data_rows = []
    overlapping_data_rows = []
    section_counts = {"PREVIEW": 0, "INTERACTIVE": 0, "COMPILED": 0}

    for section in sections:
        kind = section_kind(section)
        section_counts[kind] += 1
        section_data = list(safe_call(lambda section=section: section.get_components_by_class(data_class), []) or [])
        bounds = actor_bounds(section)
        section_overlaps = overlaps(bounds, p_bounds)
        for component in section_data:
            mesh_value = safe_call(lambda component=component: component.get_mesh(), "UNEXPOSED")
            spatial_value = safe_call(lambda component=component: component.get_spatial(), "UNEXPOSED")
            row = {
                "section": actor_label(section),
                "kind": kind,
                "section_path": object_path(section),
                "component": object_path(component),
                "bounds": bounds,
                "overlap": section_overlaps,
                "mesh": mesh_value,
                "spatial": spatial_value,
            }
            data_rows.append(row)
            if section_overlaps:
                overlapping_data_rows.append(row)

    failures = []
    if affected is not partition:
        failures.append(f"adapter affected partition mismatch: {object_path(affected)}")
    if disabled is True:
        failures.append("adapter is disabled")
    if len(data_rows) == 0:
        failures.append("no PCGDataComponent caches exist on loaded Mesh Terrain sections")
    if len(overlapping_data_rows) == 0:
        failures.append("no PCGDataComponent cache exists on a section overlapping the bounded river probe")

    cache_ready = len(data_rows) > 0 and len(overlapping_data_rows) > 0
    result = "PASS" if not failures else ("PENDING" if affected is partition and len(data_rows) == 0 else "FAIL")

    log("AETHER STAGE 15B - MESH TERRAIN PCG ADAPTER / CACHE VALIDATION")
    log("=" * 108)
    log("READ_ONLY=TRUE")
    log("NO_ASSETS_MODIFIED=TRUE")
    log("NO_ACTORS_MODIFIED=TRUE")
    log("NO_COMPONENTS_MODIFIED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PCG_GENERATION_STARTED=TRUE")
    log("NO_MESH_PARTITION_BUILD_STARTED=TRUE")
    log(f"WORLD={object_path(world)}")
    log(f"MESH_PARTITION={object_path(partition)}")
    log(f"ADAPTER_ACTOR={object_path(adapter_actor)}")
    log(f"ADAPTER_COMPONENT={object_path(adapter)}")
    log(f"ADAPTER_CLASS={class_path(adapter)}")
    log(f"ADAPTER_REGISTERED={registered}")
    log(f"ADAPTER_AFFECTED_PARTITION={object_path(affected)}")
    log(f"ADAPTER_DISABLED={disabled}")
    log(f"ADAPTER_PRIORITY_LAYER={priority_layer}")
    log(f"ADAPTER_SUBPRIORITY={priority}")
    log(f"ADAPTER_COMPUTED_BOUNDS={computed_bounds}")
    log(f"PREVIEW_SECTION_COUNT={section_counts['PREVIEW']}")
    log(f"INTERACTIVE_SECTION_COUNT={section_counts['INTERACTIVE']}")
    log(f"COMPILED_SECTION_COUNT={section_counts['COMPILED']}")
    log(f"PCG_DATA_COMPONENT_COUNT={len(data_rows)}")
    log(f"PROBE_OVERLAPPING_PCG_DATA_COMPONENT_COUNT={len(overlapping_data_rows)}")
    for index, row in enumerate(data_rows):
        log(
            f"PCG_DATA_{index:02d}=section:{row['section']} kind:{row['kind']} "
            f"component:{row['component']} overlap_probe:{row['overlap']} bounds:{row['bounds']} "
            f"mesh_access:{row['mesh']} spatial_access:{row['spatial']}"
        )
    log(f"PCG_CACHE_READY={cache_ready}")
    log(f"VALIDATION_ISSUE_COUNT={len(failures)}")
    for index, failure in enumerate(failures, 1):
        log(f"VALIDATION_ISSUE_{index:02d}={failure}")
    log(f"PCG_ADAPTER_VALIDATION_RESULT={result}")
    if result == "PASS":
        log("NEXT=The Query prerequisite is now satisfied. Recreate the bounded temporary probe and inspect Query output before changing graph settings.")
    elif result == "PENDING":
        log("NEXT=Wait for Mesh Terrain preview processing to finish and rerun this same read-only validator. Do not run the biome probe yet.")
    else:
        log("NEXT=Do not run the biome probe. Review the adapter assignment and cache rows before any repair.")
    write_report()


try:
    main()
except Exception as exc:
    log("AETHER STAGE 15B - MESH TERRAIN PCG ADAPTER / CACHE VALIDATION")
    log("=" * 108)
    log("PCG_ADAPTER_VALIDATION_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("READ_ONLY=TRUE")
    log("NO_ASSETS_MODIFIED=TRUE")
    log("NO_ACTORS_MODIFIED=TRUE")
    log("NO_COMPONENTS_MODIFIED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PCG_GENERATION_STARTED=TRUE")
    log("NO_MESH_PARTITION_BUILD_STARTED=TRUE")
    write_report()
    unreal.log_error("\n".join(LINES))
    raise
