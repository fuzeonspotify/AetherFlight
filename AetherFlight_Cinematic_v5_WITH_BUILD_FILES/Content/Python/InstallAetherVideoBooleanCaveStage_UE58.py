from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
SCULPT_LABEL = "Aether_VideoStage06_SculptPaint"
BOOLEAN_LABEL = "Aether_VideoStage07_BooleanCave"
TAG = "AetherVideoBooleanCaveStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoBooleanCaveInstall.txt"

SOURCE_MESH_PATH = "/Engine/BasicShapes/Sphere"
TRACE_TOP_Z = 900000.0
TRACE_BOTTOM_Z = -300000.0

# Engine BasicShapes/Sphere is 100 cm in diameter. This makes a deliberately
# aircraft-scale local tunnel/sinkhole test: about 420 m long, 140 m wide,
# and 110 m high. It remains contained inside the verified 1.2 km Remesh zone.
CAVE_SCALE = unreal.Vector(420.0, 140.0, 110.0)
CAVE_SURFACE_EMBED_CM = 3000.0


def record(lines, text):
    text = str(text)
    lines.append(text)
    unreal.log_warning(text)


def load_world():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def all_actors(subsystem):
    return list(subsystem.get_all_level_actors())


def clear_previous_install(subsystem, actors, lines):
    removed = 0
    for actor in actors:
        tags = []
        try:
            tags = [str(tag) for tag in actor.get_editor_property("tags")]
        except Exception:
            pass
        if actor_label(actor) == BOOLEAN_LABEL or TAG in tags:
            subsystem.destroy_actor(actor)
            removed += 1
    record(lines, f"Previous Boolean cave actors removed={removed}")


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

    trace_attempts = []
    try:
        trace_attempts.append(
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
        record(lines, f"Visibility trace warning={exc}")

    try:
        trace_attempts.append(
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
        record(lines, f"BlockAll trace warning={exc}")

    for hit in trace_attempts:
        if not hit:
            continue
        for prop in ("impact_point", "location"):
            try:
                point = hit.get_editor_property(prop)
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
        raise RuntimeError(f"Added {component_class}, but associated component could not be resolved")

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


def try_call(obj, names, args, lines):
    for name in names:
        method = getattr(obj, name, None)
        if not callable(method):
            continue
        try:
            method(*args)
            record(lines, f"Called {obj.get_name()}.{name}{args}")
            return True
        except Exception as exc:
            record(lines, f"Call failed {obj.get_name()}.{name}: {exc}")
    return False


def resolve_static_mesh_mode(lines):
    enum_type = getattr(unreal, "ModifierMeshSourceMode", None)
    if not enum_type:
        raise RuntimeError("unreal.ModifierMeshSourceMode is unavailable")

    candidates = (
        "STATIC_MESH",
        "STATIC_MESH_ASSET",
        "STATIC_MESH_COMPONENT",
    )
    for name in candidates:
        value = getattr(enum_type, name, None)
        if value is not None:
            record(lines, f"Resolved mesh source mode={name} ({value})")
            return value

    exposed = [name for name in dir(enum_type) if name.isupper()]
    raise RuntimeError(f"No static-mesh member found on ModifierMeshSourceMode. Members={exposed}")


def assign_mesh_partition(component, mesh_partition, lines):
    direct = try_set_property(
        component,
        ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"),
        mesh_partition,
        lines,
    )
    called = try_call(
        component,
        ("bp_set_affected_mega_mesh", "set_affected_mega_mesh"),
        (mesh_partition,),
        lines,
    )
    if not direct and not called:
        raise RuntimeError("BooleanModifier could not be assigned to the authoritative Mesh Partition")


def assign_static_mesh(component, mesh, lines):
    mode = resolve_static_mesh_mode(lines)
    try_set_property(component, ("mesh_source_mode",), mode, lines, required=True)

    direct = try_set_property(component, ("static_mesh",), mesh, lines)
    called = try_call(component, ("bp_set_static_mesh",), (mesh,), lines)
    if not direct and not called:
        raise RuntimeError("BooleanModifier could not receive the sphere static mesh")


def configure_boolean(component, mesh_partition, source_mesh, lines):
    assign_mesh_partition(component, mesh_partition, lines)
    assign_static_mesh(component, source_mesh, lines)

    try_set_property(component, ("priority",), 20.0, lines, required=True)
    try_set_property(component, ("is_disabled", "disabled"), False, lines, required=True)
    try_set_property(component, ("boolean_op",), unreal.BooleanOperation.SUBTRACT, lines, required=True)
    try_set_property(
        component,
        ("tool_mesh_embedding",),
        unreal.BooleanToolMeshEmbedding.INTERSECTING,
        lines,
        required=True,
    )
    try_set_property(component, ("simplify_along_new_edges",), True, lines)
    try_set_property(component, ("weld_shared_edges",), True, lines)
    try_set_property(component, ("draw_wire_mesh",), True, lines)
    try_set_property(component, ("draw_local_bounds",), True, lines)
    try_set_property(component, ("expand_operator_bounds",), unreal.Vector(3000.0, 3000.0, 3000.0), lines)
    try_set_property(
        component,
        ("expand_section_inclusion_bounds",),
        unreal.Vector(6000.0, 6000.0, 6000.0),
        lines,
    )

    preview_enum = getattr(unreal, "MegaMeshBooleanModifierPreviewVisOptions", None)
    preview_always = getattr(preview_enum, "ALWAYS", None) if preview_enum else None
    if preview_always is not None:
        try_set_property(component, ("draw_solid_mesh",), preview_always, lines)

    try:
        component.modify()
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
    record(lines, "AETHER VIDEO STAGE 07 - STATIC MESH BOOLEAN CAVE INSTALL")
    record(lines, "=" * 96)

    world = load_world()
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = all_actors(actor_subsystem)
    clear_previous_install(actor_subsystem, actors, lines)

    actors = all_actors(actor_subsystem)
    sculpt_actor = find_actor_by_label(actors, SCULPT_LABEL)
    if not sculpt_actor:
        raise RuntimeError(f"Required Sculpt/Paint actor was not found: {SCULPT_LABEL}")

    mesh_partition = find_mesh_partition(actors)
    if not mesh_partition:
        raise RuntimeError("Authoritative Mesh Partition actor could not be resolved")

    boolean_class = getattr(unreal, "BooleanModifier", None)
    if not boolean_class:
        raise RuntimeError("unreal.BooleanModifier is unavailable")

    source_mesh = unreal.EditorAssetLibrary.load_asset(SOURCE_MESH_PATH)
    if not source_mesh:
        raise RuntimeError(f"Boolean source sphere could not be loaded: {SOURCE_MESH_PATH}")

    stage_center = sculpt_actor.get_actor_location()
    hit = terrain_hit(world, stage_center.x, stage_center.y, lines)
    if hit:
        cutter_center = unreal.Vector(hit.x, hit.y, hit.z - CAVE_SURFACE_EMBED_CM)
        placement = "TERRAIN_TRACE_PASS"
    else:
        cutter_center = unreal.Vector(stage_center.x, stage_center.y, stage_center.z)
        placement = "FALLBACK_Z0_NEEDS_EDITOR_POSITION_CHECK"

    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Sculpt/Paint dependency={sculpt_actor.get_name()} at {stage_center}")
    record(lines, f"Affected Mesh Partition={mesh_partition.get_name()}")
    record(lines, f"Cutter center={cutter_center}")
    record(lines, f"Cutter placement={placement}")
    record(lines, f"Cutter scale={CAVE_SCALE}")

    modifier_actor_class = getattr(unreal, "ModifierActor", unreal.Actor)
    actor = actor_subsystem.spawn_actor_from_class(
        modifier_actor_class,
        cutter_center,
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    actor.set_actor_label(BOOLEAN_LABEL, True)
    actor.set_editor_property("tags", [unreal.Name(TAG)])

    component = add_component_to_actor(actor, boolean_class, lines)
    try_set_property(component, ("relative_scale3d",), CAVE_SCALE, lines, required=True)
    configure_boolean(component, mesh_partition, source_mesh, lines)

    saved = save_map(lines)
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "INSTALL_RESULT=PASS")
    record(lines, f"BOOLEAN_ACTOR={BOOLEAN_LABEL}")
    record(lines, "BOOLEAN_COMPONENT_CLASS=/Script/MeshPartitionEditor.BooleanModifier")
    record(lines, "BOOLEAN_OPERATION=SUBTRACT")
    record(lines, f"BOOLEAN_SOURCE_MESH={SOURCE_MESH_PATH}")
    record(lines, f"PLACEMENT_RESULT={placement}")
    record(lines, "NEXT_EDITOR_ACTION=Open AetherWorld, include Stage07 in Build To, and inspect the wireframe cutter. If fallback placement was used, press End and move the cutter partly into the terrain.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_BOOLEAN_CAVE_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"INSTALL_RESULT=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
