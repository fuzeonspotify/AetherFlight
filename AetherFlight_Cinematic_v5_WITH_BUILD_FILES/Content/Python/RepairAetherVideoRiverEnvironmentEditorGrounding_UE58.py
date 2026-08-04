"""Strict in-editor grounding pass for the Stage 13 river environment.

Run this from Unreal Editor after AetherWorld is open and the river region is
loaded. It creates a temporary replacement actor, keeps only instances that
successfully trace to Mesh Terrain collision, validates the hit rate, and swaps
the actor only after a successful pass.
"""

from pathlib import Path
import random
import sys

import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import AetherRiverEnvironmentCommon_UE58_v2 as common
from AetherRiverEnvironmentCommon_UE58 import (
    ENVIRONMENT_LABEL,
    ENVIRONMENT_TAG,
    EXCLUSION_LABEL,
    GROUND_TOKENS,
    ROCK_TOKENS,
    SHRUB_TOKENS,
    SOURCE_REMESH_LABEL,
    SOURCE_SPLINE_LABEL,
    RIVER_LABEL,
    WATER_ZONE_LABEL,
    WETLAND_LABEL,
    actor_label,
    add_component_to_actor,
    discover_static_meshes,
    find_actor,
    find_single_component,
    get_actor_subsystem_and_actors,
    list_game_assets,
    load_world,
    record,
)
from AetherRiverEnvironmentPlacement_UE58 import (
    EDGE_MARGIN_CM,
    RANDOM_SEED,
    STATION_SPACING_CM,
    add_instance,
    configure_hism,
    make_transform,
    trace_ground,
)

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherRiverEnvironmentEditorGrounding.txt"
TEMP_LABEL = "Aether_VideoStage13_RiverEnvironment_TraceCandidate"
TEMP_TAG = "AetherVideoRiverEnvironmentTraceCandidate"

MIN_TRACE_HIT_RATIO = 0.85
MIN_TRACE_HITS = 140

REPORT_LINES = []


def write_report(lines):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def actor_tags(actor):
    try:
        return [str(tag) for tag in actor.get_editor_property("tags")]
    except Exception:
        return []


def destroy_temp_candidates(subsystem, actors, lines):
    removed = 0
    for actor in actors:
        if actor_label(actor) == TEMP_LABEL or TEMP_TAG in actor_tags(actor):
            subsystem.destroy_actor(actor)
            removed += 1
    record(lines, f"Old temporary grounding candidates removed={removed}")


def mesh_half_height(mesh, scale_value):
    try:
        bounds = mesh.get_bounds()
        return max(0.0, float(bounds.box_extent.z) * float(scale_value))
    except Exception:
        return 0.0


def base_offset(mesh, scale_value, category):
    """Return a conservative base offset with slight category-specific embed."""
    try:
        bounds = mesh.get_bounds()
        minimum_z = float(bounds.origin.z) - float(bounds.box_extent.z)
        offset = max(0.0, -minimum_z * float(scale_value))
    except Exception:
        offset = 0.0

    half_height = mesh_half_height(mesh, scale_value)
    if category == "rock":
        embed = min(85.0, max(20.0, half_height * 0.16))
    elif category == "shrub":
        embed = min(30.0, max(8.0, half_height * 0.04))
    else:
        embed = min(15.0, max(3.0, half_height * 0.025))
    return offset - embed


def aligned_rotation(normal, yaw_degrees, category, rng):
    """Align local Z to the traced surface when UE exposes the helper."""
    base = None
    math_library = getattr(unreal, "MathLibrary", None)
    make_rot = getattr(math_library, "make_rot_from_z", None) if math_library else None
    if callable(make_rot) and normal is not None:
        try:
            base = make_rot(normal)
        except Exception:
            base = None

    if base is None:
        if category == "rock":
            return unreal.Rotator(
                rng.uniform(-9.0, 9.0),
                yaw_degrees,
                rng.uniform(-9.0, 9.0),
            )
        return unreal.Rotator(0.0, yaw_degrees, 0.0)

    pitch = float(base.pitch)
    yaw = float(base.yaw) + float(yaw_degrees)
    roll = float(base.roll)
    if category == "rock":
        pitch += rng.uniform(-6.0, 6.0)
        roll += rng.uniform(-6.0, 6.0)
    return unreal.Rotator(pitch, yaw, roll)


def place_strict_traced_instances(world, source_spline, candidate_actor, mesh_sets, ignored_actors, lines):
    rng = random.Random(RANDOM_SEED)
    hism_class = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    if not hism_class:
        raise RuntimeError("unreal.HierarchicalInstancedStaticMeshComponent is unavailable")

    components = {}
    counts = {}
    for category, entries in mesh_sets.items():
        for path, mesh in entries:
            component = add_component_to_actor(candidate_actor, hism_class, lines)
            configure_hism(component, mesh, category, lines)
            components[(category, path)] = component
            counts[(category, path)] = 0

    length = float(source_spline.get_spline_length())
    world_space = unreal.SplineCoordinateSpace.WORLD
    station_count = max(1, int((length - 2.0 * EDGE_MARGIN_CM) / STATION_SPACING_CM) + 1)

    requested = 0
    trace_hits = 0
    trace_misses = 0
    closest_offset = float("inf")

    def place(category, station_distance, side, offset_min, offset_max, scale_min, scale_max):
        nonlocal requested, trace_hits, trace_misses, closest_offset
        entries = mesh_sets[category]
        if not entries:
            return

        requested += 1
        sampled_distance = max(
            EDGE_MARGIN_CM,
            min(length - EDGE_MARGIN_CM, station_distance + rng.uniform(-650.0, 650.0)),
        )
        center = source_spline.get_location_at_distance_along_spline(sampled_distance, world_space)
        right = source_spline.get_right_vector_at_distance_along_spline(sampled_distance, world_space)
        offset = rng.uniform(offset_min, offset_max)
        closest_offset = min(closest_offset, offset)

        candidate = unreal.Vector(
            float(center.x) + float(right.x) * float(side) * offset,
            float(center.y) + float(right.y) * float(side) * offset,
            float(center.z),
        )
        ground, normal = trace_ground(world, candidate, ignored_actors, lines)
        if normal is None:
            trace_misses += 1
            return
        trace_hits += 1

        path, mesh = entries[rng.randrange(len(entries))]
        component = components[(category, path)]
        scale_value = rng.uniform(scale_min, scale_max)
        location = unreal.Vector(
            float(ground.x),
            float(ground.y),
            float(ground.z) + base_offset(mesh, scale_value, category),
        )
        yaw = rng.uniform(0.0, 360.0)
        rotation = aligned_rotation(normal, yaw, category, rng)
        add_instance(
            component,
            make_transform(
                location,
                rotation,
                unreal.Vector(scale_value, scale_value, scale_value),
            ),
        )
        counts[(category, path)] += 1

    for station_index in range(station_count):
        distance = min(
            EDGE_MARGIN_CM + station_index * STATION_SPACING_CM,
            length - EDGE_MARGIN_CM,
        )
        for side in (-1.0, 1.0):
            place("ground", distance, side, 1650.0, 3000.0, 0.72, 1.24)
            if station_index % 2 == 0:
                place("shrub", distance, side, 2100.0, 3900.0, 0.78, 1.22)
            if station_index % 3 == 0:
                place("rock", distance, side, 1500.0, 3600.0, 0.68, 1.35)
            if station_index % 4 == 1:
                place("ground", distance, side, 2000.0, 4200.0, 0.65, 1.12)

    total = sum(counts.values())
    hit_ratio = float(trace_hits) / float(requested) if requested else 0.0

    record(lines, f"River station count={station_count}")
    record(lines, f"Requested environment placements={requested}")
    record(lines, f"Strict Mesh Terrain trace hits={trace_hits}")
    record(lines, f"Strict Mesh Terrain trace misses={trace_misses}")
    record(lines, f"Strict trace hit ratio={hit_ratio:.6f}")
    record(lines, f"Closest requested environment offset cm={closest_offset}")
    record(lines, f"Strictly grounded HISM instances={total}")
    for (category, path), count in sorted(counts.items()):
        record(lines, f"  {category.upper()} count={count} | {path}")

    return total, counts, requested, trace_hits, trace_misses, hit_ratio, closest_offset


def save_map(lines):
    saved = False
    try:
        saved = bool(unreal.EditorLevelLibrary.save_current_level())
    except Exception as exc:
        record(lines, f"save_current_level warning={exc}")
    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
        saved = True
    except Exception as exc:
        record(lines, f"save_dirty_packages warning={exc}")
    return saved


def main():
    lines = REPORT_LINES
    record(lines, "AETHER STAGE 13.2 - STRICT IN-EDITOR MESH TERRAIN GROUNDING")
    record(lines, "=" * 96)
    record(lines, "Run from the normal Unreal Editor after AetherWorld and the river region are loaded.")
    record(lines, "A temporary actor is validated first. The saved Stage 13 environment is replaced only after sufficient trace hits.")
    record(lines, "No Mesh Partition build is started.")

    world = load_world()
    subsystem, actors = get_actor_subsystem_and_actors()
    destroy_temp_candidates(subsystem, actors, lines)
    _, actors = get_actor_subsystem_and_actors()

    source_actor = find_actor(actors, SOURCE_SPLINE_LABEL)
    remesh_actor = find_actor(actors, SOURCE_REMESH_LABEL)
    river_actor = find_actor(actors, RIVER_LABEL)
    water_zone_actor = find_actor(actors, WATER_ZONE_LABEL)
    wetland_actor = find_actor(actors, WETLAND_LABEL)
    exclusion_actor = find_actor(actors, EXCLUSION_LABEL)
    environment_actor = find_actor(actors, ENVIRONMENT_LABEL)

    required = (
        (SOURCE_SPLINE_LABEL, source_actor),
        (SOURCE_REMESH_LABEL, remesh_actor),
        (RIVER_LABEL, river_actor),
        (WATER_ZONE_LABEL, water_zone_actor),
        (WETLAND_LABEL, wetland_actor),
        (EXCLUSION_LABEL, exclusion_actor),
        (ENVIRONMENT_LABEL, environment_actor),
    )
    missing = [label for label, actor in required if not actor]
    if missing:
        raise RuntimeError(f"Required saved actors are missing: {missing}")

    spline_class = getattr(unreal, "SplineComponent", None)
    if not spline_class:
        raise RuntimeError("unreal.SplineComponent is unavailable")
    source_spline = find_single_component(source_actor, spline_class, "Stage09 SplineComponent")
    source_length = float(source_spline.get_spline_length())
    if int(source_spline.get_number_of_spline_points()) != 5:
        raise RuntimeError("Stage09 source spline does not have five points")

    asset_paths = list_game_assets()
    rocks = discover_static_meshes(asset_paths, ROCK_TOKENS, 4)
    shrubs = discover_static_meshes(asset_paths, SHRUB_TOKENS, 2)
    ground = discover_static_meshes(asset_paths, GROUND_TOKENS, 2)
    if not rocks or not shrubs or not ground:
        raise RuntimeError(
            f"Strict asset discovery failed: rocks={len(rocks)}, shrubs={len(shrubs)}, ground={len(ground)}"
        )

    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Source spline length cm={source_length}")
    record(lines, f"Existing environment actor={actor_label(environment_actor)}")

    candidate_actor = subsystem.spawn_actor_from_class(
        unreal.Actor,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if not candidate_actor:
        raise RuntimeError("Temporary grounding candidate actor could not be spawned")
    candidate_actor.set_actor_label(TEMP_LABEL, True)
    candidate_actor.set_editor_property("tags", [unreal.Name(TEMP_TAG)])

    try:
        total, counts, requested, hits, misses, ratio, closest = place_strict_traced_instances(
            world,
            source_spline,
            candidate_actor,
            {"rock": rocks, "shrub": shrubs, "ground": ground},
            [
                source_actor,
                remesh_actor,
                river_actor,
                water_zone_actor,
                wetland_actor,
                exclusion_actor,
                environment_actor,
                candidate_actor,
            ],
            lines,
        )

        if hits < MIN_TRACE_HITS or ratio < MIN_TRACE_HIT_RATIO:
            raise RuntimeError(
                "Insufficient Mesh Terrain collision was available for a safe swap: "
                f"hits={hits}, requested={requested}, ratio={ratio:.3f}, "
                f"required_hits={MIN_TRACE_HITS}, required_ratio={MIN_TRACE_HIT_RATIO:.2f}. "
                "Load the river region and compiled terrain collision, then run this script again."
            )

        subsystem.destroy_actor(environment_actor)
        candidate_actor.set_actor_label(ENVIRONMENT_LABEL, True)
        candidate_actor.set_editor_property("tags", [unreal.Name(ENVIRONMENT_TAG)])
        try:
            candidate_actor.modify()
        except Exception:
            pass

        saved = save_map(lines)
        record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
        record(lines, "")
        record(lines, "EDITOR_GROUNDING_RESULT=PASS")
        record(lines, f"ENVIRONMENT_ACTOR={ENVIRONMENT_LABEL}")
        record(lines, f"HISM_COMPONENTS={len(counts)}")
        record(lines, f"HISM_TOTAL_INSTANCES={total}")
        record(lines, f"TRACE_REQUESTS={requested}")
        record(lines, f"MESH_TERRAIN_TRACE_HITS={hits}")
        record(lines, f"MESH_TERRAIN_TRACE_MISSES={misses}")
        record(lines, f"MESH_TERRAIN_TRACE_HIT_RATIO={ratio:.6f}")
        record(lines, "UNTRACED_INSTANCES_SKIPPED=TRUE")
        record(lines, "SURFACE_NORMAL_ALIGNMENT=ATTEMPTED")
        record(lines, "ROCKS_PARTIALLY_EMBEDDED=TRUE")
        record(lines, f"CLOSEST_ENVIRONMENT_OFFSET_CM={closest}")
        record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    except Exception:
        try:
            subsystem.destroy_actor(candidate_actor)
        except Exception:
            pass
        raise

    write_report(lines)
    unreal.log_warning(f"AETHER_EDITOR_GROUNDING_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    record(REPORT_LINES, "")
    record(REPORT_LINES, "EDITOR_GROUNDING_RESULT=FAIL")
    record(REPORT_LINES, f"ERROR={type(exc).__name__}: {exc}")
    record(REPORT_LINES, "SAVED_ENVIRONMENT_ACTOR_WAS_NOT_REPLACED=TRUE")
    record(REPORT_LINES, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report(REPORT_LINES)
    unreal.log_error(f"AETHER_EDITOR_GROUNDING_FAILED={type(exc).__name__}: {exc}")
    raise
