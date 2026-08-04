"""Stage 14 read-only audit for local Mesh Partition runtime validation.

Run inside the normal Unreal Editor with /Game/Maps/AetherWorld and the river
region loaded. This script only inspects loaded actors, components, Python API
exposure, collision state, and World Partition/streaming interfaces. It never
calls a build/rebuild/compile method, never changes collision, never spawns or
destroys actors, never saves packages, and never starts PIE.
"""

from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
SOURCE_SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
ENVIRONMENT_LABEL = "Aether_VideoStage13_RiverEnvironment"
RIVER_LABEL = "Aether_VideoStage11_River"
WATER_ZONE_LABEL = "Aether_VideoStage11_WaterZone"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14LocalRuntimeAPIAudit.txt"
RIVER_MARGIN_CM = 18000.0

BUILD_KEYWORDS = ("build", "compile", "section", "region", "tile", "bounds", "rebuild")
STREAM_KEYWORDS = ("stream", "load", "unload", "cell", "runtime", "source", "partition")
COLLISION_KEYWORDS = ("collision", "physics", "body", "trace", "overlap", "closest")
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


def object_name(obj):
    try:
        return obj.get_name()
    except Exception:
        return str(obj)


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return object_name(actor)


def safe_property(obj, name):
    try:
        return obj.get_editor_property(name)
    except Exception:
        try:
            return getattr(obj, name)
        except Exception:
            return None


def safe_call(obj, name, *args):
    method = getattr(obj, name, None)
    if not callable(method):
        return None, False
    try:
        return method(*args), True
    except Exception as exc:
        return f"ERROR {type(exc).__name__}: {exc}", True


def method_doc(obj, name):
    method = getattr(obj, name, None)
    if not callable(method):
        return None
    doc = getattr(method, "__doc__", None)
    if not doc:
        return "CALLABLE_NO_DOC"
    compact = " ".join(str(doc).split())
    return compact[:900]


def relevant_methods(obj, keywords, limit=120):
    result = []
    try:
        names = dir(obj)
    except Exception:
        return result
    for name in names:
        lower = name.lower()
        if name.startswith("_") or not any(token in lower for token in keywords):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value):
            result.append(name)
    return sorted(set(result))[:limit]


def load_world():
    world = None
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if subsystem_class:
        try:
            world = unreal.get_editor_subsystem(subsystem_class).get_editor_world()
        except Exception:
            world = None
    if not world:
        try:
            world = unreal.EditorLevelLibrary.get_editor_world()
        except Exception:
            world = None
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


def get_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return list(subsystem.get_all_level_actors())


def find_actor(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    return matches[0] if len(matches) == 1 else None


def get_components(actor):
    actor_component = getattr(unreal, "ActorComponent", None)
    if actor_component:
        try:
            return list(actor.get_components_by_class(actor_component))
        except Exception:
            pass
    result = []
    for class_name in ("SceneComponent", "PrimitiveComponent", "StaticMeshComponent"):
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


def safe_static_mesh(component):
    value, exposed = safe_call(component, "get_static_mesh")
    if exposed and value and not isinstance(value, str):
        return value
    value = safe_property(component, "static_mesh")
    return value


def raw_mesh_bounds(mesh):
    try:
        bounds = mesh.get_bounds()
        return (
            float(bounds.origin.x) - float(bounds.box_extent.x),
            float(bounds.origin.x) + float(bounds.box_extent.x),
            float(bounds.origin.y) - float(bounds.box_extent.y),
            float(bounds.origin.y) + float(bounds.box_extent.y),
            float(bounds.origin.z) - float(bounds.box_extent.z),
            float(bounds.origin.z) + float(bounds.box_extent.z),
        )
    except Exception:
        return None


def actor_bounds(actor):
    try:
        origin, extent = actor.get_actor_bounds(False)
        return (
            float(origin.x) - float(extent.x),
            float(origin.x) + float(extent.x),
            float(origin.y) - float(extent.y),
            float(origin.y) + float(extent.y),
            float(origin.z) - float(extent.z),
            float(origin.z) + float(extent.z),
        )
    except Exception:
        return None


def overlaps_xy(bounds, corridor):
    if not bounds:
        return False
    return not (
        bounds[1] < corridor[0]
        or bounds[0] > corridor[1]
        or bounds[3] < corridor[2]
        or bounds[2] > corridor[3]
    )


def corridor_bounds(spline):
    length = float(spline.get_spline_length())
    space = unreal.SplineCoordinateSpace.WORLD
    samples = []
    sample_count = 25
    for index in range(sample_count):
        distance = length * (index / float(sample_count - 1))
        samples.append(spline.get_location_at_distance_along_spline(distance, space))
    return (
        min(float(point.x) for point in samples) - RIVER_MARGIN_CM,
        max(float(point.x) for point in samples) + RIVER_MARGIN_CM,
        min(float(point.y) for point in samples) - RIVER_MARGIN_CM,
        max(float(point.y) for point in samples) + RIVER_MARGIN_CM,
        min(float(point.z) for point in samples) - 30000.0,
        max(float(point.z) for point in samples) + 30000.0,
    )


def actor_intersects_corridor(actor, corridor):
    if overlaps_xy(actor_bounds(actor), corridor):
        return True, "ACTOR_BOUNDS"
    for component in get_components(actor):
        mesh = safe_static_mesh(component)
        bounds = raw_mesh_bounds(mesh) if mesh else None
        if overlaps_xy(bounds, corridor):
            return True, "RAW_STATIC_MESH_BOUNDS"
    return False, "NONE"


def collision_enabled(component):
    value, exposed = safe_call(component, "get_collision_enabled")
    return value if exposed else None


def collision_profile(component):
    value, exposed = safe_call(component, "get_collision_profile_name")
    if exposed:
        return value
    body = safe_property(component, "body_instance")
    return safe_property(body, "collision_profile_name") if body else None


def inspect_method_group(title, obj, keywords):
    names = relevant_methods(obj, keywords)
    record(f"{title}_COUNT={len(names)}")
    for name in names:
        record(f"  {title}_METHOD={name}")
        doc = method_doc(obj, name)
        if doc:
            record(f"    DOC={doc}")
    return names


def find_mesh_partition_actor(actors):
    preferred = []
    fallback = []
    for actor in actors:
        combined = f"{actor_label(actor)} {object_name(actor)} {class_path(actor)}".lower()
        if "meshpartition" not in combined and "meshterrain" not in combined and "megamesh" not in combined:
            continue
        fallback.append(actor)
        if object_name(actor) == "MeshTerrain_AetherWorld" or actor_label(actor) == "MeshTerrain_AetherWorld":
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def collect_section_actors(actors):
    preview = []
    interactive = []
    compiled = []
    for actor in actors:
        combined = f"{actor_label(actor)} {object_name(actor)} {class_path(actor)}".lower()
        if "interactivesection" in combined:
            interactive.append(actor)
        elif "compiledsection" in combined:
            compiled.append(actor)
        elif "previewsection" in combined:
            preview.append(actor)
    return preview, interactive, compiled


def inspect_section_group(title, sections, corridor):
    overlapping = []
    mesh_component_count = 0
    collision_component_count = 0
    enabled_collision_count = 0
    record("")
    record(title)
    record("-" * 96)
    record(f"SECTION_COUNT={len(sections)}")
    for index, section in enumerate(sections):
        intersects, mode = actor_intersects_corridor(section, corridor)
        if intersects:
            overlapping.append(section)
        components = get_components(section)
        section_mesh = 0
        section_collision = 0
        section_enabled = 0
        for component in components:
            cp = class_path(component).lower()
            mesh = safe_static_mesh(component)
            if mesh or "meshcomponent" in cp:
                section_mesh += 1
            if "collisioncomponent" in cp:
                section_collision += 1
            enabled = collision_enabled(component)
            if enabled is not None and "NO_COLLISION" not in str(enabled):
                section_enabled += 1
        mesh_component_count += section_mesh
        collision_component_count += section_collision
        enabled_collision_count += section_enabled
        record(
            f"SECTION_{index}=label:{actor_label(section)} class:{class_path(section)} "
            f"river_overlap:{intersects} overlap_mode:{mode} components:{len(components)} "
            f"mesh_components:{section_mesh} collision_components:{section_collision} "
            f"collision_enabled_components:{section_enabled}"
        )
        for property_name in (
            "build_info",
            "parent",
            "is_placeholder",
            "b_is_placeholder",
            "placeholder_streaming_bounds",
            "mesh_components",
            "collision_components",
        ):
            value = safe_property(section, property_name)
            if value is not None:
                try:
                    value_text = f"count={len(value)}" if not isinstance(value, (str, bytes)) and hasattr(value, "__len__") else str(value)
                except Exception:
                    value_text = str(value)
                record(f"  property {property_name}={value_text}")
        methods = relevant_methods(section, BUILD_KEYWORDS + STREAM_KEYWORDS + COLLISION_KEYWORDS, 60)
        if methods:
            record(f"  relevant_methods={','.join(methods)}")
    return overlapping, mesh_component_count, collision_component_count, enabled_collision_count


def inspect_environment(environment_actor):
    record("")
    record("STAGE 13 ENVIRONMENT COLLISION")
    record("-" * 96)
    if not environment_actor:
        record("ENVIRONMENT_ACTOR_FOUND=FALSE")
        return 0, 0, 0
    record("ENVIRONMENT_ACTOR_FOUND=TRUE")
    hism_class = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    components = list(environment_actor.get_components_by_class(hism_class)) if hism_class else []
    rock_components = []
    rock_enabled = 0
    total_instances = 0
    for index, component in enumerate(components):
        tags = safe_property(component, "component_tags") or []
        tag_text = ",".join(str(tag) for tag in tags)
        count, exposed = safe_call(component, "get_instance_count")
        count = int(count) if exposed and isinstance(count, (int, float)) else 0
        total_instances += count
        enabled = collision_enabled(component)
        profile = collision_profile(component)
        mesh = safe_static_mesh(component)
        mesh_path = mesh.get_path_name() if mesh else None
        is_rock = "AetherRiver_rock" in tag_text or "rock" in tag_text.lower()
        if is_rock:
            rock_components.append(component)
            if enabled is not None and "NO_COLLISION" not in str(enabled):
                rock_enabled += 1
        record(
            f"HISM_{index}=mesh:{mesh_path} tags:{tag_text} instances:{count} "
            f"collision:{enabled} profile:{profile} rock:{is_rock}"
        )
    return len(components), len(rock_components), rock_enabled


def trace_samples(world, spline, ignored):
    record("")
    record("RIVER COLLISION TRACE PROBE")
    record("-" * 96)
    trace_type = getattr(unreal.TraceTypeQuery, "TRACE_TYPE_QUERY1", None)
    if trace_type is None:
        trace_type = getattr(unreal.TraceTypeQuery, "ECC_VISIBILITY", None)
    if trace_type is None:
        record("TRACE_API_AVAILABLE=FALSE")
        return 0, 0
    hits = 0
    useful_hits = 0
    length = float(spline.get_spline_length())
    space = unreal.SplineCoordinateSpace.WORLD
    for index, fraction in enumerate((0.15, 0.35, 0.50, 0.65, 0.85)):
        distance = length * fraction
        center = spline.get_location_at_distance_along_spline(distance, space)
        right = spline.get_right_vector_at_distance_along_spline(distance, space)
        for side in (-1.0, 1.0):
            point = unreal.Vector(
                float(center.x) + float(right.x) * side * 2600.0,
                float(center.y) + float(right.y) * side * 2600.0,
                float(center.z),
            )
            start = unreal.Vector(float(point.x), float(point.y), float(point.z) + 60000.0)
            end = unreal.Vector(float(point.x), float(point.y), float(point.z) - 60000.0)
            try:
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
            except Exception as exc:
                record(f"TRACE_{index}_{side}=ERROR {type(exc).__name__}: {exc}")
                continue
            hit = None
            if isinstance(result, tuple):
                for item in result:
                    if "HITRESULT" in type(item).__name__.upper():
                        hit = item
                        break
            elif result is not None:
                hit = result
            if not hit:
                record(f"TRACE_{index}_{side}=MISS")
                continue
            blocking = safe_property(hit, "blocking_hit")
            actor = safe_property(hit, "hit_actor") or safe_property(hit, "actor")
            component = safe_property(hit, "hit_component") or safe_property(hit, "component")
            point_hit = safe_property(hit, "impact_point") or safe_property(hit, "location")
            if blocking:
                hits += 1
            if blocking and (actor is not None or component is not None):
                useful_hits += 1
            record(
                f"TRACE_{index}_{side}=blocking:{blocking} actor:{actor_label(actor) if actor else None} "
                f"component:{class_path(component) if component else None} point:{point_hit}"
            )
    return hits, useful_hits


def inspect_unreal_types():
    record("")
    record("GLOBAL STAGE 14 API TYPES")
    record("-" * 96)
    type_names = []
    build_candidates = []
    streaming_candidates = []
    collision_candidates = []
    for type_name in sorted(dir(unreal)):
        lower = type_name.lower()
        if not any(token in lower for token in (
            "meshpartition",
            "compiledsection",
            "previewsection",
            "worldpartition",
            "streamingsource",
        )):
            continue
        obj = getattr(unreal, type_name, None)
        build = relevant_methods(obj, BUILD_KEYWORDS, 80)
        stream = relevant_methods(obj, STREAM_KEYWORDS, 80)
        collision = relevant_methods(obj, COLLISION_KEYWORDS, 80)
        if not build and not stream and not collision:
            continue
        type_names.append(type_name)
        record(f"TYPE=unreal.{type_name}")
        if build:
            record(f"  BUILD_METHODS={','.join(build)}")
            build_candidates.extend(f"{type_name}.{name}" for name in build)
        if stream:
            record(f"  STREAM_METHODS={','.join(stream)}")
            streaming_candidates.extend(f"{type_name}.{name}" for name in stream)
        if collision:
            record(f"  COLLISION_METHODS={','.join(collision)}")
            collision_candidates.extend(f"{type_name}.{name}" for name in collision)
    return type_names, build_candidates, streaming_candidates, collision_candidates


def main():
    record("AETHER STAGE 14 - LOCAL RUNTIME / COLLISION API AUDIT")
    record("=" * 96)
    record("READ_ONLY=TRUE")
    record("No build, rebuild, compile, collision mutation, actor mutation, package save, or PIE command is called.")

    world = load_world()
    actors = get_actors()
    source_actor = find_actor(actors, SOURCE_SPLINE_LABEL)
    environment_actor = find_actor(actors, ENVIRONMENT_LABEL)
    river_actor = find_actor(actors, RIVER_LABEL)
    water_zone_actor = find_actor(actors, WATER_ZONE_LABEL)
    mesh_partition = find_mesh_partition_actor(actors)

    if not world or not source_actor or not mesh_partition:
        raise RuntimeError("AetherWorld, the Stage09 spline actor, or the authoritative Mesh Partition actor is missing")

    spline_class = getattr(unreal, "SplineComponent", None)
    splines = list(source_actor.get_components_by_class(spline_class)) if spline_class else []
    if len(splines) != 1:
        raise RuntimeError(f"Expected one Stage09 spline component, found {len(splines)}")
    spline = splines[0]
    corridor = corridor_bounds(spline)

    record(f"WORLD={world.get_path_name()}")
    record(f"LOADED_ACTORS={len(actors)}")
    record(f"RIVER_CORRIDOR_BOUNDS={corridor}")
    record(f"MESH_PARTITION_ACTOR={actor_label(mesh_partition)}")
    record(f"MESH_PARTITION_CLASS={class_path(mesh_partition)}")
    record(f"RIVER_ACTOR_FOUND={bool(river_actor)}")
    record(f"WATER_ZONE_ACTOR_FOUND={bool(water_zone_actor)}")

    record("")
    record("AUTHORITATIVE MESH PARTITION API")
    record("-" * 96)
    actor_build = inspect_method_group("ACTOR_BUILD", mesh_partition, BUILD_KEYWORDS)
    actor_stream = inspect_method_group("ACTOR_STREAM", mesh_partition, STREAM_KEYWORDS)
    actor_collision = inspect_method_group("ACTOR_COLLISION", mesh_partition, COLLISION_KEYWORDS)

    editor_components = []
    all_partition_components = get_components(mesh_partition)
    for component in all_partition_components:
        if "meshpartitioneditorcomponent" in class_path(component).lower():
            editor_components.append(component)
    record(f"MESH_PARTITION_COMPONENTS={len(all_partition_components)}")
    record(f"MESH_PARTITION_EDITOR_COMPONENTS={len(editor_components)}")

    editor_build = []
    editor_stream = []
    editor_collision = []
    bounded_preview_callable = False
    full_rebuild_callable = False
    active_build = None
    preview_build_enabled = None
    preview_visible = None
    for index, component in enumerate(editor_components):
        record("")
        record(f"EDITOR COMPONENT {index}")
        record("-" * 96)
        record(f"name={object_name(component)} class={class_path(component)}")
        build = inspect_method_group(f"EDITOR_{index}_BUILD", component, BUILD_KEYWORDS)
        stream = inspect_method_group(f"EDITOR_{index}_STREAM", component, STREAM_KEYWORDS)
        collision = inspect_method_group(f"EDITOR_{index}_COLLISION", component, COLLISION_KEYWORDS)
        editor_build.extend(build)
        editor_stream.extend(stream)
        editor_collision.extend(collision)
        bounded_preview_callable = bounded_preview_callable or callable(getattr(component, "build_mega_mesh_preview_sections", None))
        full_rebuild_callable = full_rebuild_callable or callable(getattr(component, "force_rebuild_all_sections", None))
        if active_build is None:
            active_build, exposed = safe_call(component, "is_any_preview_section_build_active")
            if not exposed:
                active_build = None
        if preview_build_enabled is None:
            preview_build_enabled, exposed = safe_call(component, "is_preview_section_build_enabled")
            if not exposed:
                preview_build_enabled = None
        if preview_visible is None:
            preview_visible, exposed = safe_call(component, "are_preview_sections_visible")
            if not exposed:
                preview_visible = None

    preview, interactive, compiled = collect_section_actors(actors)
    preview_overlap, preview_mesh, preview_collision, preview_collision_enabled = inspect_section_group(
        "PREVIEW SECTIONS", preview, corridor
    )
    interactive_overlap, interactive_mesh, interactive_collision, interactive_collision_enabled = inspect_section_group(
        "INTERACTIVE SECTIONS", interactive, corridor
    )
    compiled_overlap, compiled_mesh, compiled_collision, compiled_collision_enabled = inspect_section_group(
        "COMPILED SECTIONS", compiled, corridor
    )

    hism_count, rock_hism_count, rock_collision_enabled = inspect_environment(environment_actor)

    ignored = [actor for actor in (source_actor, environment_actor, river_actor, water_zone_actor) if actor]
    trace_hits, useful_trace_hits = trace_samples(world, spline, ignored)

    type_names, global_build, global_stream, global_collision = inspect_unreal_types()

    compiled_build_methods = [
        name for name in actor_build + editor_build + global_build
        if "compiled" in name.lower() and "build" in name.lower()
    ]
    bounded_build_methods = [
        name for name in actor_build + editor_build + global_build
        if "build" in name.lower() and any(token in name.lower() for token in ("bounds", "region", "section"))
    ]

    if compiled_overlap and compiled_collision_enabled > 0:
        route = "VALIDATE_EXISTING_LOCAL_COMPILED_SECTION_IN_PIE"
    elif bounded_preview_callable and useful_trace_hits > 0:
        route = "BOUNDED_PREVIEW_REBUILD_THEN_PIE_PLACEHOLDER_VALIDATION"
    elif compiled_build_methods:
        route = "TARGETED_COMPILED_SECTION_BUILD_API_REQUIRES_GUARDED_INVOCATION_AUDIT"
    elif bounded_preview_callable:
        route = "BOUNDED_PREVIEW_BUILD_EXPOSED_COMPILED_RUNTIME_BUILD_NOT_EXPOSED"
    else:
        route = "EDITOR_UI_OR_WORLDPARTITION_BUILDER_REQUIRED_FOR_LOCAL_RUNTIME_SECTION"

    record("")
    record("SUMMARY")
    record("-" * 96)
    record(f"RIVER_OVERLAPPING_PREVIEW_SECTIONS={len(preview_overlap)}")
    record(f"RIVER_OVERLAPPING_INTERACTIVE_SECTIONS={len(interactive_overlap)}")
    record(f"RIVER_OVERLAPPING_COMPILED_SECTIONS={len(compiled_overlap)}")
    record(f"PREVIEW_MESH_COMPONENTS={preview_mesh}")
    record(f"PREVIEW_COLLISION_COMPONENTS={preview_collision}")
    record(f"PREVIEW_COLLISION_ENABLED_COMPONENTS={preview_collision_enabled}")
    record(f"COMPILED_MESH_COMPONENTS={compiled_mesh}")
    record(f"COMPILED_COLLISION_COMPONENTS={compiled_collision}")
    record(f"COMPILED_COLLISION_ENABLED_COMPONENTS={compiled_collision_enabled}")
    record(f"STAGE13_HISM_COMPONENTS={hism_count}")
    record(f"STAGE13_ROCK_HISM_COMPONENTS={rock_hism_count}")
    record(f"STAGE13_ROCK_COLLISION_ENABLED_COMPONENTS={rock_collision_enabled}")
    record(f"RIVER_TRACE_BLOCKING_HITS={trace_hits}")
    record(f"RIVER_TRACE_USEFUL_COMPONENT_HITS={useful_trace_hits}")
    record(f"PREVIEW_BUILD_ACTIVE={active_build}")
    record(f"PREVIEW_BUILD_ENABLED={preview_build_enabled}")
    record(f"PREVIEW_SECTIONS_VISIBLE={preview_visible}")
    record(f"BOUNDED_PREVIEW_BUILD_CALLABLE={bounded_preview_callable}")
    record(f"FULL_REBUILD_CALLABLE={full_rebuild_callable}")
    record(f"BOUNDED_BUILD_API_CANDIDATES={len(set(bounded_build_methods))}")
    record(f"COMPILED_BUILD_API_CANDIDATES={len(set(compiled_build_methods))}")
    record(f"GLOBAL_STAGE14_API_TYPES={len(type_names)}")
    record(f"GLOBAL_STREAMING_API_CANDIDATES={len(set(global_stream + actor_stream + editor_stream))}")
    record(f"GLOBAL_COLLISION_API_CANDIDATES={len(set(global_collision + actor_collision + editor_collision))}")
    record(f"RECOMMENDED_STAGE14_ROUTE={route}")
    record("AUDIT_RESULT=PASS")
    record("NO_BUILD_METHOD_CALLED=TRUE")
    record("NO_COLLISION_SETTINGS_CHANGED=TRUE")
    record("NO_ACTORS_SPAWNED_OR_DESTROYED=TRUE")
    record("NO_PACKAGES_SAVED=TRUE")
    record("NO_PIE_STARTED=TRUE")
    record("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    write_report()
    unreal.log_warning(f"AETHER_STAGE14_LOCAL_RUNTIME_API_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    record("")
    record("AUDIT_RESULT=FAIL")
    record(f"ERROR={type(exc).__name__}: {exc}")
    record("NO_BUILD_METHOD_CALLED=TRUE")
    record("NO_COLLISION_SETTINGS_CHANGED=TRUE")
    record("NO_ACTORS_SPAWNED_OR_DESTROYED=TRUE")
    record("NO_PACKAGES_SAVED=TRUE")
    record("NO_PIE_STARTED=TRUE")
    record("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE14_LOCAL_RUNTIME_API_AUDIT_FAILED={type(exc).__name__}: {exc}")
    raise
