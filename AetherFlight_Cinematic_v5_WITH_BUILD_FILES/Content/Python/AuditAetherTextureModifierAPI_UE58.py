from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherTextureModifierAPIAudit.txt"

TEXTURE_ASSETS = [
    "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Grass_Weight",
    "/Game/Aether/MeshTerrain/Weightmaps/T_MT_ForestFloor_Weight",
    "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Rock_Weight",
    "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Sand_Weight",
    "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Scree_Weight",
    "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Snow_Weight",
    "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Wetland_Weight",
]


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
        if name in ("name", "value"):
            continue
        members.append(f"{name}={value}")
    return members


def texture_dimensions(texture):
    for x_name, y_name in (
        ("blueprint_get_size_x", "blueprint_get_size_y"),
        ("get_size_x", "get_size_y"),
    ):
        x_method = getattr(texture, x_name, None)
        y_method = getattr(texture, y_name, None)
        if callable(x_method) and callable(y_method):
            try:
                return int(x_method()), int(y_method())
            except Exception:
                pass
    try:
        imported = texture.get_editor_property("imported_size")
        return int(imported.x), int(imported.y)
    except Exception:
        return None, None


def main():
    lines = []
    record(lines, "AETHER UE 5.8 TEXTURE MODIFIER API AUDIT")
    record(lines, "=" * 96)
    record(lines, "Read-only: no actors are spawned, no packages are saved, and no Mesh Partition build is started.")

    modifier_class = getattr(unreal, "TexturePatchModifier", None)
    record(lines, f"unreal.TexturePatchModifier={'YES' if modifier_class else 'NO'}")
    if not modifier_class:
        names = sorted(
            name for name in dir(unreal)
            if any(token in name.lower() for token in ("texturepatch", "texture_patch", "texturemodifier"))
        )
        record(lines, f"Texture-modifier-related Unreal names={','.join(names) if names else 'None'}")
        record(lines, "AETHER_TEXTURE_MODIFIER_API=FAIL")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    component = unreal.get_default_object(modifier_class)
    record(lines, f"Class={component.get_class().get_path_name()}")
    record(lines, f"Default object={component.get_path_name()}")

    checks = [
        ("Affected Mesh Partition", ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor")),
        ("Priority", ("priority",)),
        ("Layer Sub-Priority", ("layer_sub_priority", "sub_priority", "priority_sub_layer")),
        ("Disabled", ("is_disabled", "disabled")),
        ("Texture", ("texture", "height_texture", "displacement_texture", "source_texture", "texture_asset", "patch_texture")),
        ("Texture Channel", ("texture_channel", "channel", "source_channel")),
        ("Displacement Scale", ("displacement_scale", "height_scale", "amplitude", "strength", "magnitude")),
        ("Displacement Offset", ("displacement_offset", "height_offset", "offset")),
        ("Blend Mode", ("blend_mode", "operation", "apply_mode")),
        ("Coverage", ("unscaled_coverage", "coverage", "local_coverage")),
        ("Projection Plane", ("projection_plane",)),
        ("Adaptive Tessellation", ("adaptive_tessellation", "enable_adaptive_tessellation", "use_adaptive_tessellation")),
        ("Adaptive Target Edge Length", ("adaptive_tessellation_target_edge_length", "target_edge_length", "tessellation_target_edge_length")),
        ("Adaptive Error Threshold", ("adaptive_tessellation_error_threshold", "adaptive_error_threshold", "error_threshold")),
        ("Weight Channel", ("weight_channel", "output_weight_channel", "write_weight_channel")),
        ("Draw Local Bounds", ("draw_local_bounds", "b_draw_local_bounds")),
        ("Draw World Bounds", ("draw_world_bounds", "b_draw_world_bounds")),
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
        "bp_bind_to_nearest_mesh_partition",
        "set_affected_mega_mesh",
        "set_texture",
        "bp_set_texture",
        "set_displacement_texture",
        "set_height_texture",
        "set_adaptive_tessellation",
        "set_target_edge_length",
    )
    methods = {}
    record(lines, "")
    record(lines, "METHODS")
    record(lines, "-" * 96)
    for name in method_names:
        present = callable(getattr(component, name, None))
        methods[name] = present
        record(lines, f"{name}={'YES' if present else 'NO'}")

    relevant_api = sorted(
        name for name in dir(component)
        if any(token in name.lower() for token in (
            "texture", "height", "displace", "tessell", "adaptive", "coverage",
            "projection", "weight", "channel", "affected", "priority", "blend", "offset"
        ))
    )
    record(lines, "")
    record(lines, f"Relevant component API names={','.join(relevant_api)}")

    record(lines, "")
    record(lines, "RELEVANT ENUMS AND STRUCTS")
    record(lines, "-" * 96)
    enum_names = sorted(
        name for name in dir(unreal)
        if any(token in name.lower() for token in (
            "texturepatch", "texture_patch", "tessell", "displace", "projectionplane", "blendmode"
        ))
    )
    for name in enum_names:
        obj = getattr(unreal, name, None)
        members = enum_members(obj) if obj else []
        if members:
            record(lines, f"unreal.{name}: {', '.join(members)}")

    record(lines, "")
    record(lines, "AETHER TEXTURE ASSETS")
    record(lines, "-" * 96)
    available_textures = 0
    for path in TEXTURE_ASSETS:
        exists = unreal.EditorAssetLibrary.does_asset_exist(path)
        if not exists:
            record(lines, f"NO  | {path}")
            continue
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if not asset:
            record(lines, f"YES | load failed | {path}")
            continue
        available_textures += 1
        size_x, size_y = texture_dimensions(asset)
        size_text = f"{size_x}x{size_y}" if size_x and size_y else "size-unavailable"
        record(lines, f"YES | {asset.get_class().get_path_name()} | {size_text} | {path}")

    input_exposed = bool(exposed.get("Texture")) or any(
        methods.get(name) for name in (
            "set_texture", "bp_set_texture", "set_displacement_texture", "set_height_texture"
        )
    )
    affected_exposed = bool(exposed.get("Affected Mesh Partition")) or methods.get("bp_set_affected_mega_mesh")
    status = "PASS" if modifier_class and affected_exposed and available_textures else "CHECK"

    record(lines, "")
    record(lines, f"TEXTURE_INPUT_DIRECTLY_EXPOSED={'YES' if input_exposed else 'NO_OR_REQUIRES_COMPONENT_INSPECTION'}")
    record(lines, f"AETHER_TEXTURE_MODIFIER_API={status}")
    record(lines, "NO_ACTORS_SPAWNED=TRUE")
    record(lines, "NO_PACKAGES_SAVED=TRUE")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_TEXTURE_MODIFIER_API_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"AETHER_TEXTURE_MODIFIER_API=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
