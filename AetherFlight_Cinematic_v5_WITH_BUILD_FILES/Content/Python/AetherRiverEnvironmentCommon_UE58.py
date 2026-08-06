from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
MPD_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoRiverEnvironmentInstall.txt"

SOURCE_SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
SOURCE_REMESH_LABEL = "Aether_VideoStage10_SplineRemesh"
RIVER_LABEL = "Aether_VideoStage11_River"
WATER_ZONE_LABEL = "Aether_VideoStage11_WaterZone"
WETLAND_LABEL = "Aether_VideoStage12_RiverbankWetland"
EXCLUSION_LABEL = "Aether_VideoStage13_RiverExclusion"
ENVIRONMENT_LABEL = "Aether_VideoStage13_RiverEnvironment"
EXCLUSION_TAG = "AetherVideoRiverExclusionStage"
ENVIRONMENT_TAG = "AetherVideoRiverEnvironmentStage"

EXCLUSION_PRIORITY = 56.0
EXCLUSION_PLATEAU_CM = 1400.0
EXCLUSION_FALLOFF_CM = 2400.0
MAX_Z_DISTANCE_CM = 120000.0

ROCK_TOKENS = (
    "rock_collection_04",
    "rock collection 04",
    "environment_rock",
    "/rocks/",
    "rock04",
)
SHRUB_TOKENS = ("abelia", "shrub", "bush")
GROUND_TOKENS = (
    "ophiopogon",
    "lolium",
    "groundcover",
    "ground_cover",
    "ground cover",
    "fern",
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


def actor_tags(actor):
    try:
        return [str(tag) for tag in actor.get_editor_property("tags")]
    except Exception:
        return []


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


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
        combined = f"{actor.get_name()} {class_path(actor)}"
        if "MeshPartition" not in combined and "MeshTerrain" not in combined:
            continue
        fallback.append(actor)
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in actor_tags(actor):
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def clear_previous_install(subsystem, actors, lines):
    removed = []
    for actor in actors:
        label = actor_label(actor)
        tags = actor_tags(actor)
        if label in (EXCLUSION_LABEL, ENVIRONMENT_LABEL) or EXCLUSION_TAG in tags or ENVIRONMENT_TAG in tags:
            subsystem.destroy_actor(actor)
            removed.append(label)
    record(lines, f"Previous Stage13 actors removed={len(removed)}")
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
    record(lines, f"Added component={class_path(component)}")
    return component


def try_set_property(obj, names, value, lines, required=False):
    errors = []
    for name in names:
        try:
            obj.set_editor_property(name, value)
            record(lines, f"Set {obj.get_name()}.{name}={value}")
            return name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    if required:
        raise RuntimeError(f"Could not set any of {names}. Errors={errors}")
    record(lines, f"Property not exposed or rejected: {obj.get_name()} candidates={names}")
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
                record(lines, f"Called {obj.get_name()}.{name}{args}")
                return name, args, result
            except Exception as exc:
                errors.append(f"{name}{args}: {exc}")
    if required:
        raise RuntimeError(f"Could not call any of {names}. Errors={errors}")
    if errors:
        record(lines, f"Call variants failed for {obj.get_name()} names={names}: {errors}")
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
    return None


def list_game_assets():
    try:
        return list(unreal.EditorAssetLibrary.list_assets("/Game", True, False))
    except TypeError:
        return list(unreal.EditorAssetLibrary.list_assets("/Game", recursive=True, include_folder=False))


def discover_static_meshes(asset_paths, tokens, limit):
    results = []
    static_mesh_class = getattr(unreal, "StaticMesh", None)
    if not static_mesh_class:
        return results
    for path in asset_paths:
        lower = path.lower().replace("-", "_")
        if not any(token in lower for token in tokens):
            continue
        if any(skip in lower for skip in ("/material", "/texture", "/mi_", "/m_", "/t_")):
            continue
        try:
            asset = unreal.EditorAssetLibrary.load_asset(path)
        except Exception:
            asset = None
        if isinstance(asset, static_mesh_class):
            results.append((path, asset))
            if len(results) >= limit:
                break
    return results


def channel_names(definition):
    names = []
    try:
        channel_map = definition.get_editor_property("channel_map")
        descriptions = list(channel_map.get_editor_property("channel_descs"))
    except Exception:
        return names
    for description in descriptions:
        try:
            names.append(str(description.get_editor_property("name")))
        except Exception:
            names.append(str(description))
    return names


def configure_spline_component(destination, source, lines):
    try_set_property(destination, ("relative_location",), unreal.Vector(0.0, 0.0, 0.0), lines)
    try_set_property(destination, ("relative_rotation",), unreal.Rotator(0.0, 0.0, 0.0), lines)
    try_set_property(destination, ("relative_scale3d",), unreal.Vector(1.0, 1.0, 1.0), lines)
    destination.clear_spline_points(False)
    local_space = unreal.SplineCoordinateSpace.LOCAL
    count = int(source.get_number_of_spline_points())
    if count != 5:
        raise RuntimeError(f"Stage09 spline must contain five points, found {count}")

    curve_type = getattr(unreal.SplinePointType, "CURVE", None)
    if curve_type is None:
        curve_type = getattr(unreal.SplinePointType, "CURVE_CLAMPED", None)

    for index in range(count):
        point = source.get_location_at_spline_point(index, local_space)
        destination.add_spline_point(point, local_space, False)
        record(lines, f"Copied exclusion spline point {index}={point}")
        try:
            scale = source.get_scale_at_spline_point(index)
            destination.set_scale_at_spline_point(index, scale, False)
            record(lines, f"Copied exclusion spline scale {index}={scale}")
        except Exception as exc:
            record(lines, f"Spline scale copy warning index={index}: {exc}")
        if curve_type is not None:
            try:
                destination.set_spline_point_type(index, curve_type, False)
            except Exception:
                pass

    try_set_property(destination, ("closed_loop",), False, lines)
    try_set_property(destination, ("draw_debug", "b_always_render_in_editor"), True, lines)
    try_set_property(destination, ("hidden_in_game",), True, lines)
    destination.update_spline()
    try:
        destination.modify()
    except Exception:
        pass

    length = float(destination.get_spline_length())
    record(lines, f"Stage13 exclusion spline point count={count}")
    record(lines, f"Stage13 exclusion spline length cm={length}")
    if not (80000.0 <= length <= 170000.0):
        raise RuntimeError(f"Stage13 exclusion spline validation failed: length={length}")
    return length


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
    direct = try_set_property(modifier, ("spline_ptr", "spline_component", "spline"), spline, lines)
    called, _, _ = try_call_variants(modifier, ("bp_set_spline_component",), ((spline,),), lines)
    if not direct and not called:
        raise RuntimeError("SplineModifier could not receive the exclusion SplineComponent")


def make_channel_name(channel_text, lines):
    channel_class = getattr(unreal, "ChannelName", None)
    if not channel_class:
        raise RuntimeError("unreal.ChannelName is unavailable")
    candidates = []
    try:
        candidates.append(channel_class(name=unreal.Name(channel_text)))
    except Exception:
        pass
    try:
        candidates.append(channel_class(unreal.Name(channel_text)))
    except Exception:
        pass
    try:
        value = channel_class()
        if try_set_property(value, ("name", "channel_name"), unreal.Name(channel_text), lines):
            candidates.append(value)
    except Exception:
        pass
    if not candidates:
        raise RuntimeError(f"Could not construct ChannelName for {channel_text}")
    record(lines, f"Constructed ChannelName={candidates[0]}")
    return candidates[0]


def make_weight_entry(channel_text, lines):
    entry_class = getattr(unreal, "SplineModifierWeightEntry", None)
    if not entry_class:
        raise RuntimeError("unreal.SplineModifierWeightEntry is unavailable")
    entry = entry_class()
    channel_prop = try_set_property(
        entry,
        ("weight_channel_name", "channel_name", "channel"),
        make_channel_name(channel_text, lines),
        lines,
        required=True,
    )
    value_prop = try_set_property(entry, ("value", "weight", "target_value"), 1.0, lines, required=True)
    blend = resolve_enum_member("SplineWeightBlendMode", ("ALPHA_BLEND", "MAX", "ADDITIVE"), lines)
    blend_prop = None
    if blend is not None:
        blend_prop = try_set_property(
            entry,
            ("blend_mode", "weight_blend_mode"),
            blend,
            lines,
            required=True,
        )
    return entry, channel_prop, value_prop, blend_prop, blend


def configure_exclusion_modifier(modifier, mesh_partition, spline, lines):
    assign_mesh_partition(modifier, mesh_partition, lines)
    assign_spline_component(modifier, spline, lines)
    try_set_property(modifier, ("priority",), EXCLUSION_PRIORITY, lines, required=True)
    try_set_property(modifier, ("is_disabled", "disabled"), False, lines, required=True)
    try_set_property(modifier, ("write_mode",), 2, lines, required=True)

    entry, channel_prop, value_prop, blend_prop, blend = make_weight_entry("FoliageExclusion", lines)
    try_set_property(modifier, ("weight_channels",), [entry], lines, required=True)
    try_set_property(modifier, ("falloff_distance",), EXCLUSION_FALLOFF_CM, lines, required=True)
    try_set_property(modifier, ("plateau_distance",), EXCLUSION_PLATEAU_CM, lines, required=True)
    try_set_property(modifier, ("max_z_distance",), MAX_Z_DISTANCE_CM, lines, required=True)
    try_set_property(modifier, ("use_spline_scale_for_falloff", "b_use_spline_scale_for_falloff"), True, lines)
    try_set_property(modifier, ("use_spline_scale_for_plateau", "b_use_spline_scale_for_plateau"), True, lines)
    try_set_property(modifier, ("expand_bounds_by_spline_scale", "b_expand_bounds_by_spline_scale"), True, lines)
    try_set_property(modifier, ("use_nearest_spline_frame_for_displacement", "b_use_nearest_spline_frame_for_displacement"), False, lines)
    try_set_property(modifier, ("mesh_closed_interior", "b_mesh_closed_interior"), False, lines)
    try_set_property(modifier, ("draw_projected_spline", "b_draw_projected_spline"), True, lines)
    try_set_property(modifier, ("draw_local_bounds", "b_draw_local_bounds"), True, lines)
    try_set_property(modifier, ("draw_projection_plane", "b_draw_projection_plane"), False, lines)
    try:
        modifier.modify()
    except Exception:
        pass

    write_mode = int(modifier.get_editor_property("write_mode"))
    entries = list(modifier.get_editor_property("weight_channels"))
    priority = float(modifier.get_editor_property("priority"))
    if write_mode != 2 or len(entries) != 1 or abs(priority - EXCLUSION_PRIORITY) > 0.01:
        raise RuntimeError(
            f"Exclusion validation failed: write_mode={write_mode}, entries={len(entries)}, priority={priority}"
        )
    return {
        "channel_prop": channel_prop,
        "value_prop": value_prop,
        "blend_prop": blend_prop,
        "blend": blend,
    }
