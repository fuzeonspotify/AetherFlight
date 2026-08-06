"""Guarded Stage 15B selector repair V2 for UE 5.8.1.

V1 stopped before modifying the graph because the selector Blueprint helper returns
base PCGAttributePropertySelector structs, while the PCG settings properties require
exact PCGAttributePropertyInputSelector or PCGAttributePropertyOutputSelector types.

V2 converts each verified helper result through StructBase export_text/import_text
into the exact derived selector type, proves assignability on transient settings,
then changes only the 20 saved selector fields and saves only the PCG graph asset.
"""

from pathlib import Path
from collections import Counter
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeSelectorRepairV2.txt"
GRAPH_OBJECT_PATH = "/Game/Aether/PCG/Biomes/PCG_Aether_RiverBiome.PCG_Aether_RiverBiome"
VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
PROBE_LABEL = "Aether_Stage15B_RiverBiomeProbe_UNSAVED"
EXPECTED_NODE_COUNT = 38
EXPECTED_CLASS_COUNTS = {
    "PCGAttributeFilteringSettings": 12,
    "PCGAttributeNoiseSettings": 4,
    "PCGDensityFilterSettings": 4,
    "PCGStaticMeshSpawnerSettings": 4,
    "PCGQuerySettings": 1,
    "PCGConvertToPointDataSettings": 1,
}
FILTER_CHANNELS = (
    "Wetland", "Water", "FoliageExclusion",
    "Wetland", "Water", "FoliageExclusion",
    "Grass", "Water", "FoliageExclusion",
    "Rock", "Water", "FoliageExclusion",
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
        name = safe_call(lambda: cls.get_name())
        if name:
            return str(name)
    return type(obj).__name__ if obj is not None else "NONE"


def graph_nodes(graph):
    for getter in (
        lambda: graph.get_nodes(),
        lambda: graph.get_editor_property("nodes"),
        lambda: graph.nodes,
    ):
        value = safe_call(getter)
        if value is not None:
            return [item for item in list(value) if item is not None]
    raise RuntimeError("Could not enumerate saved PCG graph nodes")


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


def package_dirty(obj):
    package = safe_call(lambda: obj.get_outermost())
    return safe_call(lambda: package.is_dirty(), False)


def helper_name(helper, selector):
    value = safe_call(lambda: helper.get_name(selector))
    return str(value) if value is not None else "UNAVAILABLE"


def helper_attribute_name(helper, selector):
    value = safe_call(lambda: helper.get_attribute_name(selector))
    return str(value) if value is not None else "UNAVAILABLE"


def helper_point_property(helper, selector):
    value = safe_call(lambda: helper.get_point_property(selector))
    return str(value) if value is not None else "UNAVAILABLE"


def export_struct(value):
    method = getattr(value, "export_text", None)
    if not callable(method):
        raise RuntimeError(f"Struct export_text unavailable on {type(value).__name__}")
    text = str(method())
    if not text:
        raise RuntimeError(f"Struct export_text returned empty text for {type(value).__name__}")
    return text


def import_exact_selector(source_selector, selector_type, expected_text, helper, kind):
    exported = export_struct(source_selector)
    exact = selector_type()
    importer = getattr(exact, "import_text", None)
    if not callable(importer):
        raise RuntimeError(f"Struct import_text unavailable on {selector_type.__name__}")
    importer(exported)

    if kind == "attribute":
        actual = helper_name(helper, exact) + " " + helper_attribute_name(helper, exact)
    else:
        actual = helper_name(helper, exact) + " " + helper_point_property(helper, exact)
    if expected_text.lower() not in actual.lower():
        raise RuntimeError(
            f"Derived selector import failed for {expected_text}: type={selector_type.__name__} "
            f"export={exported} readback={actual}"
        )
    return exact, exported, actual


def make_attribute_selector(helper, channel):
    original = unreal.PCGAttributePropertyInputSelector()
    returned = helper.set_attribute_name(original, unreal.Name(channel), True)
    source = returned if returned is not None else original
    exact, exported, actual = import_exact_selector(
        source,
        unreal.PCGAttributePropertyInputSelector,
        channel,
        helper,
        "attribute",
    )
    return exact, returned is not None, exported, actual


def make_density_selector(helper, output=False):
    selector_type = (
        unreal.PCGAttributePropertyOutputSelector
        if output else unreal.PCGAttributePropertyInputSelector
    )
    original = selector_type()
    returned = helper.set_point_property(original, unreal.PCGPointProperties.DENSITY, True)
    source = returned if returned is not None else original
    exact, exported, actual = import_exact_selector(
        source,
        selector_type,
        "Density",
        helper,
        "point",
    )
    return exact, returned is not None, exported, actual


def actor_matches(label):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return [
        actor for actor in subsystem.get_all_level_actors()
        if safe_call(lambda actor=actor: actor.get_actor_label(), "") == label
    ]


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
        count = safe_call(lambda component=component: component.get_instance_count(), 0)
        total += int(count or 0)
    return len(unique), total


def new_transient_settings(settings_type, name):
    attempts = (
        lambda: unreal.new_object(settings_type, outer=None, name=name),
        lambda: unreal.new_object(settings_type, None, name),
        lambda: unreal.new_object(settings_type),
    )
    errors = []
    for attempt in attempts:
        try:
            result = attempt()
            if result is not None:
                return result
        except Exception as exc:
            errors.append(f"{type(exc).__name__}:{exc}")
    raise RuntimeError(
        f"Could not create transient {settings_type.__name__}: " + " | ".join(errors)
    )


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_SELECTOR_REPAIR_V2_REPORT={REPORT_PATH}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before repairing Stage 15B selectors")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - RIVER BIOME SELECTOR REPAIR V2",
        "=" * 100,
        "REPAIR_SCOPE=20_SELECTOR_FIELDS_ONLY",
        "SELECTOR_CONVERSION=HELPER_BASE_EXPORT_TO_DERIVED_IMPORT",
        "LEVEL_ACTORS_MODIFIED=FALSE",
        "LEVEL_PACKAGES_SAVED=FALSE",
        "PCG_GENERATION_STARTED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
    ]

    if actor_matches(PROBE_LABEL):
        raise RuntimeError(
            f"Temporary probe actor still exists: {PROBE_LABEL}. Close without saving first"
        )

    volumes = actor_matches(VOLUME_LABEL)
    if len(volumes) != 1:
        raise RuntimeError(f"Expected exactly one {VOLUME_LABEL}; found {len(volumes)}")
    component_count, generated_instances = instance_count(volumes[0])
    lines.append(f"FULL_VOLUME_INSTANCE_COMPONENT_COUNT={component_count}")
    lines.append(f"FULL_VOLUME_INSTANCE_COUNT={generated_instances}")
    if component_count != 0 or generated_instances != 0:
        raise RuntimeError("Full river biome volume contains generated instances; refusing repair")

    graph = unreal.EditorAssetLibrary.load_asset(GRAPH_OBJECT_PATH)
    if graph is None:
        raise RuntimeError(f"Saved graph could not be loaded: {GRAPH_OBJECT_PATH}")
    dirty_before = package_dirty(graph)
    lines.append(f"GRAPH={object_path(graph)}")
    lines.append(f"GRAPH_DIRTY_BEFORE={dirty_before}")
    if dirty_before:
        raise RuntimeError("PCG graph is already dirty; close Unreal without saving and retry")

    nodes = graph_nodes(graph)
    if len(nodes) != EXPECTED_NODE_COUNT:
        raise RuntimeError(f"Graph node count {len(nodes)} != {EXPECTED_NODE_COUNT}")

    settings_by_class = {}
    counts = Counter()
    for node in nodes:
        settings = node_settings(node)
        name = class_name(settings)
        counts[name] += 1
        settings_by_class.setdefault(name, []).append(settings)

    for name, expected in EXPECTED_CLASS_COUNTS.items():
        actual = counts.get(name, 0)
        lines.append(f"CLASS_COUNT_{name}={actual}")
        if actual != expected:
            raise RuntimeError(f"{name} count {actual} != {expected}")

    helper = getattr(unreal, "PCGAttributePropertySelectorBlueprintHelpers", None)
    if helper is None:
        raise RuntimeError("PCG selector Blueprint helpers are unavailable")

    attribute_rows = []
    for index, channel in enumerate(FILTER_CHANNELS, 1):
        selector, returned, exported, actual = make_attribute_selector(helper, channel)
        attribute_rows.append((selector, returned, exported, actual))
        lines.append(
            f"PREPARED_FILTER_{index:02d}=channel:{channel} helper_returned:{returned} "
            f"type:{type(selector).__name__} export:{exported} readback:{actual}"
        )

    density_rows = []
    for index in range(1, 5):
        input_selector, input_returned, input_export, input_actual = make_density_selector(
            helper, False
        )
        output_selector, output_returned, output_export, output_actual = make_density_selector(
            helper, True
        )
        density_rows.append((input_selector, output_selector))
        lines.append(
            f"PREPARED_NOISE_{index:02d}=input_type:{type(input_selector).__name__} "
            f"output_type:{type(output_selector).__name__} "
            f"input_returned:{input_returned} output_returned:{output_returned} "
            f"input_export:{input_export} output_export:{output_export} "
            f"input_readback:{input_actual} output_readback:{output_actual}"
        )

    transient_filter = new_transient_settings(
        unreal.PCGAttributeFilteringSettings,
        "AetherStage15B_SelectorRepairV2_FilterProof",
    )
    transient_filter.set_editor_property("target_attribute", attribute_rows[0][0])
    transient_noise = new_transient_settings(
        unreal.PCGAttributeNoiseSettings,
        "AetherStage15B_SelectorRepairV2_NoiseProof",
    )
    transient_noise.set_editor_property("input_source", density_rows[0][0])
    transient_noise.set_editor_property("output_target", density_rows[0][1])
    lines.append("TRANSIENT_DERIVED_SELECTOR_ASSIGNMENT=PASS")

    filters = settings_by_class["PCGAttributeFilteringSettings"]
    noises = settings_by_class["PCGAttributeNoiseSettings"]
    repaired = 0

    for index, (settings, channel, prepared) in enumerate(
        zip(filters, FILTER_CHANNELS, attribute_rows), 1
    ):
        selector = prepared[0]
        settings.set_editor_property("target_attribute", selector)
        stored = settings.get_editor_property("target_attribute")
        stored_text = helper_name(helper, stored) + " " + helper_attribute_name(helper, stored)
        if channel.lower() not in stored_text.lower():
            raise RuntimeError(
                f"Filter {index} failed persistent readback for {channel}: {stored_text}"
            )
        repaired += 1
        lines.append(f"FILTER_{index:02d}=channel:{channel} stored:{stored_text}")

    for index, (settings, prepared) in enumerate(zip(noises, density_rows), 1):
        input_selector, output_selector = prepared
        settings.set_editor_property("input_source", input_selector)
        settings.set_editor_property("output_target", output_selector)
        stored_input = settings.get_editor_property("input_source")
        stored_output = settings.get_editor_property("output_target")
        input_text = helper_name(helper, stored_input) + " " + helper_point_property(helper, stored_input)
        output_text = helper_name(helper, stored_output) + " " + helper_point_property(helper, stored_output)
        if "density" not in input_text.lower():
            raise RuntimeError(f"Noise {index} input Density readback failed: {input_text}")
        if "density" not in output_text.lower():
            raise RuntimeError(f"Noise {index} output Density readback failed: {output_text}")
        repaired += 2
        lines.append(f"NOISE_{index:02d}=input:{input_text} output:{output_text}")

    if repaired != 20:
        raise RuntimeError(f"Selector repair count {repaired} != 20")

    dirty_after_edit = package_dirty(graph)
    lines.append(f"GRAPH_DIRTY_AFTER_EDIT={dirty_after_edit}")
    if not dirty_after_edit:
        raise RuntimeError("Graph did not become dirty after selector repair")

    saved = unreal.EditorAssetLibrary.save_asset(GRAPH_OBJECT_PATH, only_if_is_dirty=False)
    lines.append(f"GRAPH_SAVE_RETURN={saved}")
    if not saved:
        raise RuntimeError("Failed to save repaired PCG_Aether_RiverBiome graph")

    dirty_after_save = package_dirty(graph)
    lines.append(f"GRAPH_DIRTY_AFTER_SAVE={dirty_after_save}")
    if dirty_after_save:
        raise RuntimeError("Graph remains dirty after save")

    lines.extend((
        f"SELECTOR_FIELDS_REPAIRED={repaired}",
        "GRAPH_TOPOLOGY_CHANGED=FALSE",
        "FILTER_OPERATORS_CHANGED=FALSE",
        "FILTER_THRESHOLDS_CHANGED=FALSE",
        "DENSITY_GATES_CHANGED=FALSE",
        "ASSET_ROUTING_CHANGED=FALSE",
        "VOLUME_SETTINGS_CHANGED=FALSE",
        "SELECTOR_REPAIR_V2_RESULT=PASS",
        "NEXT=Rerun RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_FILTER_SEMANTICS.py before any generation.",
    ))
    write_report(lines)


try:
    main()
except Exception as exc:
    failure = "\n".join((
        "AETHER STAGE 15B - RIVER BIOME SELECTOR REPAIR V2",
        "=" * 100,
        "SELECTOR_REPAIR_V2_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "LEVEL_ACTORS_MODIFIED=FALSE",
        "LEVEL_PACKAGES_SAVED=FALSE",
        "PCG_GENERATION_STARTED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
        "ON_FAILURE=Close Unreal without saving before another repair attempt.",
    )) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(failure, encoding="utf-8")
    unreal.log_error(failure)
    raise
