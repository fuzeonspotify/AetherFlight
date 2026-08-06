"""Stage 14D: keep the grounded river environment present in PIE/runtime.

The Stage 13 actor was created at world origin while its HISM instances were
inserted in world space around the distant river. This guarded repair marks only
that 184-instance actor as non-spatially-loaded (Always Loaded), preserving all
instance transforms, collision settings, meshes, and the Mesh Partition setup.
No build method is called.
"""

from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
ENVIRONMENT_LABEL = "Aether_VideoStage13_RiverEnvironment"
ENVIRONMENT_TAG = "AetherVideoRiverEnvironmentStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14EnvironmentStreamingRepair.txt"
EXPECTED_COMPONENTS = {"rock": 4, "shrub": 2, "ground": 2}
EXPECTED_INSTANCES = {"rock": 30, "shrub": 44, "ground": 110}
LINES = []


def log(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def actor_tags(actor):
    try:
        return [str(v) for v in actor.get_editor_property("tags")]
    except Exception:
        return []


def safe_property(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        try:
            value = getattr(obj, name)
            return value() if callable(value) else value
        except Exception:
            return default


def load_world():
    world = None
    cls = getattr(unreal, "UnrealEditorSubsystem", None)
    if cls:
        try:
            world = unreal.get_editor_subsystem(cls).get_editor_world()
        except Exception:
            world = None
    if not world:
        world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        if cls:
            try:
                world = unreal.get_editor_subsystem(cls).get_editor_world()
            except Exception:
                world = None
        if not world:
            world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def all_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return subsystem, list(subsystem.get_all_level_actors())


def find_environment(actors):
    matches = [
        actor for actor in actors
        if actor_label(actor) == ENVIRONMENT_LABEL or ENVIRONMENT_TAG in actor_tags(actor)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Stage 13 environment actor, found {len(matches)}")
    return matches[0]


def component_tags(component):
    return [str(v) for v in (safe_property(component, "component_tags", []) or [])]


def category(component):
    text = " ".join(component_tags(component)).lower()
    for name in ("rock", "shrub", "ground"):
        if f"aetherriver_{name}" in text:
            return name
    return None


def instance_count(component):
    try:
        return int(component.get_instance_count())
    except Exception:
        return 0


def collision_enabled(component):
    try:
        return component.get_collision_enabled()
    except Exception:
        return None


def validate_layout(actor):
    cls = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    if not cls:
        raise RuntimeError("HierarchicalInstancedStaticMeshComponent is unavailable")
    components = list(actor.get_components_by_class(cls))
    grouped = {"rock": [], "shrub": [], "ground": []}
    for component in components:
        name = category(component)
        if name not in grouped:
            raise RuntimeError(
                f"Unexpected Stage 13 HISM component {component.get_name()} tags={component_tags(component)}"
            )
        grouped[name].append(component)

    for name, entries in grouped.items():
        count = len(entries)
        instances = sum(instance_count(component) for component in entries)
        log(f"{name.upper()}_HISM_COMPONENTS={count}")
        log(f"{name.upper()}_INSTANCES={instances}")
        if count != EXPECTED_COMPONENTS[name] or instances != EXPECTED_INSTANCES[name]:
            raise RuntimeError(
                f"Stage 13 {name} layout changed: {count}/{instances}, "
                f"expected {EXPECTED_COMPONENTS[name]}/{EXPECTED_INSTANCES[name]}"
            )

    if len(components) != 8:
        raise RuntimeError(f"Expected 8 Stage 13 HISM components, found {len(components)}")

    for component in grouped["rock"]:
        state = collision_enabled(component)
        if state is None or "NO_COLLISION" in str(state):
            raise RuntimeError(f"Rock collision is not enabled on {component.get_name()}: {state}")
    for name in ("shrub", "ground"):
        for component in grouped[name]:
            state = collision_enabled(component)
            if "NO_COLLISION" not in str(state):
                raise RuntimeError(f"{name} collision is unexpectedly enabled on {component.get_name()}: {state}")
    return components


def spatially_loaded(actor):
    for name in ("get_is_spatially_loaded", "is_spatially_loaded"):
        method = getattr(actor, name, None)
        if callable(method):
            try:
                return bool(method())
            except Exception:
                pass
    value = safe_property(actor, "is_spatially_loaded", None)
    return bool(value) if value is not None else None


def set_spatially_loaded(actor, value):
    method = getattr(actor, "set_is_spatially_loaded", None)
    if callable(method):
        try:
            method(bool(value))
            return "set_is_spatially_loaded"
        except Exception as exc:
            log(f"SETTER_WARNING={type(exc).__name__}: {exc}")
    try:
        actor.set_editor_property("is_spatially_loaded", bool(value))
        return "is_spatially_loaded property"
    except Exception as exc:
        raise RuntimeError(f"Could not set Stage 13 actor spatial loading: {type(exc).__name__}: {exc}")


def save_world():
    saved = False
    cls = getattr(unreal, "LevelEditorSubsystem", None)
    if cls:
        try:
            saved = bool(unreal.get_editor_subsystem(cls).save_current_level())
        except Exception as exc:
            log(f"LEVEL_SAVE_WARNING={type(exc).__name__}: {exc}")
    if not saved:
        try:
            saved = bool(unreal.EditorLevelLibrary.save_current_level())
        except Exception as exc:
            log(f"FALLBACK_LEVEL_SAVE_WARNING={type(exc).__name__}: {exc}")
    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
        saved = True
    except Exception as exc:
        log(f"DIRTY_PACKAGE_SAVE_WARNING={type(exc).__name__}: {exc}")
    return saved


def main():
    log("AETHER STAGE 14D - RIVER ENVIRONMENT WORLD PARTITION REPAIR")
    log("=" * 100)
    log("GUARDED_MAP_EDIT=TRUE")
    log("Only the Stage 13 environment actor spatial-loading flag may change.")
    log("No instance, mesh, collision, terrain, MPD, pipeline, or build setting is changed.")

    world = load_world()
    _, actors = all_actors()
    actor = find_environment(actors)
    validate_layout(actor)

    location = actor.get_actor_location()
    before = spatially_loaded(actor)
    runtime_grid = safe_property(actor, "runtime_grid", None)
    try:
        bounds = actor.get_actor_bounds(False, True)
    except Exception:
        bounds = None

    log(f"WORLD={world.get_path_name() if world else None}")
    log(f"ENVIRONMENT_ACTOR={actor_label(actor)}")
    log(f"ACTOR_LOCATION={location}")
    log(f"ACTOR_BOUNDS={bounds}")
    log(f"RUNTIME_GRID={runtime_grid}")
    log(f"IS_SPATIALLY_LOADED_BEFORE={before}")

    if before is None:
        raise RuntimeError("The actor spatial-loading state is not exposed in this UE build")

    setter_used = None
    try:
        try:
            actor.modify()
        except Exception:
            pass
        setter_used = set_spatially_loaded(actor, False)
        after = spatially_loaded(actor)
        log(f"SPATIAL_LOADING_SETTER={setter_used}")
        log(f"IS_SPATIALLY_LOADED_AFTER={after}")
        if after is not False:
            raise RuntimeError(f"Always Loaded validation failed; stored value={after}")

        validate_layout(actor)
        if not save_world():
            raise RuntimeError("Map save did not report success")

        log("MAP_SAVE=PASS")
        log("")
        log("ENVIRONMENT_STREAMING_REPAIR_RESULT=PASS")
        log("ENVIRONMENT_ACTOR_ALWAYS_LOADED=TRUE")
        log("HISM_COMPONENTS_PRESERVED=8")
        log("HISM_INSTANCES_PRESERVED=184")
        log("ROCK_COLLISION_PRESERVED=TRUE")
        log("NON_ROCK_COLLISION_DISABLED=TRUE")
        log("COMMON_PIPELINE_OPTIMIZATION_PRESERVED=TRUE")
        log("NO_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    except Exception:
        try:
            set_spatially_loaded(actor, before)
            log(f"ROLLBACK_SPATIAL_LOADING={before}")
        except Exception as rollback_exc:
            log(f"ROLLBACK_WARNING={type(rollback_exc).__name__}: {rollback_exc}")
        raise

    write_report()
    unreal.log_warning(f"AETHER_STAGE14_ENVIRONMENT_STREAMING_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    log("")
    log("ENVIRONMENT_STREAMING_REPAIR_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("NO_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE14_ENVIRONMENT_STREAMING_REPAIR_FAILED={type(exc).__name__}: {exc}")
    raise
