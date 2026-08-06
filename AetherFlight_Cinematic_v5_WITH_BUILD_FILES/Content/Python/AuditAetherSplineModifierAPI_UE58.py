from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSplineModifierAPIAudit.txt"
REQUIRED_LABELS = (
    "Aether_VideoStage05_LocalRemesh",
    "Aether_VideoStage08_TexturePatch",
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
        if name.startswith("_") or name in ("name", "value"):
            continue
        try:
            value = getattr(enum_type, name)
        except Exception:
            continue
        if callable(value):
            continue
        members.append(f"{name}={value}")
    return members


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


def main():
    lines = []
    record(lines, "AETHER UE 5.8 SPLINE MODIFIER API AUDIT")
    record(lines, "=" * 96)
    record(lines, "Read-only: no actors are spawned, no packages are saved, and no Mesh Partition build is started.")

    world = load_world()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(subsystem.get_all_level_actors())
    record(lines, f"Map={world.get_path_name() if world else 'None'}")

    classes = {
        "SplineModifier": getattr(unreal, "SplineModifier", None),
        "SplineRemeshModifier": getattr(unreal, "SplineRemeshModifier", None),
        "SplineComponent": getattr(unreal, "SplineComponent", None),
        "ModifierActor": getattr(unreal, "ModifierActor", None),
    }
    record(lines, "")
    record(lines, "CLASS AVAILABILITY")
    record(lines, "-" * 96)
    for name, cls in classes.items():
        record(lines, f"unreal.{name}={'YES' if cls else 'NO'}")

    spline_class = classes["SplineModifier"]
    if not spline_class:
        exposed = sorted(name for name in dir(unreal) if "spline" in name.lower())
        record(lines, f"Spline-related Unreal names={','.join(exposed)}")
        record(lines, "AETHER_SPLINE_MODIFIER_API=FAIL")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    component = unreal.get_default_object(spline_class)
    record(lines, f"Spline class={component.get_class().get_path_name()}")
    record(lines, f"Spline default object={component.get_path_name()}")

    checks = [
        ("Affected Mesh Partition", ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor")),
        ("Priority", ("priority",)),
        ("Layer Sub-Priority", ("layer_sub_priority", "sub_priority", "priority_sub_layer")),
        ("Disabled", ("is_disabled", "disabled")),
        ("Spline", ("spline_ptr", "spline_component", "spline")),
        ("Write Mode", ("write_mode",)),
        ("Blend Mode", ("blend_mode",)),
        ("Falloff Distance", ("falloff_distance",)),
        ("Plateau Distance", ("plateau_distance",)),
        ("Max Z Distance", ("max_z_distance",)),
        ("Use Spline Scale For Falloff", ("use_spline_scale_for_falloff", "b_use_spline_scale_for_falloff")),
        ("Use Spline Scale For Plateau", ("use_spline_scale_for_plateau", "b_use_spline_scale_for_plateau")),
        ("Mesh Closed Interior", ("mesh_closed_interior", "b_mesh_closed_interior")),
        ("Draw Projected Spline", ("draw_projected_spline", "b_draw_projected_spline")),
        ("Draw Local Bounds", ("draw_local_bounds", "b_draw_local_bounds")),
        ("Draw Projection Plane", ("draw_projection_plane", "b_draw_projection_plane")),
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
        "bp_bind_to_nearest_mesh_partition",
        "bp_set_spline_component",
        "set_spline_component",
        "get_spline_component",
        "update_spline_data",
        "set_falloff_distance",
        "set_max_z_distance",
        "set_use_spline_scale_for_falloff",
        "set_expand_bounds_by_spline_scale",
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
    record(lines, "RELEVANT ENUMS")
    record(lines, "-" * 96)
    enum_names = (
        "SplineModifierBlendMode",
        "SplineModifierWriteMode",
        "SplineModifierInteriorSmoothMode",
        "SplineWeightBlendMode",
        "SplineCoordinateSpace",
        "SplinePointType",
    )
    for name in enum_names:
        enum_type = getattr(unreal, name, None)
        members = enum_members(enum_type)
        record(lines, f"unreal.{name}: {', '.join(members) if members else 'no inspectable members'}")

    record(lines, "")
    record(lines, "AETHERWORLD DEPENDENCIES")
    record(lines, "-" * 96)
    labels_ok = True
    for label in REQUIRED_LABELS:
        matches = [actor for actor in actors if actor_label(actor) == label]
        labels_ok = labels_ok and len(matches) == 1
        record(lines, f"{label}={'YES' if len(matches) == 1 else f'COUNT_{len(matches)}'}")

    mesh_partition = find_mesh_partition(actors)
    record(lines, f"Authoritative Mesh Partition={mesh_partition.get_name() if mesh_partition else 'NOT_FOUND'}")

    affected_ok = bool(
        exposed.get("Affected Mesh Partition")
        or methods.get("bp_set_affected_mega_mesh")
        or methods.get("set_affected_mega_mesh")
    )
    spline_setter_ok = bool(
        exposed.get("Spline")
        or methods.get("bp_set_spline_component")
        or methods.get("set_spline_component")
    )
    config_ok = bool(
        exposed.get("Write Mode")
        and (
            exposed.get("Falloff Distance")
            or methods.get("set_falloff_distance")
        )
    )
    status = "PASS" if (
        classes["SplineComponent"]
        and classes["ModifierActor"]
        and affected_ok
        and spline_setter_ok
        and config_ok
        and labels_ok
        and mesh_partition
    ) else "CHECK"

    relevant_api = sorted(
        name for name in dir(component)
        if any(token in name.lower() for token in (
            "spline", "falloff", "plateau", "write", "blend", "weight",
            "affected", "priority", "bounds", "projection", "interior"
        ))
    )
    record(lines, "")
    record(lines, f"Relevant spline component API names={','.join(relevant_api)}")
    record(lines, f"AETHER_SPLINE_MODIFIER_API={status}")
    record(lines, "NO_ACTORS_SPAWNED=TRUE")
    record(lines, "NO_PACKAGES_SAVED=TRUE")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_SPLINE_MODIFIER_API_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"AETHER_SPLINE_MODIFIER_API=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
