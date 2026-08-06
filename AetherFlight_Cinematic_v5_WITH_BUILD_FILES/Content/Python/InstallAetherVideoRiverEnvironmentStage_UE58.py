from pathlib import Path
import sys
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from AetherRiverEnvironmentCommon_UE58 import *
from AetherRiverEnvironmentPlacement_UE58 import place_environment_instances

REPORT_LINES = []


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


def write_report(lines):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    lines = REPORT_LINES
    record(lines, "AETHER VIDEO STAGE 13 - LOCAL RIVER ENVIRONMENT INSTALL")
    record(lines, "=" * 96)
    record(lines, "Creates a weight-only FoliageExclusion spline plus deterministic local HISM rocks, shrubs, and ground cover.")
    record(lines, "Existing Stage 09-12 terrain and water actors are preserved. No compiled Mesh Partition build is started.")

    world = load_world()
    actor_subsystem, actors = get_actor_subsystem_and_actors()
    clear_previous_install(actor_subsystem, actors, lines)
    _, actors = get_actor_subsystem_and_actors()

    source_actor = find_actor(actors, SOURCE_SPLINE_LABEL)
    remesh_actor = find_actor(actors, SOURCE_REMESH_LABEL)
    river_actor = find_actor(actors, RIVER_LABEL)
    water_zone_actor = find_actor(actors, WATER_ZONE_LABEL)
    wetland_actor = find_actor(actors, WETLAND_LABEL)
    mesh_partition = find_mesh_partition(actors)

    missing = [
        label
        for label, actor in (
            (SOURCE_SPLINE_LABEL, source_actor),
            (SOURCE_REMESH_LABEL, remesh_actor),
            (RIVER_LABEL, river_actor),
            (WATER_ZONE_LABEL, water_zone_actor),
            (WETLAND_LABEL, wetland_actor),
        )
        if not actor
    ]
    if missing:
        raise RuntimeError(f"Required Stage13 dependencies are missing: {missing}")
    if not mesh_partition:
        raise RuntimeError("Authoritative Mesh Partition actor could not be resolved")

    mpd = unreal.EditorAssetLibrary.load_asset(MPD_PATH)
    if not mpd or "FoliageExclusion" not in channel_names(mpd):
        raise RuntimeError("MPD_AetherWorld does not expose the FoliageExclusion channel")

    spline_class = getattr(unreal, "SplineComponent", None)
    modifier_actor_class = getattr(unreal, "ModifierActor", None)
    spline_modifier_class = getattr(unreal, "SplineModifier", None)
    if not spline_class or not modifier_actor_class or not spline_modifier_class:
        raise RuntimeError("Required UE 5.8 spline modifier classes are unavailable")

    source_spline = find_single_component(source_actor, spline_class, "Stage09 SplineComponent")
    source_location = source_actor.get_actor_location()
    source_rotation = source_actor.get_actor_rotation()
    source_length = float(source_spline.get_spline_length())
    if int(source_spline.get_number_of_spline_points()) != 5 or not (80000.0 <= source_length <= 170000.0):
        raise RuntimeError(f"Stage09 source spline is invalid: length={source_length}")

    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Source actor={actor_label(source_actor)} at {source_location}")
    record(lines, f"Source spline length cm={source_length}")
    record(lines, f"Affected Mesh Partition={mesh_partition.get_name()}")

    asset_paths = list_game_assets()
    rocks = discover_static_meshes(asset_paths, ROCK_TOKENS, 4)
    shrubs = discover_static_meshes(asset_paths, SHRUB_TOKENS, 2)
    ground = discover_static_meshes(asset_paths, GROUND_TOKENS, 2)
    if not rocks:
        raise RuntimeError("No usable Environment Rock Collection static meshes were discovered")
    if not shrubs and not ground:
        raise RuntimeError("No usable wet shrub or ground-cover static meshes were discovered")
    if not shrubs:
        shrubs = ground[:1]
        record(lines, "No dedicated shrub mesh found; using one ground-cover mesh for sparse bank vegetation.")
    if not ground:
        ground = shrubs[:1]
        record(lines, "No dedicated ground-cover mesh found; using one shrub mesh at reduced scale.")

    for category, entries in (("ROCK", rocks), ("SHRUB", shrubs), ("GROUND", ground)):
        record(lines, f"Selected {category.lower()} meshes={len(entries)}")
        for path, _ in entries:
            record(lines, f"  {category}={path}")

    exclusion_actor = actor_subsystem.spawn_actor_from_class(
        modifier_actor_class,
        source_location,
        source_rotation,
        False,
    )
    if not exclusion_actor:
        raise RuntimeError("Stage13 exclusion actor spawn returned None")
    exclusion_actor.set_actor_label(EXCLUSION_LABEL, True)
    exclusion_actor.set_editor_property("tags", [unreal.Name(EXCLUSION_TAG)])

    exclusion_spline = add_component_to_actor(exclusion_actor, spline_class, lines)
    exclusion_length = configure_spline_component(exclusion_spline, source_spline, lines)
    exclusion_modifier = add_component_to_actor(exclusion_actor, spline_modifier_class, lines)
    exclusion_result = configure_exclusion_modifier(
        exclusion_modifier,
        mesh_partition,
        exclusion_spline,
        lines,
    )

    environment_actor = actor_subsystem.spawn_actor_from_class(
        unreal.Actor,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if not environment_actor:
        raise RuntimeError("Stage13 environment actor spawn returned None")
    environment_actor.set_actor_label(ENVIRONMENT_LABEL, True)
    environment_actor.set_editor_property("tags", [unreal.Name(ENVIRONMENT_TAG)])

    total, counts, trace_hits, fallbacks, closest_offset = place_environment_instances(
        world,
        source_spline,
        environment_actor,
        {"rock": rocks, "shrub": shrubs, "ground": ground},
        [
            source_actor,
            remesh_actor,
            river_actor,
            water_zone_actor,
            wetland_actor,
            exclusion_actor,
            environment_actor,
        ],
        lines,
    )

    saved = save_map(lines)
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "INSTALL_RESULT=PASS")
    record(lines, f"EXCLUSION_ACTOR={EXCLUSION_LABEL}")
    record(lines, f"ENVIRONMENT_ACTOR={ENVIRONMENT_LABEL}")
    record(lines, f"EXCLUSION_SPLINE_LENGTH_CM={exclusion_length}")
    record(lines, "EXCLUSION_WEIGHT_CHANNEL=FoliageExclusion")
    record(lines, "EXCLUSION_WRITE_MODE=2")
    record(lines, "TERRAIN_POSITION_DEFORMATION=DISABLED_BY_WRITE_MODE")
    record(lines, f"EXCLUSION_PLATEAU_CM={EXCLUSION_PLATEAU_CM}")
    record(lines, f"EXCLUSION_FALLOFF_CM={EXCLUSION_FALLOFF_CM}")
    record(lines, f"EXCLUSION_PRIORITY={EXCLUSION_PRIORITY}")
    record(lines, f"WEIGHT_ENTRY_CHANNEL_PROPERTY={exclusion_result['channel_prop']}")
    record(lines, f"WEIGHT_ENTRY_VALUE_PROPERTY={exclusion_result['value_prop']}")
    record(lines, f"WEIGHT_ENTRY_BLEND_PROPERTY={exclusion_result['blend_prop']}")
    record(lines, f"WEIGHT_BLEND_MODE={exclusion_result['blend']}")
    record(lines, f"HISM_COMPONENTS={len(counts)}")
    record(lines, f"HISM_TOTAL_INSTANCES={total}")
    record(lines, f"GROUND_TRACE_PLACEMENTS={trace_hits}")
    record(lines, f"CONTROLLED_SPLINE_HEIGHT_FALLBACKS={fallbacks}")
    record(lines, f"CLOSEST_ENVIRONMENT_OFFSET_CM={closest_offset}")
    record(lines, "ENVIRONMENT_COLLISION=DISABLED_UNTIL_STAGE14_RUNTIME_VALIDATION")
    record(lines, "NEXT_EDITOR_ACTION=Open AetherWorld. Move the Stage13 exclusion spline slightly and Ctrl+Z once if needed, Build To through its priority-56 SplineModifier, then inspect Aether_VideoStage13_RiverEnvironment for rocks and wet vegetation outside the water corridor.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report(lines)
    unreal.log_warning(f"AETHER_VIDEO_RIVER_ENVIRONMENT_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    record(REPORT_LINES, "")
    record(REPORT_LINES, "INSTALL_RESULT=FAIL")
    record(REPORT_LINES, f"ERROR={type(exc).__name__}: {exc}")
    record(REPORT_LINES, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report(REPORT_LINES)
    unreal.log_error(f"AETHER_VIDEO_RIVER_ENVIRONMENT_INSTALL_FAILED={type(exc).__name__}: {exc}")
    raise
