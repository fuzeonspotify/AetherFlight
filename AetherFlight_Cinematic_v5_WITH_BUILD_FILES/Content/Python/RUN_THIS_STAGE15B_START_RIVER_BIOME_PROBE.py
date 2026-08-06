"""Start a temporary low-density Stage 15B river-biome generation probe.

This script does not modify or save the persistent PCG_Aether_RiverBiome graph.
It duplicates the validated graph into /Engine/Transient, tightens the four density
gates, creates one small unsaved non-partitioned PCG Volume around the midpoint of
the Stage 09 river spline, and starts local PCG generation.

The probe actor intentionally remains in the editor for visual inspection. Do not
save the level. A separate read-only audit reports completion and instance counts.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeStart.txt"
GRAPH_OBJECT_PATH = "/Game/Aether/PCG/Biomes/PCG_Aether_RiverBiome.PCG_Aether_RiverBiome"
SOURCE_VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
PROBE_LABEL = "Aether_Stage15B_RiverBiomeProbe_UNSAVED"
SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
PROBE_SEED = 150016
PROBE_EXTENT = unreal.Vector(15000.0, 10000.0, 50000.0)
# Trees, Shrubs, GroundCover, Rocks in validated graph order.
PROBE_DENSITY_MINIMA = (0.9995, 0.9985, 0.9950, 0.9995)


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


def actor_bounds(actor):
    result = actor.get_actor_bounds(False)
    if not isinstance(result, tuple) or len(result) < 2:
        raise RuntimeError(f"Unexpected actor bounds result: {result}")
    return result[0], result[1]


def all_level_actors():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()


def actors_with_label(label):
    return [
        actor for actor in all_level_actors()
        if safe_call(lambda actor=actor: actor.get_actor_label(), "") == label
    ]


def find_single_actor(label):
    matches = actors_with_label(label)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one actor labelled {label}; found {len(matches)}")
    return matches[0]


def find_spline_component(actor):
    components = actor.get_components_by_class(unreal.SplineComponent)
    if len(components) != 1:
        raise RuntimeError(f"Expected one spline component on {SPLINE_LABEL}; found {len(components)}")
    return components[0]


def graph_nodes(graph):
    for getter in (
        lambda: graph.get_nodes(),
        lambda: graph.get_editor_property("nodes"),
    ):
        value = safe_call(getter)
        if value is not None:
            return list(value)
    raise RuntimeError("Could not enumerate PCG graph nodes")


def node_settings(node):
    for getter in (
        lambda: node.get_settings(),
        lambda: node.get_editor_property("settings"),
    ):
        value = safe_call(getter)
        if value is not None:
            return value
    return None


def duplicate_probe_graph(source_graph, lines):
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


def configure_probe_bounds(actor, center, desired_extent, lines):
    _, initial_extent = actor_bounds(actor)
    initial_scale = actor.get_actor_scale3d()
    extents = (float(initial_extent.x), float(initial_extent.y), float(initial_extent.z))
    scales = (float(initial_scale.x), float(initial_scale.y), float(initial_scale.z))
    if min(extents) <= 0.01 or min(scales) <= 0.000001:
        raise RuntimeError(f"Invalid PCGVolume default bounds/scale: {initial_extent} / {initial_scale}")

    scale = unreal.Vector(
        scales[0] * float(desired_extent.x) / extents[0],
        scales[1] * float(desired_extent.y) / extents[1],
        scales[2] * float(desired_extent.z) / extents[2],
    )
    actor.set_actor_scale3d(scale)
    actor.set_actor_location(center, False, False)

    origin, actual_extent = actor_bounds(actor)
    for calibration_index in range(3):
        if (
            float(actual_extent.x) + 10.0 >= float(desired_extent.x)
            and float(actual_extent.y) + 10.0 >= float(desired_extent.y)
            and float(actual_extent.z) + 10.0 >= float(desired_extent.z)
        ):
            break
        current_scale = actor.get_actor_scale3d()
        corrected = unreal.Vector(
            float(current_scale.x) * float(desired_extent.x) / max(float(actual_extent.x), 0.01),
            float(current_scale.y) * float(desired_extent.y) / max(float(actual_extent.y), 0.01),
            float(current_scale.z) * float(desired_extent.z) / max(float(actual_extent.z), 0.01),
        )
        actor.set_actor_scale3d(corrected)
        actor.set_actor_location(center, False, False)
        origin, actual_extent = actor_bounds(actor)
        lines.append(f"BOUNDS_CALIBRATION_{calibration_index + 1}=scale:{corrected} extent:{actual_extent}")

    if (
        float(actual_extent.x) + 10.0 < float(desired_extent.x)
        or float(actual_extent.y) + 10.0 < float(desired_extent.y)
        or float(actual_extent.z) + 10.0 < float(desired_extent.z)
    ):
        raise RuntimeError(f"Probe bounds are too small: actual={actual_extent} requested={desired_extent}")

    lines.append(f"PROBE_INITIAL_EXTENT={initial_extent}")
    lines.append(f"PROBE_INITIAL_SCALE={initial_scale}")
    lines.append(f"PROBE_CENTER={center}")
    lines.append(f"PROBE_BOUNDS_ORIGIN={origin}")
    lines.append(f"PROBE_BOUNDS_EXTENT={actual_extent}")
    lines.append(f"PROBE_SCALE={actor.get_actor_scale3d()}")


def get_component(actor):
    component = safe_call(lambda: actor.get_editor_property("pcg_component"))
    if component is None:
        components = actor.get_components_by_class(unreal.PCGComponent)
        component = components[0] if components else None
    if component is None:
        raise RuntimeError("Probe PCGVolume has no PCGComponent")
    return component


def assign_graph(component, graph):
    for method_name in ("set_graph", "set_graph_local"):
        method = getattr(component, method_name, None)
        if callable(method):
            try:
                method(graph)
                return method_name
            except Exception:
                pass
    if safe_set(component, ("graph",), graph, required=False) is not None:
        return "graph_property"
    raise RuntimeError("Could not assign the transient probe graph")


def start_generation(component):
    method = getattr(component, "generate_local", None)
    if callable(method):
        method(True)
        return "generate_local(True)"
    method = getattr(component, "generate", None)
    if callable(method):
        method(True)
        return "generate(True)"
    raise RuntimeError("PCGComponent exposes neither generate_local nor generate")


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_RIVER_BIOME_PROBE_START_REPORT={REPORT_PATH}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before starting the river-biome probe")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - TEMPORARY LOW-DENSITY RIVER BIOME PROBE",
        "=" * 100,
        "PERSISTENT_GRAPH_MODIFIED=FALSE",
        "PERSISTENT_VOLUME_MODIFIED=FALSE",
        "PACKAGES_SAVED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
        "PROBE_PARTITIONED=FALSE",
        "PROBE_ACTOR_UNSAVED=TRUE",
    ]

    if actors_with_label(PROBE_LABEL):
        raise RuntimeError(f"Probe actor already exists: {PROBE_LABEL}. Run the audit or close without saving first")

    source_volume = find_single_actor(SOURCE_VOLUME_LABEL)
    source_components = source_volume.get_components_by_class(unreal.PCGComponent)
    if len(source_components) != 1:
        raise RuntimeError(f"Validated source volume should have one PCG component; found {len(source_components)}")
    source_component = source_components[0]
    if safe_call(lambda: source_component.is_generating(), False):
        raise RuntimeError("The full river biome component is generating; refusing to start a probe")
    source_instance_components = (
        source_volume.get_components_by_class(unreal.InstancedStaticMeshComponent)
        + source_volume.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
    )
    if source_instance_components:
        raise RuntimeError("The full river biome volume already contains generated instance components")

    source_graph = unreal.EditorAssetLibrary.load_asset(GRAPH_OBJECT_PATH)
    if source_graph is None:
        raise RuntimeError(f"Validated graph is missing: {GRAPH_OBJECT_PATH}")
    probe_graph = duplicate_probe_graph(source_graph, lines)

    spline_actor = find_single_actor(SPLINE_LABEL)
    spline = find_spline_component(spline_actor)
    spline_length = float(spline.get_spline_length())
    if spline_length <= 0.0:
        raise RuntimeError("River spline length is zero")
    center = spline.get_location_at_distance_along_spline(
        spline_length * 0.5,
        unreal.SplineCoordinateSpace.WORLD,
    )
    lines.append(f"SOURCE_SPLINE_LENGTH_CM={spline_length}")
    lines.append("PROBE_SPLINE_DISTANCE_FRACTION=0.5")

    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(unreal.PCGVolume, center, unreal.Rotator())
    if actor is None:
        raise RuntimeError("Could not spawn temporary PCG probe volume")
    actor.set_actor_label(PROBE_LABEL)
    safe_set(actor, ("is_spatially_loaded",), False, required=False)

    try:
        configure_probe_bounds(actor, center, PROBE_EXTENT, lines)
        component = get_component(actor)
        safe_set(component, ("generation_trigger",), unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND, required=True)

        partition_set = False
        for method_name in ("set_is_partitioned", "set_partitioned"):
            method = getattr(component, method_name, None)
            if callable(method):
                try:
                    method(False)
                    partition_set = True
                    break
                except Exception:
                    pass
        if not partition_set:
            partition_set = safe_set(
                component,
                ("is_component_partitioned", "partitioned", "is_partitioned"),
                False,
                required=False,
            ) is not None
        if not partition_set:
            raise RuntimeError("Could not disable partitioning for the small probe")

        safe_set(component, ("seed",), PROBE_SEED, required=False)
        safe_set(component, ("regenerate_in_editor",), False, required=False)
        graph_assignment = assign_graph(component, probe_graph)
        assigned = safe_call(lambda: component.get_graph())
        if assigned is None:
            assigned = safe_call(lambda: component.get_editor_property("graph"))
        if assigned is not probe_graph:
            raise RuntimeError(
                f"Transient graph assignment failed: assigned={object_path(assigned)} expected={object_path(probe_graph)}"
            )

        lines.append(f"PROBE_ACTOR={object_path(actor)}")
        lines.append(f"PROBE_COMPONENT={object_path(component)}")
        lines.append(f"PROBE_GRAPH_ASSIGNMENT_METHOD={graph_assignment}")
        lines.append(f"PROBE_GENERATION_TRIGGER={safe_call(lambda: component.get_editor_property('generation_trigger'), 'UNEXPOSED')}")
        lines.append(f"PROBE_IS_PARTITIONED={safe_call(lambda: component.get_editor_property('is_component_partitioned'), False)}")
        lines.append(f"PROBE_SEED={safe_call(lambda: component.get_editor_property('seed'), 'UNEXPOSED')}")

        generation_method = start_generation(component)
        lines.append(f"GENERATION_METHOD={generation_method}")
        lines.append(f"IS_GENERATING_IMMEDIATELY={safe_call(lambda: component.is_generating(), 'UNEXPOSED')}")
        lines.extend((
            "PROBE_START_RESULT=PASS",
            "NEXT=Allow the editor to finish PCG generation, then run RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_PROBE.py.",
            "DO_NOT_SAVE_LEVEL=TRUE",
            "DO_NOT_PRESS_GENERATE_ON_FULL_VOLUME=TRUE",
        ))
        write_report(lines)
    except Exception:
        try:
            subsystem.destroy_actor(actor)
        except Exception:
            pass
        raise


try:
    main()
except Exception as exc:
    failure = [
        "AETHER STAGE 15B - TEMPORARY LOW-DENSITY RIVER BIOME PROBE",
        "=" * 100,
        "PROBE_START_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "PERSISTENT_GRAPH_MODIFIED=FALSE",
        "PERSISTENT_VOLUME_MODIFIED=FALSE",
        "PACKAGES_SAVED=FALSE",
        "MESH_PARTITION_BUILD_STARTED=FALSE",
    ]
    write_report(failure)
    unreal.log_error("\n".join(failure))
    raise
