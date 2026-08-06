"""Stage 13.3 V3: exact preview grounding with correct partition-space queries.

V2 correctly identifies river tiles. V3 also preserves each tile's coordinate
space while copying/querying its transient Dynamic Mesh, preventing a second
world transform from being applied to raw Mesh Partition geometry.
"""

from pathlib import Path
import math
import sys

import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

V2 = SCRIPT_DIR / "RepairAetherVideoRiverEnvironmentPreviewGrounding_UE58_v2.py"
if not V2.is_file():
    raise RuntimeError(f"Stage 13.3 V2 repair is missing: {V2}")

source = V2.read_text(encoding="utf-8")
marker = '\ntry:\n    ns["main"]()'
if marker not in source:
    raise RuntimeError("Stage 13.3 V2 entry marker was not found")

wrapper = {"__file__": str(V2), "__name__": "AetherPreviewGroundingV3Base"}
exec(compile(source.split(marker, 1)[0], str(V2), "exec"), wrapper, wrapper)

base = wrapper["ns"]
QUERY_STATS = {"ray_hits": 0, "nearest_fallback_hits": 0, "misses": 0}


def _zero_vector():
    return unreal.Vector(0.0, 0.0, 0.0)


def _vector_or_zero(value):
    return value if value is not None else _zero_vector()


def _subtract(value, offset):
    return unreal.Vector(
        float(value.x) - float(offset.x),
        float(value.y) - float(offset.y),
        float(value.z) - float(offset.z),
    )


def _add(value, offset):
    return unreal.Vector(
        float(value.x) + float(offset.x),
        float(value.y) + float(offset.y),
        float(value.z) + float(offset.z),
    )


def _property(obj, names):
    if obj is None:
        return None
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception:
            pass
        try:
            return getattr(obj, name)
        except Exception:
            pass
    return None


def _struct_from_result(result, keywords, preferred_index=1):
    items = result if isinstance(result, tuple) else (result,)
    if isinstance(result, tuple) and len(result) > preferred_index:
        candidate = result[preferred_index]
        type_text = f"{type(candidate).__name__} {type(candidate)}".upper()
        if any(keyword in type_text for keyword in keywords):
            return candidate
    for item in items:
        type_text = f"{type(item).__name__} {type(item)}".upper()
        if any(keyword in type_text for keyword in keywords):
            return item
    return None


def _ray_hit(result):
    outcome = base["extract_outcome"](result)
    if outcome is not None and not base["success"](outcome):
        return None
    hit = _struct_from_result(result, ("RAYHIT", "RAY_HIT"))
    if hit is None:
        return None
    valid = _property(hit, ("hit", "b_hit", "valid", "b_valid"))
    if valid is False:
        return None
    point = _property(hit, ("hit_position", "position"))
    parameter = _property(hit, ("ray_parameter", "distance"))
    if point is None:
        return None
    try:
        parameter = float(parameter)
    except Exception:
        parameter = 0.0
    if parameter < 0.0:
        return None
    return point, parameter


def _nearest_point(result):
    outcome = base["extract_outcome"](result)
    if outcome is not None and not base["success"](outcome):
        return None
    point_struct = _struct_from_result(result, ("TRIANGLEPOINT", "TRIANGLE_POINT"))
    if point_struct is None:
        return None
    valid = _property(point_struct, ("valid", "b_valid"))
    if valid is False:
        return None
    return _property(point_struct, ("position",))


def select_components_v3(world, actors, spline, helpers):
    corridor = base["corridor_bounds"](spline)
    selected = {}
    scanned = 0
    section_counts = {}
    mode_counts = {}

    for section in helpers["collect_section_actors"](world, actors):
        section_name = helpers["actor_label"](section)
        section_counts.setdefault(section_name, 0)
        for component in helpers["get_components"](section):
            mesh = helpers["safe_static_mesh"](component)
            if not mesh:
                continue
            scanned += 1

            matched = None
            for mode, bounds in wrapper["_candidate_bounds"](component, mesh):
                if base["overlaps"](bounds, corridor):
                    matched = (mode, bounds)
                    break
            if matched is None:
                continue

            mode, bounds = matched
            if mode == "COMPONENT_LOCATION_TRANSLATION":
                query_offset = _vector_or_zero(wrapper["_component_location"](component))
                transform_to_world = False
            elif mode == "OWNER_LOCATION_TRANSLATION":
                query_offset = _vector_or_zero(wrapper["_owner_location"](component))
                transform_to_world = False
            elif mode == "RAW_PARTITION_SPACE":
                query_offset = _zero_vector()
                transform_to_world = False
            else:
                query_offset = _zero_vector()
                transform_to_world = True

            transform = base["component_transform"](component)
            mesh_path = mesh.get_path_name()
            name = component.get_name().lower()
            class_name = helpers["class_path"](component).lower()
            rank = 0 if "staticmeshpreviewcomponent" in class_name else (1 if "virtualtexturefallback" in name else 2)
            key = (
                mesh_path,
                str(transform),
                tuple(round(float(value), 2) for value in bounds),
                mode,
            )
            old = selected.get(key)
            entry = (rank, component, mesh, bounds, mode, query_offset, transform_to_world)
            if old is None or rank < old[0]:
                selected[key] = entry
                section_counts[section_name] += 1

    result = sorted(selected.values(), key=lambda entry: (entry[0], entry[2].get_path_name()))
    for entry in result:
        mode_counts[entry[4]] = mode_counts.get(entry[4], 0) + 1

    base["log"](f"Section mesh components scanned={scanned}")
    base["log"](f"River corridor preview components selected={len(result)}")
    base["log"](f"River corridor XY bounds={corridor}")
    for section_name, count in sorted(section_counts.items()):
        base["log"](f"  section candidate matches {section_name}={count}")
    for mode, count in sorted(mode_counts.items()):
        base["log"](f"  bounds/query interpretation {mode}={count}")

    if not result or len(result) > 512:
        raise RuntimeError(f"Invalid V3 preview component count for river corridor: {len(result)}")
    return result


def build_surfaces_v3(candidates, helpers):
    dynamic_mesh_class = getattr(unreal, "DynamicMesh", None)
    scene_utils = getattr(unreal, "GeometryScript_SceneUtils", None)
    copy_options_class = getattr(unreal, "GeometryScriptCopyMeshFromComponentOptions", None)
    spatial = getattr(unreal, "GeometryScript_MeshSpatial", None)
    query_options_class = getattr(unreal, "GeometryScriptSpatialQueryOptions", None)
    if not all((dynamic_mesh_class, scene_utils, copy_options_class, spatial, query_options_class)):
        raise RuntimeError("Geometry Script preview-query API is unavailable")

    copy_options = copy_options_class()
    try:
        copy_options.set_editor_property("want_normals", True)
    except Exception:
        pass

    surfaces = []
    failures = []
    mode_copies = {}
    for _, component, mesh, bounds, mode, query_offset, transform_to_world in candidates:
        try:
            dynamic_mesh = dynamic_mesh_class()
            copy_result = scene_utils.copy_mesh_from_component(
                component,
                dynamic_mesh,
                copy_options,
                transform_to_world,
            )
            outcome = base["extract_outcome"](copy_result)
            if outcome is not None and not base["success"](outcome):
                raise RuntimeError(f"copy outcome={outcome}")
            bvh = helpers["extract_bvh"](spatial.build_bvh_for_mesh(dynamic_mesh))
            if bvh is None:
                raise RuntimeError("BVH was None")
            surfaces.append(
                (
                    component,
                    bounds,
                    dynamic_mesh,
                    bvh,
                    query_options_class(),
                    mode,
                    query_offset,
                )
            )
            mode_copies[mode] = mode_copies.get(mode, 0) + 1
        except Exception as exc:
            failures.append(f"{component.get_name()}: {type(exc).__name__}: {exc}")

    base["log"](f"Preview Dynamic Mesh copies={len(surfaces)}")
    base["log"](f"Preview Dynamic Mesh copy failures={len(failures)}")
    for mode, count in sorted(mode_copies.items()):
        base["log"](f"  Dynamic Mesh coordinate mode {mode}={count}")
    for failure in failures[:10]:
        base["log"](f"  copy failure={failure}")
    if not surfaces:
        raise RuntimeError("No preview component copied successfully")
    return surfaces, spatial


def surface_down_v3(surfaces, spatial, x, y, z):
    world_origin = unreal.Vector(x, y, z + base["RAY_LIFT"])
    world_reference = unreal.Vector(x, y, z)
    direction = unreal.Vector(0.0, 0.0, -1.0)
    best = None

    for component, bounds, dynamic_mesh, bvh, options, mode, query_offset in surfaces:
        if x < bounds[0] - 100.0 or x > bounds[1] + 100.0 or y < bounds[2] - 100.0 or y > bounds[3] + 100.0:
            continue
        query_origin = _subtract(world_origin, query_offset)
        try:
            result = spatial.find_nearest_ray_intersection_with_mesh(
                dynamic_mesh,
                bvh,
                query_origin,
                direction,
                options,
            )
        except Exception:
            continue
        parsed = _ray_hit(result)
        if parsed is None:
            continue
        local_point, distance = parsed
        if distance > base["RAY_MAX"]:
            continue
        world_point = _add(local_point, query_offset)
        if best is None or distance < best[0]:
            best = (distance, world_point, component)

    if best is not None:
        QUERY_STATS["ray_hits"] += 1
        return best

    # Defensive fallback: the earlier audit proved nearest-point queries work on
    # these preview meshes. Only accept a result very close in XY so a steep
    # cliff face cannot be mistaken for the terrain directly under the object.
    nearest_best = None
    for component, bounds, dynamic_mesh, bvh, options, mode, query_offset in surfaces:
        if x < bounds[0] - 350.0 or x > bounds[1] + 350.0 or y < bounds[2] - 350.0 or y > bounds[3] + 350.0:
            continue
        query_point = _subtract(world_reference, query_offset)
        try:
            result = spatial.find_nearest_point_on_mesh(dynamic_mesh, bvh, query_point, options)
        except Exception:
            continue
        local_point = _nearest_point(result)
        if local_point is None:
            continue
        world_point = _add(local_point, query_offset)
        horizontal = math.hypot(float(world_point.x) - x, float(world_point.y) - y)
        vertical = abs(float(world_point.z) - z)
        if horizontal > 350.0 or vertical > 12000.0:
            continue
        score = horizontal + vertical * 0.02
        if nearest_best is None or score < nearest_best[0]:
            nearest_best = (score, world_point, component)

    if nearest_best is not None:
        QUERY_STATS["nearest_fallback_hits"] += 1
        return nearest_best

    QUERY_STATS["misses"] += 1
    return None


original_place_instances = base["place_instances"]


def place_instances_v3(*args, **kwargs):
    result = original_place_instances(*args, **kwargs)
    base["log"](f"Preview ray-intersection hits={QUERY_STATS['ray_hits']}")
    base["log"](f"Preview nearest-point fallback hits={QUERY_STATS['nearest_fallback_hits']}")
    base["log"](f"Preview exact-query misses={QUERY_STATS['misses']}")
    return result


base["select_components"] = select_components_v3
base["build_surfaces"] = build_surfaces_v3
base["surface_down"] = surface_down_v3
base["place_instances"] = place_instances_v3
base["MAX_COMPONENTS"] = 512

try:
    base["main"]()
except Exception as exc:
    base["log"]("")
    base["log"]("PREVIEW_GROUNDING_RESULT=FAIL")
    base["log"](f"ERROR={type(exc).__name__}: {exc}")
    base["log"]("SAVED_ENVIRONMENT_ACTOR_WAS_NOT_REPLACED=TRUE")
    base["log"]("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    base["report"]()
    unreal.log_error(f"AETHER_PREVIEW_GROUNDING_V3_FAILED={type(exc).__name__}: {exc}")
    raise
