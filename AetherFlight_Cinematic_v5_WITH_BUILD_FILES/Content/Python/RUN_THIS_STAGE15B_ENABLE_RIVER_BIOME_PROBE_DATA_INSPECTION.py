"""Enable PCG Toolset inspection for the temporary Stage 15B river-biome probe.

The existing probe has completed twice with zero instances. This script enables
per-node data capture on the probe's transient graph, then re-executes only that
unsaved, non-partitioned probe component. A separate read-only audit retrieves
Query, ToPoint, density, and Mesh Terrain channel data from the captured run.

No persistent graph, level package, full river volume, or Mesh Partition data is
modified or saved.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeInspectionEnable.txt"
PROBE_LABEL = "Aether_Stage15B_RiverBiomeProbe_UNSAVED"
SOURCE_VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
EXPECTED_GRAPH_TOKEN = "AetherStage15B_RiverBiomeProbeGraph"


def safe_call(fn, fallback=None):
    try:
        return fn()
    except Exception:
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


def class_name(obj):
    cls = safe_call(lambda: obj.get_class())
    if cls is not None:
        value = safe_call(lambda: cls.get_name())
        if value:
            return str(value)
    return type(obj).__name__ if obj is not None else "NONE"


def actors_with_label(label):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return [
        actor for actor in subsystem.get_all_level_actors()
        if safe_call(lambda actor=actor: actor.get_actor_label(), "") == label
    ]


def find_single_actor(label):
    matches = actors_with_label(label)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one actor labelled {label}; found {len(matches)}")
    return matches[0]


def get_component(actor):
    components = actor.get_components_by_class(unreal.PCGComponent)
    if len(components) != 1:
        raise RuntimeError(f"Expected one PCG component on {actor.get_actor_label()}; found {len(components)}")
    return components[0]


def get_graph(component):
    graph = safe_call(lambda: component.get_graph())
    if graph is None:
        graph = safe_call(lambda: component.get_editor_property("graph"))
    if graph is None:
        raise RuntimeError("Probe component has no graph")
    return graph


def graph_nodes(graph):
    for getter in (
        lambda: graph.get_nodes(),
        lambda: graph.get_editor_property("nodes"),
        lambda: graph.nodes,
    ):
        value = safe_call(getter)
        if value is not None:
            return [item for item in list(value) if item is not None]
    raise RuntimeError("Could not enumerate transient probe graph nodes")


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


def find_single_node(graph, settings_class_name):
    matches = [
        node for node in graph_nodes(graph)
        if class_name(node_settings(node)) == settings_class_name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {settings_class_name} node in transient graph; found {len(matches)}"
        )
    return matches[0]


def instance_count(actor):
    components = (
        actor.get_components_by_class(unreal.InstancedStaticMeshComponent)
        + actor.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
    )
    unique = []
    seen = set()
    for component in components:
        key = object_path(component)
        if key not in seen:
            seen.add(key)
            unique.append(component)
    total = 0
    for component in unique:
        total += int(safe_call(lambda component=component: component.get_instance_count(), 0) or 0)
    return len(unique), total


def resolve_data_view_callable():
    toolset = getattr(unreal, "PCGToolset", None)
    method = getattr(toolset, "get_node_data_view", None) if toolset is not None else None
    if callable(method):
        return method, "unreal.PCGToolset.get_node_data_view"

    cls = safe_call(lambda: unreal.load_class(None, "/Script/PCGToolset.PCGToolset"))
    method = getattr(cls, "get_node_data_view", None) if cls is not None else None
    if callable(method):
        return method, "loaded PCGToolset class.get_node_data_view"

    raise RuntimeError(
        "PCG Toolset data-view API is unavailable. Confirm the editor-only PCGToolset plugin loaded after restart"
    )


def start_generation(component):
    method = getattr(component, "generate_local", None)
    if callable(method):
        method(True)
        return "generate_local(True)"
    method = getattr(component, "generate", None)
    if callable(method):
        method(True)
        return "generate(True)"
    raise RuntimeError("Probe component exposes neither generate_local nor generate")


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_REPORT={REPORT_PATH}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before enabling Stage 15B probe inspection")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - ENABLE TEMPORARY PROBE NODE DATA INSPECTION",
        "=" * 100,
        "PERSISTENT_GRAPH_MODIFIED=FALSE",
        "PERSISTENT_VOLUME_MODIFIED=FALSE",
        "PACKAGES_SAVED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
        "INSPECTION_ACTOR_SCOPE=ONE_TRANSIENT_PROBE_ONLY",
    ]

    probe = find_single_actor(PROBE_LABEL)
    full_volume = find_single_actor(SOURCE_VOLUME_LABEL)
    full_component_count, full_instances = instance_count(full_volume)
    lines.append(f"FULL_VOLUME_INSTANCE_COMPONENT_COUNT={full_component_count}")
    lines.append(f"FULL_VOLUME_INSTANCE_COUNT={full_instances}")
    if full_component_count != 0 or full_instances != 0:
        raise RuntimeError("Full river biome volume contains generated instances; refusing inspection run")

    component = get_component(probe)
    if safe_call(lambda: component.is_generating(), False):
        raise RuntimeError("Temporary probe is still generating; wait before enabling inspection")

    graph = get_graph(component)
    graph_path = object_path(graph)
    if EXPECTED_GRAPH_TOKEN not in graph_path or not graph_path.startswith("/Engine/Transient"):
        raise RuntimeError(f"Probe graph is not the expected transient graph: {graph_path}")

    query_node = find_single_node(graph, "PCGQuerySettings")
    to_point_node = find_single_node(graph, "PCGConvertToPointDataSettings")
    data_view, route = resolve_data_view_callable()

    # Epic's API enables graph inspection on the first call. The returned text is
    # expected to request a re-execution when no captured data exists yet.
    query_initial = str(data_view(probe, query_node, "Out", "", 0, 1))
    point_initial = str(data_view(probe, to_point_node, "Out", "", 0, 1))

    lines.append(f"PROBE_ACTOR={object_path(probe)}")
    lines.append(f"PROBE_COMPONENT={object_path(component)}")
    lines.append(f"PROBE_GRAPH={graph_path}")
    lines.append(f"QUERY_NODE={object_path(query_node)}")
    lines.append(f"TO_POINT_NODE={object_path(to_point_node)}")
    lines.append(f"DATA_VIEW_CALLABLE={route}")
    lines.append(f"QUERY_INITIAL_DATA_VIEW={query_initial[:2000]}")
    lines.append(f"TO_POINT_INITIAL_DATA_VIEW={point_initial[:2000]}")

    generation_method = start_generation(component)
    lines.append(f"GENERATION_METHOD={generation_method}")
    lines.append(f"IS_GENERATING_IMMEDIATELY={safe_call(lambda: component.is_generating(), 'UNEXPOSED')}")
    lines.extend((
        "PROBE_INSPECTION_ENABLE_RESULT=PASS",
        "NEXT=Wait for generation to finish, then run RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_PROBE_NODE_DATA.py.",
        "DO_NOT_SAVE_LEVEL=TRUE",
        "DO_NOT_RUN_INSPECTION_ON_ANOTHER_ACTOR=TRUE",
    ))
    write_report(lines)


try:
    main()
except Exception as exc:
    failure = [
        "AETHER STAGE 15B - ENABLE TEMPORARY PROBE NODE DATA INSPECTION",
        "=" * 100,
        "PROBE_INSPECTION_ENABLE_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "PERSISTENT_GRAPH_MODIFIED=FALSE",
        "PERSISTENT_VOLUME_MODIFIED=FALSE",
        "PACKAGES_SAVED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
    ]
    write_report(failure)
    unreal.log_error("\n".join(failure))
    raise
