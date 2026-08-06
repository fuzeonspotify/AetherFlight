from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
SOURCE_SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
SOURCE_REMESH_LABEL = "Aether_VideoStage10_SplineRemesh"
RIVER_LABEL = "Aether_VideoStage11_River"
ZONE_LABEL = "Aether_VideoStage11_WaterZone"
RIVER_TAG = "AetherVideoRiverStage"
ZONE_TAG = "AetherVideoWaterZoneStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoRiverInstall.txt"

RIVER_PRIORITY = 50.0
WATER_SURFACE_OFFSET_CM = 300.0
RIVER_HALF_WIDTH_CM = 1000.0
RIVER_DEPTH_CM = 300.0
RIVER_VELOCITY_CM_PER_SEC = 150.0
WATER_ZONE_EXTENT_CM = 160000.0
MAX_Z_DISTANCE_CM = 120000.0

RIVER_MODIFIER_CLASS_CANDIDATES = (
    "RiverModifier",
    "WaterBodyRiverModifier",
    "MeshPartitionRiverModifier",
)


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


def actor_tags(actor):
    try:
        return [str(tag) for tag in actor.get_editor_property("tags")]
    except Exception:
        return []


def clear_previous_install(subsystem, actors, lines):
    removed = []
    for actor in actors:
        label = actor_label(actor)
        tags = actor_tags(actor)
        if (
            label in (RIVER_LABEL, ZONE_LABEL)
            or RIVER_TAG in tags
            or ZONE_TAG in tags
        ):
            subsystem.destroy_actor(actor)
            removed.append(label)
    record(lines, f"Previous Stage11 actors removed={len(removed)}")
    for label in removed:
        record(lines, f"  removed={label}")


def find_actor(actors, label):
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
        tags = actor_tags(actor)
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in tags:
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def find_single_component(actor, component_class, description):
    components = list(actor.get_components_by_class(component_class))
    if len(components) != 1:
        raise RuntimeError(
            f"Expected exactly one {description} on {actor_label(actor)}, found {len(components)}"
        )
    return components[0]


def resolve_class(candidates):
    for name in candidates:
        cls = getattr(unreal, name, None)
        if cls:
            return name, cls
    return None, None


def try_set_property(obj, names, value, lines, required=False):
    errors = []
    for name in names:
        try:
            obj.set_editor_property(name, value)
            record(lines, f"Set {obj.get_name()}.{name}={value}")
            return True
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    if required:
        raise RuntimeError(f"Could not set any of {names}. Errors={errors}")
    record(lines, f"Property not exposed or rejected: {obj.get_name()} candidates={names}")
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


def get_water_body_component(river_actor, lines):
    called, component = try_call(
        river_actor,
        ("get_water_body_component",),
        (),
        lines,
    )
    if called and component:
        return component

    component_class = getattr(unreal, "WaterBodyRiverComponent", None)
    if not component_class:
        raise RuntimeError("unreal.WaterBodyRiverComponent is unavailable")
    return find_single_component(river_actor, component_class, "WaterBodyRiverComponent")


def get_water_spline(river_actor, body_component, lines):
    for owner in (river_actor, body_component):
        called, spline = try_call(owner, ("get_water_spline",), (), lines)
        if called and spline:
            return spline

    spline_class = getattr(unreal, "WaterSplineComponent", None)
    if not spline_class:
        raise RuntimeError("unreal.WaterSplineComponent is unavailable")
    return find_single_component(river_actor, spline_class, "WaterSplineComponent")


def make_water_spline_defaults(lines):
    defaults_class = getattr(unreal, "WaterSplineCurveDefaults", None)
    if not defaults_class:
        raise RuntimeError("unreal.WaterSplineCurveDefaults is unavailable")

    try:
        defaults = defaults_class(
            default_width=RIVER_HALF_WIDTH_CM,
            default_depth=RIVER_DEPTH_CM,
            default_velocity=RIVER_VELOCITY_CM_PER_SEC,
            default_audio_intensity=1.0,
        )
        record(lines, "Created WaterSplineCurveDefaults through constructor")
        return defaults
    except Exception as constructor_exc:
        record(lines, f"WaterSplineCurveDefaults constructor warning={constructor_exc}")

    defaults = defaults_class()
    for names, value in (
        (("default_width",), RIVER_HALF_WIDTH_CM),
        (("default_depth",), RIVER_DEPTH_CM),
        (("default_velocity",), RIVER_VELOCITY_CM_PER_SEC),
        (("default_audio_intensity",), 1.0),
    ):
        try_set_property(defaults, names, value, lines, required=True)
    return defaults


def source_local_points(source_spline, lines):
    count = int(source_spline.get_number_of_spline_points())
    if count != 5:
        raise RuntimeError(f"Stage09 spline must contain exactly five points, found {count}")

    local_space = unreal.SplineCoordinateSpace.LOCAL
    points = []
    for index in range(count):
        point = source_spline.get_location_at_spline_point(index, local_space)
        water_point = unreal.Vector(
            float(point.x),
            float(point.y),
            float(point.z) + WATER_SURFACE_OFFSET_CM,
        )
        points.append(water_point)
        record(lines, f"River local point {index}={water_point}")
    return points


def configure_water_spline(water_spline, points, lines):
    defaults = make_water_spline_defaults(lines)
    try_set_property(
        water_spline,
        ("water_spline_defaults",),
        defaults,
        lines,
        required=True,
    )

    reset, _ = try_call(water_spline, ("reset_spline",), (points,), lines)
    if not reset:
        water_spline.clear_spline_points(True)
        local_space = unreal.SplineCoordinateSpace.LOCAL
        for point in points:
            water_spline.add_spline_point(point, local_space, False)
        water_spline.update_spline()
        record(lines, "Water spline rebuilt through clear/add/update fallback")

    curve_type = getattr(unreal.SplinePointType, "CURVE", None)
    if curve_type is None:
        curve_type = getattr(unreal.SplinePointType, "CURVE_CLAMPED", None)
    for index in range(len(points)):
        if curve_type is not None:
            try:
                water_spline.set_spline_point_type(index, curve_type, False)
            except Exception as exc:
                record(lines, f"Water spline point type warning index={index}: {exc}")

    try:
        water_spline.set_editor_property("closed_loop", False)
    except Exception:
        pass

    try_call(water_spline, ("synchronize_water_properties",), (), lines)
    try_call(
        water_spline,
        ("k2_synchronize_and_broadcast_data_change", "synchronize_and_broadcast_data_change"),
        (),
        lines,
    )
    try:
        water_spline.update_spline()
        water_spline.modify()
    except Exception:
        pass

    count = int(water_spline.get_number_of_spline_points())
    length = float(water_spline.get_spline_length())
    record(lines, f"Water spline point count={count}")
    record(lines, f"Water spline length cm={length}")
    if count != len(points):
        raise RuntimeError(f"Water spline point count mismatch: {count}")
    if not (80000.0 <= length <= 170000.0):
        raise RuntimeError(f"Water spline length is outside expected local range: {length} cm")
    return length


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
        raise RuntimeError("RiverModifier could not be assigned to the authoritative Mesh Partition")


def configure_river_modifier(river_actor, mesh_partition, lines):
    existing = []
    for base_class in (unreal.ActorComponent, unreal.SceneComponent):
        try:
            for component in river_actor.get_components_by_class(base_class):
                path = component.get_class().get_path_name()
                if ("RiverModifier" in path or "WaterModifier" in path) and component not in existing:
                    existing.append(component)
        except Exception:
            pass

    if len(existing) > 1:
        raise RuntimeError(f"Multiple water modifiers were found on Stage11 river: {len(existing)}")

    if existing:
        modifier = existing[0]
        modifier_source = "EXISTING_COMPONENT"
        record(lines, f"Using existing water modifier={modifier.get_class().get_path_name()}")
    else:
        modifier_name, modifier_class = resolve_class(RIVER_MODIFIER_CLASS_CANDIDATES)
        if not modifier_class:
            raise RuntimeError(
                f"No concrete RiverModifier class is exposed. Candidates={RIVER_MODIFIER_CLASS_CANDIDATES}"
            )
        modifier = add_component_to_actor(river_actor, modifier_class, lines)
        modifier_source = f"ADDED_unreal.{modifier_name}"

    assign_mesh_partition(modifier, mesh_partition, lines)
    try_set_property(modifier, ("priority",), RIVER_PRIORITY, lines, required=True)
    try_set_property(modifier, ("is_disabled", "disabled"), False, lines, required=True)

    called, _ = try_call(
        modifier,
        ("set_max_z_distance",),
        (MAX_Z_DISTANCE_CM,),
        lines,
    )
    if not called:
        try_set_property(
            modifier,
            ("max_z_distance",),
            MAX_Z_DISTANCE_CM,
            lines,
        )

    try:
        modifier.modify()
    except Exception:
        pass
    return modifier, modifier_source


def configure_water_zone(zone, body_component, lines):
    extent = unreal.Vector2D(WATER_ZONE_EXTENT_CM, WATER_ZONE_EXTENT_CM)
    called, _ = try_call(zone, ("set_zone_extent",), (extent,), lines)
    if not called:
        try_set_property(zone, ("zone_extent",), extent, lines, required=True)

    water_mesh = None
    called, water_mesh = try_call(zone, ("get_water_mesh_component",), (), lines)
    if not called or not water_mesh:
        try:
            water_mesh = zone.get_editor_property("water_mesh")
        except Exception:
            water_mesh = None

    if water_mesh:
        try_set_property(water_mesh, ("tile_size",), 2400.0, lines)
        try_set_property(water_mesh, ("tessellation_factor",), 6, lines)
        try_call(water_mesh, ("update",), (), lines)
        try_call(water_mesh, ("mark_water_mesh_grid_dirty",), (), lines)

    try_call(zone, ("add_water_body_component",), (body_component,), lines)
    return water_mesh


def connect_body_to_zone(body_component, zone, lines):
    called, _ = try_call(
        body_component,
        ("set_water_zone_override",),
        (zone,),
        lines,
    )
    if called:
        return "SETTER"

    direct = try_set_property(
        body_component,
        ("water_zone_override",),
        zone,
        lines,
    )
    return "PROPERTY" if direct else "OVERLAP_DISCOVERY"


def notify_water_body(river_actor, body_component, water_spline, lines):
    try_call(
        river_actor,
        ("on_water_body_changed",),
        (True, True),
        lines,
    )
    try_call(
        body_component,
        ("on_water_body_changed",),
        (True, True),
        lines,
    )
    try_call(
        water_spline,
        ("k2_synchronize_and_broadcast_data_change", "synchronize_and_broadcast_data_change"),
        (),
        lines,
    )
    try:
        body_component.modify()
        river_actor.modify()
    except Exception:
        pass


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
    record(lines, "AETHER VIDEO STAGE 11 - LOCAL MESH TERRAIN RIVER INSTALL")
    record(lines, "=" * 96)

    world = load_world()
    actor_subsystem, actors = get_actors()
    clear_previous_install(actor_subsystem, actors, lines)

    _, actors = get_actors()
    source_actor = find_actor(actors, SOURCE_SPLINE_LABEL)
    remesh_actor = find_actor(actors, SOURCE_REMESH_LABEL)
    mesh_partition = find_mesh_partition(actors)

    if not source_actor:
        raise RuntimeError(f"Required Stage09 actor was not found: {SOURCE_SPLINE_LABEL}")
    if not remesh_actor:
        raise RuntimeError(f"Required Stage10 actor was not found: {SOURCE_REMESH_LABEL}")
    if not mesh_partition:
        raise RuntimeError("Authoritative Mesh Partition actor could not be resolved")

    source_spline_class = getattr(unreal, "SplineComponent", None)
    river_class = getattr(unreal, "WaterBodyRiver", None)
    zone_class = getattr(unreal, "WaterZone", None)
    if not source_spline_class:
        raise RuntimeError("unreal.SplineComponent is unavailable")
    if not river_class:
        raise RuntimeError("unreal.WaterBodyRiver is unavailable")
    if not zone_class:
        raise RuntimeError("unreal.WaterZone is unavailable")

    source_spline = find_single_component(source_actor, source_spline_class, "Stage09 SplineComponent")
    source_location = source_actor.get_actor_location()
    source_rotation = source_actor.get_actor_rotation()
    points = source_local_points(source_spline, lines)

    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Source actor={source_actor.get_name()} at {source_location}")
    record(lines, f"Source spline length cm={source_spline.get_spline_length()}")
    record(lines, f"Stage10 dependency={remesh_actor.get_name()}")
    record(lines, f"Affected Mesh Partition={mesh_partition.get_name()}")

    zone = actor_subsystem.spawn_actor_from_class(
        zone_class,
        source_location,
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    zone.set_actor_label(ZONE_LABEL, True)
    zone.set_editor_property("tags", [unreal.Name(ZONE_TAG)])

    river = actor_subsystem.spawn_actor_from_class(
        river_class,
        source_location,
        source_rotation,
        False,
    )
    river.set_actor_label(RIVER_LABEL, True)
    river.set_editor_property("tags", [unreal.Name(RIVER_TAG)])

    body_component = get_water_body_component(river, lines)
    water_spline = get_water_spline(river, body_component, lines)
    water_spline_length = configure_water_spline(water_spline, points, lines)

    modifier, modifier_source = configure_river_modifier(
        river,
        mesh_partition,
        lines,
    )
    water_mesh = configure_water_zone(zone, body_component, lines)
    zone_connection = connect_body_to_zone(body_component, zone, lines)
    notify_water_body(river, body_component, water_spline, lines)

    saved = save_map(lines)

    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "INSTALL_RESULT=PASS")
    record(lines, f"RIVER_ACTOR={RIVER_LABEL}")
    record(lines, f"WATER_ZONE_ACTOR={ZONE_LABEL}")
    record(lines, f"RIVER_CLASS={river.get_class().get_path_name()}")
    record(lines, f"WATER_BODY_COMPONENT_CLASS={body_component.get_class().get_path_name()}")
    record(lines, f"WATER_SPLINE_CLASS={water_spline.get_class().get_path_name()}")
    record(lines, f"RIVER_MODIFIER_CLASS={modifier.get_class().get_path_name()}")
    record(lines, f"RIVER_MODIFIER_SOURCE={modifier_source}")
    record(lines, f"WATER_MESH_COMPONENT={'YES' if water_mesh else 'CHECK_IN_EDITOR'}")
    record(lines, f"WATER_ZONE_CONNECTION={zone_connection}")
    record(lines, f"WATER_SPLINE_LENGTH_CM={water_spline_length}")
    record(lines, f"RIVER_HALF_WIDTH_CM={RIVER_HALF_WIDTH_CM}")
    record(lines, f"RIVER_TOTAL_WIDTH_CM={RIVER_HALF_WIDTH_CM * 2.0}")
    record(lines, f"RIVER_DEPTH_CM={RIVER_DEPTH_CM}")
    record(lines, f"WATER_SURFACE_OFFSET_ABOVE_STAGE09_CM={WATER_SURFACE_OFFSET_CM}")
    record(lines, f"WATER_ZONE_EXTENT_CM={WATER_ZONE_EXTENT_CM}")
    record(lines, f"PRIORITY={RIVER_PRIORITY}")
    record(lines, "NEXT_EDITOR_ACTION=Open AetherWorld, select Aether_VideoStage11_River, verify its five-point water spline follows Stage09, Build To through its RiverModifier, and use r.Water.WaterMesh.ShowWireframe 1 to confirm water tiles.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_RIVER_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"INSTALL_RESULT=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
