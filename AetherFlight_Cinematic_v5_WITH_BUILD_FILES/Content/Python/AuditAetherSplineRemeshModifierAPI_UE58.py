from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
SPLINE_LABEL = "Aether_VideoStage09_SplineChannel"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSplineRemeshModifierAPIAudit.txt"


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


def safe_property(obj, names):
    for name in names:
        try:
            return name, obj.get_editor_property(name)
        except Exception:
            continue
    return None, None


def enum_members(enum_type):
    members = []
    if not enum_type:
        return members
    for name in dir(enum_type):
        if name.startswith("_") or not name.isupper():
            continue
        try:
            members.append(f"{name}={getattr(enum_type, name)}")
        except Exception:
            continue
    return members


def find_stage09_spline(lines):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(subsystem.get_all_level_actors())
    matches = [actor for actor in actors if actor_label(actor) == SPLINE_LABEL]
    record(lines, f"Stage09 actor matches={len(matches)}")
    if len(matches) != 1:
        return None, None

    actor = matches[0]
    spline_class = getattr(unreal, "SplineComponent", None)
    if not spline_class:
        return actor, None

    splines = list(actor.get_components_by_class(spline_class))
    record(lines, f"Stage09 spline components={len(splines)}")
    for spline in splines:
        record(lines, f"  {spline.get_name()} | {spline.get_class().get_path_name()}")
    return actor, splines[0] if len(splines) == 1 else None


def main():
    lines = []
    record(lines, "AETHER UE 5.8 SPLINE REMESH MODIFIER API AUDIT")
    record(lines, "=" * 96)
    record(lines, "Read-only: no actors are spawned, no packages are saved, and no Mesh Partition build is started.")

    world = load_world()
    record(lines, f"Map={world.get_path_name() if world else 'None'}")

    modifier_class = getattr(unreal, "SplineRemeshModifier", None)
    record(lines, f"unreal.SplineRemeshModifier={'YES' if modifier_class else 'NO'}")
    if not modifier_class:
        exposed_names = sorted(
            name for name in dir(unreal)
            if "spline" in name.lower() and "remesh" in name.lower()
        )
        record(lines, f"Spline-remesh-related Unreal names={','.join(exposed_names) if exposed_names else 'None'}")
        record(lines, "AETHER_SPLINE_REMESH_API=FAIL")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    component = unreal.get_default_object(modifier_class)
    record(lines, f"Class={component.get_class().get_path_name()}")
    record(lines, f"Default object={component.get_path_name()}")

    checks = [
        ("Affected Mesh Partition", ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor")),
        ("Priority", ("priority",)),
        ("Disabled", ("is_disabled", "disabled")),
        ("Spline Reference", ("spline_ref", "spline_ptr", "spline_component", "spline")),
        ("Spline Radius", ("spline_radius",)),
        ("Draw Spline Radius", ("draw_spline_radius", "b_draw_spline_radius")),
        ("Spline Radius Samples", ("spline_radius_samples",)),
        ("Current Operation", ("current_operation", "remesh_operation", "operation")),
        ("Target Edge Length", ("target_edge_length",)),
        ("Use Target Edge Length", ("use_target_edge_length", "b_use_target_edge_length")),
        ("Remesh Iterations", ("remesh_iterations",)),
        ("Vertex Smoothing", ("vertex_smoothing", "b_vertex_smoothing")),
        ("Resample UVs", ("resample_uvs", "b_resample_uvs")),
    ]

    exposed = {}
    record(lines, "")
    record(lines, "EXPOSED EDITOR PROPERTIES")
    record(lines, "-" * 96)
    for label, names in checks:
        prop_name, value = safe_property(component, names)
        exposed[label] = prop_name
        if prop_name:
            record(lines, f"{label}={value} | property={prop_name}")
        else:
            record(lines, f"{label}=not exposed | candidates={names}")

    method_names = (
        "bp_set_affected_mega_mesh",
        "set_affected_mega_mesh",
        "set_spline_component",
        "bp_set_spline_component",
        "update_spline_data",
        "set_current_operation",
        "set_target_edge_length",
        "set_use_target_edge_length",
        "set_remesh_iterations",
        "set_vertex_smoothing",
        "set_resample_uvs",
        "set_use_density_weight_channel",
    )
    methods = {}
    record(lines, "")
    record(lines, "METHODS")
    record(lines, "-" * 96)
    for name in method_names:
        present = callable(getattr(component, name, None))
        methods[name] = present
        record(lines, f"{name}={'YES' if present else 'NO'}")

    record(lines, "")
    record(lines, "REMESH ENUMS")
    record(lines, "-" * 96)
    for enum_name in (
        "RemeshModifierOperation",
        "MegaMeshRemeshModifierBoundaryMode",
        "MegaMeshRemeshModifierTessellateMethod",
    ):
        enum_type = getattr(unreal, enum_name, None)
        members = enum_members(enum_type)
        record(lines, f"unreal.{enum_name}: {', '.join(members) if members else 'no inspectable members'}")

    stage_actor, spline = find_stage09_spline(lines)
    component_reference_available = getattr(unreal, "ComponentReference", None) is not None

    has_affected_assignment = bool(
        exposed.get("Affected Mesh Partition")
        or methods.get("bp_set_affected_mega_mesh")
        or methods.get("set_affected_mega_mesh")
    )
    has_spline_assignment = bool(
        methods.get("set_spline_component")
        or methods.get("bp_set_spline_component")
        or (exposed.get("Spline Reference") and component_reference_available)
    )
    has_radius = bool(exposed.get("Spline Radius"))
    has_operation = bool(exposed.get("Current Operation") or methods.get("set_current_operation"))
    has_target_edge = bool(exposed.get("Target Edge Length") or methods.get("set_target_edge_length"))
    has_use_target_edge = bool(
        exposed.get("Use Target Edge Length") or methods.get("set_use_target_edge_length")
    )
    has_iterations = bool(exposed.get("Remesh Iterations") or methods.get("set_remesh_iterations"))
    has_vertex_smoothing = bool(
        exposed.get("Vertex Smoothing") or methods.get("set_vertex_smoothing")
    )

    required = bool(
        stage_actor
        and spline
        and has_affected_assignment
        and has_spline_assignment
        and has_radius
        and has_operation
        and has_target_edge
        and has_use_target_edge
        and has_iterations
        and has_vertex_smoothing
    )

    record(lines, "")
    record(lines, f"Stage09 dependency available={'YES' if stage_actor else 'NO'}")
    record(lines, f"Stage09 spline available={'YES' if spline else 'NO'}")
    record(lines, f"ComponentReference struct available={component_reference_available}")
    record(lines, f"Affected assignment available={has_affected_assignment}")
    record(lines, f"Spline assignment available={has_spline_assignment}")
    record(lines, f"Spline radius available={has_radius}")
    record(lines, f"Remesh operation available={has_operation}")
    record(lines, f"Target edge length available={has_target_edge}")
    record(lines, f"Use target edge length available={has_use_target_edge}")
    record(lines, f"Remesh iterations available={has_iterations}")
    record(lines, f"Vertex smoothing available={has_vertex_smoothing}")
    record(lines, f"Resample UVs available={bool(exposed.get('Resample UVs') or methods.get('set_resample_uvs'))}")
    record(lines, f"AETHER_SPLINE_REMESH_API={'PASS' if required else 'CHECK'}")
    record(lines, "NO_ACTORS_SPAWNED=TRUE")
    record(lines, "NO_PACKAGES_SAVED=TRUE")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_SPLINE_REMESH_API_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"AETHER_SPLINE_REMESH_API=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
