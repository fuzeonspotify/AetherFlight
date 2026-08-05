"""Read-only Stage 14 terrain contact trace diagnostic.

The previous runtime probe traced from rock instance pivots. River rocks use a
mesh-base offset, so large meshes can place the terrain farther below that pivot
than the old 30,000 cm ray. This diagnostic transforms each static mesh's local
bottom into world space and compares short contact traces with long safety rays.
It never mutates assets, collision, PIE, or Mesh Partition state.
"""

from pathlib import Path
import math
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_SCRIPT = SCRIPT_DIR / "AuditAetherStage14PIERuntime_UE58.py"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14TerrainContactTraceDiagnostic.txt"
LINES = []
SAMPLE_TARGET = 10
CONTACT_UP_CM = 15000.0
CONTACT_DOWN_CM = 40000.0
LONG_UP_CM = 20000.0
LONG_DOWN_CM = 250000.0
MIN_TERRAIN_HITS = 6


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
    ns = {"__file__": str(BASE_SCRIPT), "__name__": "AetherStage14ContactDiagnosticBase"}
    exec(compile(source.split(marker, 1)[0], str(BASE_SCRIPT), "exec"), ns, ns)
    return ns


def safe_property(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        try:
            value = getattr(obj, name)
            return value() if callable(value) else value
        except Exception:
            return default


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__ if obj is not None else None


def vector_text(value):
    if value is None:
        return "None"
    return f"({float(value.x):.3f},{float(value.y):.3f},{float(value.z):.3f})"


def get_static_mesh(component):
    method = getattr(component, "get_static_mesh", None)
    if callable(method):
        try:
            mesh = method()
            if mesh:
                return mesh
        except Exception:
            pass
    return safe_property(component, "static_mesh")


def extract_transform(result):
    values = result if isinstance(result, tuple) else (result,)
    bools = [value for value in values if isinstance(value, bool)]
    if bools and not any(bools):
        return None
    for value in values:
        if value is not None and "TRANSFORM" in type(value).__name__.upper():
            return value
    return None


def instance_transform(component, index, world_space=True):
    method = getattr(component, "get_instance_transform", None)
    if not callable(method):
        return None
    for args in ((index, world_space), (index,)):
        try:
            transform = extract_transform(method(*args))
            if transform is not None:
                return transform
        except Exception:
            pass
    return None


def transform_location(transform):
    return safe_property(transform, "translation") or safe_property(transform, "location")


def transformed_mesh_bottom(mesh, transform):
    bounds = mesh.get_bounds()
    origin = safe_property(bounds, "origin")
    extent = safe_property(bounds, "box_extent")
    if origin is None or extent is None:
        return None, None

    bottom_center_local = unreal.Vector(
        float(origin.x),
        float(origin.y),
        float(origin.z) - float(extent.z),
    )
    bottom_center_world = unreal.MathLibrary.transform_location(transform, bottom_center_local)

    corners = []
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                local = unreal.Vector(
                    float(origin.x) + sx * float(extent.x),
                    float(origin.y) + sy * float(extent.y),
                    float(origin.z) + sz * float(extent.z),
                )
                corners.append(unreal.MathLibrary.transform_location(transform, local))
    lowest_corner = min(corners, key=lambda value: float(value.z)) if corners else None
    return bottom_center_world, lowest_corner


def parse_hit(result):
    if result is None:
        return None, False
    values = result if isinstance(result, tuple) else (result,)
    bools = [value for value in values if isinstance(value, bool)]
    hit = None
    for value in values:
        if value is not None and "HITRESULT" in type(value).__name__.upper():
            hit = value
            break
    if bools and not any(bools):
        return hit, False
    if hit is None:
        return None, False
    blocking = safe_property(hit, "blocking_hit")
    if blocking is None:
        blocking = safe_property(hit, "b_blocking_hit")
    return hit, bool(blocking)


def terrain_like_hit(hit):
    if not hit:
        return False
    actor = safe_property(hit, "hit_actor") or safe_property(hit, "actor")
    component = safe_property(hit, "hit_component") or safe_property(hit, "component")
    return bool(
        "COMPILEDSECTION" in str(class_path(actor)).upper()
        or "MESHPARTITIONCOLLISIONCOMPONENT" in str(class_path(component)).upper()
    )


def hit_text(hit):
    if not hit:
        return "None"
    actor = safe_property(hit, "hit_actor") or safe_property(hit, "actor")
    component = safe_property(hit, "hit_component") or safe_property(hit, "component")
    point = safe_property(hit, "impact_point") or safe_property(hit, "location")
    return (
        f"actor:{class_path(actor)} component:{class_path(component)} "
        f"point:{vector_text(point)} terrain_like:{terrain_like_hit(hit)}"
    )


def visibility_trace(world, start, end, trace_complex, ignored):
    trace_type = getattr(unreal.TraceTypeQuery, "ECC_VISIBILITY", None)
    if trace_type is None:
        trace_type = getattr(unreal.TraceTypeQuery, "TRACE_TYPE_QUERY1", None)
    if trace_type is None:
        return None, False
    result = unreal.SystemLibrary.line_trace_single(
        world, start, end, trace_type, trace_complex, ignored,
        unreal.DrawDebugTrace.NONE, True,
    )
    return parse_hit(result)


def profile_trace(world, start, end, trace_complex, ignored):
    result = unreal.SystemLibrary.line_trace_single_by_profile(
        world, start, end, "BlockAll", trace_complex, ignored,
        unreal.DrawDebugTrace.NONE, True,
    )
    return parse_hit(result)


def collect_samples(rock_components):
    samples = []
    for component in rock_components:
        mesh = get_static_mesh(component)
        if not mesh:
            continue
        try:
            count = int(component.get_instance_count())
        except Exception:
            count = 0
        for index in range(min(count, 3)):
            transform = instance_transform(component, index, True)
            if transform is None:
                continue
            pivot = transform_location(transform)
            bottom_center, lowest_corner = transformed_mesh_bottom(mesh, transform)
            if pivot is None or bottom_center is None:
                continue
            samples.append((component, mesh, index, pivot, bottom_center, lowest_corner))
            if len(samples) >= SAMPLE_TARGET:
                return samples
    return samples


def main():
    log("AETHER STAGE 14G - TERRAIN CONTACT TRACE DIAGNOSTIC")
    log("=" * 100)
    log("READ_ONLY=TRUE")
    log("Uses transformed static-mesh bottoms and long safety rays; no collision mutation, save, PIE command, or build is invoked.")

    ns = load_base()
    world = ns["get_pie_world"]()
    if not world:
        raise RuntimeError("No PIE game world exists")
    actors = ns["all_actors"](world)
    environment = ns["find_actor"](actors, ns["ENVIRONMENT_LABEL"], ns["ENVIRONMENT_TAG"])
    if not environment:
        raise RuntimeError("Stage 13 environment actor is missing from PIE")

    river = ns["find_actor"](actors, ns["RIVER_LABEL"], None)
    water_zone = ns["find_actor"](actors, ns["WATER_ZONE_LABEL"], None)
    hism_class = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    hisms = list(environment.get_components_by_class(hism_class)) if hism_class else []
    rock_components = [component for component in hisms if ns["category"](component) == "rock"]
    samples = collect_samples(rock_components)
    if len(samples) != SAMPLE_TARGET:
        raise RuntimeError(f"Expected {SAMPLE_TARGET} rock samples, found {len(samples)}")

    ignored = [environment]
    if river:
        ignored.append(river)
    if water_zone:
        ignored.append(water_zone)
    try:
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        if pawn:
            ignored.append(pawn)
    except Exception:
        pass

    contact_visibility_hits = 0
    contact_profile_hits = 0
    long_visibility_hits = 0
    long_profile_hits = 0
    max_pivot_to_base = 0.0

    log(f"PIE_WORLD={world.get_path_name()}")
    log(f"PIE_ACTORS={len(actors)}")
    log(f"ROCK_HISM_COMPONENTS={len(rock_components)}")
    log(f"SAMPLES={len(samples)}")

    for sample_index, (component, mesh, instance_index, pivot, bottom, lowest) in enumerate(samples):
        pivot_to_base = float(pivot.z) - float(bottom.z)
        max_pivot_to_base = max(max_pivot_to_base, pivot_to_base)

        contact_start = unreal.Vector(float(bottom.x), float(bottom.y), float(bottom.z) + CONTACT_UP_CM)
        contact_end = unreal.Vector(float(bottom.x), float(bottom.y), float(bottom.z) - CONTACT_DOWN_CM)
        long_start = unreal.Vector(float(pivot.x), float(pivot.y), float(pivot.z) + LONG_UP_CM)
        long_end = unreal.Vector(float(pivot.x), float(pivot.y), float(pivot.z) - LONG_DOWN_CM)

        cv_hit, cv_block = visibility_trace(world, contact_start, contact_end, False, ignored)
        cp_hit, cp_block = profile_trace(world, contact_start, contact_end, False, ignored)
        lv_hit, lv_block = visibility_trace(world, long_start, long_end, False, ignored)
        lp_hit, lp_block = profile_trace(world, long_start, long_end, False, ignored)

        cv_terrain = bool(cv_block and terrain_like_hit(cv_hit))
        cp_terrain = bool(cp_block and terrain_like_hit(cp_hit))
        lv_terrain = bool(lv_block and terrain_like_hit(lv_hit))
        lp_terrain = bool(lp_block and terrain_like_hit(lp_hit))
        contact_visibility_hits += int(cv_terrain)
        contact_profile_hits += int(cp_terrain)
        long_visibility_hits += int(lv_terrain)
        long_profile_hits += int(lp_terrain)

        log("")
        log(f"SAMPLE_{sample_index}_COMPONENT={component.get_name()}")
        log(f"SAMPLE_{sample_index}_MESH={mesh.get_path_name()}")
        log(f"SAMPLE_{sample_index}_INSTANCE_INDEX={instance_index}")
        log(f"SAMPLE_{sample_index}_PIVOT={vector_text(pivot)}")
        log(f"SAMPLE_{sample_index}_BOTTOM_CENTER={vector_text(bottom)}")
        log(f"SAMPLE_{sample_index}_LOWEST_BOUND_CORNER={vector_text(lowest)}")
        log(f"SAMPLE_{sample_index}_PIVOT_TO_BOTTOM_CM={pivot_to_base:.3f}")
        log(f"SAMPLE_{sample_index}_CONTACT_TRACE_START={vector_text(contact_start)}")
        log(f"SAMPLE_{sample_index}_CONTACT_TRACE_END={vector_text(contact_end)}")
        log(f"SAMPLE_{sample_index}_CONTACT_VISIBILITY_BLOCKING={cv_block} {hit_text(cv_hit)}")
        log(f"SAMPLE_{sample_index}_CONTACT_BLOCKALL_BLOCKING={cp_block} {hit_text(cp_hit)}")
        log(f"SAMPLE_{sample_index}_LONG_VISIBILITY_BLOCKING={lv_block} {hit_text(lv_hit)}")
        log(f"SAMPLE_{sample_index}_LONG_BLOCKALL_BLOCKING={lp_block} {hit_text(lp_hit)}")

    best_contact = max(contact_visibility_hits, contact_profile_hits)
    best_long = max(long_visibility_hits, long_profile_hits)

    log("")
    log("SUMMARY")
    log("-" * 100)
    log(f"MAX_PIVOT_TO_ESTIMATED_BASE_CM={max_pivot_to_base:.3f}")
    log(f"CONTACT_VISIBILITY_TERRAIN_HITS={contact_visibility_hits}")
    log(f"CONTACT_BLOCKALL_TERRAIN_HITS={contact_profile_hits}")
    log(f"LONG_VISIBILITY_TERRAIN_HITS={long_visibility_hits}")
    log(f"LONG_BLOCKALL_TERRAIN_HITS={long_profile_hits}")
    if best_contact >= MIN_TERRAIN_HITS:
        diagnosis = "OLD_PIVOT_RAY_WAS_TOO_SHORT_TERRAIN_COLLISION_TRACEABLE"
    elif best_long >= MIN_TERRAIN_HITS:
        diagnosis = "MESH_BOTTOM_ESTIMATE_INACCURATE_BUT_LONG_RAY_PROVES_TERRAIN_COLLISION"
    else:
        diagnosis = "TERRAIN_COLLISION_NOT_TRACEABLE_AFTER_CONTACT_AND_LONG_RAYS"
    log(f"DIAGNOSIS={diagnosis}")
    log("DIAGNOSTIC_RESULT=PASS")
    log("NO_COLLISION_SETTINGS_CHANGED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PIE_START_OR_STOP_COMMAND_CALLED=TRUE")
    log("NO_BUILD_METHOD_CALLED=TRUE")
    log("NO_WHOLE_WORLD_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_warning(f"AETHER_STAGE14_TERRAIN_CONTACT_DIAGNOSTIC_REPORT={REPORT_PATH}")


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
    unreal.log_error(f"AETHER_STAGE14_TERRAIN_CONTACT_DIAGNOSTIC_FAILED={type(exc).__name__}: {exc}")
    raise
