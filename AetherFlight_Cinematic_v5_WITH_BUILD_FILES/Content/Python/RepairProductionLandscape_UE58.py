"""Repair Aether Flight's production Landscape material in Unreal Engine 5.8.

Version 2 avoids both UE 5.8 compatibility problems found in the original
installer: dynamic LandscapeLayerBlend pins and WorldPosition output pins.
It preserves the Landscape actor, heightmap, layer-info assets, and weightmaps.
"""

import unreal


PACKAGE = "/Game/Aether/ProductionTerrain"
TEXTURE_PACKAGE = f"{PACKAGE}/Textures"
MATERIAL_NAME = "M_Landscape_Production"
LAYERS = ("Grass", "Rock", "Scree", "Snow")


def log(message: str) -> None:
    unreal.log(f"[Aether UE5.8 Repair v2] {message}")


def expression(material, expression_class, x: int, y: int):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, expression_class, x, y
    )
    if node is None:
        raise RuntimeError(f"Could not create material node {expression_class}")
    return node


def connect(source, source_output: str, target, target_input: str, description: str) -> None:
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(f"Could not connect {description}")


def load_texture(name: str) -> unreal.Texture2D:
    path = f"{TEXTURE_PACKAGE}/{name}.{name}"
    texture = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError(
            f"Missing {path}. Run InstallProductionLandscape.py once to import textures."
        )
    return texture


def get_material() -> unreal.Material:
    path = f"{PACKAGE}/{MATERIAL_NAME}.{MATERIAL_NAME}"
    material = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(material, unreal.Material):
        unreal.EditorAssetLibrary.make_directory(PACKAGE)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            MATERIAL_NAME, PACKAGE, unreal.Material, unreal.MaterialFactoryNew()
        )
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"Could not create or load {path}")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    material.set_editor_property("two_sided", False)
    material.set_editor_property("tangent_space_normal", True)
    return material


def landscape_uv(material, scale: float, x: int, y: int):
    """Use the Landscape's native coordinates; this node has one stable output."""
    coords = expression(material, unreal.MaterialExpressionLandscapeLayerCoords, x, y)
    coords.set_editor_property("mapping_scale", scale)
    return coords


def texture_sample(material, texture, parameter_name: str, uv, x: int, y: int,
                   normal=False, scalar=False):
    sample = expression(material, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    sample.set_editor_property("parameter_name", parameter_name)
    sample.set_editor_property("texture", texture)
    if normal:
        sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    elif scalar:
        sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    else:
        sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    connect(uv, "", sample, "UVs", f"Landscape UVs for {parameter_name}")
    return sample


def weighted_blend(material, sources, x: int, y: int):
    """Blend normalized Landscape weightmaps through fixed Base/Layer pins."""
    previous = None
    for index, (layer_name, source, output_name) in enumerate(sources):
        node = expression(
            material,
            unreal.MaterialExpressionLandscapeLayerWeight,
            x + index * 230,
            y,
        )
        node.set_editor_property("parameter_name", layer_name)
        node.set_editor_property("preview_weight", 1.0 if index == 0 else 0.0)
        if previous is not None:
            connect(previous, "", node, "Base", f"Base for {layer_name}")
        connect(source, output_name, node, "Layer", f"Layer for {layer_name}")
        previous = node
    return previous


def build_material() -> unreal.Material:
    material = get_material()
    detail_uv = landscape_uv(material, 420.0, -1800, -720)
    macro_uv = landscape_uv(material, 185000.0, -1800, 820)
    base_sources = []
    normal_sources = []
    roughness_sources = []

    for index, layer_name in enumerate(LAYERS):
        y = -1160 + index * 280
        base = texture_sample(
            material,
            load_texture(f"T_{layer_name}_BaseColor"),
            f"{layer_name}_BaseColor",
            detail_uv,
            -1120,
            y,
        )
        normal = texture_sample(
            material,
            load_texture(f"T_{layer_name}_Normal"),
            f"{layer_name}_Normal",
            detail_uv,
            -840,
            y,
            normal=True,
        )
        roughness = texture_sample(
            material,
            load_texture(f"T_{layer_name}_Roughness"),
            f"{layer_name}_Roughness",
            detail_uv,
            -560,
            y,
            scalar=True,
        )
        base_sources.append((layer_name, base, "RGB"))
        normal_sources.append((layer_name, normal, "RGB"))
        roughness_sources.append((layer_name, roughness, "R"))

    base_blend = weighted_blend(material, base_sources, -260, -470)
    normal_blend = weighted_blend(material, normal_sources, -260, 80)
    roughness_blend = weighted_blend(material, roughness_sources, -260, 630)

    macro = texture_sample(
        material,
        load_texture("T_MacroVariation"),
        "MacroVariation",
        macro_uv,
        700,
        -800,
        scalar=True,
    )
    tint = expression(material, unreal.MaterialExpressionMultiply, 940, -470)
    connect(base_blend, "", tint, "A", "base layers to macro tint")
    connect(macro, "R", tint, "B", "macro variation to tint")

    unreal.MaterialEditingLibrary.connect_material_property(
        tint, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        normal_blend, "", unreal.MaterialProperty.MP_NORMAL
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness_blend, "", unreal.MaterialProperty.MP_ROUGHNESS
    )

    specular = expression(material, unreal.MaterialExpressionConstant, 940, 420)
    specular.set_editor_property("r", 0.24)
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )
    ao = expression(material, unreal.MaterialExpressionConstant, 940, 540)
    ao.set_editor_property("r", 1.0)
    unreal.MaterialEditingLibrary.connect_material_property(
        ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"Rebuilt {material.get_path_name()} with Landscape-native coordinates")
    return material


def apply_to_largest_landscape(material) -> str:
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = [
        actor
        for actor in subsystem.get_all_level_actors()
        if actor.get_class().get_name() == "Landscape"
    ]
    if not landscapes:
        return "No Landscape actor was found; assign the material manually."

    production = max(
        landscapes,
        key=lambda actor: abs(actor.get_actor_scale3d().x * actor.get_actor_scale3d().y),
    )
    production.set_editor_property("landscape_material", material)
    production.modify()
    try:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    except Exception:
        pass
    return f"Applied to {production.get_actor_label()}."


def main() -> None:
    material = build_material()
    result = apply_to_largest_landscape(material)
    unreal.EditorDialog.show_message(
        "Aether UE5.8 Landscape Repair v2",
        "The production material graph was rebuilt successfully.\n"
        f"{result}\n\nWait for shaders to finish, save all, then test again.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
