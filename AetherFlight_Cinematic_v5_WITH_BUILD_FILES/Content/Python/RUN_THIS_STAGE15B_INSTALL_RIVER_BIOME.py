"""Guarded Stage 15B installer for the bounded AetherWorld river biome PCG graph.

This creates and saves the persistent PCG_Aether_RiverBiome graph plus one bounded
PCG Volume around the Stage 09 river spline. It follows the UE 5.8 Mesh Terrain
workflow: Mesh Partition Query -> ToPoint -> channel filters -> density/spacing ->
weighted Static Mesh Spawners.

The installer deliberately does NOT generate the PCG component and does NOT start
a Mesh Partition build. A later validation step must approve the graph and volume
before any foliage instances are spawned.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeInstall.txt"
GRAPH_PACKAGE_PATH = "/Game/Aether/PCG/Biomes/PCG_Aether_RiverBiome"
GRAPH_OBJECT_PATH = GRAPH_PACKAGE_PATH + ".PCG_Aether_RiverBiome"
GRAPH_FOLDER = "/Game/Aether/PCG/Biomes"
GRAPH_NAME = "PCG_Aether_RiverBiome"
VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
MESH_TERRAIN_LABEL = "MeshTerrain_AetherWorld"
SEED_BASE = 150015
XY_MARGIN_CM = 15000.0
Z_MARGIN_CM = 100000.0
SPLINE_SAMPLES = 65

QUERY_CHANNELS = (
    "Wetland",
    "ForestFloor",
    "Grass",
    "Rock",
    "Water",
    "FoliageExclusion",
    "Forest",
)

TREE_MESHES = (
    ("/Game/DZ_Assets/DZ_Trees/Meshes/Aspen/SM_Columnar_Aspen_1.SM_Columnar_Aspen_1", 4),
    ("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_3DGardenPlants_Acer_buergerianum_01_003_Free.SM_3DGardenPlants_Acer_buergerianum_01_003_Free", 3),
    ("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_3DGardenPlants_Acer_buergerianum_02_002_Free.SM_3DGardenPlants_Acer_buergerianum_02_002_Free", 3),
    ("/Game/DZ_Assets/DZ_Trees/Meshes/Pine/SM_Pine_1.SM_Pine_1", 1),
)

SHRUB_MESHES = (
    ("/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_A/GV_Vol7_Shrub_A_full_type1.GV_Vol7_Shrub_A_full_type1", 2),
    ("/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_B/GV_Vol7_Shrub_B_full_type1.GV_Vol7_Shrub_B_full_type1", 2),
    ("/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_C/GV_Vol7_Shrub_C_full_type1.GV_Vol7_Shrub_C_full_type1", 2),
    ("/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_D/GV_Vol7_Shrub_D_full_type1.GV_Vol7_Shrub_D_full_type1", 2),
    ("/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_E/GV_Vol7_Shrub_E_full_type1_A.GV_Vol7_Shrub_E_full_type1_A", 1),
    ("/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_F/GV_Vol7_Shrub_F_full_type1_B.GV_Vol7_Shrub_F_full_type1_B", 1),
)

GROUND_MESHES = (
    ("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_Free_Lolium_perenne_3DGardenPlants.SM_Free_Lolium_perenne_3DGardenPlants", 3),
    ("/Game/Nanite_Plants_Sample_Collection/Geometries/SM_Free_Ophiopogon_japonicus_3DGardenPlants.SM_Free_Ophiopogon_japonicus_3DGardenPlants", 2),
)

ROCK_MESHES = tuple(
    (f"/Game/Rock_Collection_04/Meshes/Rock_{index:02d}/StaticMeshes/SM_Rock_{index:02d}.SM_Rock_{index:02d}", 1)
    for index in range(1, 8)
)

BRANCHES = (
    {
        "name": "Trees",
        "include_channel": "Wetland",
        "include_min": 0.12,
        "density_min": 0.996,
        "seed": 150101,
        "bounds_half": 1000.0,
        "scale": (0.85, 1.20),
        "rotation": ((0.0, 0.0), (0.0, 360.0), (0.0, 0.0)),
        "meshes": TREE_MESHES,
        "cull": (30000, 300000),
        "shadow": True,
    },
    {
        "name": "Shrubs",
        "include_channel": "Wetland",
        "include_min": 0.08,
        "density_min": 0.985,
        "seed": 150201,
        "bounds_half": 300.0,
        "scale": (0.75, 1.25),
        "rotation": ((0.0, 0.0), (0.0, 360.0), (0.0, 0.0)),
        "meshes": SHRUB_MESHES,
        "cull": (10000, 120000),
        "shadow": True,
    },
    {
        "name": "GroundCover",
        "include_channel": "Grass",
        "include_min": 0.08,
        "density_min": 0.960,
        "seed": 150301,
        "bounds_half": 70.0,
        "scale": (0.65, 1.15),
        "rotation": ((0.0, 0.0), (0.0, 360.0), (0.0, 0.0)),
        "meshes": GROUND_MESHES,
        "cull": (3000, 45000),
        "shadow": False,
    },
    {
        "name": "Rocks",
        "include_channel": "Rock",
        "include_min": 0.10,
        "density_min": 0.995,
        "seed": 150401,
        "bounds_half": 600.0,
        "scale": (0.65, 1.25),
        "rotation": ((-8.0, 8.0), (0.0, 360.0), (-8.0, 8.0)),
        "meshes": ROCK_MESHES,
        "cull": (20000, 220000),
        "shadow": True,
    },
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
    for fn in (lambda: obj.get_path_name(), lambda: obj.get_full_name(), lambda: str(obj)):
        value = safe_call(fn)
        if value:
            return str(value)
    return "UNKNOWN"


def safe_set(obj, names, value, required=False):
    errors = []
    for name in names:
        try:
            obj.set_editor_property(name, value)
            return name
        except Exception as exc:
            errors.append(f"{name}:{type(exc).__name__}:{exc}")
        try:
            setattr(obj, name, value)
            return name
        except Exception as exc:
            errors.append(f"{name}:{type(exc).__name__}:{exc}")
    if required:
        raise RuntimeError(
            f"Could not set {type(obj).__name__} property candidates {names}: "
            + " | ".join(errors[:8])
        )
    return None


def enum_value(enum_type, candidates, required=True):
    if enum_type is None:
        if required:
            raise RuntimeError(f"Enum unavailable for {candidates}")
        return None
    for candidate in candidates:
        value = getattr(enum_type, candidate, None)
        if value is not None:
            return value
    normalized = {name.replace("_", "").lower(): name for name in dir(enum_type)}
    for candidate in candidates:
        name = normalized.get(candidate.replace("_", "").lower())
        if name:
            return getattr(enum_type, name)
    if required:
        raise RuntimeError(f"Could not resolve enum {enum_type} from {candidates}")
    return None


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


def node_pin_labels(node, property_name):
    try:
        pins = node.get_editor_property(property_name)
    except Exception:
        pins = []
    return [pin_label(pin) for pin in pins]


def choose_pin(node, direction, candidates, reject=()):
    property_name = "output_pins" if direction == "out" else "input_pins"
    labels = node_pin_labels(node, property_name)
    lower = [(label, label.lower()) for label in labels]
    for candidate in candidates:
        needle = candidate.lower()
        for label, normalized in lower:
            if normalized == needle and not any(bad.lower() in normalized for bad in reject):
                return label
    for candidate in candidates:
        needle = candidate.lower()
        for label, normalized in lower:
            if needle in normalized and not any(bad.lower() in normalized for bad in reject):
                return label
    for label, normalized in lower:
        if not any(bad.lower() in normalized for bad in reject):
            return label
    raise RuntimeError(f"Could not select {direction} pin from {labels} on {object_path(node)}")


def connect(source, target, source_candidates=("Out",), target_candidates=("In",), source_reject=()):
    source_pin = choose_pin(source, "out", source_candidates, source_reject)
    target_pin = choose_pin(target, "in", target_candidates)
    method = getattr(source, "add_edge_to", None)
    if not callable(method):
        raise RuntimeError(f"add_edge_to unavailable on {object_path(source)}")
    result = method(unreal.Name(source_pin), target, unreal.Name(target_pin))
    return f"{source_pin}->{target_pin} ({object_path(result)})"


def create_settings(graph, settings_class, name):
    attempts = (
        lambda: unreal.new_object(settings_class, outer=graph, name=name),
        lambda: unreal.new_object(settings_class, graph, name),
        lambda: unreal.new_object(settings_class, outer=graph),
    )
    errors = []
    for attempt in attempts:
        try:
            value = attempt()
            if value is not None:
                return value
        except Exception as exc:
            errors.append(f"{type(exc).__name__}:{exc}")
    raise RuntimeError(f"Could not create settings {name}: {' | '.join(errors)}")


def add_node(graph, settings, x, y, title):
    errors = []
    node = None
    for method_name in ("add_node_instance", "add_node"):
        method = getattr(graph, method_name, None)
        if not callable(method):
            continue
        try:
            result = method(settings)
            if isinstance(result, tuple):
                node = next((item for item in result if item is not None and "PCGNode" in type(item).__name__), None)
            elif result is not None:
                node = result
            if node is not None:
                break
        except Exception as exc:
            errors.append(f"{method_name}:{type(exc).__name__}:{exc}")
    if node is None:
        raise RuntimeError(f"Could not add PCG node {title}: {' | '.join(errors)}")
    setter = getattr(node, "set_node_position", None)
    if callable(setter):
        try:
            setter(int(x), int(y))
        except Exception:
            pass
    return node


def load_required_class(path):
    value = unreal.load_class(None, path)
    if value is None:
        raise RuntimeError(f"Required class did not load: {path}")
    return value


def selector_for_attribute(name):
    selector = unreal.PCGAttributePropertyInputSelector()
    if not selector.set_attribute_name(unreal.Name(name)):
        raise RuntimeError(f"Could not select attribute {name}")
    return selector


def selector_for_density(output=False):
    selector_type = unreal.PCGAttributePropertyOutputSelector if output else unreal.PCGAttributePropertyInputSelector
    selector = selector_type()
    density = enum_value(unreal.PCGPointProperties, ("DENSITY",))
    if not selector.set_point_property(density):
        raise RuntimeError("Could not select PCG point Density property")
    return selector


def float_constant(value):
    constant = unreal.PCGMetadataTypesConstantStruct()
    metadata_float = enum_value(unreal.PCGMetadataTypes, ("FLOAT", "DOUBLE"))
    safe_set(constant, ("type",), metadata_float, required=True)
    if safe_set(constant, ("float_value", "double_value"), float(value), required=False) is None:
        raise RuntimeError("Could not set PCG float constant value")
    return constant


def make_attribute_filter(graph, channel, operator_kind, threshold, name, x, y):
    settings = create_settings(graph, unreal.PCGAttributeFilteringSettings, f"{name}_Settings")
    safe_set(settings, ("target_attribute",), selector_for_attribute(channel), required=True)
    safe_set(settings, ("use_constant_threshold",), True, required=True)
    safe_set(settings, ("attribute_types",), float_constant(threshold), required=True)
    if operator_kind == "ge":
        operator = enum_value(
            unreal.PCGAttributeFilterOperator,
            ("GREATER_OR_EQUAL", "GREATER_THAN_OR_EQUAL", "GREATER_EQUAL", "GREATER"),
        )
    else:
        operator = enum_value(
            unreal.PCGAttributeFilterOperator,
            ("LESS_OR_EQUAL", "LESS_THAN_OR_EQUAL", "LESS_EQUAL", "LESS"),
        )
    safe_set(settings, ("operator",), operator, required=True)
    safe_set(settings, ("warn_on_data_missing_attribute",), True, required=False)
    return add_node(graph, settings, x, y, name)


def make_density_noise(graph, branch, x, y):
    settings = create_settings(graph, unreal.PCGAttributeNoiseSettings, f"{branch['name']}_DensityNoise_Settings")
    safe_set(settings, ("input_source",), selector_for_density(False), required=True)
    safe_set(settings, ("output_target",), selector_for_density(True), required=True)
    mode = enum_value(unreal.PCGAttributeNoiseMode, ("SET", "REPLACE"))
    safe_set(settings, ("mode",), mode, required=True)
    safe_set(settings, ("noise_min",), 0.0, required=True)
    safe_set(settings, ("noise_max",), 1.0, required=True)
    safe_set(settings, ("clamp_result",), True, required=False)
    safe_set(settings, ("seed",), int(branch["seed"]), required=True)
    return add_node(graph, settings, x, y, f"{branch['name']} Deterministic Density")


def make_density_filter(graph, branch, x, y):
    settings = create_settings(graph, unreal.PCGDensityFilterSettings, f"{branch['name']}_DensityFilter_Settings")
    safe_set(settings, ("lower_bound",), float(branch["density_min"]), required=True)
    safe_set(settings, ("upper_bound",), 1.0, required=True)
    safe_set(settings, ("invert_filter",), False, required=False)
    safe_set(settings, ("normalize_output_density",), False, required=False)
    safe_set(settings, ("keep_zero_density_points",), False, required=False)
    return add_node(graph, settings, x, y, f"{branch['name']} Density Gate")


def make_bounds_modifier(graph, branch, x, y):
    settings = create_settings(graph, unreal.PCGBoundsModifierSettings, f"{branch['name']}_Bounds_Settings")
    half = float(branch["bounds_half"])
    mode = enum_value(unreal.PCGBoundsModifierMode, ("SET", "REPLACE"))
    safe_set(settings, ("mode",), mode, required=True)
    safe_set(settings, ("bounds_min",), unreal.Vector(-half, -half, -half), required=True)
    safe_set(settings, ("bounds_max",), unreal.Vector(half, half, half), required=True)
    return add_node(graph, settings, x, y, f"{branch['name']} Spacing Bounds")


def make_self_pruning(graph, branch, x, y):
    settings = create_settings(graph, unreal.PCGSelfPruningSettings, f"{branch['name']}_Prune_Settings")
    pruning_type = enum_value(unreal.PCGSelfPruningType, ("ALL_EQUAL", "LARGE_TO_SMALL", "SMALL_TO_LARGE"))
    params = unreal.PCGSelfPruningParameters()
    safe_set(params, ("pruning_type",), pruning_type, required=True)
    safe_set(params, ("randomized_pruning",), True, required=False)
    safe_set(settings, ("parameters",), params, required=True)
    safe_set(settings, ("seed",), int(branch["seed"] + 7), required=False)
    return add_node(graph, settings, x, y, f"{branch['name']} Self Prune")


def make_transform(graph, branch, x, y):
    settings = create_settings(graph, unreal.PCGTransformPointsSettings, f"{branch['name']}_Transform_Settings")
    scale_min, scale_max = branch["scale"]
    pitch, yaw, roll = branch["rotation"]
    safe_set(settings, ("offset_min",), unreal.Vector(0.0, 0.0, 0.0), required=True)
    safe_set(settings, ("offset_max",), unreal.Vector(0.0, 0.0, 0.0), required=True)
    safe_set(settings, ("rotation_min",), unreal.Rotator(pitch[0], yaw[0], roll[0]), required=True)
    safe_set(settings, ("rotation_max",), unreal.Rotator(pitch[1], yaw[1], roll[1]), required=True)
    safe_set(settings, ("scale_min",), unreal.Vector(scale_min, scale_min, scale_min), required=True)
    safe_set(settings, ("scale_max",), unreal.Vector(scale_max, scale_max, scale_max), required=True)
    safe_set(settings, ("uniform_scale",), True, required=True)
    safe_set(settings, ("recompute_seed",), True, required=False)
    safe_set(settings, ("seed",), int(branch["seed"] + 13), required=True)
    return add_node(graph, settings, x, y, f"{branch['name']} Variation")


def configure_descriptor(mesh, branch):
    descriptor = unreal.PCGSoftISMComponentDescriptor()
    safe_set(descriptor, ("static_mesh",), mesh, required=True)
    safe_set(descriptor, ("mobility",), unreal.ComponentMobility.STATIC, required=False)
    safe_set(descriptor, ("can_ever_affect_navigation",), False, required=False)
    safe_set(descriptor, ("generate_overlap_events",), False, required=False)
    safe_set(descriptor, ("use_default_collision",), False, required=False)
    safe_set(descriptor, ("cast_shadow",), bool(branch["shadow"]), required=False)
    safe_set(descriptor, ("cast_dynamic_shadow",), bool(branch["shadow"]), required=False)
    safe_set(descriptor, ("cast_static_shadow",), bool(branch["shadow"]), required=False)
    safe_set(descriptor, ("affect_distance_field_lighting",), branch["name"] == "Rocks", required=False)
    safe_set(descriptor, ("enable_density_scaling",), branch["name"] in ("Shrubs", "GroundCover"), required=False)
    safe_set(descriptor, ("instance_start_cull_distance",), int(branch["cull"][0]), required=False)
    safe_set(descriptor, ("instance_end_cull_distance",), int(branch["cull"][1]), required=False)
    safe_set(descriptor, ("component_tags",), [unreal.Name(f"AetherBiome_{branch['name']}")], required=False)

    body_instance = safe_call(lambda: descriptor.get_editor_property("body_instance"))
    if body_instance is not None:
        collision_enabled = enum_value(
            getattr(unreal, "CollisionEnabled", None),
            ("NO_COLLISION",),
            required=False,
        )
        if collision_enabled is not None:
            safe_set(body_instance, ("collision_enabled",), collision_enabled, required=False)
    return descriptor


def make_spawner(graph, branch, x, y, lines):
    settings = create_settings(graph, unreal.PCGStaticMeshSpawnerSettings, f"{branch['name']}_Spawner_Settings")
    weighted_class = getattr(unreal, "PCGMeshSelectorWeighted", None)
    if weighted_class is None:
        weighted_class = load_required_class("/Script/PCG.PCGMeshSelectorWeighted")
    setter = getattr(settings, "set_mesh_selector_type", None)
    if not callable(setter):
        raise RuntimeError("PCGStaticMeshSpawnerSettings.set_mesh_selector_type is unavailable")
    setter(weighted_class)
    selector = settings.get_editor_property("mesh_selector_parameters")
    if selector is None:
        raise RuntimeError(f"Weighted selector was not created for {branch['name']}")

    entries = []
    for mesh_path, weight in branch["meshes"]:
        mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
        if mesh is None:
            raise RuntimeError(f"Required {branch['name']} mesh is missing: {mesh_path}")
        entry = unreal.PCGMeshSelectorWeightedEntry()
        safe_set(entry, ("weight",), int(weight), required=True)
        safe_set(entry, ("descriptor",), configure_descriptor(mesh, branch), required=True)
        entries.append(entry)
        lines.append(f"{branch['name'].upper()}_MESH={mesh_path} weight={weight}")

    if safe_set(selector, ("mesh_entries", "entries"), entries, required=False) is None:
        raise RuntimeError(f"Could not assign weighted mesh entries for {branch['name']}")
    safe_set(settings, ("apply_mesh_bounds_to_points",), True, required=False)
    safe_set(settings, ("allow_merge_different_data_in_same_instanced_components",), True, required=False)
    safe_set(settings, ("synchronous_load",), False, required=False)
    safe_set(settings, ("seed",), int(branch["seed"] + 19), required=True)
    return add_node(graph, settings, x, y, f"Spawn {branch['name']}")


def find_level_actor(label):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = []
    for actor in subsystem.get_all_level_actors():
        try:
            if actor.get_actor_label() == label:
                matches.append(actor)
        except Exception:
            pass
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one actor labelled {label}; found {len(matches)}")
    return matches[0]


def find_spline_component(actor):
    components = actor.get_components_by_class(unreal.SplineComponent)
    if len(components) != 1:
        raise RuntimeError(f"Expected exactly one spline component on {SPLINE_LABEL}; found {len(components)}")
    return components[0]


def spline_volume_bounds(spline):
    length = float(spline.get_spline_length())
    if length <= 0.0:
        raise RuntimeError("River spline length is zero")
    world_space = unreal.SplineCoordinateSpace.WORLD
    points = []
    for index in range(SPLINE_SAMPLES):
        distance = length * index / float(SPLINE_SAMPLES - 1)
        points.append(spline.get_location_at_distance_along_spline(distance, world_space))
    min_x = min(float(p.x) for p in points) - XY_MARGIN_CM
    max_x = max(float(p.x) for p in points) + XY_MARGIN_CM
    min_y = min(float(p.y) for p in points) - XY_MARGIN_CM
    max_y = max(float(p.y) for p in points) + XY_MARGIN_CM
    min_z = min(float(p.z) for p in points) - Z_MARGIN_CM
    max_z = max(float(p.z) for p in points) + Z_MARGIN_CM
    center = unreal.Vector((min_x + max_x) * 0.5, (min_y + max_y) * 0.5, (min_z + max_z) * 0.5)
    extent = unreal.Vector((max_x - min_x) * 0.5, (max_y - min_y) * 0.5, (max_z - min_z) * 0.5)
    return length, points, center, extent


def actor_bounds(actor):
    result = actor.get_actor_bounds(False)
    if not isinstance(result, tuple) or len(result) < 2:
        raise RuntimeError(f"Unexpected get_actor_bounds result: {result}")
    return result[0], result[1]


def create_volume(center, desired_extent, graph, lines):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(unreal.PCGVolume, center, unreal.Rotator())
    if actor is None:
        raise RuntimeError("Could not spawn PCGVolume")
    actor.set_actor_label(VOLUME_LABEL)
    safe_set(actor, ("is_spatially_loaded",), False, required=False)

    _, initial_extent = actor_bounds(actor)
    values = (float(initial_extent.x), float(initial_extent.y), float(initial_extent.z))
    if min(values) <= 0.01:
        raise RuntimeError(f"PCGVolume default bounds are invalid: {initial_extent}")
    scale = unreal.Vector(
        float(desired_extent.x) / values[0],
        float(desired_extent.y) / values[1],
        float(desired_extent.z) / values[2],
    )
    actor.set_actor_scale3d(scale)
    actor.set_actor_location(center, False, False)

    component = safe_call(lambda: actor.get_editor_property("pcg_component"))
    if component is None:
        components = actor.get_components_by_class(unreal.PCGComponent)
        component = components[0] if components else None
    if component is None:
        raise RuntimeError("Spawned PCGVolume has no PCGComponent")

    set_active = getattr(component, "set_active", None)
    if callable(set_active):
        try:
            set_active(False, False)
        except TypeError:
            try:
                set_active(False)
            except Exception:
                pass
        except Exception:
            pass

    trigger_enum = getattr(unreal, "PCGComponentGenerationTrigger", None)
    on_demand = enum_value(
        trigger_enum,
        ("GENERATE_ON_DEMAND", "ON_DEMAND"),
        required=True,
    )
    safe_set(component, ("generation_trigger",), on_demand, required=True)

    graph_set = False
    for method_name in ("set_graph", "set_graph_local"):
        method = getattr(component, method_name, None)
        if callable(method):
            try:
                method(graph)
                graph_set = True
                break
            except Exception:
                pass
    if not graph_set:
        graph_set = safe_set(component, ("graph",), graph, required=False) is not None
    if not graph_set:
        raise RuntimeError("Could not assign PCG graph to PCGVolume")

    partitioned_set = False
    for method_name in ("set_is_partitioned", "set_partitioned"):
        method = getattr(component, method_name, None)
        if callable(method):
            try:
                method(True)
                partitioned_set = True
                break
            except Exception:
                pass
    if not partitioned_set:
        partitioned_set = safe_set(
            component,
            ("is_component_partitioned", "partitioned", "is_partitioned"),
            True,
            required=False,
        ) is not None
    if not partitioned_set:
        raise RuntimeError("Could not enable partitioned generation on PCGComponent")

    safe_set(component, ("seed",), SEED_BASE, required=False)
    safe_set(component, ("regenerate_in_editor",), False, required=False)

    bounds_origin, bounds_extent = actor_bounds(actor)
    tolerance = 100.0
    if (
        float(bounds_extent.x) + tolerance < float(desired_extent.x)
        or float(bounds_extent.y) + tolerance < float(desired_extent.y)
        or float(bounds_extent.z) + tolerance < float(desired_extent.z)
    ):
        raise RuntimeError(
            f"PCGVolume bounds did not reach requested extent. actual={bounds_extent} requested={desired_extent}"
        )

    lines.append(f"VOLUME_CENTER={center}")
    lines.append(f"VOLUME_REQUESTED_EXTENT={desired_extent}")
    lines.append(f"VOLUME_ACTUAL_ORIGIN={bounds_origin}")
    lines.append(f"VOLUME_ACTUAL_EXTENT={bounds_extent}")
    lines.append(f"VOLUME_SCALE={scale}")
    lines.append(f"PCG_COMPONENT={object_path(component)}")
    lines.append(f"PCG_PARTITIONED_SET={partitioned_set}")
    lines.append(f"PCG_GENERATION_TRIGGER={safe_call(lambda: component.get_editor_property('generation_trigger'), 'UNEXPOSED')}")
    return actor, component


def create_graph(lines):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.PCGGraphFactory()
    graph = asset_tools.create_asset(GRAPH_NAME, GRAPH_FOLDER, unreal.PCGGraph, factory)
    if graph is None:
        raise RuntimeError(f"Could not create PCG graph asset {GRAPH_OBJECT_PATH}")

    query_class = load_required_class("/Script/PCGMeshPartitionInterop.PCGQuerySettings")
    to_point_class = load_required_class("/Script/PCG.PCGConvertToPointDataSettings")

    query_settings = create_settings(graph, query_class, "Aether_River_Query_Settings")
    params = unreal.PCGQueryParams()
    query_final = enum_value(unreal.PCGQueryType, ("FINAL",))
    safe_set(params, ("query_type",), query_final, required=True)
    safe_set(params, ("inclusive",), False, required=True)
    safe_set(params, ("recompute_vertex_normals",), True, required=True)
    safe_set(params, ("accept_any_hit_section",), True, required=True)
    safe_set(params, ("channels",), [unreal.Name(value) for value in QUERY_CHANNELS], required=True)
    safe_set(query_settings, ("query_params",), params, required=True)
    safe_set(query_settings, ("seed",), SEED_BASE, required=True)
    query_node = add_node(graph, query_settings, 0, 0, "Mesh Terrain Query - River Channels")

    to_point_settings = create_settings(graph, to_point_class, "Aether_River_ToPoint_Settings")
    safe_set(to_point_settings, ("match_attribute_names_with_property_names",), False, required=False)
    safe_set(to_point_settings, ("delete_original_remapped_attribute",), False, required=False)
    to_point_node = add_node(graph, to_point_settings, 330, 0, "Mesh Terrain ToPoint")
    query_to_point = connect(query_node, to_point_node)
    lines.append(f"QUERY_TO_POINT={query_to_point}")

    branch_nodes = {}
    for branch_index, branch in enumerate(BRANCHES):
        y = (branch_index - 1.5) * 650
        x = 680
        include = make_attribute_filter(
            graph,
            branch["include_channel"],
            "ge",
            branch["include_min"],
            f"{branch['name']} {branch['include_channel']} Include",
            x,
            y,
        )
        lines.append(f"{branch['name'].upper()}_SOURCE={connect(to_point_node, include)}")

        water = make_attribute_filter(
            graph,
            "Water",
            "le",
            0.05,
            f"{branch['name']} Exclude Water",
            x + 280,
            y,
        )
        lines.append(
            f"{branch['name'].upper()}_WATER={connect(include, water, source_candidates=('Inside Filter','In Filter','True','Out'), source_reject=('outside','out filter','false'))}"
        )

        exclusion = make_attribute_filter(
            graph,
            "FoliageExclusion",
            "le",
            0.05,
            f"{branch['name']} Foliage Exclusion",
            x + 560,
            y,
        )
        lines.append(
            f"{branch['name'].upper()}_EXCLUSION={connect(water, exclusion, source_candidates=('Inside Filter','In Filter','True','Out'), source_reject=('outside','out filter','false'))}"
        )

        noise = make_density_noise(graph, branch, x + 840, y)
        lines.append(
            f"{branch['name'].upper()}_NOISE={connect(exclusion, noise, source_candidates=('Inside Filter','In Filter','True','Out'), source_reject=('outside','out filter','false'))}"
        )
        density = make_density_filter(graph, branch, x + 1120, y)
        lines.append(f"{branch['name'].upper()}_DENSITY={connect(noise, density)}")
        bounds = make_bounds_modifier(graph, branch, x + 1400, y)
        lines.append(f"{branch['name'].upper()}_BOUNDS={connect(density, bounds, source_candidates=('In Filter','Inside Filter','Out'), source_reject=('outside','out filter'))}")
        pruning = make_self_pruning(graph, branch, x + 1680, y)
        lines.append(f"{branch['name'].upper()}_PRUNE={connect(bounds, pruning)}")
        transform = make_transform(graph, branch, x + 1960, y)
        lines.append(f"{branch['name'].upper()}_TRANSFORM={connect(pruning, transform)}")
        spawner = make_spawner(graph, branch, x + 2240, y, lines)
        lines.append(f"{branch['name'].upper()}_SPAWNER={connect(transform, spawner)}")
        branch_nodes[branch["name"]] = (include, water, exclusion, noise, density, bounds, pruning, transform, spawner)

    all_nodes = [query_node, to_point_node]
    for values in branch_nodes.values():
        all_nodes.extend(values)
    lines.append(f"GRAPH_NODE_COUNT={len(all_nodes)}")
    lines.append(f"QUERY_CHANNELS={','.join(QUERY_CHANNELS)}")
    lines.append(f"GRAPH_PATH={object_path(graph)}")
    for node in all_nodes:
        if node is None:
            raise RuntimeError("Graph contains a null node")
    return graph, all_nodes


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        log(line)
    log(f"AETHER_STAGE15B_RIVER_BIOME_INSTALL_REPORT={REPORT_PATH}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running the Stage 15B river biome installer.")
    except AttributeError:
        pass

    world = unreal.EditorLevelLibrary.get_editor_world()
    if world is None or "AetherWorld" not in world.get_path_name():
        raise RuntimeError(f"Open /Game/Maps/AetherWorld before running this installer. Current={object_path(world)}")

    lines = [
        "AETHER STAGE 15B - GUARDED RIVER BIOME GRAPH INSTALL",
        "=" * 100,
        "TUTORIAL_ROUTE=Mesh Partition Query -> ToPoint -> channel filters -> density/spacing -> weighted spawners",
        "BOUNDED_VERTICAL_SLICE=TRUE",
        "PCG_GENERATION_STARTED=FALSE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
        "NO_EXISTING_GRAPH_OVERWRITTEN=TRUE",
        "NO_EXISTING_ACTOR_REPLACED=TRUE",
    ]

    if unreal.EditorAssetLibrary.does_asset_exist(GRAPH_OBJECT_PATH) or unreal.EditorAssetLibrary.does_asset_exist(GRAPH_PACKAGE_PATH):
        raise RuntimeError(f"Biome graph already exists; refusing to overwrite: {GRAPH_OBJECT_PATH}")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    duplicates = [
        actor for actor in actor_subsystem.get_all_level_actors()
        if safe_call(lambda actor=actor: actor.get_actor_label(), "") == VOLUME_LABEL
    ]
    if duplicates:
        raise RuntimeError(f"Biome volume already exists; refusing to duplicate: {VOLUME_LABEL}")

    mesh_terrain = find_level_actor(MESH_TERRAIN_LABEL)
    source_spline_actor = find_level_actor(SPLINE_LABEL)
    source_spline = find_spline_component(source_spline_actor)
    spline_length, spline_points, center, desired_extent = spline_volume_bounds(source_spline)
    lines.append(f"WORLD={object_path(world)}")
    lines.append(f"MESH_TERRAIN_ACTOR={object_path(mesh_terrain)}")
    lines.append(f"SOURCE_SPLINE_ACTOR={object_path(source_spline_actor)}")
    lines.append(f"SOURCE_SPLINE_LENGTH_CM={spline_length}")
    lines.append(f"SOURCE_SPLINE_SAMPLES={len(spline_points)}")

    graph_created = False
    volume_actor = None
    try:
        graph, nodes = create_graph(lines)
        graph_created = True
        volume_actor, component = create_volume(center, desired_extent, graph, lines)

        assigned_graph = safe_call(lambda: component.get_graph(), None)
        if assigned_graph is None:
            assigned_graph = safe_call(lambda: component.get_editor_property("graph"), None)
        if assigned_graph is not graph:
            raise RuntimeError(
                f"PCGVolume graph assignment validation failed: assigned={object_path(assigned_graph)} expected={object_path(graph)}"
            )

        graph.modify()
        volume_actor.modify()
        component.modify()

        if not unreal.EditorAssetLibrary.save_asset(GRAPH_OBJECT_PATH, only_if_is_dirty=False):
            raise RuntimeError(f"Failed to save graph asset: {GRAPH_OBJECT_PATH}")
        if not unreal.EditorLevelLibrary.save_current_level():
            raise RuntimeError("Failed to save AetherWorld after creating the bounded PCG volume")

        lines.extend((
            f"GRAPH_SAVED={GRAPH_OBJECT_PATH}",
            f"VOLUME_ACTOR_SAVED={VOLUME_LABEL}",
            "PCG_GENERATION_STARTED=FALSE",
            "GENERATED_INSTANCE_COUNT=0",
            "COLLISION_SETTINGS_CHANGED=FALSE",
            "MESH_TERRAIN_CHANGED=FALSE",
            "MESH_PARTITION_BUILD_STARTED=FALSE",
            "INSTALL_RESULT=PASS",
            "NEXT=Run the Stage 15B graph/volume validation before generating any instances.",
        ))
        write_report(lines)
    except Exception:
        if volume_actor is not None:
            try:
                actor_subsystem.destroy_actor(volume_actor)
            except Exception:
                pass
        if graph_created:
            try:
                unreal.EditorAssetLibrary.delete_asset(GRAPH_OBJECT_PATH)
            except Exception:
                pass
        raise


try:
    main()
except Exception as exc:
    failure = [
        "AETHER STAGE 15B - GUARDED RIVER BIOME GRAPH INSTALL",
        "=" * 100,
        "INSTALL_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "PCG_GENERATION_STARTED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
        "NO_EXISTING_GRAPH_OVERWRITTEN=TRUE",
        "NO_EXISTING_ACTOR_REPLACED=TRUE",
    ]
    write_report(failure)
    unreal.log_error("\n".join(failure))
    raise
