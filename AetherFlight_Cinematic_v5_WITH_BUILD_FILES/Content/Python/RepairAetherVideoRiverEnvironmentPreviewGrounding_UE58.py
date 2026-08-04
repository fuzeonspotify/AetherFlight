from pathlib import Path
import random
import sys
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import AetherRiverEnvironmentCommon_UE58_v2 as common
from AetherRiverEnvironmentPlacement_UE58 import EDGE_MARGIN_CM, RANDOM_SEED, STATION_SPACING_CM, add_instance, configure_hism, make_transform

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherRiverEnvironmentPreviewGrounding.txt"
TEMP_LABEL = "Aether_VideoStage13_RiverEnvironment_PreviewGroundingCandidate"
TEMP_TAG = "AetherVideoRiverEnvironmentPreviewGroundingCandidate"
MARGIN = 12000.0
RAY_LIFT = 30000.0
RAY_MAX = 70000.0
MIN_HITS = 180
MIN_RATIO = 0.98
MAX_COMPONENTS = 256
LINES = []


def log(text=""):
    common.record(LINES, text)


def report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def load_audit_helpers():
    path = SCRIPT_DIR / "AuditAetherMeshTerrainPreviewSections_UE58.py"
    source = path.read_text(encoding="utf-8")
    marker = "\ntry:\n    main()"
    if marker not in source:
        raise RuntimeError("Preview-section audit helper marker was not found")
    ns = {"__file__": str(path), "__name__": "AetherPreviewAuditHelpers"}
    exec(compile(source.split(marker, 1)[0], str(path), "exec"), ns, ns)
    return ns


def tags(actor):
    try:
        return [str(v) for v in actor.get_editor_property("tags")]
    except Exception:
        return []


def component_transform(component):
    method = getattr(component, "get_component_transform", None)
    if callable(method):
        try:
            return method()
        except Exception:
            pass
    try:
        return component.get_editor_property("component_to_world")
    except Exception:
        return None


def world_bounds(component, mesh):
    try:
        b = mesh.get_bounds()
        t = component_transform(component)
        if t is None:
            return None
        points = []
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                for sz in (-1.0, 1.0):
                    p = unreal.Vector(float(b.origin.x) + sx * float(b.box_extent.x), float(b.origin.y) + sy * float(b.box_extent.y), float(b.origin.z) + sz * float(b.box_extent.z))
                    points.append(unreal.MathLibrary.transform_location(t, p))
        return (min(float(p.x) for p in points), max(float(p.x) for p in points), min(float(p.y) for p in points), max(float(p.y) for p in points))
    except Exception:
        return None


def corridor_bounds(spline):
    length = float(spline.get_spline_length())
    space = unreal.SplineCoordinateSpace.WORLD
    count = max(1, int((length - 2.0 * EDGE_MARGIN_CM) / STATION_SPACING_CM) + 1)
    points = [spline.get_location_at_distance_along_spline(min(EDGE_MARGIN_CM + i * STATION_SPACING_CM, length - EDGE_MARGIN_CM), space) for i in range(count)]
    return (min(float(p.x) for p in points) - MARGIN, max(float(p.x) for p in points) + MARGIN, min(float(p.y) for p in points) - MARGIN, max(float(p.y) for p in points) + MARGIN)


def overlaps(a, b):
    return not (a[1] < b[0] or a[0] > b[1] or a[3] < b[2] or a[2] > b[3])


def extract_outcome(result):
    if isinstance(result, tuple):
        for item in result:
            if "OUTCOME" in f"{type(item).__name__} {type(item)}".upper():
                return item
    return None


def success(value):
    text = str(value).upper()
    return "SUCCESS" in text and "FAIL" not in text and "NOT_FOUND" not in text


def extract_hit(result):
    outcome = extract_outcome(result)
    items = result if isinstance(result, tuple) else (result,)
    for item in items:
        if "RAYHITRESULT" not in f"{type(item).__name__} {type(item)}".upper():
            continue
        try:
            if not bool(item.get_editor_property("hit")):
                return None, outcome
            return (item.get_editor_property("hit_position"), float(item.get_editor_property("ray_parameter"))), outcome
        except Exception:
            return None, outcome
    return None, outcome


def select_components(world, actors, spline, h):
    corridor = corridor_bounds(spline)
    chosen = {}
    scanned = 0
    for section in h["collect_section_actors"](world, actors):
        for component in h["get_components"](section):
            mesh = h["safe_static_mesh"](component)
            if not mesh:
                continue
            scanned += 1
            bounds = world_bounds(component, mesh)
            if bounds is None or not overlaps(bounds, corridor):
                continue
            transform = component_transform(component)
            key = (mesh.get_path_name(), str(transform))
            name = component.get_name().lower()
            cls = h["class_path"](component).lower()
            rank = 0 if "staticmeshpreviewcomponent" in cls else (1 if "virtualtexturefallback" in name else 2)
            old = chosen.get(key)
            if old is None or rank < old[0]:
                chosen[key] = (rank, component, mesh, bounds)
    result = sorted(chosen.values(), key=lambda x: (x[0], x[2].get_path_name()))
    log(f"Section mesh components scanned={scanned}")
    log(f"River corridor preview components selected={len(result)}")
    log(f"River corridor XY bounds={corridor}")
    if not result or len(result) > MAX_COMPONENTS:
        raise RuntimeError(f"Invalid preview component count for river corridor: {len(result)}")
    return result


def build_surfaces(candidates, h):
    dm_cls = getattr(unreal, "DynamicMesh", None)
    scene = getattr(unreal, "GeometryScript_SceneUtils", None)
    copy_cls = getattr(unreal, "GeometryScriptCopyMeshFromComponentOptions", None)
    spatial = getattr(unreal, "GeometryScript_MeshSpatial", None)
    query_cls = getattr(unreal, "GeometryScriptSpatialQueryOptions", None)
    if not all((dm_cls, scene, copy_cls, spatial, query_cls)):
        raise RuntimeError("Geometry Script preview-query API is unavailable")
    copy_options = copy_cls()
    try:
        copy_options.set_editor_property("want_normals", True)
    except Exception:
        pass
    query_options = query_cls()
    surfaces, failures = [], []
    for _, component, mesh, bounds in candidates:
        try:
            dm = dm_cls()
            copied = scene.copy_mesh_from_component(component, dm, copy_options, True)
            outcome = extract_outcome(copied)
            if outcome is not None and not success(outcome):
                raise RuntimeError(f"copy outcome={outcome}")
            bvh = h["extract_bvh"](spatial.build_bvh_for_mesh(dm))
            if bvh is None:
                raise RuntimeError("BVH was None")
            surfaces.append((component, bounds, dm, bvh, query_options))
        except Exception as exc:
            failures.append(f"{component.get_name()}: {type(exc).__name__}: {exc}")
    log(f"Preview Dynamic Mesh copies={len(surfaces)}")
    log(f"Preview Dynamic Mesh copy failures={len(failures)}")
    for item in failures[:10]:
        log(f"  copy failure={item}")
    if not surfaces:
        raise RuntimeError("No preview component copied successfully")
    return surfaces, spatial


def surface_down(surfaces, spatial, x, y, z):
    origin = unreal.Vector(x, y, z + RAY_LIFT)
    direction = unreal.Vector(0.0, 0.0, -1.0)
    best = None
    for component, bounds, dm, bvh, options in surfaces:
        if x < bounds[0] - 100.0 or x > bounds[1] + 100.0 or y < bounds[2] - 100.0 or y > bounds[3] + 100.0:
            continue
        try:
            result = spatial.find_nearest_ray_intersection_with_mesh(dm, bvh, origin, direction, options)
        except Exception:
            continue
        hit, outcome = extract_hit(result)
        if hit is None or (outcome is not None and not success(outcome)):
            continue
        point, distance = hit
        if point is None or distance < 0.0 or distance > RAY_MAX:
            continue
        if best is None or distance < best[0]:
            best = (distance, point, component)
    return best


def base_offset(mesh, scale, category):
    try:
        b = mesh.get_bounds()
        offset = max(0.0, -(float(b.origin.z) - float(b.box_extent.z)) * scale)
        half = float(b.box_extent.z) * scale
    except Exception:
        return 0.0
    if category == "rock":
        return offset - min(95.0, max(25.0, half * 0.18))
    if category == "shrub":
        return offset - min(28.0, max(6.0, half * 0.035))
    return offset - min(12.0, max(2.0, half * 0.02))


def place_instances(spline, actor, mesh_sets, surfaces, spatial):
    rng = random.Random(RANDOM_SEED)
    hism_cls = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    components, counts = {}, {}
    for category, entries in mesh_sets.items():
        for path, mesh in entries:
            c = common.add_component_to_actor(actor, hism_cls, LINES)
            configure_hism(c, mesh, category, LINES)
            components[(category, path)] = c
            counts[(category, path)] = 0
    length = float(spline.get_spline_length())
    space = unreal.SplineCoordinateSpace.WORLD
    stations = max(1, int((length - 2.0 * EDGE_MARGIN_CM) / STATION_SPACING_CM) + 1)
    requested = hits = misses = 0
    closest = float("inf")
    min_dz, max_dz = float("inf"), float("-inf")

    def place(category, station, side, o_min, o_max, s_min, s_max):
        nonlocal requested, hits, misses, closest, min_dz, max_dz
        entries = mesh_sets[category]
        distance = max(EDGE_MARGIN_CM, min(length - EDGE_MARGIN_CM, station + rng.uniform(-650.0, 650.0)))
        center = spline.get_location_at_distance_along_spline(distance, space)
        right = spline.get_right_vector_at_distance_along_spline(distance, space)
        offset = rng.uniform(o_min, o_max)
        closest = min(closest, offset)
        path, mesh = entries[rng.randrange(len(entries))]
        scale = rng.uniform(s_min, s_max)
        if category == "rock":
            rotation = unreal.Rotator(rng.uniform(-9.0, 9.0), rng.uniform(0.0, 360.0), rng.uniform(-9.0, 9.0))
        else:
            rotation = unreal.Rotator(0.0, rng.uniform(0.0, 360.0), 0.0)
        x = float(center.x) + float(right.x) * side * offset
        y = float(center.y) + float(right.y) * side * offset
        requested += 1
        result = surface_down(surfaces, spatial, x, y, float(center.z))
        if result is None:
            misses += 1
            return
        _, point, _ = result
        hits += 1
        dz = float(point.z) - float(center.z)
        min_dz, max_dz = min(min_dz, dz), max(max_dz, dz)
        transform = make_transform(unreal.Vector(x, y, float(point.z) + base_offset(mesh, scale, category)), rotation, unreal.Vector(scale, scale, scale))
        add_instance(components[(category, path)], transform)
        counts[(category, path)] += 1

    for i in range(stations):
        station = min(EDGE_MARGIN_CM + i * STATION_SPACING_CM, length - EDGE_MARGIN_CM)
        for side in (-1.0, 1.0):
            place("ground", station, side, 1650.0, 3000.0, 0.72, 1.24)
            if i % 2 == 0:
                place("shrub", station, side, 2100.0, 3900.0, 0.78, 1.22)
            if i % 3 == 0:
                place("rock", station, side, 1500.0, 3600.0, 0.68, 1.35)
            if i % 4 == 1:
                place("ground", station, side, 2000.0, 4200.0, 0.65, 1.12)
    total = sum(counts.values())
    ratio = hits / requested if requested else 0.0
    log(f"River station count={stations}")
    log(f"Requested environment placements={requested}")
    log(f"Preview Dynamic Mesh surface hits={hits}")
    log(f"Preview Dynamic Mesh surface misses={misses}")
    log(f"Preview Dynamic Mesh hit ratio={ratio:.6f}")
    log(f"Strictly grounded HISM instances={total}")
    log(f"Terrain Z adjustment range cm={min_dz}..{max_dz}")
    for (category, path), count in sorted(counts.items()):
        log(f"  {category.upper()} count={count} | {path}")
    return total, counts, requested, hits, misses, ratio, closest, min_dz, max_dz


def save_map():
    saved = False
    cls = getattr(unreal, "LevelEditorSubsystem", None)
    if cls:
        try:
            saved = bool(unreal.get_editor_subsystem(cls).save_current_level())
        except Exception as exc:
            log(f"LevelEditorSubsystem save warning={exc}")
    if not saved:
        try:
            saved = bool(unreal.EditorLevelLibrary.save_current_level())
        except Exception as exc:
            log(f"EditorLevelLibrary save warning={exc}")
    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
        saved = True
    except Exception as exc:
        log(f"save_dirty_packages warning={exc}")
    return saved


def main():
    log("AETHER STAGE 13.3 - PREVIEW SECTION DYNAMIC MESH GROUNDING")
    log("=" * 96)
    log("Queries loaded Mesh Terrain preview geometry through transient world-space Dynamic Mesh BVHs.")
    log("Only the Stage 13 environment actor is replaced after successful validation. No Mesh Partition build is started.")
    h = load_audit_helpers()
    world = common.load_world()
    subsystem, actors = common.get_actor_subsystem_and_actors()
    for actor in list(actors):
        if common.actor_label(actor) == TEMP_LABEL or TEMP_TAG in tags(actor):
            subsystem.destroy_actor(actor)
    _, actors = common.get_actor_subsystem_and_actors()
    labels = (common.SOURCE_SPLINE_LABEL, common.SOURCE_REMESH_LABEL, common.RIVER_LABEL, common.WATER_ZONE_LABEL, common.WETLAND_LABEL, common.EXCLUSION_LABEL, common.ENVIRONMENT_LABEL)
    found = {label: common.find_actor(actors, label) for label in labels}
    missing = [label for label, actor in found.items() if not actor]
    if missing:
        raise RuntimeError(f"Required actors are missing: {missing}")
    spline_cls = getattr(unreal, "SplineComponent", None)
    spline = common.find_single_component(found[common.SOURCE_SPLINE_LABEL], spline_cls, "Stage09 SplineComponent")
    if int(spline.get_number_of_spline_points()) != 5:
        raise RuntimeError("Stage09 source spline must contain five points")
    assets = common.list_game_assets()
    rocks = common.discover_static_meshes(assets, common.ROCK_TOKENS, 4)
    shrubs = common.discover_static_meshes(assets, common.SHRUB_TOKENS, 2)
    ground = common.discover_static_meshes(assets, common.GROUND_TOKENS, 2)
    if (len(rocks), len(shrubs), len(ground)) != (4, 2, 2):
        raise RuntimeError(f"Stage13 asset selection changed: rocks={len(rocks)}, shrubs={len(shrubs)}, ground={len(ground)}")
    log(f"World={world.get_path_name()}")
    candidates = select_components(world, actors, spline, h)
    surfaces, spatial = build_surfaces(candidates, h)
    candidate = subsystem.spawn_actor_from_class(unreal.Actor, unreal.Vector(), unreal.Rotator(), False)
    if not candidate:
        raise RuntimeError("Could not spawn preview-grounding candidate actor")
    candidate.set_actor_label(TEMP_LABEL, True)
    candidate.set_editor_property("tags", [unreal.Name(TEMP_TAG)])
    try:
        result = place_instances(spline, candidate, {"rock": rocks, "shrub": shrubs, "ground": ground}, surfaces, spatial)
        total, counts, requested, hits, misses, ratio, closest, min_dz, max_dz = result
        if hits < MIN_HITS or ratio < MIN_RATIO:
            raise RuntimeError(f"Insufficient preview query coverage: hits={hits}, requested={requested}, ratio={ratio:.3f}")
        subsystem.destroy_actor(found[common.ENVIRONMENT_LABEL])
        candidate.set_actor_label(common.ENVIRONMENT_LABEL, True)
        candidate.set_editor_property("tags", [unreal.Name(common.ENVIRONMENT_TAG)])
        saved = save_map()
        if not saved:
            raise RuntimeError("Map save did not report success")
        log("Map save=PASS")
        log("")
        log("PREVIEW_GROUNDING_RESULT=PASS")
        log(f"ENVIRONMENT_ACTOR={common.ENVIRONMENT_LABEL}")
        log(f"PRESERVED_EXCLUSION_ACTOR={common.EXCLUSION_LABEL}")
        log(f"HISM_COMPONENTS={len(counts)}")
        log(f"HISM_TOTAL_INSTANCES={total}")
        log(f"QUERY_REQUESTS={requested}")
        log(f"PREVIEW_DYNAMIC_MESH_HITS={hits}")
        log(f"PREVIEW_DYNAMIC_MESH_MISSES={misses}")
        log(f"PREVIEW_DYNAMIC_MESH_HIT_RATIO={ratio:.6f}")
        log(f"PREVIEW_COMPONENTS_USED={len(surfaces)}")
        log(f"CLOSEST_ENVIRONMENT_OFFSET_CM={closest}")
        log(f"TERRAIN_Z_ADJUSTMENT_MIN_CM={min_dz}")
        log(f"TERRAIN_Z_ADJUSTMENT_MAX_CM={max_dz}")
        log("ROCKS_PARTIALLY_EMBEDDED=TRUE")
        log("TRANSIENT_DYNAMIC_MESH_OBJECTS_ONLY=TRUE")
        log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    except Exception:
        try:
            subsystem.destroy_actor(candidate)
        except Exception:
            pass
        raise
    report()
    unreal.log_warning(f"AETHER_PREVIEW_GROUNDING_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    log("")
    log("PREVIEW_GROUNDING_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("SAVED_ENVIRONMENT_ACTOR_WAS_NOT_REPLACED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    report()
    unreal.log_error(f"AETHER_PREVIEW_GROUNDING_FAILED={type(exc).__name__}: {exc}")
    raise
