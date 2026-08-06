from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
REMESH_LABEL = "Aether_VideoStage05_LocalRemesh"
DEPENDENCY_LABEL = "Aether_VideoStage08_TexturePatch"
SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
TAG = "AetherVideoSplineChannelStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoSplineChannelInstall.txt"

TRACE_TOP_Z = 900000.0
TRACE_BOTTOM_Z = -300000.0

# A 900 m terrain channel that stays inside the verified 1.2 km Stage 05
# remesh area. The points are relative to the Stage 05 center.
RELATIVE_POINTS_CM = (
    (-45000.0, -22000.0),
    (-23000.0, -7000.0),
    (-2000.0, 14000.0),
    (23000.0, 7000.0),
    (45000.0, -18000.0),
)

CHANNEL_DEPTH_CM = 600.0
PLATEAU_DISTANCE_CM = 1400.0
FALLOFF_DISTANCE_CM = 3200.0
MAX_Z_DISTANCE_CM = 120000.0
PRIORITY = 40.0


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


def clear_previous_install(subsystem, actors, lines):
    removed = 0
    for actor in actors:
        tags = []
        try:
            tags = [str(tag) for tag in actor.get_editor_property("tags")]
        except Exception:
            pass
        if actor_label(actor) == SPLINE_LABEL or TAG in tags:
            subsystem.destroy_actor(actor)
            removed += 1
    record(lines, f"Previous spline channel actors removed={removed}")


def find_actor_by_label(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    return matches[0] if len(matches) == 1 else None


def find_mesh_partition(actors):
    preferred = []
    fallback = []
    for actor in actors:
        combined = f"{actor.get_name()} {actor.get_class().get_path_name()}"
        if "MeshPartition" not in combined and "MeshTerrain" not in combined:
            continue
        fallback.append(actor)
        tags = []
        try:
            tags = [str(tag) for tag in actor.get_editor_property("tags")]
        except Exception:
            pass
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in tags:
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def terrain_hit(world, x, y, lines):
    start = unreal.Vector(x, y, TRACE_TOP_Z)
    end = unreal.Vector(x, y, TRACE_BOTTOM_Z)
    attempts = []
    try:
        attempts.append(unreal.SystemLibrary.line_trace_single(
            world,
            start,
            end,
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        ))
    except Exception as exc:
        record(lines, f"Visibility trace warning at {x:.0f},{y:.0f}: {exc}")
    try:
        attempts.append(unreal.SystemLibrary.line_trace_single_by_profile(
            world,
            start,
            end,
            "BlockAll",
            False,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        ))
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


def add_component_to_actor(actor, component_class, lines):
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = list(subsystem.k2_gather_subobject_data_for_instance(actor))
    if not handles:
        raise RuntimeError("SubobjectDataSubsystem returned no actor root handle")

    params = unreal.AddNewSubobjectParams()
    params.set_editor_property("parent_handle", handles[0])
    params.set_editor_property("new_class", component_class)
    new_handle, fail_reason = subsystem.add_new_subobject(params)

    if not unreal.SubobjectDataBlueprintFunctionLibrary.is_handle_valid(new_handle):
        raise RuntimeError(f"Could not add {component_class}: {fail_reason}")

    data = subsystem.k2_find_subobject_data_from_handle(new_handle)
    if not data:
        raise RuntimeError(f"Added {component_class}, but SubobjectData could not be resolved")

    component = unreal.SubobjectDataBlueprintFunctionLibrary.get_associated_object(data)
    if not component:
        raise RuntimeError(f"Added {component_class}, but associated object could not be resolved")

    record(lines, f"Added component={component.get_class().get_path_name()}")
    return component


def try_set_property(obj, names, value, lines, required=False):
    errors = []
    for name in names:
        try:
            obj.set_editor_property(name, value)
            record(lines, f"Set {obj.get_name()}.{name}={value}")
            return True
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    record(lines, f"Property not exposed or rejected: {obj.get_name()} candidates={names}")
    if required:
        raise RuntimeError(f"Could not set any of {names}. Errors={errors}")
    return False


def try_call(obj, names, args, lines, required=False):
    errors = []
    for name in names:
        method = getattr(obj, name, None)
        if not callable(method):
            continue
        try:
            result = method(*args)
            record(lines, f"Called {obj.get_name()}.{name}{args}")
            return True, result
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            record(lines, f"Call failed {obj.get_name()}.{name}: {exc}")
    if required:
        raise RuntimeError(f"Could not call any of {names}. Errors={errors}")
    return False, None


def resolve_enum_member(enum_name, candidates, lines):
    enum_type = getattr(unreal, enum_name, None)
    if not enum_type:
        record(lines, f"Enum unavailable: unreal.{enum_name}")
        return None
    for candidate in candidates:
        value = getattr(enum_type, candidate, None)
        if value is not None:
            record(lines, f"Resolved unreal.{enum_name}.{candidate}={value}")
            return value
    members = [name for name in dir(enum_type) if name.isupper()]
    record(lines, f"No matching member on unreal.{enum_name}; members={members}")
    return None


def assign_mesh_partition(component, mesh_partition, lines):
    direct = try_set_property(
        component,
        ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"),
        mesh_partition,
        lines,
    )
    called, _ = try_call(
        component,
        ("bp_set_affected_mega_mesh", "set_affected_mega_mesh"),
        (mesh_partition,),
        lines,
    )
    if not direct and not called:
        raise RuntimeError("SplineModifier could not be assigned to the authoritative Mesh Partition")


def build_spline_points(world, center, lines):
    points = []
    trace_passes = 0
    for index, (offset_x, offset_y) in enumerate(RELATIVE_POINTS_CM):
        x = center.x + offset_x
        y = center.y + offset_y
        hit = terrain_hit(world, x, y, lines)
        if hit:
            point = unreal.Vector(hit.x, hit.y, hit.z - CHANNEL_DEPTH_CM)
            trace_passes += 1
            placement = "TRACE"
        else:
            point = unreal.Vector(x, y, center.z - CHANNEL_DEPTH_CM)
            placement = "FALLBACK"
        points.append(point)
        record(lines, f"Spline point {index}={point} | {placement}")
    return points, trace_passes


def configure_spline_component(spline, points, lines):
    coordinate_space = resolve_enum_member(
        "SplineCoordinateSpace",
        ("WORLD", "LOCAL"),
        lines,
    )
    if coordinate_space is None:
        raise RuntimeError("Spline coordinate-space enum could not be resolved")

    try_call(spline, ("clear_spline_points",), (False,), lines, required=True)
    for point in points:
        try_call(
            spline,
            ("add_spline_point",),
            (point, coordinate_space, False),
            lines,
            required=True,
        )

    curve_type = resolve_enum_member(
        "SplinePointType",
        ("CURVE", "CURVE_CLAMPED", "LINEAR"),
        lines,
    )
    for index in range(len(points)):
        if curve_type is not None:
            try_call(
                spline,
                ("set_spline_point_type",),
                (index, curve_type, False),
                lines,
            )
        width_scale = 1.0 if index in (0, len(points) - 1) else 1.25
        try_call(
            spline,
            ("set_scale_at_spline_point",),
            (index, unreal.Vector(1.0, width_scale, 1.0), False),
            lines,
        )

    try_call(spline, ("update_spline",), (), lines, required=True)
    try_set_property(spline, ("draw_debug", "b_always_render_in_editor"), True, lines)
    try_set_property(spline, ("hidden_in_game",), True, lines)
    try_set_property(spline, ("closed_loop",), False, lines)
    try:
        spline.modify()
    except Exception:
        pass


def assign_spline_component(modifier, spline, lines):
    direct = try_set_property(
        modifier,
        ("spline_ptr", "spline_component", "spline"),
        spline,
        lines,
    )
    blueprint, _ = try_call(
        modifier,
        ("bp_set_spline_component",),
        (spline,),
        lines,
    )
    native, _ = try_call(
        modifier,
        ("set_spline_component",),
        (spline, True),
        lines,
    )
    if not direct and not blueprint and not native:
        raise RuntimeError("SplineModifier could not receive the SplineComponent")


def configure_modifier(modifier, mesh_partition, spline, lines):
    assign_mesh_partition(modifier, mesh_partition, lines)
    assign_spline_component(modifier, spline, lines)

    try_set_property(modifier, ("priority",), PRIORITY, lines, required=True)
    try_set_property(modifier, ("is_disabled", "disabled"), False, lines, required=True)

    # Positions = 1 << 0. Keep Stage 09 focused on terrain deformation; weight
    # channel writing is reserved for the later water/biome integration stage.
    try_set_property(modifier, ("write_mode",), 1, lines, required=True)

    blend_mode = resolve_enum_member(
        "SplineModifierBlendMode",
        ("NORMAL", "MIN", "MAX"),
        lines,
    )
    if blend_mode is not None:
        try_set_property(modifier, ("blend_mode",), blend_mode, lines)

    falloff_set, _ = try_call(
        modifier,
        ("set_falloff_distance",),
        (FALLOFF_DISTANCE_CM,),
        lines,
    )
    if not falloff_set:
        try_set_property(
            modifier,
            ("falloff_distance",),
            FALLOFF_DISTANCE_CM,
            lines,
            required=True,
        )

    try_set_property(
        modifier,
        ("plateau_distance",),
        PLATEAU_DISTANCE_CM,
        lines,
        required=True,
    )

    max_z_set, _ = try_call(
        modifier,
        ("set_max_z_distance",),
        (MAX_Z_DISTANCE_CM,),
        lines,
    )
    if not max_z_set:
        try_set_property(
            modifier,
            ("max_z_distance",),
            MAX_Z_DISTANCE_CM,
            lines,
            required=True,
        )

    scale_falloff_set, _ = try_call(
        modifier,
        ("set_use_spline_scale_for_falloff",),
        (True,),
        lines,
    )
    if not scale_falloff_set:
        try_set_property(
            modifier,
            ("use_spline_scale_for_falloff", "b_use_spline_scale_for_falloff"),
            True,
            lines,
        )

    try_set_property(
        modifier,
        ("use_spline_scale_for_plateau", "b_use_spline_scale_for_plateau"),
        True,
        lines,
    )
    try_set_property(
        modifier,
        ("expand_bounds_by_spline_scale", "b_expand_bounds_by_spline_scale"),
        True,
        lines,
    )
    try_set_property(
        modifier,
        ("use_nearest_spline_frame_for_displacement", "b_use_nearest_spline_frame_for_displacement"),
        False,
        lines,
    )
    try_set_property(
        modifier,
        ("nearest_frame_fast_approximation", "b_nearest_frame_fast_approximation"),
        True,
        lines,
    )
    try_set_property(
        modifier,
        ("mesh_closed_interior", "b_mesh_closed_interior"),
        False,
        lines,
    )
    try_set_property(
        modifier,
        ("draw_projected_spline", "b_draw_projected_spline"),
        True,
        lines,
    )
    try_set_property(
        modifier,
        ("draw_local_bounds", "b_draw_local_bounds"),
        True,
        lines,
    )
    try_set_property(
        modifier,
        ("draw_projection_plane", "b_draw_projection_plane"),
        False,
        lines,
    )

    updated, _ = try_call(
        modifier,
        ("update_spline_data",),
        (),
        lines,
    )
    if not updated:
        record(lines, "UpdateSplineData is not Python-callable; modifier initialization will update it in the editor.")

    try:
        modifier.modify()
    except Exception:
        pass


def spline_length(spline):
    method = getattr(spline, "get_spline_length", None)
    if not callable(method):
        return None
    try:
        return float(method())
    except Exception:
        return None


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
    lines = []
    record(lines, "AETHER VIDEO STAGE 09 - SPLINE TERRAIN CHANNEL INSTALL")
    record(lines, "=" * 96)

    world = load_world()
    actor_subsystem, actors = get_actors()
    clear_previous_install(actor_subsystem, actors, lines)

    _, actors = get_actors()
    remesh_actor = find_actor_by_label(actors, REMESH_LABEL)
    if not remesh_actor:
        raise RuntimeError(f"Required local Remesh actor was not found: {REMESH_LABEL}")

    dependency = find_actor_by_label(actors, DEPENDENCY_LABEL)
    if not dependency:
        raise RuntimeError(f"Required completed dependency was not found: {DEPENDENCY_LABEL}")

    mesh_partition = find_mesh_partition(actors)
    if not mesh_partition:
        raise RuntimeError("Authoritative Mesh Partition actor could not be resolved")

    spline_class = getattr(unreal, "SplineComponent", None)
    modifier_class = getattr(unreal, "SplineModifier", None)
    modifier_actor_class = getattr(unreal, "ModifierActor", unreal.Actor)
    if not spline_class:
        raise RuntimeError("unreal.SplineComponent is unavailable")
    if not modifier_class:
        raise RuntimeError("unreal.SplineModifier is unavailable")

    center = remesh_actor.get_actor_location()
    points, trace_passes = build_spline_points(world, center, lines)

    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Remesh anchor={remesh_actor.get_name()} at {center}")
    record(lines, f"Completed dependency={dependency.get_name()} at {dependency.get_actor_location()}")
    record(lines, f"Affected Mesh Partition={mesh_partition.get_name()}")
    record(lines, f"Trace passes={trace_passes}/{len(points)}")
    record(lines, f"Channel depth={CHANNEL_DEPTH_CM} cm")
    record(lines, f"Plateau distance={PLATEAU_DISTANCE_CM} cm")
    record(lines, f"Falloff distance={FALLOFF_DISTANCE_CM} cm")

    actor = actor_subsystem.spawn_actor_from_class(
        modifier_actor_class,
        center,
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    actor.set_actor_label(SPLINE_LABEL, True)
    actor.set_editor_property("tags", [unreal.Name(TAG)])

    spline = add_component_to_actor(actor, spline_class, lines)
    configure_spline_component(spline, points, lines)

    modifier = add_component_to_actor(actor, modifier_class, lines)
    configure_modifier(modifier, mesh_partition, spline, lines)

    length = spline_length(spline)
    saved = save_map(lines)

    record(lines, f"Spline length cm={length if length is not None else 'UNAVAILABLE'}")
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "INSTALL_RESULT=PASS")
    record(lines, f"SPLINE_ACTOR={SPLINE_LABEL}")
    record(lines, "SPLINE_COMPONENT_CLASS=/Script/Engine.SplineComponent")
    record(lines, "SPLINE_MODIFIER_CLASS=/Script/MeshPartitionEditor.SplineModifier")
    record(lines, "WRITE_MODE=POSITIONS")
    record(lines, f"PLACEMENT_RESULT={'ALL_TERRAIN_TRACES_PASS' if trace_passes == len(points) else 'PARTIAL_FALLBACK_REQUIRES_EDITOR_CHECK'}")
    record(lines, "NEXT_EDITOR_ACTION=Open AetherWorld, select Aether_VideoStage09_SplineChannel, include it in Build To, and inspect the lowered terrain channel. Move spline points manually if a fallback point is above or below the intended surface.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_SPLINE_CHANNEL_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"INSTALL_RESULT=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
