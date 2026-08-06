"""Stage 15B temporary river-biome probe inspection V2 for UE 5.8.1.

Uses the registered PCG Toolset through ToolsetRegistry.execute_tool. Calls
GetNodeDataView sequentially on Query and ToPoint to arm per-node capture, then
calls ExecuteGraphInstance on only the unsaved, non-partitioned probe actor.

Callbacks are retained in builtins until completion. No persistent graph, level
package, full river volume, or Mesh Partition data is modified or saved.
"""

from pathlib import Path
import builtins
import json
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeInspectionEnableV2.txt"
PROBE_LABEL = "Aether_Stage15B_RiverBiomeProbe_UNSAVED"
SOURCE_VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
EXPECTED_GRAPH_TOKEN = "AetherStage15B_RiverBiomeProbeGraph"
TOOLSET_NAME = "PCGToolset.PCGToolset"
STATE_KEY = "_AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V2"


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


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V2_REPORT={REPORT_PATH}")


def finalize(state, result, error=None):
    if state.get("finished"):
        return
    state["finished"] = True
    state["lines"].append(f"PROBE_INSPECTION_ENABLE_V2_RESULT={result}")
    if error:
        state["lines"].append(f"ERROR={error}")
    state["lines"].extend((
        "PERSISTENT_GRAPH_MODIFIED=FALSE",
        "PERSISTENT_VOLUME_MODIFIED=FALSE",
        "PACKAGES_SAVED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
        "DO_NOT_SAVE_LEVEL=TRUE",
    ))
    if result == "PASS":
        state["lines"].append(
            "NEXT=Run RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_PROBE_NODE_DATA_V2.py."
        )
    write_report(state["lines"])
    if result != "PASS":
        unreal.log_error(f"Stage 15B probe inspection V2 failed: {error}")


def bind_result(state, result, label, callback):
    if result is None:
        finalize(state, "FAIL", f"{label} returned no ToolCallAsyncResult")
        return
    state["pending"].append(result)

    def completed(*_args):
        if state.get("finished"):
            return
        error = str(safe_call(lambda: result.error, "") or "")
        value = result_value(result)
        state["lines"].append(f"{label}_COMPLETE=True")
        state["lines"].append(f"{label}_ERROR={error or 'NONE'}")
        state["lines"].append(f"{label}_VALUE={value[:4000] or 'EMPTY'}")
        callback(error, value)

    state["callbacks"].append(completed)
    delegate = safe_call(lambda: result.on_completed)
    if delegate is None:
        finalize(state, "FAIL", f"{label} result exposes no on_completed delegate")
        return
    try:
        delegate.add_callable(completed)
    except Exception as exc:
        finalize(state, "FAIL", f"{label} delegate bind failed: {type(exc).__name__}: {exc}")
        return
    safe_call(lambda: result.broadcast_on_completed_if_complete(), False)


def execute_tool(state, local_name, payload, label, callback):
    registry = getattr(unreal, "ToolsetRegistry", None)
    if registry is None:
        finalize(state, "FAIL", "unreal.ToolsetRegistry is unavailable")
        return
    full_name = f"{TOOLSET_NAME}.{local_name}"
    try:
        result = registry.execute_tool(
            TOOLSET_NAME,
            full_name,
            json.dumps(payload, separators=(",", ":")),
        )
    except Exception as exc:
        finalize(state, "FAIL", f"{label} execute_tool raised {type(exc).__name__}: {exc}")
        return
    state["lines"].append(f"{label}_TOOL_NAME={full_name}")
    bind_result(state, result, label, callback)


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before enabling Stage 15B probe inspection")
    except AttributeError:
        pass

    old_state = getattr(builtins, STATE_KEY, None)
    if isinstance(old_state, dict) and not old_state.get("finished", True):
        raise RuntimeError("A Stage 15B probe inspection V2 call chain is already pending")

    probe = find_single_actor(PROBE_LABEL)
    full_volume = find_single_actor(SOURCE_VOLUME_LABEL)
    full_component_count, full_instances = instance_count(full_volume)
    if full_component_count != 0 or full_instances != 0:
        raise RuntimeError("Full river biome volume contains generated instances; refusing inspection")

    component = get_component(probe)
    if safe_call(lambda: component.is_generating(), False):
        raise RuntimeError("Temporary probe is still generating; wait before enabling inspection")

    graph = get_graph(component)
    graph_path = object_path(graph)
    if EXPECTED_GRAPH_TOKEN not in graph_path or not graph_path.startswith("/Engine/Transient"):
        raise RuntimeError(f"Probe graph is not the expected transient graph: {graph_path}")

    query_node = find_single_node(graph, "PCGQuerySettings")
    to_point_node = find_single_node(graph, "PCGConvertToPointDataSettings")

    registry = getattr(unreal, "ToolsetRegistry", None)
    if registry is None or not registry.is_available():
        raise RuntimeError("Toolset Registry is unavailable")
    if not registry.is_toolset_registered(TOOLSET_NAME):
        raise RuntimeError(f"Toolset is not registered: {TOOLSET_NAME}")

    state = {
        "finished": False,
        "pending": [],
        "callbacks": [],
        "lines": [
            "AETHER STAGE 15B - ENABLE TEMPORARY PROBE NODE DATA INSPECTION V2",
            "=" * 100,
            "RESULT_STATE=PENDING",
            "TOOLSET_ROUTE=ToolsetRegistry.execute_tool",
            f"TOOLSET_NAME={TOOLSET_NAME}",
            f"PROBE_ACTOR={object_path(probe)}",
            f"PROBE_GRAPH={graph_path}",
            f"QUERY_NODE={object_path(query_node)}",
            f"TO_POINT_NODE={object_path(to_point_node)}",
            f"FULL_VOLUME_INSTANCE_COMPONENT_COUNT={full_component_count}",
            f"FULL_VOLUME_INSTANCE_COUNT={full_instances}",
            "PERSISTENT_GRAPH_MODIFIED=FALSE",
            "PERSISTENT_VOLUME_MODIFIED=FALSE",
            "PACKAGES_SAVED=FALSE",
            "MESH_PARTITION_BUILD_STARTED=FALSE",
        ],
    }
    setattr(builtins, STATE_KEY, state)
    write_report(state["lines"])

    volume_ref = {"refPath": object_path(probe)}
    query_ref = {"refPath": object_path(query_node)}
    point_ref = {"refPath": object_path(to_point_node)}

    def after_execute(error, _value):
        if error:
            finalize(state, "FAIL", f"ExecuteGraphInstance failed: {error}")
            return
        state["lines"].append("CAPTURE_EXECUTION_COMPLETE=TRUE")
        finalize(state, "PASS")

    def execute_probe():
        execute_tool(
            state,
            "ExecuteGraphInstance",
            {"pCGVolume": volume_ref},
            "EXECUTE_GRAPH_INSTANCE",
            after_execute,
        )

    def after_point_arm(error, _value):
        accepted = not error or any(token in error.lower() for token in ("inspection", "execute", "data"))
        state["lines"].append(f"TOPOINT_INSPECTION_ARM_ACCEPTED={accepted}")
        if not accepted:
            finalize(state, "FAIL", f"ToPoint inspection arm failed unexpectedly: {error}")
            return
        execute_probe()

    def arm_point():
        execute_tool(
            state,
            "GetNodeDataView",
            {
                "pCGVolume": volume_ref,
                "node": point_ref,
                "pinLabel": "Out",
                "attributeName": "",
                "startIndex": 0,
                "endIndex": 1,
            },
            "ARM_TOPOINT",
            after_point_arm,
        )

    def after_query_arm(error, _value):
        accepted = not error or any(token in error.lower() for token in ("inspection", "execute", "data"))
        state["lines"].append(f"QUERY_INSPECTION_ARM_ACCEPTED={accepted}")
        if not accepted:
            finalize(state, "FAIL", f"Query inspection arm failed unexpectedly: {error}")
            return
        arm_point()

    execute_tool(
        state,
        "GetNodeDataView",
        {
            "pCGVolume": volume_ref,
            "node": query_ref,
            "pinLabel": "Out",
            "attributeName": "",
            "startIndex": 0,
            "endIndex": 1,
        },
        "ARM_QUERY",
        after_query_arm,
    )


try:
    main()
except Exception as exc:
    lines = [
        "AETHER STAGE 15B - ENABLE TEMPORARY PROBE NODE DATA INSPECTION V2",
        "=" * 100,
        "PROBE_INSPECTION_ENABLE_V2_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "PERSISTENT_GRAPH_MODIFIED=FALSE",
        "PERSISTENT_VOLUME_MODIFIED=FALSE",
        "PACKAGES_SAVED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
    ]
    write_report(lines)
    unreal.log_error("\n".join(lines))
    raise
