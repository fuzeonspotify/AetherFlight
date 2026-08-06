"""Read-only validation for the saved Stage 15B AetherWorld river biome.

Validates the persistent tutorial-style PCG graph and bounded PCG volume after a
fresh editor reload. It verifies graph node/class counts, Mesh Terrain query
channels, weighted asset routing, lightweight shrub policy, volume bounds,
generation settings, graph assignment, and absence of generated instances.

No graph, actor, component, package, PCG output, or Mesh Partition data is
modified, saved, generated, cleaned, or built.
"""

from pathlib import Path
from collections import Counter
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeValidation.txt"
GRAPH_OBJECT_PATH = "/Game/Aether/PCG/Biomes/PCG_Aether_RiverBiome.PCG_Aether_RiverBiome"
VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
EXPECTED_NODE_COUNT = 38
EXPECTED_EDGE_COUNT = 37
EXPECTED_SEED = 150015
EXPECTED_CENTER = (-720000.0, -795473.995802, 360048.552163)
EXPECTED_EXTENT = (60000.0, 33336.004198, 100200.0)
BOUNDS_TOLERANCE_CM = 150.0
EXPECTED_CHANNELS = {
    "Wetland",
    "ForestFloor",
    "Grass",
    "Rock",
    "Water",
    "FoliageExclusion",
    "Forest",
}

EXPECTED_CLASS_COUNTS = {
    "PCGQuerySettings": 1,
    "PCGConvertToPointDataSettings": 1,
    "PCGAttributeFilteringSettings": 12,
    "PCGAttributeNoiseSettings": 4,
    "PCGDensityFilterSettings": 4,
    "PCGBoundsModifierSettings": 4,
    "PCGSelfPruningSettings": 4,
    "PCGTransformPointsSettings": 4,
    "PCGStaticMeshSpawnerSettings": 4,
}

EXPECTED_MESHES = {
    # Trees
    "/Game/DZ_Assets/DZ_Trees/Meshes/Aspen/SM_Columnar_Aspen_1.SM_Columnar_Aspen_1",
    "/Game/Nanite_Plants_Sample_Collection/Geometries/SM_3DGardenPlants_Acer_buergerianum_01_003_Free.SM_3DGardenPlants_Acer_buergerianum_01_003_Free",
    "/Game/Nanite_Plants_Sample_Collection/Geometries/SM_3DGardenPlants_Acer_buergerianum_02_002_Free.SM_3DGardenPlants_Acer_buergerianum_02_002_Free",
    "/Game/DZ_Assets/DZ_Trees/Meshes/Pine/SM_Pine_1.SM_Pine_1",
    # Lightweight shrubs only
    "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_A/GV_Vol7_Shrub_A_type1_L1.GV_Vol7_Shrub_A_type1_L1",
    "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_B/GV_Vol7_Shrub_B_type1_L1.GV_Vol7_Shrub_B_type1_L1",
    "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_C/GV_Vol7_Shrub_C_type1_L1.GV_Vol7_Shrub_C_type1_L1",
    "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_D/GV_Vol7_Shrub_D_type1_L1.GV_Vol7_Shrub_D_type1_L1",
    "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_E/GV_Vol7_Shrub_E_type1_A_L1.GV_Vol7_Shrub_E_type1_A_L1",
    "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_F/GV_Vol7_Shrub_F_type1_B_L1.GV_Vol7_Shrub_F_type1_B_L1",
    # Ground cover
    "/Game/Nanite_Plants_Sample_Collection/Geometries/SM_Free_Lolium_perenne_3DGardenPlants.SM_Free_Lolium_perenne_3DGardenPlants",
    "/Game/Nanite_Plants_Sample_Collection/Geometries/SM_Free_Ophiopogon_japonicus_3DGardenPlants.SM_Free_Ophiopogon_japonicus_3DGardenPlants",
    # Rocks
    *{
        f"/Game/Rock_Collection_04/Meshes/Rock_{index:02d}/StaticMeshes/SM_Rock_{index:02d}.SM_Rock_{index:02d}"
        for index in range(1, 8)
    },
}


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


def get_property(obj, names, fallback=None):
    if obj is None:
        return fallback
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


def normalize_name(value):
    text = str(value)
    if text.startswith('Name("') and text.endswith('")'):
        text = text[6:-2]
    return text.strip('"')


def query_channels(settings):
    params = get_property(settings, ("query_params",))
    channels = get_property(params, ("channels",), [])
    return {normalize_name(value) for value in list(channels)}


def mesh_path_from_entry(entry):
    descriptor = get_property(entry, ("descriptor",))
    mesh = get_property(descriptor, ("static_mesh", "mesh"))
    if mesh is None:
        return "NONE"
    return object_path(mesh)


def spawner_meshes(settings):
    selector = get_property(settings, ("mesh_selector_parameters", "mesh_selector_instance"))
    entries = get_property(selector, ("mesh_entries", "entries"), [])
    results = []
    for entry in list(entries):
        path = mesh_path_from_entry(entry)
        weight = get_property(entry, ("weight",), "UNEXPOSED")
        results.append((path, weight))
    return results


def pin_edges(node):
    total = 0
    accessible = False
    pins = get_property(node, ("output_pins",), [])
    for pin in list(pins):
        edges = get_property(pin, ("edges",), None)
        if edges is not None:
            accessible = True
            total += len(list(edges))
    return total, accessible


def find_volume():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = []
    for actor in subsystem.get_all_level_actors():
        if safe_call(lambda actor=actor: actor.get_actor_label(), "") == VOLUME_LABEL:
            matches.append(actor)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {VOLUME_LABEL}; found {len(matches)}")
    return matches[0]


def vector_tuple(value):
    return (float(value.x), float(value.y), float(value.z))


def within_vector(actual, expected, tolerance):
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def managed_resource_count(component):
    for getter in (
        lambda: component.get_managed_resources(),
        lambda: component.get_editor_property("generated_resources"),
        lambda: component.get_editor_property("managed_resources"),
    ):
        value = safe_call(getter)
        if value is not None:
            try:
                return len(list(value)), True
            except Exception:
                pass
    return 0, False


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_RIVER_BIOME_VALIDATION_REPORT={REPORT_PATH}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running Stage 15B validation")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - RIVER BIOME GRAPH/VOLUME VALIDATION",
        "=" * 100,
        "READ_ONLY=TRUE",
        "NO_ASSETS_MODIFIED=TRUE",
        "NO_ACTORS_MODIFIED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    ]
    failures = []

    graph = unreal.EditorAssetLibrary.load_asset(GRAPH_OBJECT_PATH)
    if graph is None:
        raise RuntimeError(f"Saved graph could not be loaded: {GRAPH_OBJECT_PATH}")
    lines.append(f"GRAPH={object_path(graph)}")

    nodes = graph_nodes(graph)
    lines.append(f"GRAPH_NODE_COUNT={len(nodes)}")
    if len(nodes) != EXPECTED_NODE_COUNT:
        failures.append(f"node count {len(nodes)} != {EXPECTED_NODE_COUNT}")

    counts = Counter()
    settings_rows = []
    found_query_channels = set()
    routed_meshes = []
    total_edges = 0
    edges_accessible = False

    for index, node in enumerate(nodes):
        settings = node_settings(node)
        setting_class = class_name(settings)
        counts[setting_class] += 1
        settings_rows.append(f"NODE_{index:02d}_SETTINGS_CLASS={setting_class}")
        edge_count, accessible = pin_edges(node)
        total_edges += edge_count
        edges_accessible = edges_accessible or accessible

        if setting_class == "PCGQuerySettings":
            found_query_channels |= query_channels(settings)
        if setting_class == "PCGStaticMeshSpawnerSettings":
            routed_meshes.extend(spawner_meshes(settings))

    lines.extend(settings_rows)
    for name in sorted(EXPECTED_CLASS_COUNTS):
        actual = counts.get(name, 0)
        expected = EXPECTED_CLASS_COUNTS[name]
        lines.append(f"CLASS_COUNT_{name}={actual}")
        if actual != expected:
            failures.append(f"{name} count {actual} != {expected}")

    lines.append(f"GRAPH_EDGE_COUNT={total_edges if edges_accessible else 'UNEXPOSED'}")
    if edges_accessible and total_edges != EXPECTED_EDGE_COUNT:
        failures.append(f"edge count {total_edges} != {EXPECTED_EDGE_COUNT}")

    lines.append(f"QUERY_CHANNELS={','.join(sorted(found_query_channels))}")
    missing_channels = EXPECTED_CHANNELS - found_query_channels
    unexpected_channels = found_query_channels - EXPECTED_CHANNELS
    if missing_channels:
        failures.append(f"missing query channels: {sorted(missing_channels)}")
    if unexpected_channels:
        failures.append(f"unexpected query channels: {sorted(unexpected_channels)}")

    routed_paths = {path for path, _ in routed_meshes}
    lines.append(f"ROUTED_MESH_ENTRY_COUNT={len(routed_meshes)}")
    for index, (path, weight) in enumerate(sorted(routed_meshes), 1):
        lines.append(f"ROUTED_MESH_{index:02d}={path} weight={weight}")
    missing_meshes = EXPECTED_MESHES - routed_paths
    unexpected_meshes = routed_paths - EXPECTED_MESHES
    full_shrubs = sorted(
        path for path in routed_paths
        if "/GV_FreeShrubsPack/" in path and "_full_" in path.lower()
    )
    lines.append(f"FULL_SHRUB_MESHES={len(full_shrubs)}")
    if missing_meshes:
        failures.append(f"missing routed meshes: {sorted(missing_meshes)}")
    if unexpected_meshes:
        failures.append(f"unexpected routed meshes: {sorted(unexpected_meshes)}")
    if full_shrubs:
        failures.append(f"heavy full shrub meshes present: {full_shrubs}")
    if len(routed_meshes) != len(EXPECTED_MESHES):
        failures.append(
            f"mesh entry count {len(routed_meshes)} != {len(EXPECTED_MESHES)}"
        )

    volume = find_volume()
    lines.append(f"VOLUME={object_path(volume)}")
    lines.append(
        f"VOLUME_IS_SPATIALLY_LOADED={get_property(volume, ('is_spatially_loaded',), 'UNEXPOSED')}"
    )
    location = vector_tuple(volume.get_actor_location())
    bounds_result = volume.get_actor_bounds(False)
    origin = vector_tuple(bounds_result[0])
    extent = vector_tuple(bounds_result[1])
    scale = vector_tuple(volume.get_actor_scale3d())
    lines.append(f"VOLUME_LOCATION={location}")
    lines.append(f"VOLUME_BOUNDS_ORIGIN={origin}")
    lines.append(f"VOLUME_BOUNDS_EXTENT={extent}")
    lines.append(f"VOLUME_SCALE={scale}")
    if not within_vector(location, EXPECTED_CENTER, BOUNDS_TOLERANCE_CM):
        failures.append(f"volume location mismatch: {location}")
    if not within_vector(origin, EXPECTED_CENTER, BOUNDS_TOLERANCE_CM):
        failures.append(f"volume bounds origin mismatch: {origin}")
    if not within_vector(extent, EXPECTED_EXTENT, BOUNDS_TOLERANCE_CM):
        failures.append(f"volume bounds extent mismatch: {extent}")

    components = volume.get_components_by_class(unreal.PCGComponent)
    lines.append(f"PCG_COMPONENT_COUNT={len(components)}")
    if len(components) != 1:
        failures.append(f"PCG component count {len(components)} != 1")
    else:
        component = components[0]
        assigned_graph = safe_call(lambda: component.get_graph())
        if assigned_graph is None:
            assigned_graph = get_property(component, ("graph",))
        trigger = get_property(component, ("generation_trigger",), "UNEXPOSED")
        partitioned = get_property(
            component,
            ("is_component_partitioned", "partitioned", "is_partitioned"),
            "UNEXPOSED",
        )
        active = safe_call(lambda: component.is_active(), "UNAVAILABLE")
        seed = get_property(component, ("seed",), "UNEXPOSED")
        resources, resources_accessible = managed_resource_count(component)
        lines.append(f"PCG_COMPONENT={object_path(component)}")
        lines.append(f"PCG_ASSIGNED_GRAPH={object_path(assigned_graph)}")
        lines.append(f"PCG_GENERATION_TRIGGER={trigger}")
        lines.append(f"PCG_PARTITIONED={partitioned}")
        lines.append(f"PCG_ACTIVE={active}")
        lines.append(f"PCG_SEED={seed}")
        lines.append(
            f"PCG_MANAGED_RESOURCE_COUNT={resources if resources_accessible else 'UNEXPOSED'}"
        )
        if assigned_graph is not graph:
            failures.append("PCG component is not assigned to the saved river biome graph")
        if "GENERATE_ON_DEMAND" not in str(trigger):
            failures.append(f"generation trigger is not Generate on Demand: {trigger}")
        if partitioned is not True:
            failures.append(f"PCG component is not partitioned: {partitioned}")
        if active is not False:
            failures.append(f"PCG component is active: {active}")
        if seed != EXPECTED_SEED:
            failures.append(f"PCG seed {seed} != {EXPECTED_SEED}")
        if resources_accessible and resources != 0:
            failures.append(f"PCG managed resources already exist: {resources}")

    instance_components = []
    for component_class in (
        unreal.InstancedStaticMeshComponent,
        unreal.HierarchicalInstancedStaticMeshComponent,
    ):
        for component in volume.get_components_by_class(component_class):
            if component not in instance_components:
                instance_components.append(component)
    instance_total = 0
    for component in instance_components:
        count = safe_call(lambda component=component: component.get_instance_count(), 0)
        instance_total += int(count or 0)
    lines.append(f"VOLUME_INSTANCE_COMPONENT_COUNT={len(instance_components)}")
    lines.append(f"VOLUME_INSTANCE_COUNT={instance_total}")
    if instance_total != 0:
        failures.append(f"volume already contains {instance_total} generated instances")

    lines.append(f"VALIDATION_FAILURE_COUNT={len(failures)}")
    for index, failure in enumerate(failures, 1):
        lines.append(f"FAILURE_{index}={failure}")
    lines.append(f"VALIDATION_RESULT={'PASS' if not failures else 'FAIL'}")
    lines.append(
        "NEXT=Approve a bounded low-density generation probe only after VALIDATION_RESULT=PASS."
    )
    write_report(lines)

    if failures:
        raise RuntimeError("Stage 15B river biome validation failed; see report")


try:
    main()
except Exception as exc:
    if not REPORT_PATH.exists():
        write_report([
            "AETHER STAGE 15B - RIVER BIOME GRAPH/VOLUME VALIDATION",
            "=" * 100,
            "VALIDATION_RESULT=FAIL",
            f"ERROR={type(exc).__name__}: {exc}",
            "NO_ASSETS_MODIFIED=TRUE",
            "NO_ACTORS_MODIFIED=TRUE",
            "NO_PACKAGES_SAVED=TRUE",
            "NO_PCG_GENERATION_STARTED=TRUE",
            "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
        ])
    unreal.log_error(f"STAGE15B_VALIDATION_ERROR={type(exc).__name__}: {exc}")
    raise
