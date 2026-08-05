"""Stage 14F: repair the river environment actor's double-applied translation.

The environment instances were inserted in world space while the actor was at
world origin. The saved actor later acquired a non-zero translation while its
instance-local translations remained the original world coordinates. Runtime
therefore applies the actor translation a second time. This guarded repair moves
only the actor root back to world origin, preserving all 184 local instance
transforms, meshes, collision settings, and Always Loaded state.

No Mesh Partition build, cook, PIE command, or pipeline edit is invoked.
"""

from pathlib import Path
import math
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
ENVIRONMENT_LABEL = "Aether_VideoStage13_RiverEnvironment"
ENVIRONMENT_TAG = "AetherVideoRiverEnvironmentStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14EnvironmentDoubleTransformRepair.txt"
EXPECTED_COMPONENTS = {"rock": 4, "shrub": 2, "ground": 2}
EXPECTED_INSTANCES = {"rock": 30, "shrub": 44, "ground": 110}
LOCATION_TOLERANCE_CM = 2.0
TRANSFORM_TOLERANCE = 0.01
MIN_BAD_ACTOR_OFFSET_CM = 100000.0
LINES = []


def log(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def safe_property(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        try:
            value = getattr(obj, name)
            return value() if callable(value) else value
        except Exception:
            return default


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def actor_tags(actor):
    try:
        return [str(value) for value in actor.get_editor_property("tags")]
    except Exception:
        return []


def load_world():
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    world = None
    if subsystem_class:
        try:
            world = unreal.get_editor_subsystem(subsystem_class).get_editor_world()
        except Exception:
            world = None
    if not world:
        world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        if subsystem_class:
            try:
                world = unreal.get_editor_subsystem(subsystem_class).get_editor_world()
            except Exception:
                world = None
        if not world:
            world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def find_environment():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(subsystem.get_all_level_actors())
    matches = [
        actor for actor in actors
        if actor_label(actor) == ENVIRONMENT_LABEL or ENVIRONMENT_TAG in actor_tags(actor)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one Stage 13 environment actor, found {len(matches)}")
    return matches[0]


def component_tags(component):
    return [str(value) for value in (safe_property(component, "component_tags", []) or [])]


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


def extract_transform(value):
    values = value if isinstance(value, tuple) else (value,)
    for item in values:
        if item is not None and "TRANSFORM" in type(item).__name__.upper():
            return item
    return None


def get_instance_transform(component, index, world_space):
    method = getattr(component, "get_instance_transform", None)
    if not callable(method):
        raise RuntimeError(f"{component.get_name()} exposes no get_instance_transform")
    value = method(index, bool(world_space))
    transform = extract_transform(value)
    if transform is None:
        raise RuntimeError(
            f"Could not read {'world' if world_space else 'local'} transform "
            f"for {component.get_name()}[{index}]"
        )
    return transform


def vector(value):
    if value is None:
        return None
    return (float(value.x), float(value.y), float(value.z))


def rotation_tuple(value):
    if value is None:
        return None
    names = ("roll", "pitch", "yaw")
    try:
        return tuple(float(getattr(value, name)) for name in names)
    except Exception:
        return None


def transform_signature(transform):
    translation = safe_property(transform, "translation")
    if translation is None:
        translation = safe_property(transform, "location")
    rotation = safe_property(transform, "rotation")
    scale = safe_property(transform, "scale3d")
    if scale is None:
        scale = safe_property(transform, "scale")
    t = vector(translation)
    s = vector(scale)
    try:
        r = (float(rotation.x), float(rotation.y), float(rotation.z), float(rotation.w))
    except Exception:
        r = rotation_tuple(rotation)
    if t is None or s is None or r is None:
        raise RuntimeError(f"Could not extract transform signature from {transform}")
    return t + tuple(r) + s


def translation_from_signature(signature):
    return signature[0:3]


def nearly_equal(a, b, tolerance=TRANSFORM_TOLERANCE):
    return len(a) == len(b) and all(abs(float(x) - float(y)) <= tolerance for x, y in zip(a, b))


def distance(a, b=(0.0, 0.0, 0.0)):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def validate_layout(actor):
    cls = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    if not cls:
        raise RuntimeError("HierarchicalInstancedStaticMeshComponent is unavailable")
    components = list(actor.get_components_by_class(cls))
    grouped = {"rock": [], "shrub": [], "ground": []}
    for component in components:
        name = category(component)
        if name not in grouped:
            raise RuntimeError(f"Unexpected HISM component {component.get_name()} tags={component_tags(component)}")
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
        raise RuntimeError(f"Expected 8 HISM components, found {len(components)}")
    for component in grouped["rock"]:
        state = collision_enabled(component)
        if state is None or "NO_COLLISION" in str(state):
            raise RuntimeError(f"Rock collision is not enabled on {component.get_name()}: {state}")
    for name in ("shrub", "ground"):
        for component in grouped[name]:
            state = collision_enabled(component)
            if "NO_COLLISION" not in str(state):
                raise RuntimeError(f"{name} collision is unexpectedly enabled on {component.get_name()}: {state}")
    return components, grouped


def snapshot_instances(components):
    snapshot = {}
    for component in components:
        entries = []
        for index in range(instance_count(component)):
            local_sig = transform_signature(get_instance_transform(component, index, False))
            world_sig = transform_signature(get_instance_transform(component, index, True))
            entries.append((local_sig, world_sig))
        snapshot[component.get_name()] = entries
    return snapshot


def validate_double_offset(snapshot, actor_location):
    checked = 0
    max_error = 0.0
    for entries in snapshot.values():
        for local_sig, world_sig in entries:
            local = translation_from_signature(local_sig)
            world = translation_from_signature(world_sig)
            predicted = tuple(local[i] + actor_location[i] for i in range(3))
            error = distance(world, predicted)
            max_error = max(max_error, error)
            checked += 1
    log(f"DOUBLE_OFFSET_INSTANCE_CHECKS={checked}")
    log(f"DOUBLE_OFFSET_MAX_ERROR_CM={max_error:.6f}")
    if checked != 184 or max_error > LOCATION_TOLERANCE_CM:
        raise RuntimeError(
            f"Stored transforms do not prove a pure actor-translation double offset: "
            f"checks={checked}, max_error={max_error:.3f} cm"
        )


def set_actor_location(actor, location):
    method = getattr(actor, "set_actor_location", None)
    if not callable(method):
        raise RuntimeError("Actor exposes no set_actor_location")
    last_error = None
    for args in ((location, False, True), (location, False), (location,)):
        try:
            result = method(*args)
            return result
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Could not set actor location: {type(last_error).__name__}: {last_error}")


def validate_after(actor, components, before_snapshot):
    location = vector(actor.get_actor_location())
    log(f"ACTOR_LOCATION_AFTER={location}")
    if location is None or distance(location) > LOCATION_TOLERANCE_CM:
        raise RuntimeError(f"Actor did not return to world origin: {location}")
    if spatially_loaded(actor) is not False:
        raise RuntimeError("Environment actor lost Always Loaded state")

    after_snapshot = snapshot_instances(components)
    local_changed = 0
    world_matches_intended = 0
    max_world_error = 0.0
    total = 0
    for component_name, before_entries in before_snapshot.items():
        after_entries = after_snapshot.get(component_name)
        if after_entries is None or len(after_entries) != len(before_entries):
            raise RuntimeError(f"Instance list changed for {component_name}")
        for (before_local, _before_world), (after_local, after_world) in zip(before_entries, after_entries):
            total += 1
            if not nearly_equal(before_local, after_local):
                local_changed += 1
            intended = translation_from_signature(before_local)
            actual = translation_from_signature(after_world)
            error = distance(actual, intended)
            max_world_error = max(max_world_error, error)
            if error <= LOCATION_TOLERANCE_CM:
                world_matches_intended += 1
    log(f"LOCAL_INSTANCE_TRANSFORMS_CHANGED={local_changed}")
    log(f"WORLD_INSTANCES_MATCH_STORED_INTENDED_TRANSFORMS={world_matches_intended}")
    log(f"WORLD_INSTANCE_MAX_ERROR_CM={max_world_error:.6f}")
    if total != 184 or local_changed != 0 or world_matches_intended != 184:
        raise RuntimeError(
            f"Post-repair instance validation failed: total={total}, local_changed={local_changed}, "
            f"world_matches={world_matches_intended}, max_error={max_world_error:.3f} cm"
        )


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
    log("AETHER STAGE 14F - RIVER ENVIRONMENT DOUBLE-TRANSFORM REPAIR")
    log("=" * 100)
    log("GUARDED_MAP_EDIT=TRUE")
    log("Only the Stage 13 environment actor root location may change.")
    log("All 184 local instance transforms, meshes, collision settings, Always Loaded state, terrain, and pipelines are preserved.")

    world = load_world()
    actor = find_environment()
    components, _grouped = validate_layout(actor)
    if spatially_loaded(actor) is not False:
        raise RuntimeError("Stage 14D Always Loaded repair is not present")

    actor_transform_before = actor.get_actor_transform()
    actor_location_before = vector(actor.get_actor_location())
    if actor_location_before is None:
        raise RuntimeError("Could not read actor location")
    actor_rotation = actor.get_actor_rotation()
    actor_scale = vector(actor.get_actor_scale3d())
    log(f"WORLD={world.get_path_name() if world else None}")
    log(f"ENVIRONMENT_ACTOR={actor_label(actor)}")
    log(f"ACTOR_LOCATION_BEFORE={actor_location_before}")
    log(f"ACTOR_ROTATION_BEFORE={actor_rotation}")
    log(f"ACTOR_SCALE_BEFORE={actor_scale}")
    log(f"IS_SPATIALLY_LOADED=False")

    if distance(actor_location_before) < MIN_BAD_ACTOR_OFFSET_CM:
        raise RuntimeError(
            f"Actor location is not the proven large double-transform offset: {actor_location_before}"
        )
    rotation_values = rotation_tuple(actor_rotation)
    if rotation_values is None or any(abs(value) > 0.01 for value in rotation_values):
        raise RuntimeError(f"Actor rotation is not identity: {actor_rotation}")
    if actor_scale is None or not nearly_equal(actor_scale, (1.0, 1.0, 1.0), 0.0001):
        raise RuntimeError(f"Actor scale is not identity: {actor_scale}")

    before_snapshot = snapshot_instances(components)
    validate_double_offset(before_snapshot, actor_location_before)

    try:
        try:
            actor.modify()
        except Exception:
            pass
        set_actor_location(actor, unreal.Vector(0.0, 0.0, 0.0))
        validate_layout(actor)
        validate_after(actor, components, before_snapshot)
        try:
            bounds = actor.get_actor_bounds(False, True)
        except Exception:
            bounds = None
        log(f"ACTOR_BOUNDS_AFTER={bounds}")
        if not save_world():
            raise RuntimeError("Map save did not report success")
        log("MAP_SAVE=PASS")
        log("")
        log("ENVIRONMENT_DOUBLE_TRANSFORM_REPAIR_RESULT=PASS")
        log("ENVIRONMENT_ACTOR_RETURNED_TO_ORIGIN=TRUE")
        log("ENVIRONMENT_ACTOR_ALWAYS_LOADED=TRUE")
        log("HISM_COMPONENTS_PRESERVED=8")
        log("HISM_INSTANCES_PRESERVED=184")
        log("LOCAL_INSTANCE_TRANSFORMS_PRESERVED=TRUE")
        log("WORLD_INSTANCE_POSITIONS_RESTORED_TO_RIVER=TRUE")
        log("ROCK_COLLISION_PRESERVED=TRUE")
        log("NON_ROCK_COLLISION_DISABLED=TRUE")
        log("COMMON_PIPELINE_OPTIMIZATION_PRESERVED=TRUE")
        log("NO_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    except Exception:
        try:
            set_actor_location(actor, unreal.Vector(*actor_location_before))
            log(f"ROLLBACK_ACTOR_LOCATION={actor_location_before}")
        except Exception as rollback_exc:
            log(f"ROLLBACK_WARNING={type(rollback_exc).__name__}: {rollback_exc}")
        raise

    write_report()
    unreal.log_warning(f"AETHER_STAGE14_ENVIRONMENT_DOUBLE_TRANSFORM_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    log("")
    log("ENVIRONMENT_DOUBLE_TRANSFORM_REPAIR_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("NO_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE14_ENVIRONMENT_DOUBLE_TRANSFORM_REPAIR_FAILED={type(exc).__name__}: {exc}")
    raise
