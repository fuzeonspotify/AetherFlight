"""Read-only UE 5.8 audit for Mesh Terrain surface sampling and local build APIs.

Run from the normal Unreal Editor with AetherWorld and the river region loaded.
This script does not spawn or destroy actors, modify properties, save packages,
or start any Mesh Partition build.
"""

from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
SOURCE_SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherMeshTerrainSurfaceQueryAudit.txt"

KEYWORDS = (
    "build",
    "compile",
    "section",
    "region",
    "tile",
    "partition",
    "collision",
    "mesh",
    "surface",
    "ray",
    "trace",
    "closest",
    "nearest",
    "sample",
    "height",
    "bounds",
    "query",
)

LINES = []


def record(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def relevant_names(obj, limit=120):
    found = []
    try:
        names = dir(obj)
    except Exception:
        return found
    for name in names:
        lower = str(name).lower()
        if any(keyword in lower for keyword in KEYWORDS):
            found.append(str(name))
    return sorted(set(found))[:limit]


def load_world():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def get_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return subsystem, list(subsystem.get_all_level_actors())


def find_actor(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    return matches[0] if len(matches) == 1 else None


def actor_tags(actor):
    try:
        return [str(tag) for tag in actor.get_editor_property("tags")]
    except Exception:
        return []


def find_mesh_partition(actors):
    preferred = []
    fallback = []
    for actor in actors:
        combined = f"{actor.get_name()} {class_path(actor)}"
        if "MeshPartition" not in combined and "MeshTerrain" not in combined and "MegaMesh" not in combined:
            continue
        fallback.append(actor)
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in actor_tags(actor):
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def safe_components(actor):
    actor_component_class = getattr(unreal, "ActorComponent", None)
    if actor_component_class:
        try:
            return list(actor.get_components_by_class(actor_component_class))
        except Exception:
            pass
    components = []
    for class_name in ("SceneComponent", "PrimitiveComponent"):
        component_class = getattr(unreal, class_name, None)
        if not component_class:
            continue
        try:
            for component in actor.get_components_by_class(component_class):
                if component not in components:
                    components.append(component)
        except Exception:
            pass
    return components


def make_samples(source_spline):
    length = float(source_spline.get_spline_length())
    world_space = unreal.SplineCoordinateSpace.WORLD
    samples = []
    for fraction in (0.20, 0.50, 0.80):
        distance = length * fraction
        center = source_spline.get_location_at_distance_along_spline(distance, world_space)
        right = source_spline.get_right_vector_at_distance_along_spline(distance, world_space)
        for side in (-1.0, 1.0):
            samples.append(
                unreal.Vector(
                    float(center.x) + float(right.x) * side * 2400.0,
                    float(center.y) + float(right.y) * side * 2400.0,
                    float(center.z) + 8000.0,
                )
            )
    return samples


def extract_trace_hit(result):
    if result is None:
        return None
    if isinstance(result, tuple):
        if result and isinstance(result[0], bool) and not result[0]:
            return None
        for item in reversed(result):
            if item is None or isinstance(item, bool):
                continue
            if hasattr(item, "get_editor_property") or hasattr(item, "impact_point"):
                return item
        return None
    return result


def hit_value(hit, names):
    for name in names:
        try:
            value = getattr(hit, name)
            if value is not None:
                return value
        except Exception:
            pass
        try:
            value = hit.get_editor_property(name)
            if value is not None:
                return value
        except Exception:
            pass
    return None


def audit_line_traces(world, samples):
    record("")
    record("TRACE MATRIX")
    record("-" * 96)
    trace_hits = 0
    trace_type = getattr(unreal.TraceTypeQuery, "ECC_VISIBILITY", None)
    if trace_type is None:
        trace_type = getattr(unreal.TraceTypeQuery, "TRACE_TYPE_QUERY1", None)

    for index, sample in enumerate(samples):
        start = sample
        end = unreal.Vector(float(sample.x), float(sample.y), float(sample.z) - 18000.0)
        results = []
        if trace_type is not None:
            try:
                results.append(
                    (
                        "visibility",
                        unreal.SystemLibrary.line_trace_single(
                            world,
                            start,
                            end,
                            trace_type,
                            False,
                            [],
                            unreal.DrawDebugTrace.NONE,
                            True,
                        ),
                    )
                )
            except Exception as exc:
                record(f"sample {index} visibility trace error={type(exc).__name__}: {exc}")
        for profile in ("BlockAll", "BlockAllDynamic"):
            method = getattr(unreal.SystemLibrary, "line_trace_single_by_profile", None)
            if not callable(method):
                continue
            try:
                results.append(
                    (
                        f"profile:{profile}",
                        method(
                            world,
                            start,
                            end,
                            profile,
                            False,
                            [],
                            unreal.DrawDebugTrace.NONE,
                            True,
                        ),
                    )
                )
            except Exception as exc:
                record(f"sample {index} {profile} trace error={type(exc).__name__}: {exc}")

        for mode, result in results:
            hit = extract_trace_hit(result)
            if not hit:
                record(f"sample {index} {mode}=MISS")
                continue
            trace_hits += 1
            hit_actor = hit_value(hit, ("hit_actor", "actor"))
            hit_component = hit_value(hit, ("hit_component", "component"))
            point = hit_value(hit, ("impact_point", "location"))
            record(
                f"sample {index} {mode}=HIT actor={actor_label(hit_actor) if hit_actor else None} "
                f"component={class_path(hit_component) if hit_component else None} point={point}"
            )
    return trace_hits


def audit_component(component, samples, index):
    record("")
    record(f"COMPONENT {index}")
    record("-" * 96)
    record(f"name={component.get_name()}")
    record(f"class={class_path(component)}")

    collision_enabled = None
    method = getattr(component, "get_collision_enabled", None)
    if callable(method):
        try:
            collision_enabled = method()
        except Exception as exc:
            collision_enabled = f"ERROR {type(exc).__name__}: {exc}"
    record(f"collision_enabled={collision_enabled}")

    for property_name in (
        "component_bounds",
        "bounds_scale",
        "visible",
        "hidden_in_game",
        "mobility",
        "body_instance",
        "static_mesh",
    ):
        try:
            record(f"property {property_name}={component.get_editor_property(property_name)}")
        except Exception:
            pass

    names = relevant_names(component)
    record(f"relevant API={','.join(names)}")

    closest_successes = 0
    closest_method = getattr(component, "get_closest_point_on_collision", None)
    if callable(closest_method):
        for sample_index, sample in enumerate(samples[:3]):
            try:
                result = closest_method(sample)
                record(f"closest sample {sample_index} result={result}")
                if result is not None:
                    if isinstance(result, tuple):
                        numeric = [item for item in result if isinstance(item, (int, float))]
                        if any(float(item) >= 0.0 for item in numeric):
                            closest_successes += 1
                    else:
                        closest_successes += 1
            except Exception as exc:
                record(f"closest sample {sample_index} error={type(exc).__name__}: {exc}")

    dynamic_mesh = None
    dynamic_method = getattr(component, "get_dynamic_mesh", None)
    if callable(dynamic_method):
        try:
            dynamic_mesh = dynamic_method()
            record(f"dynamic_mesh={dynamic_mesh}")
            if dynamic_mesh:
                record(f"dynamic_mesh_class={class_path(dynamic_mesh)}")
                record(f"dynamic_mesh_relevant API={','.join(relevant_names(dynamic_mesh))}")
        except Exception as exc:
            record(f"get_dynamic_mesh error={type(exc).__name__}: {exc}")

    return closest_successes, bool(dynamic_mesh)


def audit_unreal_types():
    record("")
    record("MESH TERRAIN / GEOMETRY QUERY TYPES")
    record("-" * 96)
    class_count = 0
    local_build_candidates = 0
    geometry_query_candidates = 0

    for type_name in sorted(dir(unreal)):
        lower = type_name.lower()
        if not any(token in lower for token in ("meshpartition", "meshterrain", "megamesh", "geometryscript", "dynamicmesh")):
            continue
        obj = getattr(unreal, type_name, None)
        names = relevant_names(obj, 160)
        if not names:
            continue
        class_count += 1
        build_names = [name for name in names if any(token in name.lower() for token in ("build", "compile", "section", "region", "tile"))]
        query_names = [name for name in names if any(token in name.lower() for token in ("closest", "nearest", "ray", "trace", "triangle", "surface", "sample", "query"))]
        local_build_candidates += len(build_names)
        geometry_query_candidates += len(query_names)
        record(f"TYPE unreal.{type_name}")
        if build_names:
            record(f"  build API={','.join(build_names)}")
        if query_names:
            record(f"  query API={','.join(query_names)}")
        if not build_names and not query_names:
            record(f"  relevant API={','.join(names)}")

    return class_count, local_build_candidates, geometry_query_candidates


def main():
    record("AETHER UE 5.8 MESH TERRAIN SURFACE QUERY AUDIT")
    record("=" * 96)
    record("Read-only: no actors are spawned or destroyed, no properties are modified, no packages are saved, and no Mesh Partition build is started.")

    world = load_world()
    _, actors = get_actors()
    source_actor = find_actor(actors, SOURCE_SPLINE_LABEL)
    mesh_partition = find_mesh_partition(actors)

    record(f"Map={world.get_path_name() if world else None}")
    record(f"Source spline actor={'YES' if source_actor else 'NO'}")
    record(f"Authoritative Mesh Partition={'YES' if mesh_partition else 'NO'}")

    if not world or not source_actor or not mesh_partition:
        raise RuntimeError("Required AetherWorld, Stage09 spline actor, or Mesh Partition actor is missing")

    spline_class = getattr(unreal, "SplineComponent", None)
    if not spline_class:
        raise RuntimeError("unreal.SplineComponent is unavailable")
    splines = list(source_actor.get_components_by_class(spline_class))
    if len(splines) != 1:
        raise RuntimeError(f"Expected one Stage09 spline component, found {len(splines)}")
    source_spline = splines[0]
    samples = make_samples(source_spline)

    record("")
    record("MESH PARTITION ACTOR")
    record("-" * 96)
    record(f"label={actor_label(mesh_partition)}")
    record(f"name={mesh_partition.get_name()}")
    record(f"class={class_path(mesh_partition)}")
    record(f"location={mesh_partition.get_actor_location()}")
    try:
        record(f"actor_bounds={mesh_partition.get_actor_bounds(False)}")
    except Exception as exc:
        record(f"actor_bounds error={type(exc).__name__}: {exc}")
    actor_api = relevant_names(mesh_partition, 200)
    record(f"relevant actor API={','.join(actor_api)}")
    actor_build_api = [name for name in actor_api if any(token in name.lower() for token in ("build", "compile", "section", "region", "tile"))]
    record(f"actor local-build candidates={','.join(actor_build_api)}")

    components = safe_components(mesh_partition)
    record(f"component_count={len(components)}")

    closest_successes = 0
    dynamic_mesh_components = 0
    collision_components = 0
    for index, component in enumerate(components):
        closest, has_dynamic_mesh = audit_component(component, samples, index)
        closest_successes += closest
        dynamic_mesh_components += int(has_dynamic_mesh)
        method = getattr(component, "get_collision_enabled", None)
        if callable(method):
            try:
                value = method()
                if "NO_COLLISION" not in str(value):
                    collision_components += 1
            except Exception:
                pass

    trace_hits = audit_line_traces(world, samples)
    type_count, local_build_candidates, geometry_query_candidates = audit_unreal_types()

    record("")
    record("SUMMARY")
    record("-" * 96)
    record(f"MESH_PARTITION_COMPONENTS={len(components)}")
    record(f"COLLISION_ENABLED_COMPONENTS={collision_components}")
    record(f"CLOSEST_POINT_SUCCESSES={closest_successes}")
    record(f"LINE_TRACE_HITS={trace_hits}")
    record(f"DYNAMIC_MESH_COMPONENTS={dynamic_mesh_components}")
    record(f"RELEVANT_UNREAL_TYPES={type_count}")
    record(f"LOCAL_BUILD_API_CANDIDATES={len(actor_build_api) + local_build_candidates}")
    record(f"GEOMETRY_QUERY_API_CANDIDATES={geometry_query_candidates}")

    if closest_successes > 0:
        route = "CLOSEST_POINT_ON_COLLISION"
    elif dynamic_mesh_components > 0 and geometry_query_candidates > 0:
        route = "DYNAMIC_MESH_GEOMETRY_QUERY"
    elif len(actor_build_api) + local_build_candidates > 0:
        route = "LOCAL_COMPILED_SECTION_INVESTIGATION"
    else:
        route = "NO_SAFE_SURFACE_QUERY_EXPOSED"
    record(f"RECOMMENDED_SURFACE_ROUTE={route}")
    record("AUDIT_RESULT=PASS")
    record("NO_ACTORS_SPAWNED_OR_DESTROYED=TRUE")
    record("NO_PACKAGES_SAVED=TRUE")
    record("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    write_report()
    unreal.log_warning(f"AETHER_MESH_TERRAIN_SURFACE_QUERY_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    record("")
    record("AUDIT_RESULT=FAIL")
    record(f"ERROR={type(exc).__name__}: {exc}")
    record("NO_ACTORS_SPAWNED_OR_DESTROYED=TRUE")
    record("NO_PACKAGES_SAVED=TRUE")
    record("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_MESH_TERRAIN_SURFACE_QUERY_AUDIT_FAILED={type(exc).__name__}: {exc}")
    raise
