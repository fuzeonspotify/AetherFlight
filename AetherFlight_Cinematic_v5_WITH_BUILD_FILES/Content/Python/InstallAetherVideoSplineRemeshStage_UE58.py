from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
SOURCE_SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
STAGE_LABEL = "Aether_VideoStage10_SplineRemesh"
TAG = "AetherVideoSplineRemeshStage"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoSplineRemeshInstall.txt"

SPLINE_RADIUS_CM = 6000.0
TARGET_EDGE_LENGTH_CM = 250.0
REMESH_ITERATIONS = 2
PRIORITY = 35.0


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
        if actor_label(actor) == STAGE_LABEL or TAG in tags:
            subsystem.destroy_actor(actor)
            removed += 1
    record(lines, f"Previous spline remesh actors removed={removed}")


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


def find_spline_component(actor, lines):
    spline_class = getattr(unreal, "SplineComponent", None)
    if not spline_class:
        raise RuntimeError("unreal.SplineComponent is unavailable")
    splines = list(actor.get_components_by_class(spline_class))
    record(lines, f"Source spline components found={len(splines)}")
    for spline in splines:
        record(lines, f"  {spline.get_name()} | {spline.get_class().get_path_name()}")
    if len(splines) != 1:
        raise RuntimeError(
            f"Expected exactly one SplineComponent on {SOURCE_SPLINE_LABEL}, found {len(splines)}"
        )
    return splines[0]


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


def try_call(obj, names, args, lines):
    for name in names:
        method = getattr(obj, name, None)
        if not callable(method):
            continue
        try:
            result = method(*args)
            record(lines, f"Called {obj.get_name()}.{name}{args}")
            return True, result
        except Exception as exc:
            record(lines, f"Call failed {obj.get_name()}.{name}: {exc}")
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
        raise RuntimeError("SplineRemeshModifier could not be assigned to the Mesh Partition")


def make_component_reference(source_actor, source_spline, lines):
    reference_class = getattr(unreal, "ComponentReference", None)
    if not reference_class:
        raise RuntimeError("unreal.ComponentReference is unavailable")

    component_name = unreal.Name(source_spline.get_name())
    try:
        reference = reference_class(
            other_actor=source_actor,
            component_property=component_name,
        )
        record(lines, f"Created ComponentReference actor={actor_label(source_actor)} component={component_name}")
        return reference
    except Exception as constructor_exc:
        record(lines, f"ComponentReference constructor warning={constructor_exc}")

    reference = reference_class()
    reference.set_editor_property("other_actor", source_actor)
    reference.set_editor_property("component_property", component_name)
    try:
        reference.set_editor_property("path_to_component", source_spline.get_name())
    except Exception:
        pass
    record(lines, f"Built ComponentReference through editor properties component={component_name}")
    return reference


def assign_spline_component(component, source_actor, spline, lines):
    native, _ = try_call(component, ("set_spline_component",), (spline, True), lines)
    blueprint, _ = try_call(component, ("bp_set_spline_component",), (spline,), lines)
    if native or blueprint:
        return "SETTER"

    reference = make_component_reference(source_actor, spline, lines)
    try_set_property(component, ("spline_ref",), reference, lines, required=True)

    try:
        verified = component.get_editor_property("spline_ref")
        record(lines, f"Verified spline_ref={verified}")
    except Exception as exc:
        record(lines, f"Spline reference verification warning={exc}")
    return "COMPONENT_REFERENCE"


def configure_value(component, property_names, setter_names, value, lines, required=True):
    called, _ = try_call(component, setter_names, (value,), lines)
    if called:
        return "SETTER"
    if try_set_property(component, property_names, value, lines, required=required):
        return "PROPERTY"
    return "UNAVAILABLE"


def configure_component(component, mesh_partition, source_actor, spline, lines):
    assign_mesh_partition(component, mesh_partition, lines)
    spline_assignment = assign_spline_component(component, source_actor, spline, lines)

    configure_value(component, ("priority",), (), PRIORITY, lines)
    configure_value(component, ("is_disabled", "disabled"), (), False, lines)
    configure_value(component, ("spline_radius",), (), SPLINE_RADIUS_CM, lines)
    configure_value(component, ("draw_spline_radius", "b_draw_spline_radius"), (), True, lines, required=False)
    configure_value(component, ("spline_radius_samples",), (), 32, lines, required=False)

    remesh_value = resolve_enum_member("RemeshModifierOperation", ("REMESH",), lines)
    if remesh_value is None:
        raise RuntimeError("RemeshModifierOperation.REMESH is unavailable")
    operation_assignment = configure_value(
        component,
        ("current_operation", "remesh_operation", "operation"),
        ("set_current_operation",),
        remesh_value,
        lines,
    )

    use_target_assignment = configure_value(
        component,
        ("use_target_edge_length", "b_use_target_edge_length"),
        ("set_use_target_edge_length",),
        True,
        lines,
    )
    edge_assignment = configure_value(
        component,
        ("target_edge_length",),
        ("set_target_edge_length",),
        TARGET_EDGE_LENGTH_CM,
        lines,
    )
    iterations_assignment = configure_value(
        component,
        ("remesh_iterations",),
        ("set_remesh_iterations",),
        REMESH_ITERATIONS,
        lines,
    )
    smoothing_assignment = configure_value(
        component,
        ("vertex_smoothing", "b_vertex_smoothing"),
        ("set_vertex_smoothing",),
        False,
        lines,
    )
    resample_assignment = configure_value(
        component,
        ("resample_uvs", "b_resample_uvs"),
        ("set_resample_uvs",),
        True,
        lines,
        required=False,
    )
    density_assignment = configure_value(
        component,
        ("use_density_weight_channel", "b_use_density_weight_channel"),
        ("set_use_density_weight_channel",),
        False,
        lines,
        required=False,
    )

    updated, _ = try_call(component, ("update_spline_data",), (), lines)
    if not updated:
        record(lines, "UpdateSplineData is not Python-callable; reload or the editor button can refresh cached spline data.")

    try:
        component.modify()
    except Exception:
        pass

    return {
        "spline": spline_assignment,
        "operation": operation_assignment,
        "use_target": use_target_assignment,
        "edge": edge_assignment,
        "iterations": iterations_assignment,
        "smoothing": smoothing_assignment,
        "resample_uvs": resample_assignment,
        "density": density_assignment,
    }


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
    record(lines, "AETHER VIDEO STAGE 10 - SPLINE REMESH INSTALL")
    record(lines, "=" * 96)

    world = load_world()
    actor_subsystem, actors = get_actors()
    clear_previous_install(actor_subsystem, actors, lines)

    _, actors = get_actors()
    source_actor = find_actor_by_label(actors, SOURCE_SPLINE_LABEL)
    if not source_actor:
        raise RuntimeError(f"Required completed Stage 09 actor was not found: {SOURCE_SPLINE_LABEL}")

    source_spline = find_spline_component(source_actor, lines)
    mesh_partition = find_mesh_partition(actors)
    if not mesh_partition:
        raise RuntimeError("Authoritative Mesh Partition actor could not be resolved")

    modifier_class = getattr(unreal, "SplineRemeshModifier", None)
    modifier_actor_class = getattr(unreal, "ModifierActor", unreal.Actor)
    if not modifier_class:
        raise RuntimeError("unreal.SplineRemeshModifier is unavailable")

    source_location = source_actor.get_actor_location()
    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Source spline actor={source_actor.get_name()} at {source_location}")
    record(lines, f"Source spline component={source_spline.get_name()}")
    record(lines, f"Source spline length cm={spline_length(source_spline)}")
    record(lines, f"Affected Mesh Partition={mesh_partition.get_name()}")
    record(lines, f"Spline radius={SPLINE_RADIUS_CM} cm")
    record(lines, f"Target edge length={TARGET_EDGE_LENGTH_CM} cm")
    record(lines, f"Priority={PRIORITY}")

    actor = actor_subsystem.spawn_actor_from_class(
        modifier_actor_class,
        source_location,
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    actor.set_actor_label(STAGE_LABEL, True)
    actor.set_editor_property("tags", [unreal.Name(TAG)])

    component = add_component_to_actor(actor, modifier_class, lines)
    assignments = configure_component(
        component,
        mesh_partition,
        source_actor,
        source_spline,
        lines,
    )

    saved = save_map(lines)
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "INSTALL_RESULT=PASS")
    record(lines, f"SPLINE_REMESH_ACTOR={STAGE_LABEL}")
    record(lines, "SPLINE_REMESH_COMPONENT_CLASS=/Script/MeshPartitionEditor.SplineRemeshModifier")
    record(lines, f"SOURCE_SPLINE_ACTOR={SOURCE_SPLINE_LABEL}")
    record(lines, "OPERATION=REMESH")
    record(lines, f"SPLINE_RADIUS_CM={SPLINE_RADIUS_CM}")
    record(lines, f"TARGET_EDGE_LENGTH_CM={TARGET_EDGE_LENGTH_CM}")
    record(lines, f"REMESH_ITERATIONS={REMESH_ITERATIONS}")
    record(lines, f"PRIORITY={PRIORITY}")
    for key, value in assignments.items():
        record(lines, f"ASSIGNMENT_{key.upper()}={value}")
    record(lines, "NEXT_EDITOR_ACTION=Open AetherWorld, select Aether_VideoStage10_SplineRemesh, click Update Spline Data if available, include Stage10 and Stage09 in Build To, then compare wireframe density with Stage10 disabled/enabled.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_SPLINE_REMESH_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"INSTALL_RESULT=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
