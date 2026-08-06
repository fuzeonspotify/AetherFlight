"""Guarded Stage 15B Mesh Terrain PCG Adapter installer for UE 5.8.1.

The Stage 15B prerequisite audit proved that river probe bounds overlap real Mesh
Terrain preview geometry, but AetherWorld contains no PCGAdapterComponent and no
PCGDataComponent section caches. Epic's Mesh Terrain PCG Query samples those
section caches, so the Query correctly returns no data until an adapter exists.

This script creates exactly one saved modifier actor containing exactly one
PCGAdapterComponent and assigns it to MeshTerrain_AetherWorld. It does not alter
the PCG graph, Query settings, biome volume, Mesh Partition Definition, weight
channels, or any existing terrain modifier. It does not start a compiled Mesh
Partition build or PCG generation. Adding the adapter is expected to invalidate
and asynchronously refresh editor preview sections so they can receive caches.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BMeshTerrainPCGAdapterInstall.txt"
MAP_PREFIX = "/Game/Maps/AetherWorld"
MESH_PARTITION_LABEL = "MeshTerrain_AetherWorld"
ADAPTER_ACTOR_LABEL = "Aether_Stage15B_MeshTerrainPCGAdapter"
ADAPTER_TAG = "AetherStage15BMeshTerrainPCGAdapter"
ADAPTER_CLASS_PATH = "/Script/PCGMeshPartitionInteropEditor.PCGAdapterComponent"
DATA_CLASS_PATH = "/Script/PCGMeshPartitionInterop.PCGDataComponent"

LINES = []


def log(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES).rstrip() + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_STAGE15B_PCG_ADAPTER_INSTALL_REPORT={REPORT_PATH}")


def safe_call(fn, fallback=None):
    try:
        return fn()
    except Exception:
        return fallback


def class_path(obj):
    cls = safe_call(lambda: obj.get_class())
    if cls is not None:
        value = safe_call(lambda: cls.get_path_name())
        if value:
            return str(value)
    return type(obj).__name__ if obj is not None else "NONE"


def object_path(obj):
    if obj is None:
        return "NONE"
    for fn in (lambda: obj.get_path_name(), lambda: obj.get_full_name(), lambda: str(obj)):
        value = safe_call(fn)
        if value:
            return str(value)
    return "UNKNOWN"


def actor_label(actor):
    return str(safe_call(lambda: actor.get_actor_label(), safe_call(lambda: actor.get_name(), "UNKNOWN")))


def actor_tags(actor):
    values = safe_call(lambda: actor.get_editor_property("tags"), []) or []
    return [str(value).strip('Name()"') for value in list(values)]


def all_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return subsystem, list(subsystem.get_all_level_actors())


def all_components(actor):
    component_class = getattr(unreal, "ActorComponent", None)
    if component_class is None:
        return []
    return list(safe_call(lambda: actor.get_components_by_class(component_class), []) or [])


def components_of_class(actors, component_class):
    rows = []
    for actor in actors:
        for component in list(safe_call(lambda actor=actor: actor.get_components_by_class(component_class), []) or []):
            rows.append((actor, component))
    return rows


def find_exact_actor(actors, label):
    return [actor for actor in actors if actor_label(actor) == label]


def find_mesh_partition(actors):
    matches = [actor for actor in actors if actor_label(actor) == MESH_PARTITION_LABEL]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {MESH_PARTITION_LABEL}; found {len(matches)}")
    return matches[0]


def add_component_to_actor(actor, component_class):
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = list(subsystem.k2_gather_subobject_data_for_instance(actor))
    if not handles:
        raise RuntimeError("SubobjectDataSubsystem returned no actor root handle")

    params = unreal.AddNewSubobjectParams()
    params.set_editor_property("parent_handle", handles[0])
    params.set_editor_property("new_class", component_class)
    new_handle, fail_reason = subsystem.add_new_subobject(params)
    if not unreal.SubobjectDataBlueprintFunctionLibrary.is_handle_valid(new_handle):
        raise RuntimeError(f"Could not add PCGAdapterComponent: {fail_reason}")

    data = subsystem.k2_find_subobject_data_from_handle(new_handle)
    component = unreal.SubobjectDataBlueprintFunctionLibrary.get_associated_object(data) if data else None
    if component is None:
        raise RuntimeError("PCGAdapterComponent was added but its associated object was not resolved")
    return component


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


def assign_partition(component, mesh_partition):
    errors = []
    for method_name in (
        "bp_set_affected_mega_mesh",
        "set_affected_mesh_partition",
        "set_affected_mega_mesh",
    ):
        method = getattr(component, method_name, None)
        if not callable(method):
            continue
        try:
            method(mesh_partition)
            if get_affected_partition(component) is mesh_partition:
                return f"METHOD:{method_name}"
        except Exception as exc:
            errors.append(f"{method_name}:{type(exc).__name__}:{exc}")

    for property_name in ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"):
        try:
            component.set_editor_property(property_name, mesh_partition)
            if get_affected_partition(component) is mesh_partition:
                return f"PROPERTY:{property_name}"
        except Exception as exc:
            errors.append(f"{property_name}:{type(exc).__name__}:{exc}")

    raise RuntimeError("Could not assign adapter to MeshTerrain_AetherWorld: " + " | ".join(errors[:12]))


def set_disabled(component, value):
    method = getattr(component, "set_is_disabled_flag", None)
    if callable(method):
        try:
            method(bool(value))
            return "set_is_disabled_flag"
        except Exception:
            pass
    for property_name in ("is_disabled", "disabled"):
        try:
            component.set_editor_property(property_name, bool(value))
            return property_name
        except Exception:
            pass
    return "UNEXPOSED"


def set_last_priority_layer_when_exposed(component):
    layers = []
    getter = getattr(component, "get_definition_priority_layers", None)
    if callable(getter):
        layers = [str(value).strip('Name()"') for value in list(safe_call(getter, []) or [])]
        layers = [value for value in layers if value and value.lower() not in ("none", "name")]
    if not layers:
        return "UNEXPOSED_OR_EMPTY", "UNCHANGED", []

    chosen = layers[-1]
    setter = getattr(component, "set_priority_layer", None)
    if callable(setter):
        try:
            setter(unreal.Name(chosen))
            readback = safe_call(lambda: component.get_priority_layer(), "UNEXPOSED")
            return chosen, f"METHOD_READBACK:{readback}", layers
        except Exception as exc:
            return chosen, f"SET_WARNING:{type(exc).__name__}:{exc}", layers
    return chosen, "SETTER_UNEXPOSED_UNCHANGED", layers


def set_subpriority_after_existing(component, actors, mesh_partition, chosen_layer):
    maximum = None
    rows = []
    for actor in actors:
        for other in all_components(actor):
            if other is component:
                continue
            affected = get_affected_partition(other)
            if affected is not mesh_partition:
                continue
            get_layer = getattr(other, "get_priority_layer", None)
            layer = str(safe_call(get_layer, "UNEXPOSED")) if callable(get_layer) else "UNEXPOSED"
            get_priority = getattr(other, "get_priority", None)
            priority = safe_call(get_priority) if callable(get_priority) else safe_call(lambda: other.get_editor_property("priority"))
            try:
                priority = float(priority)
            except Exception:
                continue
            rows.append((actor_label(actor), class_path(other), layer, priority))
            if chosen_layer in ("UNEXPOSED_OR_EMPTY", "") or chosen_layer in layer:
                maximum = priority if maximum is None else max(maximum, priority)

    desired = (maximum + 1.0) if maximum is not None else 100.0
    setter = getattr(component, "set_priority", None)
    route = "UNEXPOSED_UNCHANGED"
    if callable(setter):
        try:
            setter(float(desired))
            route = "METHOD:set_priority"
        except Exception as exc:
            route = f"METHOD_WARNING:{type(exc).__name__}:{exc}"
    else:
        try:
            component.set_editor_property("priority", float(desired))
            route = "PROPERTY:priority"
        except Exception as exc:
            route = f"PROPERTY_WARNING:{type(exc).__name__}:{exc}"
    readback = safe_call(lambda: component.get_priority(), safe_call(lambda: component.get_editor_property("priority"), "UNEXPOSED"))
    return desired, readback, route, rows


def save_current_level():
    subsystem_class = getattr(unreal, "LevelEditorSubsystem", None)
    if subsystem_class is not None:
        result = safe_call(lambda: unreal.get_editor_subsystem(subsystem_class).save_current_level())
        if bool(result):
            return True, "LevelEditorSubsystem.save_current_level"
    result = safe_call(lambda: unreal.EditorLevelLibrary.save_current_level())
    if bool(result):
        return True, "EditorLevelLibrary.save_current_level"
    return False, "NO_SAVE_ROUTE_REPORTED_SUCCESS"


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before installing the Mesh Terrain PCG Adapter")
    except AttributeError:
        pass

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world is None or not str(world.get_path_name()).startswith(MAP_PREFIX):
        raise RuntimeError(f"Open /Game/Maps/AetherWorld first. Current={object_path(world)}")

    actor_subsystem, actors = all_actors()
    mesh_partition = find_mesh_partition(actors)
    adapter_class = unreal.load_class(None, ADAPTER_CLASS_PATH)
    data_class = unreal.load_class(None, DATA_CLASS_PATH)
    if adapter_class is None or data_class is None:
        raise RuntimeError("Required PCG Mesh Partition Interop classes did not load")

    existing_adapters = components_of_class(actors, adapter_class)
    target_actors = find_exact_actor(actors, ADAPTER_ACTOR_LABEL)
    existing_data = components_of_class(actors, data_class)

    log("AETHER STAGE 15B - MESH TERRAIN PCG ADAPTER INSTALL")
    log("=" * 108)
    log("ROOT_CAUSE=MISSING_PCG_ADAPTER_AND_SECTION_DATA_CACHE")
    log("GRAPH_MODIFIED=FALSE")
    log("QUERY_SETTINGS_MODIFIED=FALSE")
    log("BIOME_VOLUME_MODIFIED=FALSE")
    log("MESH_PARTITION_DEFINITION_MODIFIED=FALSE")
    log("WEIGHT_CHANNELS_MODIFIED=FALSE")
    log("PCG_GENERATION_STARTED=FALSE")
    log("COMPILED_MESH_PARTITION_BUILD_STARTED=FALSE")
    log("EDITOR_PREVIEW_INVALIDATION_EXPECTED=TRUE")
    log(f"WORLD={object_path(world)}")
    log(f"MESH_PARTITION={object_path(mesh_partition)}")
    log(f"EXISTING_ADAPTER_COMPONENT_COUNT={len(existing_adapters)}")
    log(f"EXISTING_TARGET_ACTOR_COUNT={len(target_actors)}")
    log(f"PCG_DATA_COMPONENT_COUNT_BEFORE={len(existing_data)}")

    if len(existing_adapters) == 1 and len(target_actors) == 1:
        actor, component = existing_adapters[0]
        if actor is not target_actors[0] or get_affected_partition(component) is not mesh_partition:
            raise RuntimeError("An existing adapter is present but does not match the expected saved installation")
        log("INSTALL_ACTION=ALREADY_PRESENT")
        log(f"ADAPTER_ACTOR={object_path(actor)}")
        log(f"ADAPTER_COMPONENT={object_path(component)}")
        log("PCG_ADAPTER_INSTALL_RESULT=PASS")
        log("NEXT=Wait for Mesh Terrain preview processing, then run RUN_THIS_STAGE15B_VALIDATE_MESH_TERRAIN_PCG_ADAPTER.py")
        write_report()
        return

    if existing_adapters or target_actors:
        raise RuntimeError(
            f"Unexpected partial/duplicate adapter state: adapters={len(existing_adapters)} target_actors={len(target_actors)}"
        )

    candidate = actor_subsystem.spawn_actor_from_class(unreal.Actor, unreal.Vector(), unreal.Rotator(), False)
    if candidate is None:
        raise RuntimeError("Could not spawn the PCG Adapter modifier actor")

    saved = False
    try:
        candidate.set_actor_label(ADAPTER_ACTOR_LABEL, True)
        candidate.set_editor_property("tags", [unreal.Name(ADAPTER_TAG)])
        try:
            candidate.set_editor_property("is_spatially_loaded", False)
        except Exception:
            pass

        component = add_component_to_actor(candidate, adapter_class)
        disable_route = set_disabled(component, True)
        assignment_route = assign_partition(component, mesh_partition)
        chosen_layer, layer_route, available_layers = set_last_priority_layer_when_exposed(component)
        desired_priority, priority_readback, priority_route, existing_modifier_rows = set_subpriority_after_existing(
            component, actors, mesh_partition, chosen_layer
        )
        enable_route = set_disabled(component, False)

        safe_call(lambda: candidate.modify())
        safe_call(lambda: component.modify())

        affected = get_affected_partition(component)
        if affected is not mesh_partition:
            raise RuntimeError(f"Adapter affected-partition readback failed: {object_path(affected)}")

        adapter_components = list(candidate.get_components_by_class(adapter_class))
        if len(adapter_components) != 1 or adapter_components[0] is not component:
            raise RuntimeError(f"Candidate adapter component count/readback failed: {len(adapter_components)}")

        compute_bounds = getattr(component, "compute_bounds", None)
        computed_bounds = safe_call(compute_bounds, "UNEXPOSED") if callable(compute_bounds) else "UNEXPOSED"
        registered = safe_call(lambda: component.is_registered(), "UNEXPOSED")
        disabled_readback = safe_call(lambda: component.get_is_disabled_flag(), safe_call(lambda: component.get_editor_property("is_disabled"), "UNEXPOSED"))

        log("INSTALL_ACTION=CREATED")
        log(f"ADAPTER_ACTOR={object_path(candidate)}")
        log(f"ADAPTER_COMPONENT={object_path(component)}")
        log(f"ADAPTER_CLASS={class_path(component)}")
        log(f"ADAPTER_REGISTERED={registered}")
        log(f"ADAPTER_DISABLE_DURING_CONFIGURATION_ROUTE={disable_route}")
        log(f"ADAPTER_ASSIGNMENT_ROUTE={assignment_route}")
        log(f"ADAPTER_AFFECTED_PARTITION={object_path(affected)}")
        log(f"AVAILABLE_PRIORITY_LAYERS={available_layers}")
        log(f"CHOSEN_FINAL_PRIORITY_LAYER={chosen_layer}")
        log(f"PRIORITY_LAYER_ROUTE={layer_route}")
        log(f"DESIRED_SUBPRIORITY={desired_priority}")
        log(f"SUBPRIORITY_READBACK={priority_readback}")
        log(f"SUBPRIORITY_ROUTE={priority_route}")
        log(f"EXISTING_AFFECTED_MODIFIER_COUNT={len(existing_modifier_rows)}")
        for index, row in enumerate(existing_modifier_rows):
            log(f"EXISTING_MODIFIER_{index:02d}=actor:{row[0]} class:{row[1]} layer:{row[2]} priority:{row[3]}")
        log(f"ADAPTER_ENABLE_ROUTE={enable_route}")
        log(f"ADAPTER_DISABLED_READBACK={disabled_readback}")
        log(f"ADAPTER_COMPUTED_BOUNDS={computed_bounds}")

        saved, save_route = save_current_level()
        log(f"LEVEL_SAVE_ROUTE={save_route}")
        log(f"LEVEL_SAVE_RESULT={saved}")
        if not saved:
            raise RuntimeError("The adapter was configured but the level save did not report success")

        log("PCG_ADAPTER_INSTALL_RESULT=PASS")
        log("NEXT=Do not run the biome probe yet. Wait for editor preview processing, then run RUN_THIS_STAGE15B_VALIDATE_MESH_TERRAIN_PCG_ADAPTER.py")
    except Exception:
        if not saved:
            safe_call(lambda: actor_subsystem.destroy_actor(candidate))
        raise

    write_report()


try:
    main()
except Exception as exc:
    log("")
    log("PCG_ADAPTER_INSTALL_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("GRAPH_MODIFIED=FALSE")
    log("QUERY_SETTINGS_MODIFIED=FALSE")
    log("BIOME_VOLUME_MODIFIED=FALSE")
    log("PCG_GENERATION_STARTED=FALSE")
    log("COMPILED_MESH_PARTITION_BUILD_STARTED=FALSE")
    log("ON_FAILURE=Close Unreal without saving before another install attempt if the level is dirty")
    write_report()
    unreal.log_error("\n".join(LINES))
    raise
