from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherBooleanModifierAPIAudit.txt"


def record(lines, text=""):
    text = str(text)
    lines.append(text)
    unreal.log_warning(text)


def safe_property(obj, names):
    for name in names:
        try:
            return name, obj.get_editor_property(name)
        except Exception:
            continue
    return None, None


def enum_members(enum_type):
    members = []
    for name in dir(enum_type):
        if name.startswith("_"):
            continue
        try:
            value = getattr(enum_type, name)
        except Exception:
            continue
        if callable(value):
            continue
        members.append(f"{name}={value}")
    return members


def main():
    lines = []
    record(lines, "AETHER UE 5.8 BOOLEAN MODIFIER API AUDIT")
    record(lines, "=" * 96)
    record(lines, "Read-only: no actors are spawned, no packages are saved, and no Mesh Partition build is started.")

    boolean_class = getattr(unreal, "BooleanModifier", None)
    record(lines, f"unreal.BooleanModifier={'YES' if boolean_class else 'NO'}")
    if not boolean_class:
        exposed_names = sorted(name for name in dir(unreal) if "boolean" in name.lower())
        record(lines, f"Boolean-related Unreal names={','.join(exposed_names)}")
        record(lines, "AETHER_BOOLEAN_API=FAIL")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    component = unreal.get_default_object(boolean_class)
    record(lines, f"Class={component.get_class().get_path_name()}")
    record(lines, f"Default object={component.get_path_name()}")

    property_checks = [
        ("Affected Mesh Partition", ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor")),
        ("Priority", ("priority",)),
        ("Disabled", ("is_disabled", "disabled")),
        ("Mesh Source Mode", ("mesh_source_mode",)),
        ("Static Mesh", ("static_mesh",)),
        ("Desired LOD", ("desired_lod",)),
        ("Boolean Operation", ("boolean_op",)),
        ("Tool Mesh Embedding", ("tool_mesh_embedding",)),
        ("Expand Operator Bounds", ("expand_operator_bounds",)),
        ("Expand Section Inclusion Bounds", ("expand_section_inclusion_bounds",)),
        ("Simplify Along New Edges", ("simplify_along_new_edges", "b_simplify_along_new_edges")),
        ("Weld Shared Edges", ("weld_shared_edges", "b_weld_shared_edges")),
        ("Draw Wire Mesh", ("draw_wire_mesh", "b_draw_wire_mesh")),
        ("Draw Local Bounds", ("draw_local_bounds", "b_draw_local_bounds")),
    ]

    exposed = {}
    record(lines, "")
    record(lines, "EXPOSED EDITOR PROPERTIES")
    record(lines, "-" * 96)
    for label, names in property_checks:
        prop_name, value = safe_property(component, names)
        exposed[label] = prop_name
        if prop_name:
            record(lines, f"{label}={value} | property={prop_name}")
        else:
            record(lines, f"{label}=not exposed | candidates={names}")

    record(lines, "")
    record(lines, "METHODS")
    record(lines, "-" * 96)
    method_names = (
        "update_from_mesh",
        "bp_set_static_mesh",
        "set_expand_operator_bounds",
        "get_expand_operator_bounds",
        "bp_set_affected_mega_mesh",
        "set_affected_mega_mesh",
    )
    methods = {}
    for name in method_names:
        present = callable(getattr(component, name, None))
        methods[name] = present
        record(lines, f"{name}={'YES' if present else 'NO'}")

    record(lines, "")
    record(lines, "BOOLEAN AND MESH-SOURCE ENUMS")
    record(lines, "-" * 96)
    enum_names = {
        "BooleanOperation",
        "BooleanToolMeshEmbedding",
        "BooleanModifierChannelSourceMode",
        "ModifierMeshSourceMode",
        "MegaMeshBooleanModifierPreviewVisOptions",
    }
    enum_names.update(
        name for name in dir(unreal)
        if "boolean" in name.lower() or "modifiermeshsourcemode" in name.lower()
    )
    for name in sorted(enum_names):
        enum_type = getattr(unreal, name, None)
        members = enum_members(enum_type) if enum_type else []
        record(lines, f"unreal.{name}: {', '.join(members) if members else 'no inspectable members'}")

    relevant_api = sorted(
        name for name in dir(component)
        if any(token in name.lower() for token in (
            "boolean", "mesh", "source", "static", "affected", "priority", "expand", "weld", "simpl"
        ))
    )
    record(lines, "")
    record(lines, f"Relevant component API names={','.join(relevant_api)}")

    record(lines, "")
    record(lines, "SOURCE ASSET CHECK")
    record(lines, "-" * 96)
    source_assets = [
        "/Engine/BasicShapes/Sphere",
        "/Game/Rock_Collection_04/Meshes/Rock_01/StaticMeshes/SM_Rock_01",
        "/Game/Rock_Collection_04/Meshes/Rock_02/StaticMeshes/SM_Rock_02",
        "/Game/Rock_Collection_04/Meshes/Rock_03/StaticMeshes/SM_Rock_03",
        "/Game/Rock_Collection_04/Meshes/Rock_04/StaticMeshes/SM_Rock_04",
        "/Game/Rock_Collection_04/Meshes/Rock_05/StaticMeshes/SM_Rock_05",
        "/Game/Rock_Collection_04/Meshes/Rock_06/StaticMeshes/SM_Rock_06",
        "/Game/Rock_Collection_04/Meshes/Rock_07/StaticMeshes/SM_Rock_07",
    ]
    assets_ok = True
    for path in source_assets:
        exists = unreal.EditorAssetLibrary.does_asset_exist(path)
        assets_ok = assets_ok and exists
        record(lines, f"{'YES' if exists else 'NO '} | {path}")

    # UE 5.8 exposes the Blueprint setter for the source mesh even though the
    # native CallInEditor UpdateFromMesh function is not wrapped for Python.
    # Either the direct property or the Blueprint setter is sufficient.
    has_affected_setter = bool(
        exposed.get("Affected Mesh Partition")
        or methods.get("bp_set_affected_mega_mesh")
        or methods.get("set_affected_mega_mesh")
    )
    has_mesh_setter = bool(
        exposed.get("Static Mesh")
        or methods.get("bp_set_static_mesh")
        or methods.get("update_from_mesh")
    )
    required = bool(
        has_affected_setter
        and has_mesh_setter
        and exposed.get("Mesh Source Mode")
        and exposed.get("Boolean Operation")
        and assets_ok
    )

    record(lines, "")
    record(lines, f"Affected setter available={has_affected_setter}")
    record(lines, f"Static-mesh setter available={has_mesh_setter}")
    record(lines, f"AETHER_BOOLEAN_API={'PASS' if required else 'CHECK'}")
    record(lines, "NO_ACTORS_SPAWNED=TRUE")
    record(lines, "NO_PACKAGES_SAVED=TRUE")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_BOOLEAN_API_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"AETHER_BOOLEAN_API=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
