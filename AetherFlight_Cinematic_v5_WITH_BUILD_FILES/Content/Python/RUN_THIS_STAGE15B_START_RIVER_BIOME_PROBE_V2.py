"""Stage 15B temporary river-biome probe launcher V2 for UE 5.8.1.

The original probe stopped safely because this UE Python build does not expose
unreal.duplicate_object. V2 patches only the transient graph-clone routine in
memory. It reconstructs a new /Engine/Transient PCGGraph using
PCGGraph.add_node_copy, rebuilds the validated 37-edge topology, and tightens
only the copied density filters.

The persistent PCG graph and full river volume remain untouched and no package
is saved.
"""

from pathlib import Path
import unreal

SOURCE_PATH = Path(__file__).with_name("RUN_THIS_STAGE15B_START_RIVER_BIOME_PROBE.py")


def replace_exact(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Stage15B probe V2 expected exactly one {label} block; found {count}"
        )
    return source.replace(old, new, 1)


def main():
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"Original Stage 15B probe is missing: {SOURCE_PATH}")

    source = SOURCE_PATH.read_text(encoding="utf-8")

    old_clone = """def duplicate_probe_graph(source_graph, lines):
    duplicate_fn = getattr(unreal, "duplicate_object", None)
    if not callable(duplicate_fn):
        raise RuntimeError("unreal.duplicate_object is unavailable; persistent graph will not be modified")
    transient_package = unreal.get_transient_package()
    duplicate = duplicate_fn(
        source_graph,
        transient_package,
        "AetherStage15B_RiverBiomeProbeGraph",
    )
    if duplicate is None:
        raise RuntimeError("Could not duplicate the validated river-biome graph into /Engine/Transient")

    density_settings = []
    for node in graph_nodes(duplicate):
        settings = node_settings(node)
        if settings is not None and type(settings).__name__ == "PCGDensityFilterSettings":
            density_settings.append(settings)

    if len(density_settings) != 4:
        raise RuntimeError(f"Expected four density filters in transient graph; found {len(density_settings)}")

    for index, (settings, minimum) in enumerate(zip(density_settings, PROBE_DENSITY_MINIMA), 1):
        safe_set(settings, ("lower_bound",), float(minimum), required=True)
        safe_set(settings, ("upper_bound",), 1.0, required=True)
        actual = safe_call(lambda settings=settings: settings.get_editor_property("lower_bound"), "UNEXPOSED")
        lines.append(f"PROBE_DENSITY_FILTER_{index}_LOWER_BOUND={actual}")

    lines.append(f"PERSISTENT_GRAPH={object_path(source_graph)}")
    lines.append(f"TRANSIENT_PROBE_GRAPH={object_path(duplicate)}")
    return duplicate
"""

    new_clone = """def _pin_label(pin):
    for property_name in ("label", "pin_label"):
        try:
            value = pin.get_editor_property(property_name)
            if value is not None:
                return str(value)
        except Exception:
            pass
    properties = safe_call(lambda: pin.get_editor_property("properties"))
    if properties is not None:
        for property_name in ("label", "pin_label"):
            try:
                value = properties.get_editor_property(property_name)
                if value is not None:
                    return str(value)
            except Exception:
                pass
    return object_path(pin)


def _pin_labels(node, property_name):
    pins = safe_call(lambda: node.get_editor_property(property_name), [])
    return [_pin_label(pin) for pin in list(pins or [])]


def _choose_pin(node, direction, candidates, reject=()):
    property_name = "output_pins" if direction == "out" else "input_pins"
    labels = _pin_labels(node, property_name)
    normalized = [(label, label.lower().replace(" ", "")) for label in labels]
    rejected = tuple(value.lower().replace(" ", "") for value in reject)

    for candidate in candidates:
        wanted = candidate.lower().replace(" ", "")
        for label, value in normalized:
            if value == wanted and not any(bad in value for bad in rejected):
                return label
    for candidate in candidates:
        wanted = candidate.lower().replace(" ", "")
        for label, value in normalized:
            if wanted in value and not any(bad in value for bad in rejected):
                return label
    for label, value in normalized:
        if not any(bad in value for bad in rejected):
            return label
    raise RuntimeError(
        f"Could not choose {direction} pin on {object_path(node)} from {labels}"
    )


def _connect_copy(source_node, target_node, source_candidates=("Out",),
                  target_candidates=("In",), source_reject=()):
    source_pin = _choose_pin(
        source_node, "out", source_candidates, reject=source_reject
    )
    target_pin = _choose_pin(target_node, "in", target_candidates)
    method = getattr(source_node, "add_edge_to", None)
    if not callable(method):
        raise RuntimeError(f"add_edge_to unavailable on {object_path(source_node)}")
    method(
        unreal.Name(source_pin),
        target_node,
        unreal.Name(target_pin),
    )
    return f"{source_pin}->{target_pin}"


def _extract_copied_node(result):
    if result is None:
        return None
    if "PCGNode" in type(result).__name__:
        return result
    if isinstance(result, tuple):
        for item in result:
            if item is not None and "PCGNode" in type(item).__name__:
                return item
    return None


def _copy_node_position(source_node, copied_node):
    getter = getattr(source_node, "get_node_position", None)
    setter = getattr(copied_node, "set_node_position", None)
    if not callable(getter) or not callable(setter):
        return False
    try:
        position = getter()
        if isinstance(position, tuple) and len(position) >= 2:
            setter(int(position[0]), int(position[1]))
        elif hasattr(position, "x") and hasattr(position, "y"):
            setter(int(position.x), int(position.y))
        else:
            return False
        return True
    except Exception:
        return False


def _edge_count(graph):
    total = 0
    accessible = False
    for node in graph_nodes(graph):
        pins = safe_call(lambda node=node: node.get_editor_property("output_pins"), [])
        for pin in list(pins or []):
            edges = safe_call(lambda pin=pin: pin.get_editor_property("edges"))
            if edges is not None:
                accessible = True
                total += len(list(edges))
    return total, accessible


def duplicate_probe_graph(source_graph, lines):
    transient_package = unreal.get_transient_package()
    duplicate = unreal.new_object(
        unreal.PCGGraph,
        outer=transient_package,
        name="AetherStage15B_RiverBiomeProbeGraph",
    )
    if duplicate is None:
        raise RuntimeError("Could not create transient PCG probe graph")

    source_nodes = graph_nodes(source_graph)
    if len(source_nodes) != 38:
        raise RuntimeError(
            f"Validated source graph should have 38 nodes; found {len(source_nodes)}"
        )

    source_density_values = []
    source_dirty_before = safe_call(
        lambda: source_graph.get_outermost().is_dirty(), False
    )
    copied_nodes = []
    copied_settings_objects = []

    add_copy = getattr(duplicate, "add_node_copy", None)
    if not callable(add_copy):
        raise RuntimeError(
            "PCGGraph.add_node_copy is unavailable; persistent graph will not be modified"
        )

    for index, source_node in enumerate(source_nodes):
        source_settings = node_settings(source_node)
        if source_settings is None:
            raise RuntimeError(f"Source node {index} has no settings")

        if type(source_settings).__name__ == "PCGDensityFilterSettings":
            source_density_values.append(
                float(source_settings.get_editor_property("lower_bound"))
            )

        try:
            result = add_copy(source_settings)
        except Exception as exc:
            raise RuntimeError(
                f"add_node_copy failed for source node {index} "
                f"({type(source_settings).__name__}): {type(exc).__name__}: {exc}"
            )

        copied_node = _extract_copied_node(result)
        if copied_node is None:
            raise RuntimeError(
                f"add_node_copy returned no PCGNode for source node {index}: {result}"
            )

        copied_settings = node_settings(copied_node)
        if copied_settings is None:
            raise RuntimeError(f"Copied node {index} has no settings")
        if copied_settings is source_settings:
            raise RuntimeError(
                f"Copied node {index} still references persistent settings; aborting"
            )

        copied_nodes.append(copied_node)
        copied_settings_objects.append(copied_settings)
        _copy_node_position(source_node, copied_node)

    # Rebuild the exact validated topology: Query -> ToPoint, then four
    # independent nine-node branches.
    edge_rows = []
    edge_rows.append(
        _connect_copy(copied_nodes[0], copied_nodes[1])
    )
    for branch_start in (2, 11, 20, 29):
        edge_rows.append(
            _connect_copy(copied_nodes[1], copied_nodes[branch_start])
        )
        edge_rows.append(
            _connect_copy(
                copied_nodes[branch_start],
                copied_nodes[branch_start + 1],
                source_candidates=("InsideFilter", "Inside Filter", "In Filter", "True", "Out"),
                source_reject=("Outside", "OutFilter", "Out Filter", "False"),
            )
        )
        edge_rows.append(
            _connect_copy(
                copied_nodes[branch_start + 1],
                copied_nodes[branch_start + 2],
                source_candidates=("InsideFilter", "Inside Filter", "In Filter", "True", "Out"),
                source_reject=("Outside", "OutFilter", "Out Filter", "False"),
            )
        )
        edge_rows.append(
            _connect_copy(
                copied_nodes[branch_start + 2],
                copied_nodes[branch_start + 3],
                source_candidates=("InsideFilter", "Inside Filter", "In Filter", "True", "Out"),
                source_reject=("Outside", "OutFilter", "Out Filter", "False"),
            )
        )
        edge_rows.append(
            _connect_copy(copied_nodes[branch_start + 3], copied_nodes[branch_start + 4])
        )
        edge_rows.append(
            _connect_copy(
                copied_nodes[branch_start + 4],
                copied_nodes[branch_start + 5],
                source_candidates=("InFilter", "In Filter", "InsideFilter", "Inside Filter", "Out"),
                source_reject=("Outside", "OutFilter", "Out Filter"),
            )
        )
        edge_rows.append(
            _connect_copy(copied_nodes[branch_start + 5], copied_nodes[branch_start + 6])
        )
        edge_rows.append(
            _connect_copy(copied_nodes[branch_start + 6], copied_nodes[branch_start + 7])
        )
        edge_rows.append(
            _connect_copy(copied_nodes[branch_start + 7], copied_nodes[branch_start + 8])
        )

    if len(edge_rows) != 37:
        raise RuntimeError(f"Transient edge plan produced {len(edge_rows)} edges, expected 37")

    copied_density_settings = [
        settings for settings in copied_settings_objects
        if type(settings).__name__ == "PCGDensityFilterSettings"
    ]
    if len(copied_density_settings) != 4:
        raise RuntimeError(
            f"Expected four copied density filters; found {len(copied_density_settings)}"
        )

    for index, (settings, minimum) in enumerate(
        zip(copied_density_settings, PROBE_DENSITY_MINIMA), 1
    ):
        safe_set(settings, ("lower_bound",), float(minimum), required=True)
        safe_set(settings, ("upper_bound",), 1.0, required=True)
        actual = float(settings.get_editor_property("lower_bound"))
        if abs(actual - float(minimum)) > 0.0000001:
            raise RuntimeError(
                f"Copied density filter {index} lower bound did not update: {actual}"
            )
        lines.append(f"PROBE_DENSITY_FILTER_{index}_LOWER_BOUND={actual}")

    # Prove that the saved graph's density values and package dirty state were
    # not changed by the transient reconstruction.
    source_density_after = [
        float(node_settings(node).get_editor_property("lower_bound"))
        for node in source_nodes
        if type(node_settings(node)).__name__ == "PCGDensityFilterSettings"
    ]
    if source_density_after != source_density_values:
        raise RuntimeError(
            f"Persistent density settings changed: before={source_density_values} "
            f"after={source_density_after}"
        )
    source_dirty_after = safe_call(
        lambda: source_graph.get_outermost().is_dirty(), False
    )
    if source_dirty_after != source_dirty_before:
        raise RuntimeError(
            f"Persistent graph dirty state changed: before={source_dirty_before} "
            f"after={source_dirty_after}"
        )

    actual_edges, edges_accessible = _edge_count(duplicate)
    if edges_accessible and actual_edges != 37:
        raise RuntimeError(
            f"Transient graph edge count is {actual_edges}, expected 37"
        )

    lines.append(f"PERSISTENT_GRAPH={object_path(source_graph)}")
    lines.append(f"PERSISTENT_GRAPH_DIRTY_BEFORE={source_dirty_before}")
    lines.append(f"PERSISTENT_GRAPH_DIRTY_AFTER={source_dirty_after}")
    lines.append(f"PERSISTENT_DENSITY_VALUES={source_density_after}")
    lines.append(f"TRANSIENT_PROBE_GRAPH={object_path(duplicate)}")
    lines.append(f"TRANSIENT_NODE_COPY_METHOD=PCGGraph.add_node_copy")
    lines.append(f"TRANSIENT_NODE_COUNT={len(copied_nodes)}")
    lines.append(
        f"TRANSIENT_EDGE_COUNT={actual_edges if edges_accessible else len(edge_rows)}"
    )
    return duplicate
"""

    source = replace_exact(
        source,
        old_clone,
        new_clone,
        "transient graph clone",
    )

    compile(source, str(SOURCE_PATH), "exec")

    unreal.log_warning("AETHER_STAGE15B_PROBE_COMPATIBILITY=V2")
    unreal.log_warning("AETHER_STAGE15B_TRANSIENT_CLONE=PCGGRAPH_ADD_NODE_COPY")
    unreal.log_warning("AETHER_STAGE15B_TRANSIENT_TOPOLOGY=38_NODES_37_EDGES")
    unreal.log_warning("AETHER_STAGE15B_PERSISTENT_GRAPH_GUARD=ENABLED")
    unreal.log_warning("AETHER_STAGE15B_PATCHED_SOURCE_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
        "__package__": None,
    }
    exec(compile(source, str(SOURCE_PATH), "exec"), namespace, namespace)


main()
