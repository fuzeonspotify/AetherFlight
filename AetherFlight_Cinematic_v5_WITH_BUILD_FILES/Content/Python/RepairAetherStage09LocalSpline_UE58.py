from pathlib import Path
import math
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
STAGE09_LABEL = "Aether_VideoStage09_SplineChannel"
STAGE10_LABEL = "Aether_VideoStage10_SplineRemesh"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage09LocalSplineRepair.txt"

TRACE_TOP_Z = 900000.0
TRACE_BOTTOM_Z = -300000.0
CHANNEL_DEPTH_CM = 600.0
RELATIVE_POINTS_CM = (
    (-45000.0, -22000.0),
    (-23000.0, -7000.0),
    (-2000.0, 14000.0),
    (23000.0, 7000.0),
    (45000.0, -18000.0),
)
EXPECTED_POINT_COUNT = len(RELATIVE_POINTS_CM)
MIN_EXPECTED_LENGTH_CM = 80000.0
MAX_EXPECTED_LENGTH_CM = 170000.0
REPORT_LINES = []


def record(lines, text=""):
    text = str(text)
    lines.append(text)
    unreal.log_warning(text)


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def load_world():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def get_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return subsystem, list(subsystem.get_all_level_actors())


def find_actor(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one actor named {label}, found {len(matches)}")
    return matches[0]


def find_single_component(actor, component_class, description):
    components = list(actor.get_components_by_class(component_class))
    if len(components) != 1:
        raise RuntimeError(
            f"Expected exactly one {description} on {actor_label(actor)}, found {len(components)}"
        )
    return components[0]


def safe_relative_scale(component):
    try:
        return component.get_editor_property("relative_scale3d")
    except Exception:
        try:
            return component.get_relative_scale3d()
        except Exception:
            return None


def normalize_transforms(actor, spline, lines):
    old_actor_scale = actor.get_actor_scale3d()
    old_spline_scale = safe_relative_scale(spline)
    record(lines, f"Stage09 actor scale before={old_actor_scale}")
    record(lines, f"Stage09 spline relative scale before={old_spline_scale}")

    unit_scale = unreal.Vector(1.0, 1.0, 1.0)
    actor.set_actor_scale3d(unit_scale)

    set_relative = getattr(spline, "set_relative_scale3d", None)
    if callable(set_relative):
        set_relative(unit_scale)
    else:
        spline.set_editor_property("relative_scale3d", unit_scale)

    new_actor_scale = actor.get_actor_scale3d()
    new_spline_scale = safe_relative_scale(spline)
    record(lines, f"Stage09 actor scale after={new_actor_scale}")
    record(lines, f"Stage09 spline relative scale after={new_spline_scale}")

    for label, scale in (
        ("actor", new_actor_scale),
        ("spline", new_spline_scale),
    ):
        if scale is None:
            continue
        if not (
            math.isclose(float(scale.x), 1.0, abs_tol=0.001)
            and math.isclose(float(scale.y), 1.0, abs_tol=0.001)
            and math.isclose(float(scale.z), 1.0, abs_tol=0.001)
        ):
            raise RuntimeError(f"Could not normalize Stage09 {label} scale: {scale}")

    return old_actor_scale, old_spline_scale


def terrain_hit(world, x, y, lines):
    start = unreal.Vector(x, y, TRACE_TOP_Z)
    end = unreal.Vector(x, y, TRACE_BOTTOM_Z)
    attempts = []

    try:
        attempts.append(
            unreal.SystemLibrary.line_trace_single(
                world,
                start,
                end,
                unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                False,
                [],
                unreal.DrawDebugTrace.NONE,
                True,
            )
        )
    except Exception as exc:
        record(lines, f"Visibility trace warning at {x:.0f},{y:.0f}: {exc}")

    try:
        attempts.append(
            unreal.SystemLibrary.line_trace_single_by_profile(
                world,
                start,
                end,
                "BlockAll",
                False,
                [],
                unreal.DrawDebugTrace.NONE,
                True,
            )
        )
    except Exception as exc:
        record(lines, f"BlockAll trace warning at {x:.0f},{y:.0f}: {exc}")

    for hit in attempts:
        if not hit:
            continue
        for property_name in ("impact_point", "location"):
            try:
                point = hit.get_editor_property(property_name)
                if point:
                    return point
            except Exception:
                continue
    return None


def spline_length(spline):
    method = getattr(spline, "get_spline_length", None)
    if not callable(method):
        return None
    try:
        return float(method())
    except Exception:
        return None


def existing_world_points(spline, lines):
    count = int(spline.get_number_of_spline_points())
    world_space = unreal.SplineCoordinateSpace.WORLD
    points = []
    record(lines, f"Spline point count before repair={count}")
    for index in range(count):
        try:
            point = spline.get_location_at_spline_point(index, world_space)
            points.append(point)
            record(lines, f"Existing world point {index}={point}")
        except Exception as exc:
            record(lines, f"Could not read existing spline point {index}: {exc}")
            points.append(None)
    return points


def validate_local_points(spline, lines):
    count = int(spline.get_number_of_spline_points())
    record(lines, f"Spline point count after repair={count}")
    if count != EXPECTED_POINT_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_POINT_COUNT} repaired points, but spline contains {count}"
        )

    local_space = unreal.SplineCoordinateSpace.LOCAL
    for index, (expected_x, expected_y) in enumerate(RELATIVE_POINTS_CM):
        point = spline.get_location_at_spline_point(index, local_space)
        record(lines, f"Verified local point {index}={point}")
        if not (
            math.isclose(float(point.x), expected_x, abs_tol=2.0)
            and math.isclose(float(point.y), expected_y, abs_tol=2.0)
        ):
            raise RuntimeError(
                f"Local point {index} was not rebuilt correctly: {point}; "
                f"expected X={expected_x}, Y={expected_y}"
            )


def rebuild_stage09_spline(world, actor, spline, lines):
    actor_location = actor.get_actor_location()
    record(lines, f"Stage09 actor location={actor_location}")
    record(lines, f"Stage09 actor rotation={actor.get_actor_rotation()}")

    old_length = spline_length(spline)
    old_points = existing_world_points(spline, lines)
    record(lines, f"Spline length before repair cm={old_length}")

    old_actor_scale, old_spline_scale = normalize_transforms(actor, spline, lines)

    try:
        spline.set_editor_property("closed_loop", False)
    except Exception:
        set_closed_loop = getattr(spline, "set_closed_loop", None)
        if callable(set_closed_loop):
            set_closed_loop(False, True)

    spline.clear_spline_points(True)
    cleared_count = int(spline.get_number_of_spline_points())
    record(lines, f"Spline point count immediately after clear={cleared_count}")
    if cleared_count != 0:
        raise RuntimeError(f"Spline clear failed; {cleared_count} points remain")

    local_space = unreal.SplineCoordinateSpace.LOCAL
    curve_type = getattr(unreal.SplinePointType, "CURVE", None)
    if curve_type is None:
        curve_type = getattr(unreal.SplinePointType, "CURVE_CLAMPED", None)

    trace_passes = 0
    for index, (offset_x, offset_y) in enumerate(RELATIVE_POINTS_CM):
        world_x = actor_location.x + offset_x
        world_y = actor_location.y + offset_y
        hit = terrain_hit(world, world_x, world_y, lines)

        if hit:
            world_z = hit.z - CHANNEL_DEPTH_CM
            placement = "TRACE"
            trace_passes += 1
        elif index < len(old_points) and old_points[index] is not None:
            world_z = old_points[index].z
            placement = "EXISTING_Z_FALLBACK"
        else:
            world_z = actor_location.z - CHANNEL_DEPTH_CM
            placement = "ACTOR_Z_FALLBACK"

        local_point = unreal.Vector(offset_x, offset_y, world_z - actor_location.z)
        spline.add_spline_point(local_point, local_space, False)
        record(lines, f"Added local spline point {index}={local_point} | {placement}")

    for index in range(EXPECTED_POINT_COUNT):
        if curve_type is not None:
            spline.set_spline_point_type(index, curve_type, False)
        width_scale = 1.0 if index in (0, EXPECTED_POINT_COUNT - 1) else 1.25
        spline.set_scale_at_spline_point(
            index,
            unreal.Vector(1.0, width_scale, 1.0),
            False,
        )

    spline.update_spline()
    validate_local_points(spline, lines)

    try:
        spline.set_editor_property("draw_debug", True)
    except Exception:
        pass
    try:
        spline.modify()
        actor.modify()
    except Exception:
        pass

    new_length = spline_length(spline)
    record(lines, f"Spline length after repair cm={new_length}")
    record(lines, f"Terrain trace passes={trace_passes}/{EXPECTED_POINT_COUNT}")

    if new_length is None or not (
        MIN_EXPECTED_LENGTH_CM <= new_length <= MAX_EXPECTED_LENGTH_CM
    ):
        raise RuntimeError(
            f"Repaired spline length is outside the expected local range: {new_length} cm"
        )

    return (
        old_length,
        new_length,
        trace_passes,
        old_actor_scale,
        old_spline_scale,
    )


def refresh_stage09_modifier(stage09_actor, lines):
    modifier_class = getattr(unreal, "SplineModifier", None)
    if not modifier_class:
        record(lines, "Stage09 SplineModifier class unavailable for cache refresh")
        return False
    modifiers = list(stage09_actor.get_components_by_class(modifier_class))
    if len(modifiers) != 1:
        record(lines, f"Stage09 SplineModifier count={len(modifiers)}; cache refresh skipped")
        return False
    update_method = getattr(modifiers[0], "update_spline_data", None)
    if not callable(update_method):
        record(lines, "Stage09 UpdateSplineData is not Python-callable; editor reload will refresh it")
        return False
    try:
        update_method()
        record(lines, "Stage09 spline modifier cache refreshed")
        return True
    except Exception as exc:
        record(lines, f"Stage09 spline modifier cache refresh warning={exc}")
        return False


def repair_stage10_reference(stage09_actor, stage09_spline, stage10_actor, lines):
    modifier_class = getattr(unreal, "SplineRemeshModifier", None)
    reference_class = getattr(unreal, "ComponentReference", None)
    if not modifier_class or not reference_class:
        raise RuntimeError("SplineRemeshModifier or ComponentReference is unavailable")

    modifier = find_single_component(stage10_actor, modifier_class, "SplineRemeshModifier")
    component_name = unreal.Name(stage09_spline.get_name())

    try:
        reference = reference_class(
            other_actor=stage09_actor,
            component_property=component_name,
        )
    except Exception:
        reference = reference_class()
        reference.set_editor_property("other_actor", stage09_actor)
        reference.set_editor_property("component_property", component_name)

    modifier.set_editor_property("spline_ref", reference)
    try:
        modifier.modify()
    except Exception:
        pass
    record(lines, f"Stage10 spline_ref refreshed to {actor_label(stage09_actor)}.{component_name}")


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
    record(lines, "AETHER STAGE 09 LOCAL-SPACE SPLINE REPAIR V2")
    record(lines, "=" * 96)
    record(lines, "Normalizes transform scale and rebuilds exactly five local-space points.")
    record(lines, "No compiled Mesh Partition build is started.")

    world = load_world()
    _, actors = get_actors()
    stage09_actor = find_actor(actors, STAGE09_LABEL)
    stage10_actor = find_actor(actors, STAGE10_LABEL)

    spline_class = getattr(unreal, "SplineComponent", None)
    if not spline_class:
        raise RuntimeError("unreal.SplineComponent is unavailable")
    stage09_spline = find_single_component(stage09_actor, spline_class, "SplineComponent")

    (
        old_length,
        new_length,
        trace_passes,
        old_actor_scale,
        old_spline_scale,
    ) = rebuild_stage09_spline(world, stage09_actor, stage09_spline, lines)

    stage09_cache_refreshed = refresh_stage09_modifier(stage09_actor, lines)
    repair_stage10_reference(stage09_actor, stage09_spline, stage10_actor, lines)

    saved = save_map(lines)
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "REPAIR_RESULT=PASS")
    record(lines, f"SPLINE_LENGTH_BEFORE_CM={old_length}")
    record(lines, f"SPLINE_LENGTH_AFTER_CM={new_length}")
    record(lines, f"TERRAIN_TRACE_PASSES={trace_passes}/{EXPECTED_POINT_COUNT}")
    record(lines, f"ACTOR_SCALE_BEFORE={old_actor_scale}")
    record(lines, f"SPLINE_RELATIVE_SCALE_BEFORE={old_spline_scale}")
    record(lines, "ACTOR_SCALE_AFTER=1,1,1")
    record(lines, "SPLINE_RELATIVE_SCALE_AFTER=1,1,1")
    record(lines, "SPLINE_POINT_COUNT=5")
    record(lines, "SPLINE_COORDINATE_SPACE=LOCAL")
    record(lines, f"STAGE09_CACHE_REFRESHED={str(stage09_cache_refreshed).upper()}")
    record(lines, "STAGE10_REFERENCE_REFRESHED=TRUE")
    record(lines, "NEXT_EDITOR_ACTION=Open AetherWorld, confirm the Stage09 line, points, and bounds move together, then include Stage10 and Stage09 in Build To.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    write_report(lines)
    unreal.log_warning(f"AETHER_STAGE09_LOCAL_SPLINE_REPAIR_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    record(REPORT_LINES, "")
    record(REPORT_LINES, "REPAIR_RESULT=FAIL")
    record(REPORT_LINES, f"ERROR={type(exc).__name__}: {exc}")
    record(REPORT_LINES, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report(REPORT_LINES)
    unreal.log_error(f"Stage09 repair failed: {type(exc).__name__}: {exc}")
    raise
