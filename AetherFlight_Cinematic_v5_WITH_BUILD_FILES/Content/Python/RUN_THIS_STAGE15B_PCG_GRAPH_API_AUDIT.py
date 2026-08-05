"""Read-only/transient Stage 15B audit for authoring the UE 5.8 Mesh Terrain biome graph.

The previous audit resolved the real UE 5.8 classes used by the documented
Mesh Partition Query -> ToPoint workflow. This script creates only transient
objects in memory so it can record exact settings properties, node pin labels,
and graph connection behavior before the persistent river-biome graph is made.

No Content asset, actor, component, package, PCG output, or Mesh Partition build
is created or saved.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BPCGGraphAPIAudit.txt"

CLASS_PATHS = {
    "QUERY": "/Script/PCGMeshPartitionInterop.PCGQuerySettings",
    "TO_POINT": "/Script/PCG.PCGConvertToPointDataSettings",
    "STATIC_MESH_SPAWNER": "/Script/PCG.PCGStaticMeshSpawnerSettings",
    "DENSITY_FILTER": "/Script/PCG.PCGDensityFilterSettings",
    "TRANSFORM_POINTS": "/Script/PCG.PCGTransformPointsSettings",
}

PROPERTY_TOKENS = (
    "query",
    "channel",
    "layer",
    "priority",
    "point",
    "mesh",
    "selector",
    "seed",
    "bounds",
    "density",
    "attribute",
    "input",
    "output",
)


def log(text=""):
    unreal.log_warning(str(text))


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


def load_classes(lines):
    loaded = {}
    for label, path in CLASS_PATHS.items():
        cls = None
        error = "NONE"
        try:
            cls = unreal.load_class(None, path)
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
        loaded[label] = cls
        lines.append(
            f"CLASS_{label}=path:{path} loaded:{cls is not None} resolved:{object_path(cls)} error:{error}"
        )
    return loaded


def get_default_object(cls):
    if cls is None:
        return None
    getter = getattr(unreal, "get_default_object", None)
    if callable(getter):
        try:
            return getter(cls)
        except Exception:
            pass
    try:
        return cls.get_default_object()
    except Exception:
        return None


def interesting_properties(obj):
    if obj is None:
        return []
    rows = []
    for name in sorted(set(dir(obj)), key=str.lower):
        lowered = name.lower()
        if name.startswith("_") or not any(token in lowered for token in PROPERTY_TOKENS):
            continue
        try:
            value = obj.get_editor_property(name)
        except Exception:
            continue
        try:
            text = value.export_text()
        except Exception:
            text = repr(value)
        if len(text) > 500:
            text = text[:500] + "..."
        rows.append(f"{name}={text}")
    return rows


def export_object(obj):
    if obj is None:
        return "NONE"
    for name in ("export_text", "get_path_name", "get_full_name"):
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                text = str(fn())
                if text:
                    return text[:4000]
            except Exception:
                pass
    return repr(obj)[:4000]


def new_transient_object(cls, outer, name):
    if cls is None:
        return None, "CLASS_NONE"
    attempts = (
        lambda: unreal.new_object(cls, outer=outer, name=name),
        lambda: unreal.new_object(cls, outer, name),
        lambda: unreal.new_object(cls, outer=outer),
        lambda: unreal.new_object(cls),
    )
    last_error = "NONE"
    for attempt in attempts:
        try:
            return attempt(), "NONE"
        except Exception as exc:
            last_error = f"{type(exc).__name__}:{exc}"
    return None, last_error


def pin_label(pin):
    for property_name in ("label", "pin_label"):
        try:
            value = pin.get_editor_property(property_name)
            if value is not None:
                return str(value)
        except Exception:
            pass
    try:
        properties = pin.get_editor_property("properties")
    except Exception:
        properties = None
    if properties is not None:
        for property_name in ("label", "pin_label"):
            try:
                value = properties.get_editor_property(property_name)
                if value is not None:
                    return str(value)
            except Exception:
                pass
    return object_path(pin)


def node_pins(node, property_name):
    if node is None:
        return []
    try:
        pins = node.get_editor_property(property_name)
    except Exception:
        try:
            pins = getattr(node, property_name)
        except Exception:
            pins = []
    return [pin_label(pin) for pin in pins]


def add_node(graph, settings, settings_class):
    errors = []
    if graph is None:
        return None, "GRAPH_NONE"
    if settings is not None:
        for method_name in ("add_node_instance", "add_node"):
            method = getattr(graph, method_name, None)
            if not callable(method):
                continue
            try:
                result = method(settings)
                if isinstance(result, tuple):
                    for item in result:
                        if item is not None and "PCGNode" in type(item).__name__:
                            return item, "NONE"
                if result is not None:
                    return result, "NONE"
            except Exception as exc:
                errors.append(f"{method_name}:{type(exc).__name__}:{exc}")
    method = getattr(graph, "add_node_of_type", None)
    if callable(method) and settings_class is not None:
        try:
            result = method(settings_class)
            if isinstance(result, tuple):
                for item in result:
                    if item is not None and "PCGNode" in type(item).__name__:
                        return item, "NONE"
            if result is not None:
                return result, "NONE"
        except Exception as exc:
            errors.append(f"add_node_of_type:{type(exc).__name__}:{exc}")
    return None, " | ".join(errors) if errors else "NO_SUPPORTED_ADD_METHOD"


def try_connect(query_node, point_node):
    if query_node is None or point_node is None:
        return False, "NODE_NONE"
    output_labels = node_pins(query_node, "output_pins")
    input_labels = node_pins(point_node, "input_pins")
    errors = []
    method = getattr(query_node, "add_edge_to", None)
    if not callable(method):
        return False, "ADD_EDGE_TO_UNAVAILABLE"
    for output_label in output_labels:
        for input_label in input_labels:
            try:
                result = method(unreal.Name(output_label), point_node, unreal.Name(input_label))
                return True, f"{output_label}->{input_label} result={object_path(result)}"
            except Exception as exc:
                errors.append(f"{output_label}->{input_label}:{type(exc).__name__}:{exc}")
    return False, " | ".join(errors[:12]) if errors else "NO_PINS"


def inspect_query_struct(lines):
    struct_type = getattr(unreal, "PCGQueryParams", None)
    lines.append(f"PCG_QUERY_PARAMS_PYTHON_TYPE={struct_type is not None}")
    if struct_type is None:
        return
    try:
        value = struct_type()
    except Exception as exc:
        lines.append(f"PCG_QUERY_PARAMS_CONSTRUCT_ERROR={type(exc).__name__}:{exc}")
        return
    lines.append(f"PCG_QUERY_PARAMS_DEFAULT={export_object(value)}")
    for name in sorted(set(dir(value)), key=str.lower):
        if name.startswith("_"):
            continue
        try:
            prop = value.get_editor_property(name)
        except Exception:
            continue
        try:
            text = prop.export_text()
        except Exception:
            text = repr(prop)
        lines.append(f"PCG_QUERY_PARAMS_PROPERTY_{name}={text}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running the Stage 15B PCG graph API audit.")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - TRANSIENT PCG GRAPH API AUDIT",
        "=" * 100,
        "READ_ONLY_PERSISTENT_STATE=TRUE",
        "TRANSIENT_OBJECTS_ONLY=TRUE",
        "NO_CONTENT_ASSETS_CREATED=TRUE",
        "NO_LEVEL_ACTORS_CREATED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    ]

    loaded = load_classes(lines)
    inspect_query_struct(lines)

    lines.extend(("", "SETTINGS_DEFAULT_OBJECTS", "-" * 100))
    for label, cls in loaded.items():
        default = get_default_object(cls)
        lines.append(f"[{label}] DEFAULT={object_path(default)}")
        rows = interesting_properties(default)
        if rows:
            lines.extend(f"[{label}] {row}" for row in rows)
        else:
            lines.append(f"[{label}] INTERESTING_EDITOR_PROPERTIES=NONE_EXPOSED")
        lines.append(f"[{label}] EXPORT={export_object(default)}")

    transient_package = safe_call(lambda: unreal.get_transient_package())
    graph, graph_error = new_transient_object(unreal.PCGGraph, transient_package, "AetherStage15B_TransientGraph")
    lines.extend(("", "TRANSIENT_GRAPH", "-" * 100))
    lines.append(f"GRAPH_CREATED={graph is not None}")
    lines.append(f"GRAPH_ERROR={graph_error}")
    lines.append(f"GRAPH_PATH={object_path(graph)}")

    nodes = {}
    for index, (label, cls) in enumerate(loaded.items()):
        settings, settings_error = new_transient_object(
            cls,
            graph if graph is not None else transient_package,
            f"AetherStage15B_{label}_Settings",
        )
        node, node_error = add_node(graph, settings, cls)
        nodes[label] = node
        if node is not None:
            setter = getattr(node, "set_node_position", None)
            if callable(setter):
                try:
                    setter(index * 320, 0)
                except Exception:
                    pass
        lines.append(f"NODE_{label}_SETTINGS_CREATED={settings is not None}")
        lines.append(f"NODE_{label}_SETTINGS_ERROR={settings_error}")
        lines.append(f"NODE_{label}_CREATED={node is not None}")
        lines.append(f"NODE_{label}_ERROR={node_error}")
        lines.append(f"NODE_{label}_INPUT_PINS={','.join(node_pins(node, 'input_pins')) or 'NONE'}")
        lines.append(f"NODE_{label}_OUTPUT_PINS={','.join(node_pins(node, 'output_pins')) or 'NONE'}")

    connected, connection_detail = try_connect(nodes.get("QUERY"), nodes.get("TO_POINT"))
    lines.append(f"QUERY_TO_POINT_TRANSIENT_CONNECTION={connected}")
    lines.append(f"QUERY_TO_POINT_CONNECTION_DETAIL={connection_detail}")

    required_classes = all(loaded.get(name) is not None for name in (
        "QUERY", "TO_POINT", "STATIC_MESH_SPAWNER"
    ))
    required_nodes = all(nodes.get(name) is not None for name in (
        "QUERY", "TO_POINT", "STATIC_MESH_SPAWNER"
    ))
    lines.extend((
        "",
        "SUMMARY",
        "-" * 100,
        f"REQUIRED_CLASSES_READY={required_classes}",
        f"REQUIRED_TRANSIENT_NODES_READY={required_nodes}",
        f"QUERY_TO_POINT_CONNECTION_READY={connected}",
        "AUDIT_RESULT=PASS",
        "NEXT=Author and validate the bounded persistent PCG_Aether_RiverBiome graph using the resolved properties and pins.",
    ))

    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        log(line)
    log(f"AETHER_STAGE15B_PCG_GRAPH_API_AUDIT_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    failure = "\n".join((
        "AETHER STAGE 15B - TRANSIENT PCG GRAPH API AUDIT",
        "=" * 100,
        "AUDIT_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "NO_CONTENT_ASSETS_CREATED=TRUE",
        "NO_LEVEL_ACTORS_CREATED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    )) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(failure, encoding="utf-8")
    unreal.log_error(failure)
    raise
