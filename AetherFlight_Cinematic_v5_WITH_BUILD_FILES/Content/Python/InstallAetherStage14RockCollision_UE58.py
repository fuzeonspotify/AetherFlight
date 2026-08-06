"""Stage 14A: enable collision only on the grounded river rocks.

The script validates the exact Stage 13 HISM layout, preserves every instance
transform, enables query collision on the four rock components, keeps shrubs
and ground cover non-colliding, and requires a simple component trace on every
rock HISM before saving. Any failure restores the previous component settings.
It never changes Mesh Terrain collision or starts a Mesh Partition build.
"""

from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
ENVIRONMENT_LABEL = "Aether_VideoStage13_RiverEnvironment"
ENVIRONMENT_TAG = "AetherVideoRiverEnvironmentStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14RockCollisionInstall.txt"
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
        return [str(value) for value in actor.get_editor_property("tags")]
    except Exception:
        return []


def safe_property(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        try:
            return getattr(obj, name)
        except Exception:
            return default


def call_optional(obj, name, *args):
    method = getattr(obj, name, None)
    if not callable(method):
        return None, False
    return method(*args), True


def load_world():
    world = None
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
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


def all_editor_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return list(subsystem.get_all_level_actors())


def find_environment(actors):
    matches = []
    for actor in actors:
        if actor_label(actor) == ENVIRONMENT_LABEL or ENVIRONMENT_TAG in actor_tags(actor):
            matches.append(actor)
    return matches[0] if len(matches) == 1 else None


def component_tags(component):
    values = safe_property(component, "component_tags", []) or []
    return [str(value) for value in values]


def category(component):
    text = " ".join(component_tags(component)).lower()
    for name in ("rock", "shrub", "ground"):
        if f"aetherriver_{name}" in text:
            return name
    return None


def static_mesh(component):
    try:
        mesh = component.get_static_mesh()
        if mesh:
            return mesh
    except Exception:
        pass
    return safe_property(component, "static_mesh")


def mesh_path(component):
    mesh = static_mesh(component)
    return mesh.get_path_name() if mesh else "NONE"


def instance_count(component):
    try:
        return int(component.get_instance_count())
    except Exception:
        return int(safe_property(component, "instance_count", 0) or 0)


def extract_transform(value):
    values = value if isinstance(value, tuple) else (value,)
    for item in values:
        if item is None or isinstance(item, bool):
            continue
        if "TRANSFORM" in type(item).__name__.upper():
            return item
    return None


def instance_transform(component, index):
    method = getattr(component, "get_instance_transform", None)
    if not callable(method):
        return None
    for args in ((index, True), (index,)):
        try:
            transform = extract_transform(method(*args))
            if transform is not None:
                return transform
        except Exception:
            pass
    return None


def transform_signature(component):
    result = []
    for index in range(instance_count(component)):
        transform = instance_transform(component, index)
        if transform is None:
            raise RuntimeError(f"Could not read instance transform {index} from {component.get_name()}")
        result.append(str(transform))
    return tuple(result)


def collect_and_validate(environment):
    hism_class = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    if not hism_class:
        raise RuntimeError("unreal.HierarchicalInstancedStaticMeshComponent is unavailable")
    components = list(environment.get_components_by_class(hism_class))
    grouped = {"rock": [], "shrub": [], "ground": []}
    for component in components:
        name = category(component)
        if name not in grouped:
            raise RuntimeError(
                f"Unexpected Stage 13 HISM category on {component.get_name()}: tags={component_tags(component)}"
            )
        grouped[name].append(component)

    for name in grouped:
        count = len(grouped[name])
        instances = sum(instance_count(component) for component in grouped[name])
        log(f"{name.upper()}_HISM_COMPONENTS={count}")
        log(f"{name.upper()}_INSTANCES={instances}")
        if count != EXPECTED_COMPONENTS[name] or instances != EXPECTED_INSTANCES[name]:
            raise RuntimeError(
                f"Stage 13 {name} layout changed: components={count}, instances={instances}, "
                f"expected={EXPECTED_COMPONENTS[name]}/{EXPECTED_INSTANCES[name]}"
            )
    if len(components) != 8:
        raise RuntimeError(f"Expected 8 Stage 13 HISM components, found {len(components)}")
    return components, grouped


def collision_enabled(component):
    try:
        return component.get_collision_enabled()
    except Exception:
        return None


def collision_profile(component):
    try:
        return component.get_collision_profile_name()
    except Exception:
        return safe_property(safe_property(component, "body_instance"), "collision_profile_name")


def overlap_events(component):
    method = getattr(component, "get_generate_overlap_events", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            pass
    value = safe_property(component, "generate_overlap_events")
    return bool(value) if value is not None else None


def snapshot(component):
    return {
        "collision": collision_enabled(component),
        "profile": collision_profile(component),
        "overlap": overlap_events(component),
    }


def refresh_collision(component):
    for method_name in ("recreate_physics_state", "mark_render_state_dirty", "update_bounds"):
        method = getattr(component, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:
                pass


def set_profile(component, value):
    method = getattr(component, "set_collision_profile_name", None)
    if not callable(method):
        raise RuntimeError(f"{component.get_name()} exposes no set_collision_profile_name")
    try:
        method(value, True)
    except TypeError:
        method(value)


def set_collision(component, value):
    method = getattr(component, "set_collision_enabled", None)
    if not callable(method):
        raise RuntimeError(f"{component.get_name()} exposes no set_collision_enabled")
    method(value)


def set_overlap(component, value):
    method = getattr(component, "set_generate_overlap_events", None)
    if callable(method):
        method(bool(value))
        return
    try:
        component.set_editor_property("generate_overlap_events", bool(value))
    except Exception:
        pass


def restore(component, state):
    try:
        if state["profile"] is not None:
            set_profile(component, state["profile"])
    except Exception as exc:
        log(f"ROLLBACK_PROFILE_WARNING={component.get_name()}: {exc}")
    try:
        if state["collision"] is not None:
            set_collision(component, state["collision"])
    except Exception as exc:
        log(f"ROLLBACK_COLLISION_WARNING={component.get_name()}: {exc}")
    try:
        if state["overlap"] is not None:
            set_overlap(component, state["overlap"])
    except Exception as exc:
        log(f"ROLLBACK_OVERLAP_WARNING={component.get_name()}: {exc}")
    refresh_collision(component)


def apply_collision(grouped):
    enum = getattr(unreal, "CollisionEnabled", None)
    if not enum:
        raise RuntimeError("unreal.CollisionEnabled is unavailable")
    query_only = getattr(enum, "QUERY_ONLY", None)
    no_collision = getattr(enum, "NO_COLLISION", None)
    if query_only is None or no_collision is None:
        raise RuntimeError("Required CollisionEnabled members are unavailable")

    for component in grouped["rock"]:
        set_profile(component, unreal.Name("BlockAll"))
        set_collision(component, query_only)
        set_overlap(component, False)
        refresh_collision(component)
        log(
            f"ENABLED_ROCK_COLLISION={component.get_name()} mesh={mesh_path(component)} "
            f"collision={collision_enabled(component)} profile={collision_profile(component)}"
        )

    for name in ("shrub", "ground"):
        for component in grouped[name]:
            set_collision(component, no_collision)
            set_overlap(component, False)
            refresh_collision(component)
            log(
                f"DISABLED_{name.upper()}_COLLISION={component.get_name()} "
                f"mesh={mesh_path(component)} collision={collision_enabled(component)}"
            )


def trace_result_hit(result):
    if result is None:
        return False
    if isinstance(result, tuple):
        if result and isinstance(result[0], bool):
            return bool(result[0])
        return len(result) > 0
    return True


def transform_vector(transform, name):
    value = safe_property(transform, name)
    if value is not None:
        return value
    try:
        return getattr(transform, name)
    except Exception:
        return None


def trace_instance(component, index, trace_complex):
    transform = instance_transform(component, index)
    if transform is None:
        return False, "NO_TRANSFORM"
    location = transform_vector(transform, "translation")
    scale = transform_vector(transform, "scale3d")
    if location is None:
        return False, "NO_LOCATION"
    mesh = static_mesh(component)
    extent_z = 1500.0
    if mesh:
        try:
            extent_z = float(mesh.get_bounds().box_extent.z)
        except Exception:
            pass
    scale_z = abs(float(scale.z)) if scale is not None else 1.0
    half_span = max(5000.0, extent_z * max(scale_z, 0.01) * 4.0 + 1000.0)
    start = unreal.Vector(float(location.x), float(location.y), float(location.z) + half_span)
    end = unreal.Vector(float(location.x), float(location.y), float(location.z) - half_span)
    method = getattr(component, "line_trace_component", None)
    if not callable(method):
        return False, "NO_COMPONENT_TRACE_API"
    errors = []
    for args in (
        (start, end, bool(trace_complex), False, False),
        (start, end, bool(trace_complex), False),
    ):
        try:
            result = method(*args)
            return trace_result_hit(result), str(result)[:600]
        except Exception as exc:
            errors.append(f"{args[2:]}:{type(exc).__name__}:{exc}")
    return False, "; ".join(errors)


def validate_collision(grouped):
    simple_pass = 0
    complex_pass = 0
    for component in grouped["rock"]:
        enabled = collision_enabled(component)
        profile = str(collision_profile(component))
        if enabled is None or "NO_COLLISION" in str(enabled) or "BlockAll" not in profile:
            raise RuntimeError(
                f"Rock collision state validation failed on {component.get_name()}: "
                f"collision={enabled}, profile={profile}"
            )

        component_simple = False
        component_complex = False
        attempts = min(instance_count(component), 3)
        for index in range(attempts):
            hit, detail = trace_instance(component, index, False)
            log(f"ROCK_SIMPLE_TRACE={component.get_name()} instance={index} hit={hit} detail={detail}")
            if hit:
                component_simple = True
                break
        for index in range(attempts):
            hit, detail = trace_instance(component, index, True)
            log(f"ROCK_COMPLEX_TRACE={component.get_name()} instance={index} hit={hit} detail={detail}")
            if hit:
                component_complex = True
                break
        simple_pass += int(component_simple)
        complex_pass += int(component_complex)

    for name in ("shrub", "ground"):
        for component in grouped[name]:
            if "NO_COLLISION" not in str(collision_enabled(component)):
                raise RuntimeError(f"{name} collision was not disabled on {component.get_name()}")

    log(f"ROCK_SIMPLE_TRACE_COMPONENTS_PASS={simple_pass}")
    log(f"ROCK_COMPLEX_TRACE_COMPONENTS_PASS={complex_pass}")
    if simple_pass != 4:
        raise RuntimeError(
            f"Not all rock HISM components have usable simple collision: {simple_pass}/4. "
            "No Stage 14 collision changes will be saved."
        )
    return simple_pass, complex_pass


def save_world():
    saved = False
    subsystem_class = getattr(unreal, "LevelEditorSubsystem", None)
    if subsystem_class:
        try:
            saved = bool(unreal.get_editor_subsystem(subsystem_class).save_current_level())
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
    log("AETHER STAGE 14A - STRICT RIVER ROCK COLLISION")
    log("=" * 96)
    log("Only the 30 Stage 13 river rocks receive query collision. Shrubs and ground cover remain non-colliding.")
    log("Mesh Terrain collision is not modified and no Mesh Partition build is started.")

    world = load_world()
    actors = all_editor_actors()
    environment = find_environment(actors)
    log(f"WORLD={world.get_path_name() if world else None}")
    log(f"ENVIRONMENT_ACTOR={actor_label(environment) if environment else None}")
    if not world or not environment:
        raise RuntimeError("AetherWorld or the Stage 13 river environment actor is missing")

    components, grouped = collect_and_validate(environment)
    before_layout = {mesh_path(component): transform_signature(component) for component in components}
    states = {component: snapshot(component) for component in components}

    try:
        apply_collision(grouped)
        simple_pass, complex_pass = validate_collision(grouped)
        after_layout = {mesh_path(component): transform_signature(component) for component in components}
        if before_layout != after_layout:
            raise RuntimeError("One or more Stage 13 instance transforms changed during collision setup")
        if not save_world():
            raise RuntimeError("Map save did not report success")

        log("MAP_SAVE=PASS")
        log("")
        log("ROCK_COLLISION_INSTALL_RESULT=PASS")
        log("ROCK_HISM_COMPONENTS=4")
        log("ROCK_INSTANCES=30")
        log(f"ROCK_SIMPLE_TRACE_COMPONENTS_PASS={simple_pass}")
        log(f"ROCK_COMPLEX_TRACE_COMPONENTS_PASS={complex_pass}")
        log("ROCK_COLLISION_MODE=QUERY_ONLY")
        log("ROCK_COLLISION_PROFILE=BlockAll")
        log("NON_ROCK_COLLISION_DISABLED=TRUE")
        log("INSTANCE_TRANSFORMS_PRESERVED=TRUE")
        log("TERRAIN_COLLISION_UNCHANGED=TRUE")
        log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    except Exception:
        log("ROLLBACK_STARTED=TRUE")
        for component, state in states.items():
            restore(component, state)
        log("ROLLBACK_FINISHED=TRUE")
        raise

    write_report()
    unreal.log_warning(f"AETHER_STAGE14_ROCK_COLLISION_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    log("")
    log("ROCK_COLLISION_INSTALL_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("COLLISION_CHANGES_WERE_NOT_SAVED=TRUE")
    log("TERRAIN_COLLISION_UNCHANGED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE14_ROCK_COLLISION_FAILED={type(exc).__name__}: {exc}")
    raise
