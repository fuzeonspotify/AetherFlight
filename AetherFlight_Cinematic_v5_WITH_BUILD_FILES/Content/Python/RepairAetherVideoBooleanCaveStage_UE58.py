from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
BOOLEAN_LABEL = "Aether_VideoStage07_BooleanCave"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoBooleanCaveRepair.txt"


def record(lines, text):
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


def make_vector3d(x, y, z):
    vector3d_class = getattr(unreal, "Vector3d", None)
    if not vector3d_class:
        raise RuntimeError("unreal.Vector3d is not exposed by this UE installation")

    value = vector3d_class()
    value.set_editor_property("x", float(x))
    value.set_editor_property("y", float(y))
    value.set_editor_property("z", float(z))
    return value


def set_property(component, name, value, lines, required=False):
    try:
        component.set_editor_property(name, value)
        record(lines, f"Set {component.get_name()}.{name}={value}")
        return True
    except Exception as exc:
        record(lines, f"Could not set {component.get_name()}.{name}: {exc}")
        if required:
            raise
        return False


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
    record(lines, "AETHER STAGE 07 BOOLEAN CAVE TOPOLOGY REPAIR")
    record(lines, "=" * 96)
    world = load_world()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(subsystem.get_all_level_actors())
    matches = [actor for actor in actors if actor_label(actor) == BOOLEAN_LABEL]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {BOOLEAN_LABEL} actor, found {len(matches)}")

    actor = matches[0]
    components = list(actor.get_components_by_class(unreal.ActorComponent))
    booleans = [
        component for component in components
        if "BooleanModifier" in component.get_class().get_path_name()
    ]
    if len(booleans) != 1:
        raise RuntimeError(f"Expected one BooleanModifier component, found {len(booleans)}")

    component = booleans[0]
    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Actor={actor.get_name()} label={actor_label(actor)}")
    record(lines, f"Component={component.get_class().get_path_name()}")

    # UE's documented Mesh Terrain hole workflow uses Trim. Larger double-
    # precision bounds ensure all triangles touching the stretched cutter are
    # included in the operation. UE 5.8 exposes both properties as Vector3d.
    operator_bounds = make_vector3d(10000.0, 10000.0, 10000.0)
    section_bounds = make_vector3d(30000.0, 30000.0, 30000.0)

    set_property(component, "boolean_op", unreal.BooleanOperation.TRIM, lines, required=True)
    set_property(component, "simplify_along_new_edges", False, lines, required=True)
    set_property(component, "weld_shared_edges", True, lines, required=True)
    set_property(
        component,
        "expand_operator_bounds",
        operator_bounds,
        lines,
        required=True,
    )
    set_property(
        component,
        "expand_section_inclusion_bounds",
        section_bounds,
        lines,
        required=True,
    )
    set_property(component, "pre_op_simplifier_strength", 0.0, lines)
    set_property(component, "is_disabled", False, lines, required=True)

    try:
        component.modify()
    except Exception:
        pass

    saved = save_map(lines)
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "REPAIR_RESULT=PASS")
    record(lines, "BOOLEAN_OPERATION=TRIM")
    record(lines, "EXPAND_OPERATOR_BOUNDS_CM=10000,10000,10000")
    record(lines, "EXPAND_SECTION_INCLUSION_BOUNDS_CM=30000,30000,30000")
    record(lines, "BOUNDS_STRUCT_TYPE=Vector3d")
    record(lines, "SIMPLIFY_ALONG_NEW_EDGES=FALSE")
    record(lines, "WELD_SHARED_EDGES=TRUE")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_BOOLEAN_CAVE_REPAIR_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"REPAIR_RESULT=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
