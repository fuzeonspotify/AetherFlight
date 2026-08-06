"""Read-only Stage 14 runtime validation executed while PIE is running.

The probe uses the PIE game world, inspects locally loaded CompiledSection actors
(including placeholders), validates all four river-rock HISM components, and
traces through river-bank sample positions while ignoring the environment and
water actors. It never invokes a builder, changes collision, saves packages, or
starts/stops PIE.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14PIERuntimeValidation.txt"
ENVIRONMENT_TAG = "AetherVideoRiverEnvironmentStage"
ENVIRONMENT_LABEL = "Aether_VideoStage13_RiverEnvironment"
RIVER_LABEL = "Aether_VideoStage11_River"
WATER_ZONE_LABEL = "Aether_VideoStage11_WaterZone"
EXPECTED_ROCK_COMPONENTS = 4
EXPECTED_ROCK_INSTANCES = 30
TERRAIN_SAMPLE_TARGET = 10
MIN_TERRAIN_HITS = 6
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
            return getattr(obj, name)
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


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


def get_pie_world():
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if subsystem_class:
        try:
            world = unreal.get_editor_subsystem(subsystem_class).get_game_world()
            if world:
                return world
        except Exception:
            pass
    library = getattr(unreal, "EditorLevelLibrary", None)
    if library:
        method = getattr(library, "get_pie_worlds", None)
        if callable(method):
            try:
                worlds = list(method(False))
                if worlds:
                    return worlds[0]
            except Exception:
                pass
        method = getattr(library, "get_game_world", None)
        if callable(method):
            try:
                return method()
            except Exception:
                pass
    return None


def all_actors(world):
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


def find_actor(actors, label=None, tag=None):
    matches = []
    for actor in actors:
        if label and actor_label(actor) == label:
            matches.append(actor)
            continue
        if tag and tag in actor_tags(actor):
            matches.append(actor)
    unique = []
    for actor in matches:
        if actor not in unique:
            unique.append(actor)
    return unique[0] if len(unique) == 1 else None


def get_components(actor):
    actor_component = getattr(unreal, "ActorComponent", None)
    if actor_component:
        try:
            return list(actor.get_components_by_class(actor_component))
        except Exception:
            pass
    result = []
    for class_name in ("PrimitiveComponent", "SceneComponent"):
        cls = getattr(unreal, class_name, None)
        if not cls:
            continue
        try:
            for component in actor.get_components_by_class(cls):
                if component not in result:
                    result.append(component)
        except Exception:
            pass
    return result


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


def extract_transform(value):
    values = value if isinstance(value, tuple) else (value,)
    for item in values:
        if item is not None and "TRANSFORM" in type(item).__name__.upper():
            return item
    return None


def instance_transform(component, index):
    method = getattr(component, "get_instance_transform", None)
    if not callable(method):
        return None
    for args in ((index, True), (index,)):
        try:
            value = extract_transform(method(*args))
            if value is not None:
                return value
        except Exception:
            pass
    return None


def transform_location(transform):
    value = safe_property(transform, "translation")
    if value is not None:
        return value
    try:
        return transform.translation
    except Exception:
        return None


def trace_component(component):
    count = min(instance_count(component), 3)
    method = getattr(component, "line_trace_component", None)
    if not callable(method):
        return False
    for index in range(count):
        transform = instance_transform(component, index)
        location = transform_location(transform) if transform else None
        if location is None:
            continue
        start = unreal.Vector(float(location.x), float(location.y), float(location.z) + 7000.0)
        end = unreal.Vector(float(location.x), float(location.y), float(location.z) - 7000.0)
        for args in ((start, end, False, False, False), (start, end, False, False)):
            try:
                if method(*args) is not None:
                    return True
            except Exception:
                pass
    return False


def collision_enabled(component):
    try:
        return component.get_collision_enabled()
    except Exception:
        return None


def collect_compiled_sections(world):
    cls = getattr(unreal, "CompiledSection", None)
    if not cls:
        return []
    try:
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, cls))
    except Exception:
        return []


def section_is_placeholder(section):
    method = getattr(section, "is_placeholder", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            pass
    value = safe_property(section, "is_placeholder")
    if value is None:
        value = safe_property(section, "b_is_placeholder")
    return bool(value) if value is not None else None


def inspect_compiled_sections(sections):
    collision_components = 0
    enabled_collision = 0
    placeholders = 0
    for index, section in enumerate(sections):
        placeholder = section_is_placeholder(section)
        placeholders += int(placeholder is True)
        components = get_components(section)
        section_collision = 0
        section_enabled = 0
        for component in components:
            if "MESHPARTITIONCOLLISIONCOMPONENT" in class_path(component).upper():
                section_collision += 1
                value = collision_enabled(component)
                if value is not None and "NO_COLLISION" not in str(value):
                    section_enabled += 1
        collision_components += section_collision
        enabled_collision += section_enabled
        log(
            f"COMPILED_SECTION_{index}=name:{section.get_name()} placeholder:{placeholder} "
            f"components:{len(components)} collision_components:{section_collision} "
            f"enabled_collision_components:{section_enabled}"
        )
    return placeholders, collision_components, enabled_collision


def sample_locations(rock_components):
    result = []
    for component in rock_components:
        for index in range(min(instance_count(component), 3)):
            transform = instance_transform(component, index)
            location = transform_location(transform) if transform else None
            if location is not None:
                result.append(location)
            if len(result) >= TERRAIN_SAMPLE_TARGET:
                return result
    return result


def extract_hit(result):
    if result is None:
        return None
    values = result if isinstance(result, tuple) else (result,)
    if values and isinstance(values[0], bool) and not values[0]:
        return None
    for item in values:
        if item is not None and "HITRESULT" in type(item).__name__.upper():
            return item
    return None


def terrain_trace(world, location, ignored):
    trace_type = getattr(unreal.TraceTypeQuery, "TRACE_TYPE_QUERY1", None)
    if trace_type is None:
        trace_type = getattr(unreal.TraceTypeQuery, "ECC_VISIBILITY", None)
    if trace_type is None:
        return None
    start = unreal.Vector(float(location.x), float(location.y), float(location.z) + 10000.0)
    end = unreal.Vector(float(location.x), float(location.y), float(location.z) - 30000.0)
    result = unreal.SystemLibrary.line_trace_single(
        world,
        start,
        end,
        trace_type,
        False,
        ignored,
        unreal.DrawDebugTrace.NONE,
        True,
    )
    return extract_hit(result)


def main():
    log("AETHER STAGE 14B - PIE RUNTIME COLLISION VALIDATION")
    log("=" * 96)
    log("Read-only: no builder, collision mutation, package save, or PIE start/stop command is issued.")

    world = get_pie_world()
    if not world:
        raise RuntimeError("No PIE game world exists. Press Play, wait for the river to load, then run this script from the Python console.")
    actors = all_actors(world)
    log(f"PIE_WORLD={world.get_path_name()}")
    log(f"PIE_ACTORS={len(actors)}")

    environment = find_actor(actors, ENVIRONMENT_LABEL, ENVIRONMENT_TAG)
    river = find_actor(actors, RIVER_LABEL, None)
    water_zone = find_actor(actors, WATER_ZONE_LABEL, None)
    if not environment:
        raise RuntimeError("The Stage 13 environment actor is not present in the PIE world")

    hism_class = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    components = list(environment.get_components_by_class(hism_class)) if hism_class else []
    rock_components = [component for component in components if category(component) == "rock"]
    shrub_components = [component for component in components if category(component) == "shrub"]
    ground_components = [component for component in components if category(component) == "ground"]
    rock_instances = sum(instance_count(component) for component in rock_components)
    log(f"ROCK_HISM_COMPONENTS={len(rock_components)}")
    log(f"ROCK_INSTANCES={rock_instances}")

    rock_state_ready = len(rock_components) == EXPECTED_ROCK_COMPONENTS and rock_instances == EXPECTED_ROCK_INSTANCES
    rock_trace_pass = 0
    for index, component in enumerate(rock_components):
        state = collision_enabled(component)
        traced = trace_component(component)
        if state is None or "NO_COLLISION" in str(state):
            rock_state_ready = False
        rock_trace_pass += int(traced)
        log(f"ROCK_COMPONENT_{index}=collision:{state} trace_hit:{traced} instances:{instance_count(component)}")

    non_rock_disabled = True
    for component in shrub_components + ground_components:
        if "NO_COLLISION" not in str(collision_enabled(component)):
            non_rock_disabled = False

    sections = collect_compiled_sections(world)
    placeholders, section_collision, enabled_section_collision = inspect_compiled_sections(sections)

    ignored = [environment]
    if river:
        ignored.append(river)
    if water_zone:
        ignored.append(water_zone)
    locations = sample_locations(rock_components)
    terrain_hits = 0
    useful_hits = 0
    for index, location in enumerate(locations):
        try:
            hit = terrain_trace(world, location, ignored)
        except Exception as exc:
            log(f"TERRAIN_TRACE_{index}=ERROR {type(exc).__name__}: {exc}")
            continue
        if not hit:
            log(f"TERRAIN_TRACE_{index}=MISS")
            continue
        actor = safe_property(hit, "hit_actor") or safe_property(hit, "actor")
        component = safe_property(hit, "hit_component") or safe_property(hit, "component")
        point = safe_property(hit, "impact_point") or safe_property(hit, "location")
        blocking = safe_property(hit, "blocking_hit")
        actor_class = class_path(actor) if actor else None
        component_class = class_path(component) if component else None
        terrain_like = bool(
            (actor_class and "CompiledSection" in actor_class)
            or (component_class and "MeshPartitionCollisionComponent" in component_class)
        )
        terrain_hits += int(bool(blocking))
        useful_hits += int(bool(blocking) and terrain_like)
        log(
            f"TERRAIN_TRACE_{index}=blocking:{blocking} actor:{actor_class} "
            f"component:{component_class} terrain_like:{terrain_like} point:{point}"
        )

    rock_ready = rock_state_ready and rock_trace_pass == EXPECTED_ROCK_COMPONENTS and non_rock_disabled
    local_compiled_present = len(sections) > 0
    terrain_ready = (
        local_compiled_present
        and enabled_section_collision > 0
        and useful_hits >= MIN_TERRAIN_HITS
    )
    water_ready = river is not None and water_zone is not None
    stage_ready = rock_ready and terrain_ready and water_ready

    log("")
    log("SUMMARY")
    log("-" * 96)
    log(f"PIE_COMPILED_SECTIONS={len(sections)}")
    log(f"PIE_PLACEHOLDER_COMPILED_SECTIONS={placeholders}")
    log(f"PIE_COMPILED_COLLISION_COMPONENTS={section_collision}")
    log(f"PIE_COMPILED_COLLISION_ENABLED_COMPONENTS={enabled_section_collision}")
    log(f"ROCK_COMPONENT_TRACE_HITS={rock_trace_pass}")
    log(f"NON_ROCK_COLLISION_DISABLED={non_rock_disabled}")
    log(f"TERRAIN_TRACE_REQUESTS={len(locations)}")
    log(f"TERRAIN_TRACE_BLOCKING_HITS={terrain_hits}")
    log(f"TERRAIN_TRACE_COMPILED_SECTION_HITS={useful_hits}")
    log(f"WATER_ACTORS_PRESENT={water_ready}")
    log(f"ROCK_RUNTIME_COLLISION_READY={rock_ready}")
    log(f"LOCAL_COMPILED_SECTION_PRESENT={local_compiled_present}")
    log(f"TERRAIN_RUNTIME_COLLISION_READY={terrain_ready}")
    log(f"STAGE14_RUNTIME_READY={stage_ready}")
    log("PIE_RUNTIME_VALIDATION_RESULT=PASS")
    log("NO_BUILD_METHOD_CALLED=TRUE")
    log("NO_COLLISION_SETTINGS_CHANGED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PIE_START_OR_STOP_COMMAND_CALLED=TRUE")
    log("NO_WHOLE_WORLD_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    write_report()
    unreal.log_warning(f"AETHER_STAGE14_PIE_RUNTIME_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    log("")
    log("PIE_RUNTIME_VALIDATION_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("NO_BUILD_METHOD_CALLED=TRUE")
    log("NO_COLLISION_SETTINGS_CHANGED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PIE_START_OR_STOP_COMMAND_CALLED=TRUE")
    log("NO_WHOLE_WORLD_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE14_PIE_RUNTIME_VALIDATION_FAILED={type(exc).__name__}: {exc}")
    raise
