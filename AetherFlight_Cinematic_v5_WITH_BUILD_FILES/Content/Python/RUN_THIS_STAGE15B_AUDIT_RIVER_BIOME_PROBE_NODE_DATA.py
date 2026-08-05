"""Read-only PCG Toolset data audit for the temporary Stage 15B river probe.

Run only after RUN_THIS_STAGE15B_ENABLE_RIVER_BIOME_PROBE_DATA_INSPECTION.py and
after the probe has finished re-executing. It retrieves bounded JSON data views
from the Mesh Partition Query and ToPoint nodes, including the actual Density,
Wetland, Grass, Rock, Water, and FoliageExclusion values on the first points.

No graph, actor, component, package, PCG generation, or Mesh Partition data is
modified, saved, generated, cleaned, or built.
"""

from pathlib import Path
import json
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeNodeData.txt"
PROBE_LABEL = "Aether_Stage15B_RiverBiomeProbe_UNSAVED"
SOURCE_VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
EXPECTED_GRAPH_TOKEN = "AetherStage15B_RiverBiomeProbeGraph"
SAMPLE_END_INDEX = 10
ATTRIBUTES = (
    "$Position",
    "$Density",
    "Wetland",
    "Grass",
    "Rock",
    "Water",
    "FoliageExclusion",
)


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

    raise RuntimeError("PCG Toolset data-view API is unavailable after plugin restart")


def summarize_json_value(value, path="$", rows=None, metrics=None, depth=0):
    if rows is None:
        rows = []
    if metrics is None:
        metrics = []
    if depth > 8:
        return rows, metrics

    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            child_path = f"{path}.{key_text}"
            if isinstance(item, (int, float)) and any(
                token in lowered for token in ("count", "total", "num", "size", "length")
            ):
                metrics.append(f"{child_path}={item}")
            if isinstance(item, list):
                metrics.append(f"{child_path}.list_length={len(item)}")
            summarize_json_value(item, child_path, rows, metrics, depth + 1)
    elif isinstance(value, list):
        if value:
            rows.append(f"{path}[0]={repr(value[0])[:1000]}")
        for index, item in enumerate(value[:3]):
            summarize_json_value(item, f"{path}[{index}]", rows, metrics, depth + 1)
    return rows, metrics


def inspect_text(text):
    result = {
        "json_valid": False,
        "contains_error": False,
        "nonempty": False,
        "metrics": [],
        "rows": [],
    }
    stripped = str(text).strip()
    lowered = stripped.lower()
    result["contains_error"] = any(
        token in lowered for token in (
            '"error"',
            "no inspection data",
            "re-execute",
            "reexecute",
            "failed",
        )
    )
    if stripped and stripped not in ("{}", "[]", "null", "None"):
        result["nonempty"] = True
    try:
        parsed = json.loads(stripped)
        result["json_valid"] = True
        rows, metrics = summarize_json_value(parsed)
        result["rows"] = rows
        result["metrics"] = sorted(set(metrics))
        if parsed in ({}, [], None, ""):
            result["nonempty"] = False
    except Exception:
        pass
    return result


def capture(data_view, volume, node, attribute):
    text = str(data_view(volume, node, "Out", attribute, 0, SAMPLE_END_INDEX))
    return text, inspect_text(text)


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_PROBE_NODE_DATA_REPORT={REPORT_PATH}")


def append_capture(lines, label, text, analysis):
    lines.append(f"{label}_JSON_VALID={analysis['json_valid']}")
    lines.append(f"{label}_CONTAINS_ERROR={analysis['contains_error']}")
    lines.append(f"{label}_NONEMPTY={analysis['nonempty']}")
    lines.append(f"{label}_METRICS={' | '.join(analysis['metrics']) or 'NONE'}")
    lines.append(f"{label}_FIRST_ROWS={' | '.join(analysis['rows']) or 'NONE'}")
    lines.append(f"{label}_RAW={text[:12000]}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running Stage 15B probe node-data audit")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - TEMPORARY PROBE QUERY/TOPOINT NODE DATA AUDIT",
        "=" * 100,
        "READ_ONLY=TRUE",
        "NO_ASSETS_MODIFIED=TRUE",
        "NO_ACTORS_MODIFIED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
        "INSPECTION_ACTOR_SCOPE=ONE_TRANSIENT_PROBE_ONLY",
    ]
    failures = []

    probe = find_single_actor(PROBE_LABEL)
    full_volume = find_single_actor(SOURCE_VOLUME_LABEL)
    component = get_component(probe)
    if safe_call(lambda: component.is_generating(), False):
        raise RuntimeError("Temporary probe is still generating; wait before auditing node data")

    graph = get_graph(component)
    graph_path = object_path(graph)
    if EXPECTED_GRAPH_TOKEN not in graph_path or not graph_path.startswith("/Engine/Transient"):
        raise RuntimeError(f"Probe graph is not the expected transient graph: {graph_path}")

    query_node = find_single_node(graph, "PCGQuerySettings")
    to_point_node = find_single_node(graph, "PCGConvertToPointDataSettings")
    data_view, route = resolve_data_view_callable()

    full_component_count, full_instances = instance_count(full_volume)
    probe_component_count, probe_instances = instance_count(probe)
    lines.append(f"PROBE_ACTOR={object_path(probe)}")
    lines.append(f"PROBE_GRAPH={graph_path}")
    lines.append(f"DATA_VIEW_CALLABLE={route}")
    lines.append(f"PROBE_GENERATED={safe_call(lambda: component.generated, 'UNEXPOSED')}")
    lines.append(f"FULL_VOLUME_INSTANCE_COMPONENT_COUNT={full_component_count}")
    lines.append(f"FULL_VOLUME_INSTANCE_COUNT={full_instances}")
    lines.append(f"PROBE_INSTANCE_COMPONENT_COUNT={probe_component_count}")
    lines.append(f"PROBE_TOTAL_INSTANCE_COUNT={probe_instances}")

    query_text, query_analysis = capture(data_view, probe, query_node, "")
    append_capture(lines, "QUERY_OUT", query_text, query_analysis)

    point_all_text, point_all_analysis = capture(data_view, probe, to_point_node, "")
    append_capture(lines, "TOPOINT_OUT_ALL", point_all_text, point_all_analysis)

    attribute_results = {}
    for attribute in ATTRIBUTES:
        text, analysis = capture(data_view, probe, to_point_node, attribute)
        safe_label = (
            attribute.replace("$", "POINT_")
            .replace(" ", "_")
            .replace("-", "_")
            .upper()
        )
        append_capture(lines, f"TOPOINT_{safe_label}", text, analysis)
        attribute_results[attribute] = analysis

    if query_analysis["contains_error"]:
        failures.append("Query data view still reports an inspection error after re-execution")
    if point_all_analysis["contains_error"]:
        failures.append("ToPoint data view still reports an inspection error after re-execution")

    query_has_data = query_analysis["nonempty"] and not query_analysis["contains_error"]
    point_has_data = point_all_analysis["nonempty"] and not point_all_analysis["contains_error"]
    position_has_data = (
        attribute_results["$Position"]["nonempty"]
        and not attribute_results["$Position"]["contains_error"]
    )

    if not query_has_data:
        diagnosis = "MESH_PARTITION_QUERY_RETURNED_NO_INSPECTABLE_DATA"
    elif not point_has_data or not position_has_data:
        diagnosis = "QUERY_HAS_DATA_BUT_TOPOINT_RETURNED_NO_POINTS"
    elif any(attribute_results[name]["contains_error"] for name in (
        "Wetland", "Grass", "Rock", "Water", "FoliageExclusion"
    )):
        diagnosis = "TOPOINT_HAS_POINTS_BUT_ONE_OR_MORE_WEIGHT_CHANNELS_ARE_MISSING"
    else:
        diagnosis = "TOPOINT_HAS_POINTS_AND_REQUESTED_WEIGHT_CHANNELS_ARE_INSPECTABLE"

    lines.extend((
        "",
        "SUMMARY",
        "-" * 100,
        f"QUERY_HAS_INSPECTABLE_DATA={query_has_data}",
        f"TOPOINT_HAS_INSPECTABLE_DATA={point_has_data}",
        f"TOPOINT_POSITION_HAS_DATA={position_has_data}",
        f"NODE_DATA_FAILURE_COUNT={len(failures)}",
    ))
    for index, failure in enumerate(failures, 1):
        lines.append(f"FAILURE_{index:02d}={failure}")
    lines.append(f"NODE_DATA_DIAGNOSIS={diagnosis}")
    lines.append("NODE_DATA_AUDIT_RESULT=PASS")
    lines.append("NEXT=Use NODE_DATA_DIAGNOSIS and captured channel values to correct only the failing boundary; do not generate the persistent volume.")
    write_report(lines)


try:
    main()
except Exception as exc:
    failure = [
        "AETHER STAGE 15B - TEMPORARY PROBE QUERY/TOPOINT NODE DATA AUDIT",
        "=" * 100,
        "NODE_DATA_AUDIT_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "NO_ASSETS_MODIFIED=TRUE",
        "NO_ACTORS_MODIFIED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    ]
    write_report(failure)
    unreal.log_error("\n".join(failure))
    raise
