"""Read-only UE 5.8 audit for exact Mesh Terrain preview-section surface queries.

Run from the normal Unreal Editor with AetherWorld and the river region loaded.
The audit enumerates transient Mesh Partition preview sections, inspects their
mesh/collision components, and attempts in-memory Geometry Script copies and
nearest-surface queries. It does not spawn or destroy actors, change properties,
save packages, or start any Mesh Partition build.
"""

from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
SOURCE_SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherMeshTerrainPreviewSectionAudit.txt"
MAX_COMPONENT_COPY_ATTEMPTS = 32

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


def get_all_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return list(subsystem.get_all_level_actors())


def find_actor(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    return matches[0] if len(matches) == 1 else None


def add_unique_actor(result, seen, actor):
    if not actor:
        return
    try:
        key = actor.get_path_name()
    except Exception:
        key = str(actor)
    if key in seen:
        return
    seen.add(key)
    result.append(actor)


def collect_section_actors(world, actors):
    sections = []
    seen = set()

    for actor in actors:
        combined = f"{class_path(actor)} {actor.get_name()} {actor_label(actor)}".lower()
        if any(token in combined for token in ("previewsection", "interactivesection", "compiledsection")):
            add_unique_actor(sections, seen, actor)

    gameplay = getattr(unreal, "GameplayStatics", None)
    if gameplay:
        for class_name in ("PreviewSection", "InteractiveSection", "CompiledSection"):
            actor_class = getattr(unreal, class_name, None)
            if not actor_class:
                continue
            try:
                for actor in gameplay.get_all_actors_of_class(world, actor_class):
                    add_unique_actor(sections, seen, actor)
            except Exception:
                pass

    editor_component_class = getattr(unreal, "MeshPartitionEditorComponent", None)
    if editor_component_class:
        for actor in actors:
            try:
                components = list(actor.get_components_by_class(editor_component_class))
            except Exception:
                components = []
            for component in components:
                for property_name in (
                    "interactive_preview_sections",
                    "preview_sections",
                    "compiled_sections",
                ):
                    try:
                        values = list(component.get_editor_property(property_name))
                    except Exception:
                        continue
                    for value in values:
                        add_unique_actor(sections, seen, value)
    return sections


def get_components(actor):
    actor_component = getattr(unreal, "ActorComponent", None)
    if actor_component:
        try:
            return list(actor.get_components_by_class(actor_component))
        except Exception:
            pass
    result = []
    for class_name in ("SceneComponent", "PrimitiveComponent", "StaticMeshComponent"):
        component_class = getattr(unreal, class_name, None)
        if not component_class:
            continue
        try:
            for component in actor.get_components_by_class(component_class):
                if component not in result:
                    result.append(component)
        except Exception:
            pass
    return result


def make_samples(source_spline):
    length = float(source_spline.get_spline_length())
    world_space = unreal.SplineCoordinateSpace.WORLD
    samples = []
    for fraction in (0.10, 0.25, 0.50, 0.75, 0.90):
        distance = length * fraction
        center = source_spline.get_location_at_distance_along_spline(distance, world_space)
        right = source_spline.get_right_vector_at_distance_along_spline(distance, world_space)
        for side in (-1.0, 1.0):
            samples.append(
                unreal.Vector(
                    float(center.x) + float(right.x) * side * 2400.0,
                    float(center.y) + float(right.y) * side * 2400.0,
                    float(center.z) + 6000.0,
                )
            )
    return samples


def safe_actor_bounds(actor):
    try:
        return actor.get_actor_bounds(False)
    except Exception:
        return None


def safe_component_bounds(component):
    for property_name in ("bounds", "component_bounds"):
        try:
            return component.get_editor_property(property_name)
        except Exception:
            pass
    try:
        return component.bounds
    except Exception:
        return None


def safe_static_mesh(component):
    method = getattr(component, "get_static_mesh", None)
    if callable(method):
        try:
            value = method()
            if value:
                return value
        except Exception:
            pass
    try:
        return component.get_editor_property("static_mesh")
    except Exception:
        return None


def outcome_is_success(value):
    text = str(value).upper()
    return "SUCCESS" in text and "FAIL" not in text


def extract_bvh(result):
    if isinstance(result, tuple):
        for item in reversed(result):
            if "BVH" in type(item).__name__.upper() or "BVH" in str(type(item)).upper():
                return item
        return result[-1] if result else None
    return result


def try_copy_and_query(component, samples, lines):
    dynamic_mesh_class = getattr(unreal, "DynamicMesh", None)
    scene_utils = getattr(unreal, "GeometryScript_SceneUtils", None)
    options_class = getattr(unreal, "GeometryScriptCopyMeshFromComponentOptions", None)
    mesh_queries = getattr(unreal, "GeometryScript_MeshQueries", None)
    spatial = getattr(unreal, "GeometryScript_MeshSpatial", None)
    spatial_options_class = getattr(unreal, "GeometryScriptSpatialQueryOptions", None)

    if not all((dynamic_mesh_class, scene_utils, options_class, spatial)):
        return False, False, 0, "Required Geometry Script Python classes are unavailable"

    try:
        dynamic_mesh = dynamic_mesh_class()
        options = options_class()
        try:
            options.set_editor_property("want_normals", True)
        except Exception:
            pass
        copy_result = scene_utils.copy_mesh_from_component(component, dynamic_mesh, options, True)
    except Exception as exc:
        return False, False, 0, f"copy error={type(exc).__name__}: {exc}"

    copy_outcome = None
    if isinstance(copy_result, tuple):
        for item in copy_result:
            if "OUTCOME" in type(item).__name__.upper() or "OUTCOME" in str(type(item)).upper():
                copy_outcome = item
    copied = copy_outcome is None or outcome_is_success(copy_outcome)

    info = None
    if mesh_queries:
        method = getattr(mesh_queries, "get_mesh_info_string", None)
        if callable(method):
            try:
                info = method(dynamic_mesh)
            except Exception:
                info = None

    try:
        bvh_result = spatial.build_bvh_for_mesh(dynamic_mesh)
        bvh = extract_bvh(bvh_result)
    except Exception as exc:
        return copied, False, 0, f"mesh_info={info} | BVH error={type(exc).__name__}: {exc}"

    nearest_successes = 0
    query_method = getattr(spatial, "find_nearest_point_on_mesh", None)
    if callable(query_method) and bvh is not None:
        query_options = spatial_options_class() if spatial_options_class else None
        for sample in samples:
            try:
                if query_options is not None:
                    query_result = query_method(dynamic_mesh, bvh, sample, query_options)
                else:
                    query_result = query_method(dynamic_mesh, bvh, sample)
                text = str(query_result).upper()
                if "NOT_FOUND" not in text and "FAIL" not in text:
                    nearest_successes += 1
            except Exception:
                continue

    return copied, bvh is not None, nearest_successes, f"mesh_info={info} | copy_outcome={copy_outcome}"


def main():
    record("AETHER UE 5.8 MESH TERRAIN PREVIEW SECTION SURFACE AUDIT")
    record("=" * 96)
    record("Read-only world audit. No actors are spawned/destroyed, no properties are changed, no packages are saved, and no Mesh Partition build is started.")

    world = load_world()
    actors = get_all_actors()
    source_actor = find_actor(actors, SOURCE_SPLINE_LABEL)
    if not world or not source_actor:
        raise RuntimeError("AetherWorld or the saved Stage09 spline actor could not be resolved")

    spline_class = getattr(unreal, "SplineComponent", None)
    splines = list(source_actor.get_components_by_class(spline_class)) if spline_class else []
    if len(splines) != 1:
        raise RuntimeError(f"Expected one Stage09 spline component, found {len(splines)}")
    samples = make_samples(splines[0])

    sections = collect_section_actors(world, actors)
    preview_count = 0
    interactive_count = 0
    compiled_count = 0
    mesh_components = []
    collision_components = []

    record(f"Map={world.get_path_name()}")
    record(f"Loaded level actors={len(actors)}")
    record(f"Discovered section actors={len(sections)}")

    for index, section in enumerate(sections):
        path = class_path(section)
        lower = path.lower()
        if "interactive" in lower:
            interactive_count += 1
        elif "compiled" in lower:
            compiled_count += 1
        else:
            preview_count += 1

        record("")
        record(f"SECTION {index}")
        record("-" * 96)
        record(f"label={actor_label(section)}")
        record(f"name={section.get_name()}")
        record(f"class={path}")
        record(f"bounds={safe_actor_bounds(section)}")

        components = get_components(section)
        record(f"component_count={len(components)}")
        for component in components:
            component_path = class_path(component)
            component_lower = component_path.lower()
            static_mesh = safe_static_mesh(component)
            collision_enabled = None
            method = getattr(component, "get_collision_enabled", None)
            if callable(method):
                try:
                    collision_enabled = method()
                except Exception:
                    collision_enabled = None
            record(
                f"  component={component.get_name()} class={component_path} "
                f"collision={collision_enabled} bounds={safe_component_bounds(component)} "
                f"static_mesh={static_mesh.get_path_name() if static_mesh else None}"
            )
            if static_mesh or "staticmeshcomponent" in component_lower or "previewmeshcomponent" in component_lower:
                mesh_components.append(component)
            if "collisioncomponent" in component_lower:
                collision_components.append(component)

    copy_attempts = 0
    copy_successes = 0
    bvh_successes = 0
    nearest_successes = 0

    record("")
    record("GEOMETRY SCRIPT PREVIEW-MESH QUERIES")
    record("-" * 96)
    for component in mesh_components[:MAX_COMPONENT_COPY_ATTEMPTS]:
        copy_attempts += 1
        copied, bvh_ok, nearest_count, detail = try_copy_and_query(component, samples, LINES)
        copy_successes += int(bool(copied))
        bvh_successes += int(bool(bvh_ok))
        nearest_successes += int(nearest_count)
        record(
            f"component={component.get_name()} class={class_path(component)} "
            f"copy={copied} bvh={bvh_ok} nearest_successes={nearest_count} | {detail}"
        )

    if copy_successes > 0 and nearest_successes > 0:
        route = "PREVIEW_SECTION_DYNAMIC_MESH_QUERY"
    elif sections and mesh_components:
        route = "PREVIEW_SECTION_COMPONENT_API_REPAIR"
    elif not sections:
        route = "REBUILD_OR_LOAD_PREVIEW_SECTIONS"
    else:
        route = "LOCAL_COMPILED_SECTION_REQUIRED"

    record("")
    record("SUMMARY")
    record("-" * 96)
    record(f"PREVIEW_SECTION_ACTORS={preview_count}")
    record(f"INTERACTIVE_SECTION_ACTORS={interactive_count}")
    record(f"COMPILED_SECTION_ACTORS={compiled_count}")
    record(f"SECTION_MESH_COMPONENTS={len(mesh_components)}")
    record(f"SECTION_COLLISION_COMPONENTS={len(collision_components)}")
    record(f"GEOMETRY_SCRIPT_COPY_ATTEMPTS={copy_attempts}")
    record(f"GEOMETRY_SCRIPT_COPY_SUCCESSES={copy_successes}")
    record(f"BVH_BUILD_SUCCESSES={bvh_successes}")
    record(f"NEAREST_POINT_QUERY_SUCCESSES={nearest_successes}")
    record(f"RECOMMENDED_SURFACE_ROUTE={route}")
    record("TRANSIENT_DYNAMIC_MESH_OBJECTS_ONLY=TRUE")
    record("AUDIT_RESULT=PASS")
    record("NO_ACTORS_SPAWNED_OR_DESTROYED=TRUE")
    record("NO_PACKAGES_SAVED=TRUE")
    record("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_warning(f"AETHER_MESH_TERRAIN_PREVIEW_SECTION_REPORT={REPORT_PATH}")


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
    unreal.log_error(f"AETHER_PREVIEW_SECTION_AUDIT_FAILED={type(exc).__name__}: {exc}")
    raise
