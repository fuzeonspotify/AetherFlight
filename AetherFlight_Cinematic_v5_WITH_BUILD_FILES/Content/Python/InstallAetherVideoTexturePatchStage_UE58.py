from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
DEPENDENCY_LABEL = "Aether_VideoStage07_BooleanCave"
TEXTURE_LABEL = "Aether_VideoStage08_TexturePatch"
TAG = "AetherVideoTexturePatchStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoTexturePatchInstall.txt"

TEXTURE_PATH = "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Rock_Weight"
TRACE_TOP_Z = 900000.0
TRACE_BOTTOM_Z = -300000.0
OFFSET_X_CM = 32000.0
OFFSET_Y_CM = 26000.0
COVERAGE_CM = 24000.0
HEIGHT_SCALE_CM = 1800.0
ZERO_VALUE = 0.5


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
        if actor_label(actor) == TEXTURE_LABEL or TAG in tags:
            subsystem.destroy_actor(actor)
            removed += 1
    record(lines, f"Previous texture patch actors removed={removed}")


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
            world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False, [], unreal.DrawDebugTrace.NONE, True))
    except Exception as exc:
        record(lines, f"Visibility trace warning={exc}")
    try:
        attempts.append(unreal.SystemLibrary.line_trace_single_by_profile(
            world, start, end, "BlockAll", False, [],
            unreal.DrawDebugTrace.NONE, True))
    except Exception as exc:
        record(lines, f"BlockAll trace warning={exc}")
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


def try_get_property(obj, names, lines):
    for name in names:
        try:
            value = obj.get_editor_property(name)
            record(lines, f"Read {obj.get_name()}.{name}={value}")
            return True, value, name
        except Exception:
            continue
    record(lines, f"Property not readable: {obj.get_name()} candidates={names}")
    return False, None, None


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


def assign_mesh_partition(component, mesh_partition, lines):
    direct = try_set_property(component,
        ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"),
        mesh_partition, lines)
    called, _ = try_call(component,
        ("bp_set_affected_mega_mesh", "set_affected_mega_mesh"),
        (mesh_partition,), lines)
    if not direct and not called:
        raise RuntimeError("TexturePatchModifier could not be assigned to the Mesh Partition")


def create_height_entry(component, lines):
    entry_class = getattr(unreal, "TexturePatchHeightEntry", None)
    if not entry_class:
        raise RuntimeError("unreal.TexturePatchHeightEntry is unavailable")
    try:
        entry = unreal.new_object(entry_class, outer=component)
        record(lines, "Created TexturePatchHeightEntry with component outer")
    except Exception as first_exc:
        record(lines, f"new_object keyword form warning={first_exc}")
        try:
            entry = unreal.new_object(entry_class, component)
            record(lines, "Created TexturePatchHeightEntry with positional outer")
        except Exception as second_exc:
            raise RuntimeError(f"Could not create TexturePatchHeightEntry: {second_exc}")
    if not entry:
        raise RuntimeError("TexturePatchHeightEntry creation returned None")
    return entry


def get_or_create_height_entry(component, lines):
    called, entry = try_call(component, ("get_height_channel",), (), lines)
    if called and entry:
        record(lines, f"Height entry={entry.get_class().get_path_name()} | source=get_height_channel")
        return entry

    readable, entry, property_name = try_get_property(
        component, ("height_channel", "height_entry", "height_displacement"), lines)
    if readable and entry:
        record(lines, f"Height entry={entry.get_class().get_path_name()} | source=property:{property_name}")
        return entry

    entry = create_height_entry(component, lines)
    property_set = try_set_property(
        component, ("height_channel", "height_entry", "height_displacement"), entry, lines)
    method_set, _ = try_call(
        component, ("set_height_channel", "bp_set_height_channel"), (entry,), lines)
    if not property_set and not method_set:
        api_names = sorted(name for name in dir(component)
                           if "height" in name.lower() or "channel" in name.lower())
        record(lines, f"Height/channel component API names={','.join(api_names)}")
        raise RuntimeError(
            "TexturePatchModifier could not accept the height entry through its instanced property or setter")

    called, verified = try_call(component, ("get_height_channel",), (), lines)
    if called and verified:
        entry = verified
    else:
        readable, verified, _ = try_get_property(
            component, ("height_channel", "height_entry", "height_displacement"), lines)
        if readable and verified:
            entry = verified
    record(lines, f"Height entry={entry.get_class().get_path_name()} | source=created_and_assigned")
    return entry


def configure_height_entry(entry, texture, lines):
    texture_set, _ = try_call(entry, ("set_texture_asset",), (texture,), lines)
    if not texture_set:
        texture_set = try_set_property(entry, ("texture_asset",), texture, lines)
    if not texture_set:
        raise RuntimeError("TexturePatchHeightEntry could not receive the source texture")
    channel_set, _ = try_call(entry, ("set_texture_channel_index",), (0,), lines)
    if not channel_set:
        try_set_property(entry, ("texture_channel_index",), 0, lines, required=True)
    blend_value = getattr(unreal.TexturePatchBlendMode, "ADDITIVE", None)
    if blend_value is not None:
        blend_set, _ = try_call(entry, ("set_texture_patch_blend_mode",), (blend_value,), lines)
        if not blend_set:
            try_set_property(entry, ("blend_mode", "texture_patch_blend_mode"), blend_value, lines)
    alpha_value = getattr(unreal.TexturePatchAlphaMode, "ALWAYS_ONE", None)
    if alpha_value is not None:
        alpha_set, _ = try_call(entry, ("set_alpha_blending_mode",), (alpha_value,), lines)
        if not alpha_set:
            try_set_property(entry, ("alpha_mode",), alpha_value, lines)
    try_set_property(entry, ("encoding_scale",), float(HEIGHT_SCALE_CM), lines, required=True)
    try_set_property(entry, ("zero_in_encoding",), float(ZERO_VALUE), lines, required=True)
    falloff_value = getattr(unreal.TexturePatchFalloffMode, "SMOOTH", None)
    if falloff_value is not None:
        try_set_property(entry, ("falloff_mode",), falloff_value, lines)
    use_curve, _ = try_call(entry, ("set_use_value_curve",), (False,), lines)
    if not use_curve:
        try_set_property(entry, ("use_value_curve", "b_use_value_curve"), False, lines)


def configure_adaptive_tessellation(component, lines):
    mode = getattr(unreal.TexturePatchTessellationMode, "ADAPTIVE_FAST", None)
    if mode is None:
        mode = getattr(unreal.TexturePatchTessellationMode, "ADAPTIVE", None)
    if mode is None:
        record(lines, "Adaptive tessellation enum unavailable")
        return False
    called, _ = try_call(component,
        ("set_adaptive_tessellation_mode", "set_adaptive_tesselation_mode"),
        (mode,), lines)
    if called:
        return True
    return try_set_property(component,
        ("adaptive_tessellation_mode", "adaptive_tesselation_mode", "tessellation_mode"),
        mode, lines)


def configure_component(component, mesh_partition, texture, lines):
    assign_mesh_partition(component, mesh_partition, lines)
    try_set_property(component, ("priority",), 30.0, lines, required=True)
    try_set_property(component, ("is_disabled", "disabled"), False, lines, required=True)
    coverage = unreal.Vector2D(COVERAGE_CM, COVERAGE_CM)
    called, _ = try_call(component, ("set_unscaled_coverage",), (coverage,), lines)
    if not called:
        raise RuntimeError("TexturePatchModifier.set_unscaled_coverage was not callable")
    apply_z_called, _ = try_call(component, ("set_apply_component_z_scale",), (False,), lines)
    if not apply_z_called:
        record(lines, "Apply Component Z Scale setter not exposed; default retained")
    entry = get_or_create_height_entry(component, lines)
    configure_height_entry(entry, texture, lines)
    adaptive = configure_adaptive_tessellation(component, lines)
    reread, _ = try_call(component, ("update_from_texture",), (), lines)
    if not reread:
        raise RuntimeError("TexturePatchModifier.update_from_texture was not callable")
    try_call(component, ("trigger_update",), (), lines)
    try:
        component.modify()
    except Exception:
        pass
    return adaptive


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
    record(lines, "AETHER VIDEO STAGE 08 - TEXTURE PATCH INSTALL")
    record(lines, "=" * 96)
    world = load_world()
    actor_subsystem, actors = get_actors()
    clear_previous_install(actor_subsystem, actors, lines)
    _, actors = get_actors()
    dependency = find_actor_by_label(actors, DEPENDENCY_LABEL)
    if not dependency:
        raise RuntimeError(f"Required completed dependency was not found: {DEPENDENCY_LABEL}")
    mesh_partition = find_mesh_partition(actors)
    if not mesh_partition:
        raise RuntimeError("Authoritative Mesh Partition actor could not be resolved")
    modifier_class = getattr(unreal, "TexturePatchModifier", None)
    if not modifier_class:
        raise RuntimeError("unreal.TexturePatchModifier is unavailable")
    texture = unreal.EditorAssetLibrary.load_asset(TEXTURE_PATH)
    if not texture:
        raise RuntimeError(f"Texture source could not be loaded: {TEXTURE_PATH}")

    dependency_location = dependency.get_actor_location()
    target_x = dependency_location.x + OFFSET_X_CM
    target_y = dependency_location.y + OFFSET_Y_CM
    hit = terrain_hit(world, target_x, target_y, lines)
    if hit:
        location = unreal.Vector(hit.x, hit.y, hit.z)
        placement = "TERRAIN_TRACE_PASS"
    else:
        location = unreal.Vector(target_x, target_y, dependency_location.z)
        placement = "FALLBACK_DEPENDENCY_Z_NEEDS_EDITOR_CHECK"

    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Dependency={dependency.get_name()} at {dependency_location}")
    record(lines, f"Affected Mesh Partition={mesh_partition.get_name()}")
    record(lines, f"Texture={texture.get_path_name()}")
    record(lines, f"Texture dimensions={texture.blueprint_get_size_x()}x{texture.blueprint_get_size_y()}")
    record(lines, f"Patch location={location}")
    record(lines, f"Patch placement={placement}")
    record(lines, f"Coverage={COVERAGE_CM}x{COVERAGE_CM} cm")
    record(lines, f"Height scale={HEIGHT_SCALE_CM} cm | zero value={ZERO_VALUE}")

    modifier_actor_class = getattr(unreal, "ModifierActor", unreal.Actor)
    actor = actor_subsystem.spawn_actor_from_class(
        modifier_actor_class, location, unreal.Rotator(0.0, 0.0, 0.0), False)
    actor.set_actor_label(TEXTURE_LABEL, True)
    actor.set_editor_property("tags", [unreal.Name(TAG)])
    component = add_component_to_actor(actor, modifier_class, lines)
    adaptive = configure_component(component, mesh_partition, texture, lines)

    saved = save_map(lines)
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "INSTALL_RESULT=PASS")
    record(lines, f"TEXTURE_PATCH_ACTOR={TEXTURE_LABEL}")
    record(lines, "TEXTURE_PATCH_COMPONENT_CLASS=/Script/MeshPartitionEditor.TexturePatchModifier")
    record(lines, f"TEXTURE_SOURCE={TEXTURE_PATH}")
    record(lines, f"COVERAGE_CM={COVERAGE_CM},{COVERAGE_CM}")
    record(lines, f"HEIGHT_SCALE_CM={HEIGHT_SCALE_CM}")
    record(lines, f"ZERO_VALUE={ZERO_VALUE}")
    record(lines, f"ADAPTIVE_TESSELLATION={'ENABLED' if adaptive else 'NOT_EXPOSED_DEFAULT_RETAINED'}")
    record(lines, f"PLACEMENT_RESULT={placement}")
    record(lines, "NEXT_EDITOR_ACTION=Open AetherWorld, select Stage08 in Mesh Partition Outliner, and click its Build To button.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_TEXTURE_PATCH_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"INSTALL_RESULT=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
