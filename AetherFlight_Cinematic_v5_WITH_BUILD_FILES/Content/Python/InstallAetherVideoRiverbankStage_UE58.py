from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
SOURCE_LABEL = "Aether_VideoStage09_SplineChannel"
REMESH_LABEL = "Aether_VideoStage10_SplineRemesh"
RIVER_LABEL = "Aether_VideoStage11_River"
ZONE_LABEL = "Aether_VideoStage11_WaterZone"
STAGE12_LABEL = "Aether_VideoStage12_RiverbankWetland"
STAGE12_TAG = "AetherVideoRiverbankWetlandStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoRiverbankInstall.txt"

CHANNEL_NAME = "Wetland"
PRIORITY = 55.0
PLATEAU_DISTANCE_CM = 1400.0
FALLOFF_DISTANCE_CM = 3200.0
MAX_Z_DISTANCE_CM = 120000.0
WRITE_MODE_WEIGHTS_ONLY = 2
WEIGHT_VALUE = 1.0

REPORT_LINES = []


def record(lines, text=""):
    text = str(text)
    lines.append(text)
    unreal.log_warning(text)


def object_name(obj):
    try:
        return obj.get_name()
    except Exception:
        return type(obj).__name__


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def actor_tags(actor):
    try:
        return [str(tag) for tag in actor.get_editor_property("tags")]
    except Exception:
        return []


def load_world():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def get_actor_subsystem_and_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return subsystem, list(subsystem.get_all_level_actors())


def find_actor(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    return matches[0] if len(matches) == 1 else None


def find_mesh_partition(actors):
    preferred = []
    fallback = []
    for actor in actors:
        try:
            class_path = actor.get_class().get_path_name()
        except Exception:
            class_path = type(actor).__name__
        combined = f"{actor.get_name()} {class_path}"
        if "MeshPartition" not in combined and "MeshTerrain" not in combined:
            continue
        fallback.append(actor)
        tags = actor_tags(actor)
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in tags:
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def clear_previous_install(subsystem, actors, lines):
    removed = []
    for actor in actors:
        label = actor_label(actor)
        tags = actor_tags(actor)
        if label == STAGE12_LABEL or STAGE12_TAG in tags:
            subsystem.destroy_actor(actor)
            removed.append(label)
    record(lines, f"Previous Stage12 actors removed={len(removed)}")
    for label in removed:
        record(lines, f"  removed={label}")


def find_single_component(actor, component_class, description):
    components = list(actor.get_components_by_class(component_class))
    if len(components) != 1:
        raise RuntimeError(
            f"Expected exactly one {description} on {actor_label(actor)}, found {len(components)}"
        )
    return components[0]


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


def try_get_property(obj, names):
    for name in names:
        try:
            return name, obj.get_editor_property(name)
        except Exception:
            continue
    return None, None


def try_set_property(obj, names, value, lines, required=False):
    errors = []
    for name in names:
        try:
            obj.set_editor_property(name, value)
            record(lines, f"Set {object_name(obj)}.{name}={value}")
            return name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    if required:
        raise RuntimeError(f"Could not set any of {names}. Errors={errors}")
    record(lines, f"Property not exposed or rejected: {object_name(obj)} candidates={names}")
    return None


def try_call_variants(obj, names, arg_variants, lines, required=False):
    errors = []
    for name in names:
        method = getattr(obj, name, None)
        if not callable(method):
            continue
        for args in arg_variants:
            try:
                result = method(*args)
                record(lines, f"Called {object_name(obj)}.{name}{args}")
                return name, args, result
            except Exception as exc:
                errors.append(f"{name}{args}: {exc}")
    if required:
        raise RuntimeError(f"Could not call any of {names}. Errors={errors}")
    if errors:
        record(lines, f"Call variants failed for {object_name(obj)} names={names}: {errors}")
    return None, None, None


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
    record(lines, f"No matching member on unreal.{enum_name}; members={[name for name in dir(enum_type) if name.isupper()]}")
    return None


def assign_mesh_partition(component, mesh_partition, lines):
    direct = try_set_property(
        component,
        ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"),
        mesh_partition,
        lines,
    )
    called, _, _ = try_call_variants(
        component,
        ("bp_set_affected_mega_mesh", "set_affected_mega_mesh"),
        ((mesh_partition,),),
        lines,
    )
    if not direct and not called:
        raise RuntimeError("SplineModifier could not be assigned to the authoritative Mesh Partition")


def assign_spline_component(modifier, spline, lines):
    direct = try_set_property(
        modifier,
        ("spline_ptr", "spline_component", "spline"),
        spline,
        lines,
    )
    blueprint, _, _ = try_call_variants(
        modifier,
        ("bp_set_spline_component",),
        ((spline,),),
        lines,
    )
    native, _, _ = try_call_variants(
        modifier,
        ("set_spline_component",),
        ((spline, True), (spline,)),
        lines,
    )
    if not direct and not blueprint and not native:
        raise RuntimeError("SplineModifier could not receive the Stage12 SplineComponent")


def copy_spline(source, destination, lines):
    count = int(source.get_number_of_spline_points())
    if count != 5:
        raise RuntimeError(f"Stage09 spline must contain exactly five points, found {count}")

    local_space = unreal.SplineCoordinateSpace.LOCAL
    destination.clear_spline_points(False)

    for index in range(count):
        location = source.get_location_at_spline_point(index, local_space)
        destination.add_spline_point(location, local_space, False)
        record(lines, f"Copied local spline point {index}={location}")

        try:
            point_type = source.get_spline_point_type(index)
            destination.set_spline_point_type(index, point_type, False)
        except Exception as exc:
            record(lines, f"Point type copy warning index={index}: {exc}")

        try:
            scale = source.get_scale_at_spline_point(index)
            destination.set_scale_at_spline_point(index, scale, False)
            record(lines, f"Copied spline scale {index}={scale}")
        except Exception as exc:
            record(lines, f"Spline scale copy warning index={index}: {exc}")

        try:
            arrive = source.get_arrive_tangent_at_spline_point(index, local_space)
            leave = source.get_leave_tangent_at_spline_point(index, local_space)
            destination.set_tangents_at_spline_point(index, arrive, leave, local_space, False)
        except Exception as exc:
            record(lines, f"Spline tangent copy warning index={index}: {exc}")

    try:
        destination.set_editor_property("closed_loop", False)
    except Exception:
        setter = getattr(destination, "set_closed_loop", None)
        if callable(setter):
            setter(False, False)

    destination.update_spline()
    try_set_property(destination, ("draw_debug", "b_always_render_in_editor"), True, lines)
    try_set_property(destination, ("hidden_in_game",), True, lines)

    length = float(destination.get_spline_length())
    copied_count = int(destination.get_number_of_spline_points())
    record(lines, f"Stage12 spline point count={copied_count}")
    record(lines, f"Stage12 spline length cm={length}")
    if copied_count != count:
        raise RuntimeError(f"Stage12 spline point count mismatch: {copied_count}")
    if not (80000.0 <= length <= 170000.0):
        raise RuntimeError(f"Stage12 spline length is outside expected local range: {length} cm")

    try:
        destination.modify()
    except Exception:
        pass
    return length


def channel_value_candidates(lines):
    values = [unreal.Name(CHANNEL_NAME), CHANNEL_NAME]
    channel_class = getattr(unreal, "ChannelName", None)
    if not channel_class:
        return values

    constructor_attempts = (
        {"name": unreal.Name(CHANNEL_NAME)},
        {"channel_name": unreal.Name(CHANNEL_NAME)},
        {"value": unreal.Name(CHANNEL_NAME)},
        {},
    )
    for kwargs in constructor_attempts:
        try:
            candidate = channel_class(**kwargs)
        except Exception:
            continue
        if not kwargs:
            for property_names in (
                ("name",),
                ("channel_name",),
                ("value",),
            ):
                prop = try_set_property(candidate, property_names, unreal.Name(CHANNEL_NAME), lines)
                if prop:
                    break
        values.insert(0, candidate)
        record(lines, f"Constructed ChannelName candidate={candidate}")
        break
    return values


def make_weight_entry(lines):
    entry_class = getattr(unreal, "SplineModifierWeightEntry", None)
    if not entry_class:
        raise RuntimeError("unreal.SplineModifierWeightEntry is unavailable")

    blend_mode = resolve_enum_member(
        "SplineWeightBlendMode",
        ("ALPHA_BLEND", "ALPHABLEND", "ALPHA", "MAX"),
        lines,
    )
    if blend_mode is None:
        raise RuntimeError("SplineWeightBlendMode AlphaBlend could not be resolved")

    entry = entry_class()
    record(lines, f"Created weight entry={entry}")

    channel_property = None
    channel_errors = []
    for value in channel_value_candidates(lines):
        try:
            channel_property = try_set_property(
                entry,
                ("channel_name", "weight_channel_name", "name"),
                value,
                lines,
            )
            if channel_property:
                break
        except Exception as exc:
            channel_errors.append(str(exc))
    if not channel_property:
        raise RuntimeError(f"Could not assign Wetland channel to weight entry. Errors={channel_errors}")

    value_property = try_set_property(
        entry,
        ("value", "weight", "weight_value", "channel_value", "target_value"),
        WEIGHT_VALUE,
        lines,
    )
    if not value_property:
        record(lines, "Weight entry exposes no value property; retaining its engine default value.")

    blend_property = try_set_property(
        entry,
        ("blend_mode", "weight_blend_mode"),
        blend_mode,
        lines,
        required=True,
    )

    return entry, channel_property, value_property, blend_property, blend_mode


def configure_modifier(modifier, mesh_partition, spline, lines):
    assign_mesh_partition(modifier, mesh_partition, lines)
    assign_spline_component(modifier, spline, lines)

    try_set_property(modifier, ("priority",), PRIORITY, lines, required=True)
    try_set_property(modifier, ("is_disabled", "disabled"), False, lines, required=True)

    # Official UE 5.8 bitmask: Positions=1, Weights=2. Stage 12 must write
    # only weights so it cannot alter any vertex position authored by Stage 09.
    try_set_property(
        modifier,
        ("write_mode",),
        WRITE_MODE_WEIGHTS_ONLY,
        lines,
        required=True,
    )

    entry, channel_prop, value_prop, blend_prop, blend_mode = make_weight_entry(lines)
    try_set_property(
        modifier,
        ("weight_channels",),
        [entry],
        lines,
        required=True,
    )

    falloff_method, _, _ = try_call_variants(
        modifier,
        ("set_falloff_distance",),
        ((FALLOFF_DISTANCE_CM,),),
        lines,
    )
    if not falloff_method:
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

    max_z_method, _, _ = try_call_variants(
        modifier,
        ("set_max_z_distance",),
        ((MAX_Z_DISTANCE_CM,),),
        lines,
    )
    if not max_z_method:
        try_set_property(
            modifier,
            ("max_z_distance",),
            MAX_Z_DISTANCE_CM,
            lines,
            required=True,
        )

    scale_method, _, _ = try_call_variants(
        modifier,
        ("set_use_spline_scale_for_falloff",),
        ((True,),),
        lines,
    )
    if not scale_method:
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

    updated, _, _ = try_call_variants(
        modifier,
        ("update_spline_data",),
        ((),),
        lines,
    )
    if not updated:
        record(lines, "UpdateSplineData is not Python-callable; selecting or moving the Stage12 spline once in the editor will refresh it.")

    try:
        modifier.modify()
    except Exception:
        pass

    write_mode = int(modifier.get_editor_property("write_mode"))
    weight_channels = list(modifier.get_editor_property("weight_channels"))
    priority = float(modifier.get_editor_property("priority"))
    record(lines, f"Validated write_mode={write_mode}")
    record(lines, f"Validated weight channel entries={len(weight_channels)}")
    record(lines, f"Validated priority={priority}")

    if write_mode != WRITE_MODE_WEIGHTS_ONLY:
        raise RuntimeError(f"Stage12 write_mode must be 2 (Weights only), found {write_mode}")
    if len(weight_channels) != 1:
        raise RuntimeError(f"Stage12 must contain exactly one weight-channel entry, found {len(weight_channels)}")
    if abs(priority - PRIORITY) > 0.01:
        raise RuntimeError(f"Stage12 priority mismatch: {priority}")

    return {
        "channel_property": channel_prop,
        "value_property": value_prop,
        "blend_property": blend_prop,
        "blend_mode": blend_mode,
    }


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
    record(lines, "AETHER VIDEO STAGE 12 - RIVERBANK WETLAND WEIGHT INSTALL")
    record(lines, "=" * 96)
    record(lines, "Writes only the Wetland channel. Terrain positions, river geometry, and water height are not modified.")
    record(lines, "No compiled Mesh Partition build is started.")

    world = load_world()
    actor_subsystem, actors = get_actor_subsystem_and_actors()
    clear_previous_install(actor_subsystem, actors, lines)

    _, actors = get_actor_subsystem_and_actors()
    source_actor = find_actor(actors, SOURCE_LABEL)
    remesh_actor = find_actor(actors, REMESH_LABEL)
    river_actor = find_actor(actors, RIVER_LABEL)
    zone_actor = find_actor(actors, ZONE_LABEL)
    mesh_partition = find_mesh_partition(actors)

    for label, actor in (
        (SOURCE_LABEL, source_actor),
        (REMESH_LABEL, remesh_actor),
        (RIVER_LABEL, river_actor),
        (ZONE_LABEL, zone_actor),
    ):
        if not actor:
            raise RuntimeError(f"Required saved dependency was not found: {label}")
    if not mesh_partition:
        raise RuntimeError("Authoritative Mesh Partition actor could not be resolved")

    spline_class = getattr(unreal, "SplineComponent", None)
    modifier_class = getattr(unreal, "SplineModifier", None)
    modifier_actor_class = getattr(unreal, "ModifierActor", None)
    if not spline_class or not modifier_class or not modifier_actor_class:
        raise RuntimeError(
            f"Required classes unavailable: SplineComponent={spline_class}, "
            f"SplineModifier={modifier_class}, ModifierActor={modifier_actor_class}"
        )

    source_spline = find_single_component(source_actor, spline_class, "Stage09 SplineComponent")
    source_location = source_actor.get_actor_location()
    source_rotation = source_actor.get_actor_rotation()

    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Source actor={SOURCE_LABEL} at {source_location}")
    record(lines, f"Source spline length cm={source_spline.get_spline_length()}")
    record(lines, f"Stage10 dependency={REMESH_LABEL}")
    record(lines, f"Stage11 river dependency={RIVER_LABEL}")
    record(lines, f"Stage11 WaterZone dependency={ZONE_LABEL}")
    record(lines, f"Affected Mesh Partition={mesh_partition.get_name()}")

    actor = actor_subsystem.spawn_actor_from_class(
        modifier_actor_class,
        source_location,
        source_rotation,
        False,
    )
    if not actor:
        raise RuntimeError("Stage12 ModifierActor spawn returned None")
    actor.set_actor_label(STAGE12_LABEL, True)
    actor.set_editor_property("tags", [unreal.Name(STAGE12_TAG)])
    actor.set_actor_scale3d(unreal.Vector(1.0, 1.0, 1.0))

    spline = add_component_to_actor(actor, spline_class, lines)
    try_set_property(spline, ("relative_location",), unreal.Vector(0.0, 0.0, 0.0), lines)
    try_set_property(spline, ("relative_rotation",), unreal.Rotator(0.0, 0.0, 0.0), lines)
    try_set_property(spline, ("relative_scale3d",), unreal.Vector(1.0, 1.0, 1.0), lines)
    spline_length = copy_spline(source_spline, spline, lines)

    modifier = add_component_to_actor(actor, modifier_class, lines)
    config = configure_modifier(modifier, mesh_partition, spline, lines)

    saved = save_map(lines)
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "INSTALL_RESULT=PASS")
    record(lines, f"RIVERBANK_ACTOR={STAGE12_LABEL}")
    record(lines, f"SPLINE_COMPONENT_CLASS={spline.get_class().get_path_name()}")
    record(lines, f"SPLINE_MODIFIER_CLASS={modifier.get_class().get_path_name()}")
    record(lines, f"SPLINE_POINTS={spline.get_number_of_spline_points()}")
    record(lines, f"SPLINE_LENGTH_CM={spline_length}")
    record(lines, f"WEIGHT_CHANNEL={CHANNEL_NAME}")
    record(lines, f"WEIGHT_VALUE={WEIGHT_VALUE}")
    record(lines, f"WEIGHT_ENTRY_CHANNEL_PROPERTY={config['channel_property']}")
    record(lines, f"WEIGHT_ENTRY_VALUE_PROPERTY={config['value_property'] or 'ENGINE_DEFAULT'}")
    record(lines, f"WEIGHT_ENTRY_BLEND_PROPERTY={config['blend_property']}")
    record(lines, f"WEIGHT_BLEND_MODE={config['blend_mode']}")
    record(lines, f"WRITE_MODE={WRITE_MODE_WEIGHTS_ONLY}")
    record(lines, "POSITION_DEFORMATION=DISABLED_BY_WRITE_MODE")
    record(lines, f"PLATEAU_DISTANCE_CM={PLATEAU_DISTANCE_CM}")
    record(lines, f"FALLOFF_DISTANCE_CM={FALLOFF_DISTANCE_CM}")
    record(lines, f"PRIORITY={PRIORITY}")
    record(lines, "NEXT_EDITOR_ACTION=Open AetherWorld, Build To through Aether_VideoStage12_RiverbankWetland at priority 55, and compare the riverbanks with Disabled in Editor checked versus unchecked. If the material does not refresh, move the Stage12 spline slightly and Ctrl+Z once.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    write_report(lines)
    unreal.log_warning(f"AETHER_VIDEO_RIVERBANK_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    record(REPORT_LINES, "")
    record(REPORT_LINES, "INSTALL_RESULT=FAIL")
    record(REPORT_LINES, f"ERROR={type(exc).__name__}: {exc}")
    record(REPORT_LINES, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report(REPORT_LINES)
    unreal.log_error(f"AETHER_VIDEO_RIVERBANK_INSTALL_FAILED={type(exc).__name__}: {exc}")
    raise
