"""Read-only Stage 14 terrain collision path diagnostic.

Compares world traces with direct MeshPartitionCollisionComponent traces at the
river-rock sample positions. Logs sample coordinates, component bounds coverage,
registration/physics-state/collision-response state, and parses actual HitResult
blocking flags. It never mutates collision, saves packages, starts/stops PIE, or
invokes any Mesh Partition build.
"""

from pathlib import Path
import math
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_SCRIPT = SCRIPT_DIR / "AuditAetherStage14PIERuntime_UE58.py"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14TerrainCollisionDiagnostic.txt"
LINES = []


def log(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def load_base():
    if not BASE_SCRIPT.is_file():
        raise RuntimeError(f"Base Stage 14 validator is missing: {BASE_SCRIPT}")
    source = BASE_SCRIPT.read_text(encoding="utf-8")
    marker = "\ntry:\n    main()"
    if marker not in source:
        raise RuntimeError("Base Stage 14 validator entry marker was not found")
    ns = {"__file__": str(BASE_SCRIPT), "__name__": "AetherStage14CollisionDiagnosticBase"}
    exec(compile(source.split(marker, 1)[0], str(BASE_SCRIPT), "exec"), ns, ns)
    return ns


def safe_property(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        try:
            return getattr(obj, name)
        except Exception:
            return default


def safe_method(obj, name, *args):
    method = getattr(obj, name, None)
    if not callable(method):
        return None
    try:
        return method(*args)
    except Exception:
        return None


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


def parse_hit(result):
    if result is None:
        return None, False
    values = result if isinstance(result, tuple) else (result,)
    bools = [item for item in values if isinstance(item, bool)]
    hit = None
    for item in values:
        if item is not None and "HITRESULT" in type(item).__name__.upper():
            hit = item
            break
    if bools and not any(bools):
        return hit, False
    if hit is None:
        return None, False
    blocking = safe_property(hit, "blocking_hit")
    if blocking is None:
        blocking = safe_property(hit, "b_blocking_hit")
    return hit, bool(blocking)


def vector_text(value):
    if value is None:
        return "None"
    return f"({float(value.x):.3f},{float(value.y):.3f},{float(value.z):.3f})"


def component_bounds(component):
    bounds = safe_property(component, "bounds")
    if bounds is None:
        bounds = safe_method(component, "get_bounds")
    if bounds is None:
        return None
    origin = safe_property(bounds, "origin")
    extent = safe_property(bounds, "box_extent")
    if origin is None or extent is None:
        return None
    return (
        float(origin.x) - float(extent.x), float(origin.x) + float(extent.x),
        float(origin.y) - float(extent.y), float(origin.y) + float(extent.y),
        float(origin.z) - float(extent.z), float(origin.z) + float(extent.z),
    )


def xy_distance_to_bounds(location, bounds):
    x, y = float(location.x), float(location.y)
    dx = max(bounds[0] - x, 0.0, x - bounds[1])
    dy = max(bounds[2] - y, 0.0, y - bounds[3])
    return math.sqrt(dx * dx + dy * dy)


def segment_overlaps_bounds(start, end, bounds, pad=100.0):
    x, y = float(start.x), float(start.y)
    z_min, z_max = sorted((float(start.z), float(end.z)))
    return (
        bounds[0] - pad <= x <= bounds[1] + pad
        and bounds[2] - pad <= y <= bounds[3] + pad
        and z_max >= bounds[4] - pad
        and z_min <= bounds[5] + pad
    )


def world_trace(world, start, end, trace_complex, ignored):
    trace_type = getattr(unreal.TraceTypeQuery, "ECC_VISIBILITY", None)
    if trace_type is None:
        trace_type = getattr(unreal.TraceTypeQuery, "TRACE_TYPE_QUERY1", None)
    if trace_type is None:
        return None, False, "NO_VISIBILITY_TRACE_ENUM"
    try:
        result = unreal.SystemLibrary.line_trace_single(
            world, start, end, trace_type, trace_complex, ignored,
            unreal.DrawDebugTrace.NONE, True,
        )
    except Exception as exc:
        return None, False, f"ERROR {type(exc).__name__}: {exc}"
    hit, blocking = parse_hit(result)
    return hit, blocking, type(result).__name__


def component_trace(component, start, end, trace_complex):
    method = getattr(component, "line_trace_component", None)
    if not callable(method):
        return None, False, "METHOD_UNAVAILABLE"
    last_error = None
    for args in (
        (start, end, trace_complex, False, False),
        (start, end, trace_complex, False),
    ):
        try:
            result = method(*args)
            hit, blocking = parse_hit(result)
            return hit, blocking, type(result).__name__
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
    return None, False, f"ERROR {last_error}"


def component_state(component):
    registered = safe_method(component, "is_registered")
    active = safe_method(component, "is_active")
    physics = safe_method(component, "is_physics_state_created")
    collision = safe_method(component, "get_collision_enabled")
    object_type = safe_method(component, "get_collision_object_type")
    channel = getattr(unreal.CollisionChannel, "ECC_VISIBILITY", None)
    response = safe_method(component, "get_collision_response_to_channel", channel) if channel is not None else None
    return registered, active, physics, collision, object_type, response


def main():
    log("AETHER STAGE 14E - TERRAIN COLLISION PATH DIAGNOSTIC")
    log("=" * 100)
    log("READ_ONLY=TRUE")
    log("No collision mutation, package save, PIE command, Mesh Partition build, cook, or commandlet is invoked.")

    ns = load_base()
    world = ns["get_pie_world"]()
    if not world:
        raise RuntimeError("No PIE game world exists")
    actors = ns["all_actors"](world)
    environment = ns["find_actor"](actors, ns["ENVIRONMENT_LABEL"], ns["ENVIRONMENT_TAG"])
    river = ns["find_actor"](actors, ns["RIVER_LABEL"], None)
    water_zone = ns["find_actor"](actors, ns["WATER_ZONE_LABEL"], None)
    if not environment:
        raise RuntimeError("Stage 13 environment actor is missing from PIE")

    hism_class = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    hisms = list(environment.get_components_by_class(hism_class)) if hism_class else []
    rock_components = [component for component in hisms if ns["category"](component) == "rock"]
    locations = ns["sample_locations"](rock_components)
    if len(locations) != ns["TERRAIN_SAMPLE_TARGET"]:
        raise RuntimeError(f"Expected {ns['TERRAIN_SAMPLE_TARGET']} rock sample locations, found {len(locations)}")

    sections = ns["collect_compiled_sections"](world)
    collision_components = []
    for section in sections:
        for component in ns["get_components"](section):
            if "MESHPARTITIONCOLLISIONCOMPONENT" in class_path(component).upper():
                collision_components.append((section, component))

    bounded = []
    registered_count = active_count = physics_true = physics_false = 0
    visibility_block = 0
    for section, component in collision_components:
        bounds = component_bounds(component)
        if bounds is not None:
            bounded.append((section, component, bounds))
        registered, active, physics, collision, object_type, response = component_state(component)
        registered_count += int(registered is True)
        active_count += int(active is True)
        physics_true += int(physics is True)
        physics_false += int(physics is False)
        visibility_block += int(response is not None and "BLOCK" in str(response).upper())

    log(f"PIE_WORLD={world.get_path_name()}")
    log(f"PIE_ACTORS={len(actors)}")
    log(f"PIE_COMPILED_SECTIONS={len(sections)}")
    log(f"COLLISION_COMPONENTS={len(collision_components)}")
    log(f"COLLISION_COMPONENTS_WITH_BOUNDS={len(bounded)}")
    log(f"REGISTERED_COLLISION_COMPONENTS={registered_count}")
    log(f"ACTIVE_COLLISION_COMPONENTS={active_count}")
    log(f"PHYSICS_STATE_TRUE={physics_true}")
    log(f"PHYSICS_STATE_FALSE={physics_false}")
    log(f"VISIBILITY_BLOCKING_COMPONENTS={visibility_block}")

    ignored = [environment]
    if river:
        ignored.append(river)
    if water_zone:
        ignored.append(water_zone)

    samples_with_bounds = 0
    world_simple_hits = world_complex_hits = 0
    direct_simple_hits = direct_complex_hits = 0

    for index, location in enumerate(locations):
        start = unreal.Vector(float(location.x), float(location.y), float(location.z) + 10000.0)
        end = unreal.Vector(float(location.x), float(location.y), float(location.z) - 30000.0)
        overlapping = [item for item in bounded if segment_overlaps_bounds(start, end, item[2])]
        ordered = sorted(bounded, key=lambda item: xy_distance_to_bounds(location, item[2]))
        candidates = overlapping if overlapping else ordered[:12]
        samples_with_bounds += int(bool(overlapping))
        nearest_distance = xy_distance_to_bounds(location, ordered[0][2]) if ordered else float("inf")

        simple_hit, simple_blocking, simple_type = world_trace(world, start, end, False, ignored)
        complex_hit, complex_blocking, complex_type = world_trace(world, start, end, True, ignored)
        world_simple_hits += int(simple_blocking)
        world_complex_hits += int(complex_blocking)

        direct_simple = []
        direct_complex = []
        for section, component, bounds in candidates:
            hit, blocking, result_type = component_trace(component, start, end, False)
            if blocking:
                direct_simple.append((section, component, hit, result_type))
            hit, blocking, result_type = component_trace(component, start, end, True)
            if blocking:
                direct_complex.append((section, component, hit, result_type))
        direct_simple_hits += int(bool(direct_simple))
        direct_complex_hits += int(bool(direct_complex))

        log("")
        log(f"SAMPLE_{index}_LOCATION={vector_text(location)}")
        log(f"SAMPLE_{index}_TRACE_START={vector_text(start)}")
        log(f"SAMPLE_{index}_TRACE_END={vector_text(end)}")
        log(f"SAMPLE_{index}_OVERLAPPING_COLLISION_BOUNDS={len(overlapping)}")
        log(f"SAMPLE_{index}_NEAREST_COLLISION_BOUNDS_DISTANCE_CM={nearest_distance:.3f}")
        log(f"SAMPLE_{index}_WORLD_SIMPLE_BLOCKING={simple_blocking} result_type:{simple_type}")
        log(f"SAMPLE_{index}_WORLD_COMPLEX_BLOCKING={complex_blocking} result_type:{complex_type}")
        log(f"SAMPLE_{index}_DIRECT_SIMPLE_BLOCKING_COMPONENTS={len(direct_simple)}")
        log(f"SAMPLE_{index}_DIRECT_COMPLEX_BLOCKING_COMPONENTS={len(direct_complex)}")
        for label, hits in (("SIMPLE", direct_simple), ("COMPLEX", direct_complex)):
            for hit_index, (section, component, hit, result_type) in enumerate(hits[:3]):
                point = safe_property(hit, "impact_point") or safe_property(hit, "location")
                log(
                    f"  SAMPLE_{index}_{label}_HIT_{hit_index}=section:{section.get_name()} "
                    f"component:{component.get_name()} point:{vector_text(point)} result_type:{result_type}"
                )
        for candidate_index, (section, component, bounds) in enumerate(candidates[:3]):
            registered, active, physics, collision, object_type, response = component_state(component)
            log(
                f"  SAMPLE_{index}_CANDIDATE_{candidate_index}=section:{section.get_name()} component:{component.get_name()} "
                f"registered:{registered} active:{active} physics:{physics} collision:{collision} "
                f"object:{object_type} visibility:{response} bounds:{bounds}"
            )

    log("")
    log("SUMMARY")
    log("-" * 100)
    log(f"SAMPLES={len(locations)}")
    log(f"SAMPLES_WITH_OVERLAPPING_COLLISION_BOUNDS={samples_with_bounds}")
    log(f"WORLD_SIMPLE_BLOCKING_HITS={world_simple_hits}")
    log(f"WORLD_COMPLEX_BLOCKING_HITS={world_complex_hits}")
    log(f"DIRECT_SIMPLE_BLOCKING_HITS={direct_simple_hits}")
    log(f"DIRECT_COMPLEX_BLOCKING_HITS={direct_complex_hits}")
    if samples_with_bounds == 0:
        diagnosis = "SAMPLE_COORDINATE_OR_COLLISION_BOUNDS_MISMATCH"
    elif direct_simple_hits == 0 and direct_complex_hits == 0 and physics_false > 0:
        diagnosis = "COLLISION_COMPONENT_PHYSICS_STATE_MISSING"
    elif direct_simple_hits + direct_complex_hits > 0 and world_simple_hits + world_complex_hits == 0:
        diagnosis = "WORLD_TRACE_CHANNEL_OR_REGISTRATION_PATH_FAILURE"
    elif direct_simple_hits + direct_complex_hits == 0:
        diagnosis = "COLLISION_BODY_DATA_NOT_TRACEABLE"
    else:
        diagnosis = "COLLISION_PATH_TRACEABLE"
    log(f"DIAGNOSIS={diagnosis}")
    log("DIAGNOSTIC_RESULT=PASS")
    log("NO_COLLISION_SETTINGS_CHANGED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PIE_START_OR_STOP_COMMAND_CALLED=TRUE")
    log("NO_BUILD_METHOD_CALLED=TRUE")
    log("NO_WHOLE_WORLD_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_warning(f"AETHER_STAGE14_TERRAIN_COLLISION_DIAGNOSTIC_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    log("")
    log("DIAGNOSTIC_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("NO_COLLISION_SETTINGS_CHANGED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PIE_START_OR_STOP_COMMAND_CALLED=TRUE")
    log("NO_BUILD_METHOD_CALLED=TRUE")
    log("NO_WHOLE_WORLD_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE14_TERRAIN_COLLISION_DIAGNOSTIC_FAILED={type(exc).__name__}: {exc}")
    raise
