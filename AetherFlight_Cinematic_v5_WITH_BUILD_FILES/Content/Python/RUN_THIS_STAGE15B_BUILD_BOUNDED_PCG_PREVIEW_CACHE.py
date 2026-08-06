"""Build only the bounded Stage 15B river-probe Mesh Terrain preview section.

The PCG Adapter is already installed and saved. The validation report showed that
no preview/interactive/compiled section actors were loaded, so there was no
section post-build event on which the adapter could create UPCGDataComponent.

This script uses UMeshPartitionEditorComponent::BuildMegaMeshPreviewSections with
one exact 300 m x 200 m x 1000 m box matching the existing Stage 15B probe. It
forces that preview build synchronously when the exposed API supports it, then
checks for a PCGDataComponent on an overlapping section.

It does not build compiled/runtime sections, does not rebuild the whole world,
does not modify/save the PCG graph or level, and does not start PCG generation.
Preview sections and PCGDataComponents created here are transient editor state.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BBoundedPCGPreviewCacheBuild.txt"
MAP_PREFIX = "/Game/Maps/AetherWorld"
MESH_PARTITION_LABEL = "MeshTerrain_AetherWorld"
ADAPTER_ACTOR_LABEL = "Aether_Stage15B_MeshTerrainPCGAdapter"
EDITOR_COMPONENT_CLASS_PATH = "/Script/MeshPartitionEditor.MeshPartitionEditorComponent"
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
    unreal.log_warning(f"AETHER_STAGE15B_BOUNDED_PCG_PREVIEW_CACHE_REPORT={REPORT_PATH}")


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


def load_class_required(path):
    value = unreal.load_class(None, path)
    if value is None:
        raise RuntimeError(f"Required class could not be loaded: {path}")
    return value


def find_single_actor(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one actor labelled {label}; found {len(matches)}")
    return matches[0]


def get_single_component(actor, component_class, description):
    values = list(safe_call(lambda: actor.get_components_by_class(component_class), []) or [])
    if len(values) != 1:
        raise RuntimeError(f"Expected exactly one {description} on {actor_label(actor)}; found {len(values)}")
    return values[0]


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


def vector(xyz):
    return unreal.Vector(float(xyz[0]), float(xyz[1]), float(xyz[2]))


def make_probe_box():
    minimum = vector(tuple(PROBE_CENTER[i] - PROBE_EXTENT[i] for i in range(3)))
    maximum = vector(tuple(PROBE_CENTER[i] + PROBE_EXTENT[i] for i in range(3)))
    box_class = getattr(unreal, "Box", None)
    if box_class is None:
        raise RuntimeError("unreal.Box is unavailable")

    errors = []
    for attempt in (
        lambda: box_class(min=minimum, max=maximum, is_valid=True),
        lambda: box_class(minimum, maximum),
        lambda: box_class(),
    ):
        try:
            box = attempt()
            if box is None:
                continue
            for name, value in (("min", minimum), ("max", maximum), ("is_valid", True)):
                try:
                    box.set_editor_property(name, value)
                except Exception:
                    try:
                        setattr(box, name, value)
                    except Exception:
                        pass
            exported = safe_call(lambda: box.export_text(), str(box))
            if "is_valid: True" in str(exported) or "bIsValid=True" in str(exported) or "IsValid=True" in str(exported):
                return box, minimum, maximum
            # UE's Box string may omit the valid flag; exact min/max readback is enough.
            stored_min = safe_call(lambda: box.get_editor_property("min"), safe_call(lambda: box.min))
            stored_max = safe_call(lambda: box.get_editor_property("max"), safe_call(lambda: box.max))
            if stored_min is not None and stored_max is not None:
                return box, minimum, maximum
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
    raise RuntimeError("Could not construct exact unreal.Box: " + " | ".join(errors))


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
            float(origin.x) - float(extent.x), float(origin.x) + float(extent.x),
            float(origin.y) - float(extent.y), float(origin.y) + float(extent.y),
            float(origin.z) - float(extent.z), float(origin.z) + float(extent.z),
        )
    except Exception:
        return None


def probe_bounds_tuple():
    return (
        PROBE_CENTER[0] - PROBE_EXTENT[0], PROBE_CENTER[0] + PROBE_EXTENT[0],
        PROBE_CENTER[1] - PROBE_EXTENT[1], PROBE_CENTER[1] + PROBE_EXTENT[1],
        PROBE_CENTER[2] - PROBE_EXTENT[2], PROBE_CENTER[2] + PROBE_EXTENT[2],
    )


def overlaps(a, b):
    if a is None or b is None:
        return False
    return not (
        a[1] < b[0] or a[0] > b[1]
        or a[3] < b[2] or a[2] > b[3]
        or a[5] < b[4] or a[4] > b[5]
    )


def collect_state(data_class):
    actors = all_actors()
    sections = [actor for actor in actors if is_section_actor(actor)]
    counts = {"PREVIEW": 0, "INTERACTIVE": 0, "COMPILED": 0}
    data_rows = []
    overlap_count = 0
    target_bounds = probe_bounds_tuple()
    for section in sections:
        kind = section_kind(section)
        counts[kind] = counts.get(kind, 0) + 1
        components = list(safe_call(lambda section=section: section.get_components_by_class(data_class), []) or [])
        section_overlaps = overlaps(actor_bounds(section), target_bounds)
        for component in components:
            data_rows.append((section, component, section_overlaps))
            if section_overlaps:
                overlap_count += 1
    return actors, sections, counts, data_rows, overlap_count


def require_callable(obj, name):
    method = getattr(obj, name, None)
    if not callable(method):
        raise RuntimeError(f"Required MeshPartitionEditorComponent method is not Python-exposed: {name}")
    return method


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before building the bounded Stage 15B preview cache")
    except AttributeError:
        pass

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world is None or not object_path(world).startswith(MAP_PREFIX):
        raise RuntimeError(f"Open /Game/Maps/AetherWorld first. Current={object_path(world)}")

    log("AETHER STAGE 15B - BOUNDED MESH TERRAIN PCG PREVIEW CACHE BUILD")
    log("=" * 108)
    log("BOUNDED_PREVIEW_BUILD_ONLY=TRUE")
    log("WHOLE_WORLD_BUILD=FALSE")
    log("COMPILED_MESH_PARTITION_BUILD_STARTED=FALSE")
    log("PCG_GENERATION_STARTED=FALSE")
    log("GRAPH_MODIFIED=FALSE")
    log("LEVEL_PACKAGE_SAVED=FALSE")

    editor_class = load_class_required(EDITOR_COMPONENT_CLASS_PATH)
    adapter_class = load_class_required(ADAPTER_CLASS_PATH)
    data_class = load_class_required(DATA_CLASS_PATH)

    actors = all_actors()
    mesh_partition = find_single_actor(actors, MESH_PARTITION_LABEL)
    adapter_actor = find_single_actor(actors, ADAPTER_ACTOR_LABEL)
    editor_component = get_single_component(mesh_partition, editor_class, "MeshPartitionEditorComponent")
    adapter_component = get_single_component(adapter_actor, adapter_class, "PCGAdapterComponent")

    if get_affected_partition(adapter_component) is not mesh_partition:
        raise RuntimeError("Saved PCG Adapter is not assigned to MeshTerrain_AetherWorld")
    disabled = safe_call(lambda: bool(adapter_component.get_editor_property("is_disabled")), False)
    if disabled:
        raise RuntimeError("Saved PCG Adapter is disabled")

    build_method = require_callable(editor_component, "build_mega_mesh_preview_sections")
    active_method = require_callable(editor_component, "is_any_preview_section_build_active")
    enabled_getter = require_callable(editor_component, "is_preview_section_build_enabled")
    enabled_setter = require_callable(editor_component, "set_preview_section_build_enabled")
    sync_getter = require_callable(editor_component, "is_synchronous_preview_section_build_forced")
    sync_setter = require_callable(editor_component, "set_force_synchronous_preview_section_build")

    if bool(active_method()):
        raise RuntimeError("A Mesh Terrain preview section build is already active")

    _, before_sections, before_counts, before_data, before_overlap = collect_state(data_class)
    log(f"WORLD={object_path(world)}")
    log(f"MESH_PARTITION={object_path(mesh_partition)}")
    log(f"EDITOR_COMPONENT={object_path(editor_component)}")
    log(f"ADAPTER_COMPONENT={object_path(adapter_component)}")
    log(f"PREVIEW_BUILD_ENABLED_BEFORE={bool(enabled_getter())}")
    log(f"SYNCHRONOUS_PREVIEW_BUILD_FORCED_BEFORE={bool(sync_getter())}")
    log(f"SECTION_COUNT_BEFORE={len(before_sections)}")
    log(f"PREVIEW_SECTION_COUNT_BEFORE={before_counts.get('PREVIEW', 0)}")
    log(f"INTERACTIVE_SECTION_COUNT_BEFORE={before_counts.get('INTERACTIVE', 0)}")
    log(f"COMPILED_SECTION_COUNT_BEFORE={before_counts.get('COMPILED', 0)}")
    log(f"PCG_DATA_COMPONENT_COUNT_BEFORE={len(before_data)}")
    log(f"PROBE_OVERLAPPING_PCG_DATA_COMPONENT_COUNT_BEFORE={before_overlap}")

    box, minimum, maximum = make_probe_box()
    log(f"BUILD_BOUNDS_MIN={minimum}")
    log(f"BUILD_BOUNDS_MAX={maximum}")
    log(f"BUILD_BOUNDS_EXPORT={safe_call(lambda: box.export_text(), str(box))}")

    original_enabled = bool(enabled_getter())
    original_sync = bool(sync_getter())
    restored_enabled = False
    restored_sync = False
    try:
        if not original_enabled:
            enabled_setter(True)
        sync_setter(True)
        log("PREVIEW_BUILD_ENABLED_FOR_CALL=True")
        log("SYNCHRONOUS_PREVIEW_BUILD_FORCED_FOR_CALL=True")
        result = build_method([box])
        log(f"BUILD_CALL_RETURN={result}")
        log(f"BUILD_ACTIVE_IMMEDIATELY_AFTER={bool(active_method())}")
    finally:
        # A forced synchronous build should be complete before return. Restore only
        # transient editor flags; no package is saved by these calls.
        if not bool(active_method()):
            sync_setter(original_sync)
            restored_sync = bool(sync_getter()) == original_sync
            if not original_enabled:
                enabled_setter(False)
                restored_enabled = bool(enabled_getter()) is False
            else:
                restored_enabled = True

    _, after_sections, after_counts, after_data, after_overlap = collect_state(data_class)
    log(f"TRANSIENT_SYNC_FLAG_RESTORED={restored_sync}")
    log(f"TRANSIENT_BUILD_ENABLED_FLAG_RESTORED={restored_enabled}")
    log(f"SECTION_COUNT_AFTER={len(after_sections)}")
    log(f"PREVIEW_SECTION_COUNT_AFTER={after_counts.get('PREVIEW', 0)}")
    log(f"INTERACTIVE_SECTION_COUNT_AFTER={after_counts.get('INTERACTIVE', 0)}")
    log(f"COMPILED_SECTION_COUNT_AFTER={after_counts.get('COMPILED', 0)}")
    log(f"PCG_DATA_COMPONENT_COUNT_AFTER={len(after_data)}")
    log(f"PROBE_OVERLAPPING_PCG_DATA_COMPONENT_COUNT_AFTER={after_overlap}")
    for index, (section, component, section_overlaps) in enumerate(after_data[:32]):
        log(
            f"PCG_DATA_{index:02d}=section:{actor_label(section)} "
            f"section_class:{class_path(section)} component:{object_path(component)} "
            f"probe_overlap:{section_overlaps}"
        )

    if bool(active_method()):
        log("BOUNDED_PREVIEW_CACHE_BUILD_RESULT=PENDING")
        log("NEXT=Wait for the bounded preview build to finish, then run RUN_THIS_STAGE15B_VALIDATE_MESH_TERRAIN_PCG_ADAPTER.py.")
    elif after_overlap > 0:
        log("PCG_CACHE_READY=True")
        log("BOUNDED_PREVIEW_CACHE_BUILD_RESULT=PASS")
        log("NEXT=Run RUN_THIS_STAGE15B_VALIDATE_MESH_TERRAIN_PCG_ADAPTER.py as an independent read-only confirmation.")
    elif len(after_sections) > 0:
        log("PCG_CACHE_READY=False")
        log("BOUNDED_PREVIEW_CACHE_BUILD_RESULT=FAIL")
        log("ERROR=Bounded preview sections were built, but the PCG Adapter created no overlapping PCGDataComponent.")
    else:
        log("PCG_CACHE_READY=False")
        log("BOUNDED_PREVIEW_CACHE_BUILD_RESULT=FAIL")
        log("ERROR=BuildMegaMeshPreviewSections returned without creating any loaded section actor.")

    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()


try:
    main()
except Exception as exc:
    log("")
    log("BOUNDED_PREVIEW_CACHE_BUILD_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PCG_GENERATION_STARTED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE15B_BOUNDED_PCG_PREVIEW_CACHE_FAILED={type(exc).__name__}: {exc}")
    raise
