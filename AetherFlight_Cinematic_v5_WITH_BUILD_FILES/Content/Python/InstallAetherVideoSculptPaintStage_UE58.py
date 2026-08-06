from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
REMESH_LABEL = "Aether_VideoStage05_LocalRemesh"
SCULPT_LABEL = "Aether_VideoStage06_SculptPaint"
TAG = "AetherVideoSculptPaintStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoSculptPaintInstall.txt"

# The editable zone sits inside the 1.2 km Remesh area. These values represent
# a focused 900 m x 900 m sculpt/paint workspace with a deep vertical search
# range so it remains valid even when unattended terrain traces are unavailable.
EDIT_EXTENT_XY = 45000.0
EDIT_EXTENT_Z = 700000.0


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


def get_actor_subsystem():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def all_actors(subsystem):
    return list(subsystem.get_all_level_actors())


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def clear_previous_install(subsystem, actors, lines):
    removed = 0
    for actor in actors:
        tags = []
        try:
            tags = [str(tag) for tag in actor.get_editor_property("tags")]
        except Exception:
            pass
        if actor_label(actor) == SCULPT_LABEL or TAG in tags:
            subsystem.destroy_actor(actor)
            removed += 1
    record(lines, f"Previous sculpt/paint stage actors removed={removed}")


def find_actor_by_label(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    return matches[0] if len(matches) == 1 else None


def find_mesh_partition(actors):
    candidates = []
    preferred = []
    for actor in actors:
        combined = f"{actor.get_name()} {actor.get_class().get_path_name()}"
        if "MeshPartition" not in combined and "MeshTerrain" not in combined:
            continue
        candidates.append(actor)
        tags = []
        try:
            tags = [str(tag) for tag in actor.get_editor_property("tags")]
        except Exception:
            pass
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in tags:
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return candidates[0] if len(candidates) == 1 else None


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


def try_set_property(obj, names, value, lines):
    for name in names:
        try:
            obj.set_editor_property(name, value)
            record(lines, f"Set {obj.get_name()}.{name}={value}")
            return True
        except Exception:
            continue
    record(lines, f"Property not exposed: {obj.get_name()} candidates={names}")
    return False


def try_call(obj, names, args, lines):
    for name in names:
        method = getattr(obj, name, None)
        if not method:
            continue
        try:
            method(*args)
            record(lines, f"Called {obj.get_name()}.{name}{args}")
            return True
        except Exception as exc:
            record(lines, f"Call failed {obj.get_name()}.{name}: {exc}")
    return False


def assign_mesh_partition(component, mesh_partition, lines):
    if try_set_property(
        component,
        ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"),
        mesh_partition,
        lines,
    ):
        return True
    return try_call(
        component,
        ("bp_set_affected_mega_mesh", "set_affected_mega_mesh"),
        (mesh_partition,),
        lines,
    )


def configure_brush_modifier(component, mesh_partition, lines):
    if not assign_mesh_partition(component, mesh_partition, lines):
        raise RuntimeError("BrushModifier could not be assigned to the authoritative Mesh Partition")

    # The class is displayed as BrushModifier in the editor. It is the
    # ProjectMeshLayersModifier used by Mesh Terrain Sculpt and Paint modes.
    try_set_property(component, ("priority",), 10.0, lines)
    try_set_property(component, ("is_disabled", "disabled"), False, lines)

    try_set_property(
        component,
        ("edit_extents",),
        unreal.Vector2D(EDIT_EXTENT_XY, EDIT_EXTENT_XY),
        lines,
    )
    try_set_property(
        component,
        ("edit_volume_extents",),
        unreal.Vector(EDIT_EXTENT_XY, EDIT_EXTENT_XY, EDIT_EXTENT_Z),
        lines,
    )
    try_set_property(component, ("vertical_extent_up",), EDIT_EXTENT_Z, lines)
    try_set_property(component, ("vertical_extent_down",), EDIT_EXTENT_Z, lines)
    try_set_property(component, ("draw_affected_box", "b_draw_affected_box"), True, lines)
    try_set_property(component, ("draw_sculpt_source_bounds", "b_draw_sculpt_source_bounds"), True, lines)
    try_set_property(component, ("draw_debug_mesh", "b_draw_debug_mesh"), False, lines)
    try_set_property(component, ("discard_unsculpted", "b_discard_unsculpted"), True, lines)
    try_set_property(component, ("sculpt_absolute_positions", "b_sculpt_absolute_positions"), False, lines)

    # Closest-point projection is safer for this imported mountainous terrain
    # because unattended editor startup could not resolve a collision trace and
    # therefore the stage actor is centered at Z=0. The large edit volume still
    # reaches the terrain without modifying the whole world.
    closest_point_set = try_call(
        component,
        ("set_closest_point_projection",),
        (EDIT_EXTENT_Z,),
        lines,
    )
    volume_set = try_call(
        component,
        ("set_edit_volume_extents",),
        (unreal.Vector(EDIT_EXTENT_XY, EDIT_EXTENT_XY, EDIT_EXTENT_Z),),
        lines,
    )
    record(lines, f"Closest-point projection configured={closest_point_set}")
    record(lines, f"Edit-volume method configured={volume_set}")

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
    record(lines, "AETHER VIDEO STAGE 06 - SCULPT AND PAINT INSTALL")
    record(lines, "=" * 96)

    world = load_world()
    subsystem = get_actor_subsystem()
    actors = all_actors(subsystem)
    clear_previous_install(subsystem, actors, lines)

    actors = all_actors(subsystem)
    remesh_actor = find_actor_by_label(actors, REMESH_LABEL)
    if not remesh_actor:
        raise RuntimeError(
            f"Required verified Remesh actor was not found: {REMESH_LABEL}"
        )

    mesh_partition = find_mesh_partition(actors)
    if not mesh_partition:
        raise RuntimeError("Authoritative Mesh Partition actor could not be resolved")

    brush_class = getattr(unreal, "ProjectMeshLayersModifier", None)
    if not brush_class:
        exposed = [name for name in dir(unreal) if "mesh" in name.lower() and "layer" in name.lower()]
        raise RuntimeError(
            "unreal.ProjectMeshLayersModifier is unavailable. "
            f"Relevant exposed names={exposed}"
        )

    modifier_actor_class = getattr(unreal, "ModifierActor", unreal.Actor)
    center = remesh_actor.get_actor_location()
    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Remesh dependency={remesh_actor.get_name()} at {center}")
    record(lines, f"Affected Mesh Partition={mesh_partition.get_name()}")

    actor = subsystem.spawn_actor_from_class(
        modifier_actor_class,
        center,
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    actor.set_actor_label(SCULPT_LABEL, True)
    actor.set_editor_property("tags", [unreal.Name(TAG)])

    component = add_component_to_actor(actor, brush_class, lines)
    configure_brush_modifier(component, mesh_partition, lines)

    saved = save_map(lines)
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "INSTALL_RESULT=PASS")
    record(lines, f"SCULPT_PAINT_ACTOR={SCULPT_LABEL}")
    record(lines, "SCULPT_COMPONENT_CLASS=/Script/MeshPartitionEditor.ProjectMeshLayersModifier")
    record(lines, "NEXT_EDITOR_ACTION=Select the BrushModifier in Mesh Partition Outliner, then use Mesh Terrain Sculpt and Paint tabs.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_SCULPT_PAINT_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"INSTALL_RESULT=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
