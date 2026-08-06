"""Read-only Stage 15B Query/ToPoint node-data audit V2 for UE 5.8.1.

Uses ToolsetRegistry.execute_tool to call the registered PCG Toolset's
GetNodeDataView sequentially. Run only after the V2 inspection enable script has
completed with PASS. No graph, actor, package, generation, or Mesh Partition data
is modified, saved, generated, cleaned, or built.
"""

from pathlib import Path
import builtins
import json
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeNodeDataV2.txt"
PROBE_LABEL = "Aether_Stage15B_RiverBiomeProbe_UNSAVED"
SOURCE_VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
EXPECTED_GRAPH_TOKEN = "AetherStage15B_RiverBiomeProbeGraph"
TOOLSET_NAME = "PCGToolset.PCGToolset"
STATE_KEY = "_AETHER_STAGE15B_PROBE_NODE_DATA_AUDIT_V2"
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


def result_value(result):
    value = safe_call(lambda: result.get_editor_property("value"))
    if value is None:
        value = safe_call(lambda: result.value)
    if value is not None:
        return str(value)
    encoded = safe_call(lambda: result.get_value_as_json_string(), "")
    if encoded:
        try:
            return str(json.loads(encoded))
        except Exception:
            return str(encoded)
    return ""


def unwrap_return_value(value):
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except Exception:
        return text
    if isinstance(parsed, dict) and "returnValue" in parsed:
        returned = parsed["returnValue"]
        if isinstance(returned, str):
            return returned
        return json.dumps(returned, ensure_ascii=False, separators=(",", ":"))
    if isinstance(parsed, str):
        return parsed
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


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
            '"error"', "no inspection data", "re-execute", "reexecute", "failed"
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


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_PROBE_NODE_DATA_V2_REPORT={REPORT_PATH}")


def append_capture(lines, label, text, analysis, error):
    lines.append(f"{label}_TOOL_ERROR={error or 'NONE'}")
    lines.append(f"{label}_JSON_VALID={analysis['json_valid']}")
    lines.append(f"{label}_CONTAINS_ERROR={analysis['contains_error']}")
    lines.append(f"{label}_NONEMPTY={analysis['nonempty']}")
    lines.append(f"{label}_METRICS={' | '.join(analysis['metrics']) or 'NONE'}")
    lines.append(f"{label}_FIRST_ROWS={' | '.join(analysis['rows']) or 'NONE'}")
    lines.append(f"{label}_RAW={text[:12000] or 'EMPTY'}")


def finalize(state):
    if state.get("finished"):
        return
    state["finished"] = True
    captures = state["captures"]
    query = captures.get("QUERY_OUT", {})
    point = captures.get("TOPOINT_OUT_ALL", {})
    attrs = {name: captures.get(f"ATTR::{name}", {}) for name in ATTRIBUTES}

    query_has_data = bool(query.get("analysis", {}).get("nonempty")) and not query.get("error")
    point_has_data = bool(point.get("analysis", {}).get("nonempty")) and not point.get("error")
    position_has_data = bool(attrs.get("$Position", {}).get("analysis", {}).get("nonempty")) and not attrs.get("$Position", {}).get("error")

    if not query_has_data:
        diagnosis = "MESH_PARTITION_QUERY_RETURNED_NO_INSPECTABLE_DATA"
    elif not point_has_data or not position_has_data:
        diagnosis = "QUERY_HAS_DATA_BUT_TOPOINT_RETURNED_NO_POINTS"
    elif any(attrs[name].get("error") or attrs[name].get("analysis", {}).get("contains_error") for name in (
        "Wetland", "Grass", "Rock", "Water", "FoliageExclusion"
    )):
        diagnosis = "TOPOINT_HAS_POINTS_BUT_ONE_OR_MORE_WEIGHT_CHANNELS_ARE_MISSING"
    else:
        diagnosis = "TOPOINT_HAS_POINTS_AND_REQUESTED_WEIGHT_CHANNELS_ARE_INSPECTABLE"

    state["lines"].extend((
        "",
        "SUMMARY",
        "-" * 100,
        f"QUERY_HAS_INSPECTABLE_DATA={query_has_data}",
        f"TOPOINT_HAS_INSPECTABLE_DATA={point_has_data}",
        f"TOPOINT_POSITION_HAS_DATA={position_has_data}",
        f"NODE_DATA_TOOL_ERROR_COUNT={len(state['tool_errors'])}",
        f"NODE_DATA_DIAGNOSIS={diagnosis}",
        "NODE_DATA_AUDIT_V2_RESULT=PASS",
        "NEXT=Use NODE_DATA_DIAGNOSIS to correct only the failing Query/ToPoint/channel boundary; do not generate the persistent volume.",
    ))
    for index, error in enumerate(state["tool_errors"], 1):
        state["lines"].append(f"TOOL_ERROR_{index:02d}={error}")
    write_report(state["lines"])


def bind_result(state, result, label, callback):
    if result is None:
        callback("No ToolCallAsyncResult", "")
        return
    state["pending"].append(result)

    def completed(*_args):
        error = str(safe_call(lambda: result.error, "") or "")
        callback(error, result_value(result))

    state["callbacks"].append(completed)
    delegate = safe_call(lambda: result.on_completed)
    if delegate is None:
        callback("Result exposes no on_completed delegate", "")
        return
    try:
        delegate.add_callable(completed)
    except Exception as exc:
        callback(f"Delegate bind failed: {type(exc).__name__}: {exc}", "")
        return
    safe_call(lambda: result.broadcast_on_completed_if_complete(), False)


def execute_capture(state, capture, callback):
    registry = unreal.ToolsetRegistry
    full_name = f"{TOOLSET_NAME}.GetNodeDataView"
    payload = {
        "pCGVolume": {"refPath": state["probe_path"]},
        "node": {"refPath": capture["node_path"]},
        "pinLabel": "Out",
        "attributeName": capture["attribute"],
        "startIndex": 0,
        "endIndex": SAMPLE_END_INDEX,
    }
    try:
        result = registry.execute_tool(
            TOOLSET_NAME,
            full_name,
            json.dumps(payload, separators=(",", ":")),
        )
    except Exception as exc:
        callback(f"execute_tool raised {type(exc).__name__}: {exc}", "")
        return
    bind_result(state, result, capture["label"], callback)


def run_next(state):
    if state["index"] >= len(state["queue"]):
        finalize(state)
        return
    capture = state["queue"][state["index"]]
    state["index"] += 1

    def completed(error, value):
        data_text = unwrap_return_value(value)
        analysis = inspect_text(data_text)
        append_capture(state["lines"], capture["label"], data_text, analysis, error)
        state["captures"][capture["key"]] = {
            "error": error,
            "text": data_text,
            "analysis": analysis,
        }
        if error:
            state["tool_errors"].append(f"{capture['label']}: {error}")
        state["lines"].append(f"CAPTURES_COMPLETED={state['index']}/{len(state['queue'])}")
        write_report(state["lines"] + ["NODE_DATA_AUDIT_V2_RESULT=PENDING"])
        run_next(state)

    execute_capture(state, capture, completed)


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running Stage 15B probe node-data audit V2")
    except AttributeError:
        pass

    old_state = getattr(builtins, STATE_KEY, None)
    if isinstance(old_state, dict) and not old_state.get("finished", True):
        raise RuntimeError("A Stage 15B node-data audit V2 call chain is already pending")

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
    full_component_count, full_instances = instance_count(full_volume)
    probe_component_count, probe_instances = instance_count(probe)

    if not unreal.ToolsetRegistry.is_available() or not unreal.ToolsetRegistry.is_toolset_registered(TOOLSET_NAME):
        raise RuntimeError("Registered PCG Toolset is unavailable")

    queue = [
        {"key": "QUERY_OUT", "label": "QUERY_OUT", "node_path": object_path(query_node), "attribute": ""},
        {"key": "TOPOINT_OUT_ALL", "label": "TOPOINT_OUT_ALL", "node_path": object_path(to_point_node), "attribute": ""},
    ]
    for attribute in ATTRIBUTES:
        label = "TOPOINT_" + attribute.replace("$", "POINT_").replace(" ", "_").replace("-", "_").upper()
        queue.append({
            "key": f"ATTR::{attribute}",
            "label": label,
            "node_path": object_path(to_point_node),
            "attribute": attribute,
        })

    state = {
        "finished": False,
        "pending": [],
        "callbacks": [],
        "queue": queue,
        "index": 0,
        "captures": {},
        "tool_errors": [],
        "probe_path": object_path(probe),
        "lines": [
            "AETHER STAGE 15B - TEMPORARY PROBE QUERY/TOPOINT NODE DATA AUDIT V2",
            "=" * 100,
            "READ_ONLY=TRUE",
            "RESULT_STATE=PENDING",
            "TOOLSET_ROUTE=ToolsetRegistry.execute_tool",
            f"TOOLSET_NAME={TOOLSET_NAME}",
            f"PROBE_ACTOR={object_path(probe)}",
            f"PROBE_GRAPH={graph_path}",
            f"QUERY_NODE={object_path(query_node)}",
            f"TO_POINT_NODE={object_path(to_point_node)}",
            f"PROBE_GENERATED={safe_call(lambda: component.generated, 'UNEXPOSED')}",
            f"FULL_VOLUME_INSTANCE_COMPONENT_COUNT={full_component_count}",
            f"FULL_VOLUME_INSTANCE_COUNT={full_instances}",
            f"PROBE_INSTANCE_COMPONENT_COUNT={probe_component_count}",
            f"PROBE_TOTAL_INSTANCE_COUNT={probe_instances}",
            "NO_ASSETS_MODIFIED=TRUE",
            "NO_ACTORS_MODIFIED=TRUE",
            "NO_PACKAGES_SAVED=TRUE",
            "NO_PCG_GENERATION_STARTED=TRUE",
            "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
        ],
    }
    setattr(builtins, STATE_KEY, state)
    write_report(state["lines"] + ["NODE_DATA_AUDIT_V2_RESULT=PENDING"])
    run_next(state)


try:
    main()
except Exception as exc:
    lines = [
        "AETHER STAGE 15B - TEMPORARY PROBE QUERY/TOPOINT NODE DATA AUDIT V2",
        "=" * 100,
        "NODE_DATA_AUDIT_V2_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "NO_ASSETS_MODIFIED=TRUE",
        "NO_ACTORS_MODIFIED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    ]
    write_report(lines)
    unreal.log_error("\n".join(lines))
    raise
