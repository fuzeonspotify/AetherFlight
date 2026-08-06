"""Read-only probe for the exact UE 5.8 Geometry Script return values and coordinates.

This script does not spawn/destroy actors, modify the map, save packages, or
start a Mesh Partition build. It inspects one river-overlapping preview tile in
both raw and world-copy modes and records exact Dynamic Mesh bounds and query
results.
"""

from pathlib import Path
import sys
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherRiverGroundingQueryDiagnostic.txt"
MAP_PATH = "/Game/Maps/AetherWorld"
SOURCE_LABEL = "Aether_VideoStage09_SplineChannel"
LINES = []


def log(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def save_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


def load_helpers():
    audit_path = SCRIPT_DIR / "AuditAetherMeshTerrainPreviewSections_UE58.py"
    source = audit_path.read_text(encoding="utf-8")
    marker = "\ntry:\n    main()"
    if marker not in source:
        raise RuntimeError("Preview-section audit helper marker missing")
    ns = {"__file__": str(audit_path), "__name__": "AetherPreviewDiagnosticHelpers"}
    exec(compile(source.split(marker, 1)[0], str(audit_path), "exec"), ns, ns)
    return ns


def get_world_and_actors():
    editor_subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    world = None
    if editor_subsystem_class:
        try:
            world = unreal.get_editor_subsystem(editor_subsystem_class).get_editor_world()
        except Exception:
            pass
    if not world:
        world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        world = unreal.EditorLevelLibrary.get_editor_world()
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return world, list(actor_subsystem.get_all_level_actors())


def raw_bounds(mesh):
    bounds = mesh.get_bounds()
    return (
        float(bounds.origin.x) - float(bounds.box_extent.x),
        float(bounds.origin.x) + float(bounds.box_extent.x),
        float(bounds.origin.y) - float(bounds.box_extent.y),
        float(bounds.origin.y) + float(bounds.box_extent.y),
        float(bounds.origin.z) - float(bounds.box_extent.z),
        float(bounds.origin.z) + float(bounds.box_extent.z),
    )


def component_transform(component):
    method = getattr(component, "get_component_transform", None)
    if callable(method):
        try:
            return method()
        except Exception:
            pass
    return component.get_editor_property("component_to_world")


def transform_bounds(component, mesh):
    bounds = mesh.get_bounds()
    transform = component_transform(component)
    points = []
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                local = unreal.Vector(
                    float(bounds.origin.x) + sx * float(bounds.box_extent.x),
                    float(bounds.origin.y) + sy * float(bounds.box_extent.y),
                    float(bounds.origin.z) + sz * float(bounds.box_extent.z),
                )
                points.append(unreal.MathLibrary.transform_location(transform, local))
    return (
        min(float(p.x) for p in points), max(float(p.x) for p in points),
        min(float(p.y) for p in points), max(float(p.y) for p in points),
        min(float(p.z) for p in points), max(float(p.z) for p in points),
    )


def overlaps_xy(bounds, corridor):
    return not (
        bounds[1] < corridor[0] or bounds[0] > corridor[1] or
        bounds[3] < corridor[2] or bounds[2] > corridor[3]
    )


def corridor_bounds(spline):
    length = float(spline.get_spline_length())
    space = unreal.SplineCoordinateSpace.WORLD
    points = [spline.get_location_at_distance_along_spline(length * fraction, space) for fraction in (0.05, 0.25, 0.5, 0.75, 0.95)]
    margin = 12000.0
    return (
        min(float(point.x) for point in points) - margin,
        max(float(point.x) for point in points) + margin,
        min(float(point.y) for point in points) - margin,
        max(float(point.y) for point in points) + margin,
    )


def describe_result(prefix, result):
    log(f"{prefix}_RESULT_REPR={result}")
    items = result if isinstance(result, tuple) else (result,)
    log(f"{prefix}_TUPLE_LENGTH={len(items)}")
    for index, item in enumerate(items):
        log(f"{prefix}_ITEM_{index}_TYPE={type(item).__name__}")
        log(f"{prefix}_ITEM_{index}_REPR={item}")
        names = []
        try:
            names = [name for name in dir(item) if any(token in name.lower() for token in ("valid", "hit", "position", "point", "ray", "distance", "triangle", "outcome", "found"))]
        except Exception:
            pass
        log(f"{prefix}_ITEM_{index}_RELEVANT_NAMES={','.join(sorted(set(names)))}")
        for name in sorted(set(names)):
            value = None
            ok = False
            try:
                value = item.get_editor_property(name)
                ok = True
            except Exception:
                try:
                    value = getattr(item, name)
                    ok = True
                except Exception:
                    pass
            if ok:
                log(f"{prefix}_ITEM_{index}_{name}={value}")


def dynamic_bounds(mesh_queries, dynamic_mesh):
    method = getattr(mesh_queries, "get_mesh_bounding_box", None)
    if not callable(method):
        return "UNAVAILABLE"
    try:
        return method(dynamic_mesh)
    except Exception as exc:
        return f"ERROR {type(exc).__name__}: {exc}"


def main():
    log("AETHER RIVER GROUNDING QUERY DIAGNOSTIC")
    log("=" * 96)
    log("Read-only: no actors are spawned/destroyed, no map properties are changed, no packages are saved, and no Mesh Partition build is started.")

    helpers = load_helpers()
    world, actors = get_world_and_actors()
    source_actor = next((actor for actor in actors if actor_label(actor) == SOURCE_LABEL), None)
    if not source_actor:
        raise RuntimeError("Stage09 source spline actor was not found")
    spline_class = getattr(unreal, "SplineComponent", None)
    splines = list(source_actor.get_components_by_class(spline_class))
    if len(splines) != 1:
        raise RuntimeError(f"Expected one source spline, found {len(splines)}")
    spline = splines[0]
    corridor = corridor_bounds(spline)

    selected = []
    scanned = 0
    for section in helpers["collect_section_actors"](world, actors):
        for component in helpers["get_components"](section):
            mesh = helpers["safe_static_mesh"](component)
            if not mesh:
                continue
            scanned += 1
            raw = raw_bounds(mesh)
            if overlaps_xy(raw, corridor):
                selected.append((component, mesh, raw, transform_bounds(component, mesh)))

    log(f"WORLD={world.get_path_name()}")
    log(f"COMPONENTS_SCANNED={scanned}")
    log(f"RAW_XY_RIVER_MATCHES={len(selected)}")
    log(f"CORRIDOR_XY={corridor}")
    if not selected:
        raise RuntimeError("No raw-space river component was found")

    component, mesh, raw, transformed = selected[0]
    transform = component_transform(component)
    log(f"TEST_COMPONENT={component.get_name()}")
    log(f"TEST_COMPONENT_CLASS={class_path(component)}")
    log(f"TEST_MESH={mesh.get_path_name()}")
    log(f"STATIC_MESH_RAW_BOUNDS_XYZ={raw}")
    log(f"STATIC_MESH_COMPONENT_TRANSFORMED_BOUNDS_XYZ={transformed}")
    log(f"COMPONENT_TRANSFORM={transform}")
    try:
        log(f"COMPONENT_LOCATION={component.get_world_location()}")
    except Exception:
        pass
    try:
        owner = component.get_owner()
        log(f"OWNER={actor_label(owner) if owner else None}")
        log(f"OWNER_LOCATION={owner.get_actor_location() if owner else None}")
    except Exception:
        pass

    dynamic_mesh_class = getattr(unreal, "DynamicMesh", None)
    scene_utils = getattr(unreal, "GeometryScript_SceneUtils", None)
    copy_options_class = getattr(unreal, "GeometryScriptCopyMeshFromComponentOptions", None)
    spatial = getattr(unreal, "GeometryScript_MeshSpatial", None)
    spatial_options_class = getattr(unreal, "GeometryScriptSpatialQueryOptions", None)
    mesh_queries = getattr(unreal, "GeometryScript_MeshQueries", None)
    if not all((dynamic_mesh_class, scene_utils, copy_options_class, spatial, spatial_options_class, mesh_queries)):
        raise RuntimeError("Required Geometry Script API is unavailable")

    copy_options = copy_options_class()
    try:
        copy_options.set_editor_property("want_normals", True)
    except Exception:
        pass

    length = float(spline.get_spline_length())
    sample_center = spline.get_location_at_distance_along_spline(length * 0.5, unreal.SplineCoordinateSpace.WORLD)
    sample = unreal.Vector((raw[0] + raw[1]) * 0.5, (raw[2] + raw[3]) * 0.5, float(sample_center.z))
    ray_origin = unreal.Vector(float(sample.x), float(sample.y), float(sample.z) + 100000.0)
    ray_direction = unreal.Vector(0.0, 0.0, -1.0)
    log(f"QUERY_SAMPLE={sample}")
    log(f"RAY_ORIGIN={ray_origin}")

    for mode_name, to_world in (("RAW_COPY", False), ("WORLD_COPY", True)):
        dynamic_mesh = dynamic_mesh_class()
        copy_result = scene_utils.copy_mesh_from_component(component, dynamic_mesh, copy_options, to_world)
        log("")
        log(f"{mode_name}_COPY_RESULT={copy_result}")
        log(f"{mode_name}_DYNAMIC_BOUNDS={dynamic_bounds(mesh_queries, dynamic_mesh)}")
        bvh_result = spatial.build_bvh_for_mesh(dynamic_mesh)
        bvh = helpers["extract_bvh"](bvh_result)
        log(f"{mode_name}_BVH_RESULT={bvh_result}")
        log(f"{mode_name}_BVH_OBJECT={bvh}")
        valid_method = getattr(spatial, "is_bvh_valid_for_mesh", None)
        if callable(valid_method):
            try:
                log(f"{mode_name}_BVH_VALID_RESULT={valid_method(dynamic_mesh, bvh)}")
            except Exception as exc:
                log(f"{mode_name}_BVH_VALID_ERROR={type(exc).__name__}: {exc}")

        options = spatial_options_class()
        try:
            log(f"{mode_name}_QUERY_OPTIONS={options}")
            log(f"{mode_name}_QUERY_OPTION_PROPERTIES={','.join(sorted(name for name in dir(options) if not name.startswith('_')))}")
        except Exception:
            pass

        nearest_result = spatial.find_nearest_point_on_mesh(dynamic_mesh, bvh, sample, options)
        ray_result = spatial.find_nearest_ray_intersection_with_mesh(dynamic_mesh, bvh, ray_origin, ray_direction, options)
        describe_result(f"{mode_name}_NEAREST", nearest_result)
        describe_result(f"{mode_name}_RAY", ray_result)

    log("")
    log("DIAGNOSTIC_RESULT=PASS")
    log("NO_ACTORS_SPAWNED_OR_DESTROYED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    save_report()
    unreal.log_warning(f"AETHER_RIVER_GROUNDING_QUERY_DIAGNOSTIC={REPORT_PATH}")


try:
    main()
except Exception as exc:
    log("")
    log("DIAGNOSTIC_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("NO_ACTORS_SPAWNED_OR_DESTROYED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    save_report()
    unreal.log_error(f"AETHER_RIVER_GROUNDING_QUERY_DIAGNOSTIC_FAILED={type(exc).__name__}: {exc}")
    raise
