"""Read-only Stage 15B Mesh Terrain Query prerequisite/context audit.

This audit follows the first useful runtime signal from the bounded river-biome
probe: MegaMeshQuery_0 executed but produced no data on Out.

It inspects, without mutation:
- the saved PCG Query settings and Bounding Shape connectivity;
- the persistent volume and the exact intended temporary-probe bounds;
- loaded Mesh Partition, preview, interactive, and compiled section actors;
- Mesh Partition PCG Adapter modifiers;
- section-level PCGDataComponent caches required by Mesh Terrain PCG sampling;
- preview static-mesh sections overlapping the intended probe bounds.

No graph, actor, component, package, PCG output, Mesh Partition build, or save is
created, modified, generated, cleaned, or started.
"""

from pathlib import Path
from collections import Counter
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BMeshTerrainQueryPrerequisites.txt"
MAP_PREFIX = "/Game/Maps/AetherWorld"
GRAPH_OBJECT_PATH = "/Game/Aether/PCG/Biomes/PCG_Aether_RiverBiome.PCG_Aether_RiverBiome"
PERSISTENT_VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
MESH_PARTITION_LABEL = "MeshTerrain_AetherWorld"

# Exact bounded probe used by RUN_THIS_STAGE15B_START_RIVER_BIOME_PROBE_V4.py.
PROBE_CENTER = (-720281.762624, -777396.263126, 360041.204628)
PROBE_EXTENT = (15000.0, 10000.0, 50000.0)

QUERY_FIELDS = (
    "query_type",
    "layer_name",
    "sub_priority",
    "inclusive",
    "recompute_vertex_normals",
    "override_default_params",
    "ray_origin",
    "ray_direction",
    "ray_length",
    "channels",
    "get_impact_point",
    "get_impact_normal",
    "get_distance",
    "get_face_index",
    "get_uv_coords",
    "accept_any_hit_section",
    "mega_mesh_override",
)

LINES = []


def record(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES).rstrip() + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_STAGE15B_QUERY_PREREQUISITES_REPORT={REPORT_PATH}")


def safe_call(fn, fallback=None):
    try:
        return fn()
    except Exception:
        return fallback


def get_property(obj, names, fallback=None):
    if obj is None:
        return fallback
    if isinstance(names, str):
        names = (names,)
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception:
            pass
        try:
            return getattr(obj, name)
        except Exception:
            pass
    return fallback


def object_path(obj):
    if obj is None:
        return "NONE"
    for fn in (
        lambda: obj.get_path_name(),
        lambda: obj.get_full_name(),
        lambda: str(obj),
    ):
        value = safe_call(fn)
        if value:
            return str(value)
    return "UNKNOWN"


def class_path(obj):
    cls = safe_call(lambda: obj.get_class())
    if cls is not None:
        path = safe_call(lambda: cls.get_path_name())
        if path:
            return str(path)
        name = safe_call(lambda: cls.get_name())
        if name:
            return str(name)
    return type(obj).__name__ if obj is not None else "NONE"


def class_name(obj):
    path = class_path(obj)
    return path.rsplit(".", 1)[-1].rsplit("/", 1)[-1]


def actor_label(actor):
    return str(safe_call(lambda: actor.get_actor_label(), safe_call(lambda: actor.get_name(), "UNKNOWN")))


def graph_nodes(graph):
    for getter in (
        lambda: graph.get_nodes(),
        lambda: graph.get_editor_property("nodes"),
        lambda: graph.nodes,
    ):
        value = safe_call(getter)
        if value is not None:
            return [item for item in list(value) if item is not None]
    raise RuntimeError("Could not enumerate PCG graph nodes")


def node_settings(node):
    for getter in (
        lambda: node.get_settings(),
        lambda: node.get_editor_property("settings"),
        lambda: node.settings,
    ):
        value = safe_call(getter)
        if value is not None:
            return value
    return None


def find_single_query_node(graph):
    matches = [
        node for node in graph_nodes(graph)
        if class_name(node_settings(node)) == "PCGQuerySettings"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one PCGQuerySettings node; found {len(matches)}")
    return matches[0], node_settings(matches[0])


def pin_label(pin):
    props = get_property(pin, ("properties", "pin_properties"))
    value = get_property(props, ("label", "name"))
    if value is None:
        value = get_property(pin, ("label", "name"))
    return str(value) if value is not None else "UNKNOWN"


def pin_edges(pin):
    edges = get_property(pin, ("edges",), None)
    return list(edges) if edges is not None else []


def describe_node_pins(node):
    rows = []
    for direction, property_names in (
        ("INPUT", ("input_pins", "inputs")),
        ("OUTPUT", ("output_pins", "outputs")),
    ):
        pins = get_property(node, property_names, []) or []
        for pin in list(pins):
            edges = pin_edges(pin)
            rows.append((direction, pin_label(pin), len(edges)))
    return rows


def normalize_name(value):
    text = str(value)
    if text.startswith('Name("') and text.endswith('")'):
        return text[6:-2]
    return text.strip('"')


def query_snapshot(settings):
    params = get_property(settings, ("query_params",))
    if params is None:
        raise RuntimeError("PCGQuerySettings.query_params is unavailable")
    snapshot = {}
    for field in QUERY_FIELDS:
        value = get_property(params, (field,), "UNEXPOSED")
        if field == "channels" and value != "UNEXPOSED":
            value = tuple(sorted(normalize_name(item) for item in list(value)))
        elif field == "mega_mesh_override":
            value = object_path(value) if value is not None else "NONE"
        snapshot[field] = value
    snapshot["export_text"] = safe_call(lambda: params.export_text(), str(params))
    snapshot["settings_export_text"] = safe_call(lambda: settings.export_text(), object_path(settings))
    return snapshot


def vector_tuple(value):
    return (float(value.x), float(value.y), float(value.z))


def actor_bounds(actor):
    result = safe_call(lambda: actor.get_actor_bounds(False))
    if not result or len(result) < 2:
        return None
    return vector_tuple(result[0]), vector_tuple(result[1])


def bounds_min_max(center, extent):
    return (
        center[0] - extent[0], center[0] + extent[0],
        center[1] - extent[1], center[1] + extent[1],
        center[2] - extent[2], center[2] + extent[2],
    )


def bounds_overlap(a, b):
    return not (
        a[1] < b[0] or a[0] > b[1]
        or a[3] < b[2] or a[2] > b[3]
        or a[5] < b[4] or a[4] > b[5]
    )


def bounds_overlap_xy(a, b):
    return not (
        a[1] < b[0] or a[0] > b[1]
        or a[3] < b[2] or a[2] > b[3]
    )


def get_components(actor):
    component_class = getattr(unreal, "ActorComponent", None)
    if component_class is not None:
        value = safe_call(lambda: actor.get_components_by_class(component_class))
        if value is not None:
            return list(value)
    result = []
    for class_token in ("SceneComponent", "PrimitiveComponent", "StaticMeshComponent"):
        cls = getattr(unreal, class_token, None)
        if cls is None:
            continue
        for component in list(safe_call(lambda cls=cls: actor.get_components_by_class(cls), []) or []):
            if component not in result:
                result.append(component)
    return result


def safe_static_mesh(component):
    value = safe_call(lambda: component.get_static_mesh())
    if value is not None:
        return value
    return get_property(component, ("static_mesh",), None)


def raw_static_mesh_bounds(mesh):
    result = safe_call(lambda: mesh.get_bounds())
    if result is None:
        return None
    origin = result.origin
    extent = result.box_extent
    return bounds_min_max(vector_tuple(origin), vector_tuple(extent))


def translated_bounds(bounds, location):
    if bounds is None or location is None:
        return None
    x, y, z = vector_tuple(location)
    return (
        bounds[0] + x, bounds[1] + x,
        bounds[2] + y, bounds[3] + y,
        bounds[4] + z, bounds[5] + z,
    )


def component_location(component):
    for fn in (
        lambda: component.get_world_location(),
        lambda: component.get_component_location(),
        lambda: component.get_component_transform().translation,
    ):
        value = safe_call(fn)
        if value is not None:
            return value
    return None


def collect_section_actors(world, actors):
    sections = []
    seen = set()

    def add(actor):
        if actor is None:
            return
        key = object_path(actor)
        if key not in seen:
            seen.add(key)
            sections.append(actor)

    for actor in actors:
        combined = f"{class_path(actor)} {actor.get_name()} {actor_label(actor)}".lower()
        if any(token in combined for token in ("previewsection", "interactivesection", "compiledsection")):
            add(actor)

    gameplay = getattr(unreal, "GameplayStatics", None)
    if gameplay is not None:
        for class_token in ("PreviewSection", "InteractiveSection", "CompiledSection"):
            cls = getattr(unreal, class_token, None)
            if cls is None:
                continue
            for actor in list(safe_call(lambda cls=cls: gameplay.get_all_actors_of_class(world, cls), []) or []):
                add(actor)
    return sections


def component_state(component):
    return {
        "registered": safe_call(lambda: component.is_registered(), "UNEXPOSED"),
        "active": safe_call(lambda: component.is_active(), "UNEXPOSED"),
        "visible": get_property(component, ("visible",), "UNEXPOSED"),
        "disabled": get_property(
            component,
            ("is_disabled", "disabled_in_editor", "disabled", "is_disabled_in_editor"),
            "UNEXPOSED",
        ),
        "affected_mesh": object_path(get_property(
            component,
            ("affected_mega_mesh", "affected_mesh_partition", "mesh_partition"),
            None,
        )),
        "priority": get_property(component, ("priority", "layer_priority"), "UNEXPOSED"),
        "sub_priority": get_property(component, ("sub_priority", "layer_sub_priority"), "UNEXPOSED"),
    }


def find_actors_by_label(actors, label):
    return [actor for actor in actors if actor_label(actor) == label]


def world_from_editor():
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if subsystem_class is not None:
        world = safe_call(lambda: unreal.get_editor_subsystem(subsystem_class).get_editor_world())
        if world is not None:
            return world
    return safe_call(lambda: unreal.EditorLevelLibrary.get_editor_world())


def main():
    record("AETHER STAGE 15B - MESH TERRAIN QUERY PREREQUISITE / CONTEXT AUDIT")
    record("=" * 108)
    record("READ_ONLY=TRUE")
    record("NO_ASSETS_MODIFIED=TRUE")
    record("NO_ACTORS_MODIFIED=TRUE")
    record("NO_COMPONENTS_MODIFIED=TRUE")
    record("NO_PACKAGES_SAVED=TRUE")
    record("NO_PCG_GENERATION_STARTED=TRUE")
    record("NO_MESH_PARTITION_BUILD_STARTED=TRUE")
    record("PROBE_ACTOR_REQUIRED=FALSE")
    record("AUDIT_TRIGGER=Mesh Terrain Query executed but produced no data on Out")

    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running the query prerequisite audit")
    except AttributeError:
        pass

    world = world_from_editor()
    if world is None or not object_path(world).startswith(MAP_PREFIX):
        raise RuntimeError("Open /Game/Maps/AetherWorld before running this audit")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(actor_subsystem.get_all_level_actors())
    record(f"WORLD={object_path(world)}")
    record(f"LOADED_ACTOR_COUNT={len(actors)}")

    graph = unreal.EditorAssetLibrary.load_asset(GRAPH_OBJECT_PATH)
    if graph is None:
        raise RuntimeError(f"Could not load {GRAPH_OBJECT_PATH}")
    query_node, query_settings = find_single_query_node(graph)
    query = query_snapshot(query_settings)

    record("")
    record("SAVED QUERY SETTINGS")
    record("-" * 108)
    record(f"GRAPH={object_path(graph)}")
    record(f"GRAPH_DIRTY={safe_call(lambda: graph.get_outermost().is_dirty(), False)}")
    record(f"QUERY_NODE={object_path(query_node)}")
    record(f"QUERY_SETTINGS={object_path(query_settings)}")
    for field in QUERY_FIELDS:
        record(f"QUERY_{field.upper()}={query[field]}")
    record(f"QUERY_PARAMS_EXPORT={query['export_text']}")
    for direction, label, edge_count in describe_node_pins(query_node):
        record(f"QUERY_PIN={direction}:{label}:EDGE_COUNT={edge_count}")

    bounding_shape_edges = sum(
        edge_count for direction, label, edge_count in describe_node_pins(query_node)
        if direction == "INPUT" and "bounding" in label.lower()
    )
    record(f"QUERY_BOUNDING_SHAPE_EDGE_COUNT={bounding_shape_edges}")

    persistent_volumes = find_actors_by_label(actors, PERSISTENT_VOLUME_LABEL)
    if len(persistent_volumes) != 1:
        raise RuntimeError(
            f"Expected one {PERSISTENT_VOLUME_LABEL}; found {len(persistent_volumes)}"
        )
    persistent_volume = persistent_volumes[0]
    persistent_bounds = actor_bounds(persistent_volume)
    intended_probe_bounds = bounds_min_max(PROBE_CENTER, PROBE_EXTENT)

    record("")
    record("EXECUTION BOUNDS")
    record("-" * 108)
    record(f"PERSISTENT_VOLUME={object_path(persistent_volume)}")
    record(f"PERSISTENT_VOLUME_BOUNDS={persistent_bounds}")
    record(f"INTENDED_PROBE_CENTER={PROBE_CENTER}")
    record(f"INTENDED_PROBE_EXTENT={PROBE_EXTENT}")
    record(f"INTENDED_PROBE_MIN_MAX={intended_probe_bounds}")

    mesh_partition_matches = find_actors_by_label(actors, MESH_PARTITION_LABEL)
    if len(mesh_partition_matches) != 1:
        mesh_partition_matches = [
            actor for actor in actors
            if class_path(actor) == "/Script/MeshPartition.MeshPartition"
        ]
    record(f"MESH_PARTITION_ACTOR_COUNT={len(mesh_partition_matches)}")
    for index, actor in enumerate(mesh_partition_matches):
        record(f"MESH_PARTITION_{index}_ACTOR={object_path(actor)}")
        record(f"MESH_PARTITION_{index}_LABEL={actor_label(actor)}")
        record(f"MESH_PARTITION_{index}_CLASS={class_path(actor)}")
        record(f"MESH_PARTITION_{index}_BOUNDS={actor_bounds(actor)}")
        record(
            f"MESH_PARTITION_{index}_PCG_BOUNDS="
            f"{safe_call(lambda actor=actor: actor.get_actor_bounds_pcg(True), 'UNEXPOSED')}"
        )
        record(
            f"MESH_PARTITION_{index}_DEFINITION="
            f"{object_path(safe_call(lambda actor=actor: actor.get_mesh_partition_definition()))}"
        )

    adapter_class = getattr(unreal, "PCGAdapterComponent", None)
    data_class = getattr(unreal, "PCGDataComponent", None)
    record(f"PCG_ADAPTER_CLASS_AVAILABLE={adapter_class is not None}")
    record(f"PCG_DATA_CLASS_AVAILABLE={data_class is not None}")

    section_actors = collect_section_actors(world, actors)
    section_type_counts = Counter()
    all_adapter_components = []
    all_data_components = []
    overlapping_sections = []
    overlapping_mesh_rows = []
    overlapping_data_components = []

    for actor in actors:
        components = get_components(actor)
        for component in components:
            path = class_path(component)
            if path == "/Script/PCGMeshPartitionInteropEditor.PCGAdapterComponent":
                all_adapter_components.append((actor, component))
            if path == "/Script/PCGMeshPartitionInterop.PCGDataComponent":
                all_data_components.append((actor, component))

    for section in section_actors:
        path = class_path(section)
        lower = path.lower()
        if "compiledsection" in lower:
            section_type = "COMPILED"
        elif "interactivesection" in lower:
            section_type = "INTERACTIVE"
        else:
            section_type = "PREVIEW"
        section_type_counts[section_type] += 1

        section_bounds = actor_bounds(section)
        section_min_max = (
            bounds_min_max(section_bounds[0], section_bounds[1])
            if section_bounds is not None else None
        )
        section_overlaps = bool(
            section_min_max is not None
            and bounds_overlap(section_min_max, intended_probe_bounds)
        )

        components = get_components(section)
        section_data = [
            component for component in components
            if class_path(component) == "/Script/PCGMeshPartitionInterop.PCGDataComponent"
        ]
        if section_overlaps:
            overlapping_sections.append(section)
            overlapping_data_components.extend((section, component) for component in section_data)

        for component in components:
            mesh = safe_static_mesh(component)
            if mesh is None:
                continue
            raw = raw_static_mesh_bounds(mesh)
            if raw is None:
                continue
            candidates = [("RAW_PARTITION_SPACE", raw)]
            location = component_location(component)
            translated = translated_bounds(raw, location)
            if translated is not None:
                candidates.append(("COMPONENT_LOCATION_TRANSLATION", translated))
            owner_location = safe_call(lambda section=section: section.get_actor_location())
            owner_translated = translated_bounds(raw, owner_location)
            if owner_translated is not None:
                candidates.append(("OWNER_LOCATION_TRANSLATION", owner_translated))

            matched = None
            for mode, candidate in candidates:
                if bounds_overlap_xy(candidate, intended_probe_bounds):
                    matched = (mode, candidate)
                    break
            if matched is not None:
                mode, candidate = matched
                overlapping_mesh_rows.append(
                    (
                        section,
                        component,
                        mesh,
                        mode,
                        candidate,
                        len(section_data),
                    )
                )

    record("")
    record("MESH PARTITION PCG ADAPTER / DATA CACHE")
    record("-" * 108)
    record(f"PCG_ADAPTER_COMPONENT_COUNT={len(all_adapter_components)}")
    for index, (owner, component) in enumerate(all_adapter_components):
        state = component_state(component)
        record(
            f"ADAPTER_{index:02d}=owner:{object_path(owner)} component:{object_path(component)} "
            f"class:{class_path(component)} registered:{state['registered']} active:{state['active']} "
            f"disabled:{state['disabled']} affected_mesh:{state['affected_mesh']} "
            f"priority:{state['priority']} sub_priority:{state['sub_priority']}"
        )

    record(f"PCG_DATA_COMPONENT_COUNT={len(all_data_components)}")
    data_owner_counts = Counter(actor_label(owner) for owner, _ in all_data_components)
    for owner_label, count in sorted(data_owner_counts.items()):
        record(f"PCG_DATA_OWNER={owner_label}:COUNT={count}")
    for index, (owner, component) in enumerate(all_data_components[:64]):
        state = component_state(component)
        record(
            f"DATA_{index:02d}=owner:{object_path(owner)} component:{object_path(component)} "
            f"registered:{state['registered']} active:{state['active']}"
        )
    if len(all_data_components) > 64:
        record(f"PCG_DATA_COMPONENT_ROWS_TRUNCATED={len(all_data_components) - 64}")

    record("")
    record("LOADED SECTION / PROBE OVERLAP")
    record("-" * 108)
    record(f"SECTION_ACTOR_COUNT={len(section_actors)}")
    record(f"PREVIEW_SECTION_COUNT={section_type_counts['PREVIEW']}")
    record(f"INTERACTIVE_SECTION_COUNT={section_type_counts['INTERACTIVE']}")
    record(f"COMPILED_SECTION_COUNT={section_type_counts['COMPILED']}")
    record(f"PROBE_OVERLAPPING_SECTION_ACTOR_COUNT={len(overlapping_sections)}")
    for index, section in enumerate(overlapping_sections):
        record(
            f"OVERLAPPING_SECTION_{index:02d}=label:{actor_label(section)} "
            f"class:{class_path(section)} bounds:{actor_bounds(section)}"
        )
    record(f"PROBE_OVERLAPPING_STATIC_MESH_COMPONENT_COUNT={len(overlapping_mesh_rows)}")
    for index, row in enumerate(overlapping_mesh_rows[:64]):
        section, component, mesh, mode, candidate, section_data_count = row
        record(
            f"OVERLAP_MESH_{index:02d}=section:{actor_label(section)} "
            f"component:{component.get_name()} class:{class_path(component)} "
            f"mesh:{object_path(mesh)} mode:{mode} bounds:{candidate} "
            f"section_pcg_data_components:{section_data_count}"
        )
    if len(overlapping_mesh_rows) > 64:
        record(f"OVERLAP_MESH_ROWS_TRUNCATED={len(overlapping_mesh_rows) - 64}")
    record(f"PROBE_OVERLAPPING_PCG_DATA_COMPONENT_COUNT={len(overlapping_data_components)}")

    adapter_present = len(all_adapter_components) > 0
    data_present = len(all_data_components) > 0
    overlap_geometry_present = len(overlapping_mesh_rows) > 0
    overlap_data_present = len(overlapping_data_components) > 0
    compiled_present = section_type_counts["COMPILED"] > 0
    query_final = "FINAL" in str(query["query_type"]).upper()
    query_target_override = query["mega_mesh_override"] != "NONE"

    if not adapter_present and not data_present:
        cache_status = "MISSING_PCG_ADAPTER_AND_SECTION_DATA_CACHE"
    elif adapter_present and not data_present:
        cache_status = "PCG_ADAPTER_PRESENT_BUT_NO_SECTION_DATA_CACHE"
    elif data_present and not overlap_data_present:
        cache_status = "PCG_DATA_CACHE_EXISTS_BUT_NOT_ON_PROBE_OVERLAP"
    else:
        cache_status = "PCG_SECTION_DATA_CACHE_PRESENT_ON_PROBE_OVERLAP"

    risks = []
    if not adapter_present:
        risks.append("NO_PCG_ADAPTER_COMPONENT")
    if not data_present:
        risks.append("NO_PCG_DATA_COMPONENTS")
    if overlap_geometry_present and not overlap_data_present:
        risks.append("PREVIEW_GEOMETRY_OVERLAPS_BUT_NO_PCG_CACHE_OVERLAPS")
    if query_final and not compiled_present:
        risks.append("QUERY_FINAL_WITH_NO_LOADED_COMPILED_SECTION_ACTORS")
    if bounding_shape_edges == 0:
        risks.append("BOUNDING_SHAPE_PIN_UNCONNECTED")
    if not query_target_override:
        risks.append("MEGA_MESH_OVERRIDE_NONE")

    record("")
    record("DECISION MATRIX")
    record("-" * 108)
    record(f"QUERY_NODE_EXECUTION_SIGNAL=EXECUTED_BUT_OUT_PIN_EMPTY")
    record(f"PROBE_OVERLAPS_PREVIEW_GEOMETRY={overlap_geometry_present}")
    record(f"PROBE_OVERLAPS_PCG_DATA_CACHE={overlap_data_present}")
    record(f"PCG_ADAPTER_PRESENT={adapter_present}")
    record(f"PCG_DATA_CACHE_PRESENT_ANYWHERE={data_present}")
    record(f"QUERY_TYPE_IS_FINAL={query_final}")
    record(f"LOADED_COMPILED_SECTIONS_PRESENT={compiled_present}")
    record(f"BOUNDING_SHAPE_PIN_CONNECTED={bounding_shape_edges > 0}")
    record(f"MEGA_MESH_OVERRIDE_ASSIGNED={query_target_override}")
    record(f"PCG_CACHE_PREREQUISITE_STATUS={cache_status}")
    record(f"CONTEXT_RISK_COUNT={len(risks)}")
    for index, risk in enumerate(risks, 1):
        record(f"CONTEXT_RISK_{index:02d}={risk}")

    record("AUDIT_RESULT=PASS")
    record(
        "NEXT=Use the adapter/data-cache evidence as the primary branch. "
        "Do not modify Query mode, Bounding Shape, MegaMeshOverride, or partitioning until this report is reviewed."
    )
    write_report()


try:
    main()
except Exception as exc:
    record("")
    record("AUDIT_RESULT=FAIL")
    record(f"ERROR={type(exc).__name__}: {exc}")
    record("NO_ASSETS_MODIFIED=TRUE")
    record("NO_ACTORS_MODIFIED=TRUE")
    record("NO_COMPONENTS_MODIFIED=TRUE")
    record("NO_PACKAGES_SAVED=TRUE")
    record("NO_PCG_GENERATION_STARTED=TRUE")
    record("NO_MESH_PARTITION_BUILD_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE15B_QUERY_PREREQUISITES_FAILED={type(exc).__name__}: {exc}")
    raise
