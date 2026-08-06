from pathlib import Path
import sys
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Patches ChannelName construction and strict production-mesh discovery.
import AetherRiverEnvironmentCommon_UE58_v2 as common
from AetherRiverEnvironmentPlacement_UE58_v2 import place_environment_instances

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherRiverEnvironmentGroundingRepair.txt"
REPORT_LINES = []


def write_report(lines):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def component_instance_count(component):
    method = getattr(component, "get_instance_count", None)
    if callable(method):
        try:
            return int(method())
        except Exception:
            pass
    for property_name in ("per_instance_sm_data", "per_instance_data"):
        try:
            return len(component.get_editor_property(property_name))
        except Exception:
            continue
    return 0


def save_map(lines):
    saved = False
    try:
        saved = bool(unreal.EditorLevelLibrary.save_current_level())
    except Exception as exc:
        common.record(lines, f"save_current_level warning={exc}")
    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
        saved = True
    except Exception as exc:
        common.record(lines, f"save_dirty_packages warning={exc}")
    return saved


def main():
    lines = REPORT_LINES
    common.record(lines, "AETHER STAGE 13.1 - RIVER ENVIRONMENT GROUNDING REPAIR")
    common.record(lines, "=" * 96)
    common.record(lines, "Rebuilds only the Stage 13 HISM environment actor with offset-aware bank heights.")
    common.record(lines, "The Stage 13 exclusion spline and every Stage 09-12 terrain/water actor are preserved.")
    common.record(lines, "No compiled Mesh Partition build is started.")

    world = common.load_world()
    actor_subsystem, actors = common.get_actor_subsystem_and_actors()

    source_actor = common.find_actor(actors, common.SOURCE_SPLINE_LABEL)
    remesh_actor = common.find_actor(actors, common.SOURCE_REMESH_LABEL)
    river_actor = common.find_actor(actors, common.RIVER_LABEL)
    water_zone_actor = common.find_actor(actors, common.WATER_ZONE_LABEL)
    wetland_actor = common.find_actor(actors, common.WETLAND_LABEL)
    exclusion_actor = common.find_actor(actors, common.EXCLUSION_LABEL)
    environment_actor = common.find_actor(actors, common.ENVIRONMENT_LABEL)

    missing = [
        label
        for label, actor in (
            (common.SOURCE_SPLINE_LABEL, source_actor),
            (common.SOURCE_REMESH_LABEL, remesh_actor),
            (common.RIVER_LABEL, river_actor),
            (common.WATER_ZONE_LABEL, water_zone_actor),
            (common.WETLAND_LABEL, wetland_actor),
            (common.EXCLUSION_LABEL, exclusion_actor),
            (common.ENVIRONMENT_LABEL, environment_actor),
        )
        if not actor
    ]
    if missing:
        raise RuntimeError(f"Required grounding-repair actors are missing: {missing}")

    spline_class = getattr(unreal, "SplineComponent", None)
    hism_class = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    if not spline_class or not hism_class:
        raise RuntimeError("Required spline/HISM classes are unavailable")

    source_spline = common.find_single_component(
        source_actor,
        spline_class,
        "Stage09 SplineComponent",
    )
    source_length = float(source_spline.get_spline_length())
    if int(source_spline.get_number_of_spline_points()) != 5 or not (80000.0 <= source_length <= 170000.0):
        raise RuntimeError(f"Stage09 source spline is invalid: length={source_length}")

    old_components = list(environment_actor.get_components_by_class(hism_class))
    old_total = sum(component_instance_count(component) for component in old_components)
    common.record(lines, f"World={world.get_path_name()}")
    common.record(lines, f"Source spline length cm={source_length}")
    common.record(lines, f"Existing Stage13 HISM components={len(old_components)}")
    common.record(lines, f"Existing Stage13 HISM instances={old_total}")
    if len(old_components) != 8 or old_total != 184:
        raise RuntimeError(
            f"Expected the committed Stage13 environment to contain 8 HISM components and 184 instances; "
            f"found components={len(old_components)}, instances={old_total}"
        )

    asset_paths = common.list_game_assets()
    rocks = common.discover_static_meshes(asset_paths, common.ROCK_TOKENS, 4)
    shrubs = common.discover_static_meshes(asset_paths, common.SHRUB_TOKENS, 2)
    ground = common.discover_static_meshes(asset_paths, common.GROUND_TOKENS, 2)
    if len(rocks) != 4 or len(shrubs) != 2 or len(ground) != 2:
        raise RuntimeError(
            f"Strict Stage13 asset selection changed: rocks={len(rocks)}, shrubs={len(shrubs)}, ground={len(ground)}"
        )

    for category, entries in (("ROCK", rocks), ("SHRUB", shrubs), ("GROUND", ground)):
        common.record(lines, f"Selected {category.lower()} meshes={len(entries)}")
        for path, _ in entries:
            common.record(lines, f"  {category}={path}")

    # Destroy only after every dependency and asset validation has passed. A
    # failure after this point remains unsaved and therefore does not damage the
    # committed Stage 13 actor on disk.
    actor_subsystem.destroy_actor(environment_actor)
    common.record(lines, f"Removed old environment actor={common.ENVIRONMENT_LABEL}")

    repaired_actor = actor_subsystem.spawn_actor_from_class(
        unreal.Actor,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if not repaired_actor:
        raise RuntimeError("Repaired Stage13 environment actor spawn returned None")
    repaired_actor.set_actor_label(common.ENVIRONMENT_LABEL, True)
    repaired_actor.set_editor_property("tags", [unreal.Name(common.ENVIRONMENT_TAG)])

    total, counts, trace_hits, fallbacks, closest_offset = place_environment_instances(
        world,
        source_spline,
        repaired_actor,
        {"rock": rocks, "shrub": shrubs, "ground": ground},
        [
            source_actor,
            remesh_actor,
            river_actor,
            water_zone_actor,
            wetland_actor,
            exclusion_actor,
            repaired_actor,
        ],
        lines,
    )

    if len(counts) != 8 or total != 184:
        raise RuntimeError(
            f"Repaired deterministic layout changed unexpectedly: components={len(counts)}, instances={total}"
        )

    saved = save_map(lines)
    common.record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    common.record(lines, "")
    common.record(lines, "REPAIR_RESULT=PASS")
    common.record(lines, f"ENVIRONMENT_ACTOR={common.ENVIRONMENT_LABEL}")
    common.record(lines, f"PRESERVED_EXCLUSION_ACTOR={common.EXCLUSION_LABEL}")
    common.record(lines, f"HISM_COMPONENTS={len(counts)}")
    common.record(lines, f"HISM_TOTAL_INSTANCES={total}")
    common.record(lines, f"GROUND_TRACE_PLACEMENTS={trace_hits}")
    common.record(lines, f"OFFSET_AWARE_FALLBACKS={fallbacks}")
    common.record(lines, f"CLOSEST_ENVIRONMENT_OFFSET_CM={closest_offset}")
    common.record(lines, "INNER_BANK_FALLBACK_LIFT_CM=340.0")
    common.record(lines, "OUTER_BANK_FALLBACK_LIFT_CM=600.0")
    common.record(lines, "ROCKS_PARTIALLY_EMBEDDED=TRUE")
    common.record(lines, "ENVIRONMENT_COLLISION=DISABLED_UNTIL_STAGE14_RUNTIME_VALIDATION")
    common.record(lines, "NEXT_EDITOR_ACTION=Open AetherWorld and inspect the beginning, center bend, and end of both banks from a low camera angle. Compare floating and buried instances before committing the repair.")
    common.record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report(lines)
    unreal.log_warning(f"AETHER_RIVER_ENVIRONMENT_GROUNDING_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    common.record(REPORT_LINES, "")
    common.record(REPORT_LINES, "REPAIR_RESULT=FAIL")
    common.record(REPORT_LINES, f"ERROR={type(exc).__name__}: {exc}")
    common.record(REPORT_LINES, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report(REPORT_LINES)
    unreal.log_error(f"AETHER_RIVER_ENVIRONMENT_GROUNDING_FAILED={type(exc).__name__}: {exc}")
    raise
