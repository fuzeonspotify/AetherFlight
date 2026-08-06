"""Guarded Stage 15B repair for saved river-biome PCG selectors.

The semantic audit proved the persistent graph's 12 attribute filters remained on
@Last and the four density-noise nodes remained on @Last/@Source because the
Blueprint helper return values were discarded during installation.

This repair preserves graph topology, operators, thresholds, density gates, asset
routing, volume settings, and all generated state. It changes only:
- 12 PCGAttributeFilteringSettings.target_attribute selectors
- 4 PCGAttributeNoiseSettings.input_source selectors
- 4 PCGAttributeNoiseSettings.output_target selectors

Only PCG_Aether_RiverBiome is saved. No level actor is modified or saved, no PCG
generation is started, and no Mesh Partition build is started.
"""

from pathlib import Path
from collections import Counter
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeSelectorRepair.txt"
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
        value = safe_call(lambda: cls.get_name())
        if value:
            return str(value)
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


def make_attribute_selector(helper, channel):
    original = unreal.PCGAttributePropertyInputSelector()
    returned = helper.set_attribute_name(original, unreal.Name(channel), True)
    candidate = returned if returned is not None else original
    name = helper_name(helper, candidate)
    attribute_name = helper_attribute_name(helper, candidate)
    if channel.lower() not in (name + " " + attribute_name).lower():
        raise RuntimeError(
            f"Selector helper did not produce attribute {channel}: "
            f"name={name} attribute={attribute_name} returned={returned is not None}"
        )
    return candidate, name, attribute_name, returned is not None


def make_density_selector(helper, output=False):
    selector_type = (
        unreal.PCGAttributePropertyOutputSelector
        if output else unreal.PCGAttributePropertyInputSelector
    )
    original = selector_type()
    density = unreal.PCGPointProperties.DENSITY
    returned = helper.set_point_property(original, density, True)
    candidate = returned if returned is not None else original
    name = helper_name(helper, candidate)
    point_property = helper_point_property(helper, candidate)
    if "density" not in (name + " " + point_property).lower():
        raise RuntimeError(
            "Selector helper did not produce point Density: "
            f"name={name} point_property={point_property} output={output} "
            f"returned={returned is not None}"
        )
    return candidate, name, point_property, returned is not None


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


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_SELECTOR_REPAIR_REPORT={REPORT_PATH}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before repairing Stage 15B selectors")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - RIVER BIOME SELECTOR REPAIR",
        "=" * 100,
        "REPAIR_SCOPE=20_SELECTOR_FIELDS_ONLY",
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
    volume = volumes[0]
    component_count, generated_instances = instance_count(volume)
    lines.append(f"FULL_VOLUME_INSTANCE_COMPONENT_COUNT={component_count}")
    lines.append(f"FULL_VOLUME_INSTANCE_COUNT={generated_instances}")
    if component_count != 0 or generated_instances != 0:
        raise RuntimeError("Full river biome volume contains generated instances; refusing repair")

    graph = unreal.EditorAssetLibrary.load_asset(GRAPH_OBJECT_PATH)
    if graph is None:
        raise RuntimeError(f"Saved graph could not be loaded: {GRAPH_OBJECT_PATH}")

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

    # Prove the return-value behavior before touching persistent settings.
    probe_attribute, probe_name, probe_attr, probe_returned = make_attribute_selector(
        helper, "AetherSelectorRepairProbe"
    )
    probe_density, probe_density_name, probe_point, probe_density_returned = make_density_selector(
        helper, False
    )
    lines.append(f"TRANSIENT_ATTRIBUTE_RETURNED_VALUE={probe_returned}")
    lines.append(f"TRANSIENT_ATTRIBUTE_NAME={probe_name}")
    lines.append(f"TRANSIENT_ATTRIBUTE_ATTRIBUTE_NAME={probe_attr}")
    lines.append(f"TRANSIENT_DENSITY_RETURNED_VALUE={probe_density_returned}")
    lines.append(f"TRANSIENT_DENSITY_NAME={probe_density_name}")
    lines.append(f"TRANSIENT_DENSITY_POINT_PROPERTY={probe_point}")

    dirty_before = package_dirty(graph)
    lines.append(f"GRAPH={object_path(graph)}")
    lines.append(f"GRAPH_DIRTY_BEFORE={dirty_before}")

    filters = settings_by_class["PCGAttributeFilteringSettings"]
    noises = settings_by_class["PCGAttributeNoiseSettings"]

    repaired = 0
    for index, (settings, channel) in enumerate(zip(filters, FILTER_CHANNELS), 1):
        selector, name, attribute_name, returned = make_attribute_selector(helper, channel)
        settings.set_editor_property("target_attribute", selector)
        stored = settings.get_editor_property("target_attribute")
        stored_name = helper_name(helper, stored)
        stored_attribute = helper_attribute_name(helper, stored)
        if channel.lower() not in (stored_name + " " + stored_attribute).lower():
            raise RuntimeError(
                f"Filter {index} failed readback for {channel}: "
                f"name={stored_name} attribute={stored_attribute}"
            )
        repaired += 1
        lines.append(
            f"FILTER_{index:02d}=channel:{channel} helper_returned:{returned} "
            f"stored_name:{stored_name} stored_attribute:{stored_attribute}"
        )

    for index, settings in enumerate(noises, 1):
        input_selector, input_name, input_point, input_returned = make_density_selector(
            helper, False
        )
        output_selector, output_name, output_point, output_returned = make_density_selector(
            helper, True
        )
        settings.set_editor_property("input_source", input_selector)
        settings.set_editor_property("output_target", output_selector)

        stored_input = settings.get_editor_property("input_source")
        stored_output = settings.get_editor_property("output_target")
        stored_input_text = helper_name(helper, stored_input) + " " + helper_point_property(helper, stored_input)
        stored_output_text = helper_name(helper, stored_output) + " " + helper_point_property(helper, stored_output)
        if "density" not in stored_input_text.lower():
            raise RuntimeError(f"Noise {index} input Density readback failed: {stored_input_text}")
        if "density" not in stored_output_text.lower():
            raise RuntimeError(f"Noise {index} output Density readback failed: {stored_output_text}")

        repaired += 2
        lines.append(
            f"NOISE_{index:02d}=input:{stored_input_text} output:{stored_output_text} "
            f"input_returned:{input_returned} output_returned:{output_returned}"
        )

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
        "SELECTOR_REPAIR_RESULT=PASS",
        "NEXT=Rerun RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_FILTER_SEMANTICS.py before any generation.",
    ))
    write_report(lines)


try:
    main()
except Exception as exc:
    failure = "\n".join((
        "AETHER STAGE 15B - RIVER BIOME SELECTOR REPAIR",
        "=" * 100,
        "SELECTOR_REPAIR_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "LEVEL_ACTORS_MODIFIED=FALSE",
        "LEVEL_PACKAGES_SAVED=FALSE",
        "PCG_GENERATION_STARTED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
    )) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(failure, encoding="utf-8")
    unreal.log_error(failure)
    raise
