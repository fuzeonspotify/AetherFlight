"""Import Aether Flight's production terrain textures and build its landscape material.

Run with Tools > Execute Python Script before importing the 4033 heightmap.
The heightmap itself is imported from Landscape Mode; public Unreal Python APIs
do not reliably create partitioned Landscape actors across installed versions.
"""

from pathlib import Path

import unreal


PROJECT_DIR = Path(unreal.Paths.project_dir())
SOURCE_DIR = PROJECT_DIR / "SourceAssets" / "ProductionTerrain" / "Textures"
PACKAGE = "/Game/Aether/ProductionTerrain"
TEXTURE_PACKAGE = f"{PACKAGE}/Textures"
LAYERS = ("Grass", "Rock", "Scree", "Snow")


def log(message: str) -> None:
    unreal.log(f"[Aether Production Landscape] {message}")


def import_textures() -> dict[str, unreal.Texture2D]:
    if not SOURCE_DIR.is_dir():
        raise RuntimeError(f"Missing generated texture folder: {SOURCE_DIR}")

    unreal.EditorAssetLibrary.make_directory(TEXTURE_PACKAGE)
    tasks = []
    for source in sorted(SOURCE_DIR.glob("*.png")):
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(source))
        task.set_editor_property("destination_path", TEXTURE_PACKAGE)
        task.set_editor_property("destination_name", source.stem)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        tasks.append(task)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    imported = {}
    for source in sorted(SOURCE_DIR.glob("*.png")):
        asset_path = f"{TEXTURE_PACKAGE}/{source.stem}.{source.stem}"
        texture = unreal.EditorAssetLibrary.load_asset(asset_path)
        if not isinstance(texture, unreal.Texture2D):
            raise RuntimeError(f"Texture import failed: {asset_path}")

        is_normal = source.stem.endswith("_Normal")
        is_scalar = source.stem.endswith("_Roughness") or source.stem == "T_MacroVariation"
        texture.set_editor_property("srgb", not (is_normal or is_scalar))
        texture.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
        texture.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
        if is_normal:
            texture.set_editor_property(
                "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP
            )
        elif is_scalar:
            texture.set_editor_property(
                "compression_settings", unreal.TextureCompressionSettings.TC_MASKS
            )
        texture.modify()
        unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False)
        imported[source.stem] = texture
        log(f"Imported {source.stem}")
    return imported


def expression(material, expression_class, x: int, y: int):
    return unreal.MaterialEditingLibrary.create_material_expression(
        material, expression_class, x, y
    )


def create_material() -> unreal.Material:
    unreal.EditorAssetLibrary.make_directory(PACKAGE)
    path = f"{PACKAGE}/M_Landscape_Production.M_Landscape_Production"
    material = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(material, unreal.Material):
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_Landscape_Production", PACKAGE, unreal.Material, unreal.MaterialFactoryNew()
        )
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"Could not create {path}")

    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    material.set_editor_property("two_sided", False)
    material.set_editor_property("tangent_space_normal", True)
    return material


def world_xy(material, scale_cm: float, x: int, y: int):
    position = expression(material, unreal.MaterialExpressionWorldPosition, x, y)
    mask = expression(material, unreal.MaterialExpressionComponentMask, x + 190, y)
    mask.set_editor_property("r", True)
    mask.set_editor_property("g", True)
    mask.set_editor_property("b", False)
    mask.set_editor_property("a", False)
    unreal.MaterialEditingLibrary.connect_material_expressions(position, "", mask, "Input")

    divisor = expression(material, unreal.MaterialExpressionConstant2Vector, x + 190, y + 120)
    divisor.set_editor_property("r", scale_cm)
    divisor.set_editor_property("g", scale_cm)
    divide = expression(material, unreal.MaterialExpressionDivide, x + 390, y)
    unreal.MaterialEditingLibrary.connect_material_expressions(mask, "", divide, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(divisor, "", divide, "B")
    return divide


def texture_sample(material, texture, parameter_name: str, uv, x: int, y: int,
                   normal=False, linear=False):
    sample = expression(material, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    sample.set_editor_property("parameter_name", parameter_name)
    sample.set_editor_property("texture", texture)
    if normal:
        sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    elif linear:
        sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    else:
        sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_expressions(uv, "", sample, "UVs")
    return sample


def layer_blend(material, x: int, y: int):
    blend = expression(material, unreal.MaterialExpressionLandscapeLayerBlend, x, y)
    entries = []
    for index, layer_name in enumerate(LAYERS):
        entry = unreal.LayerBlendInput()
        entry.set_editor_property("layer_name", layer_name)
        entry.set_editor_property(
            "blend_type", unreal.LandscapeLayerBlendType.LB_WEIGHT_BLEND
        )
        entry.set_editor_property("preview_weight", 1.0 if index == 0 else 0.0)
        entries.append(entry)
    blend.set_editor_property("layers", entries)
    return blend


def connect_layer(source, output_name: str, blend, layer_name: str) -> None:
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, output_name, blend, layer_name
    ):
        raise RuntimeError(f"Could not connect Landscape layer pin '{layer_name}'")


def build_material(textures: dict[str, unreal.Texture2D]) -> unreal.Material:
    material = create_material()
    detail_uv = world_xy(material, 420.0, -1700, -720)
    macro_uv = world_xy(material, 185000.0, -1700, 820)

    base_blend = layer_blend(material, -430, -560)
    normal_blend = layer_blend(material, -430, 80)
    roughness_blend = layer_blend(material, -430, 660)

    for index, layer_name in enumerate(LAYERS):
        y = -1160 + index * 280
        base = texture_sample(
            material, textures[f"T_{layer_name}_BaseColor"],
            f"{layer_name}_BaseColor", detail_uv, -1060, y
        )
        normal = texture_sample(
            material, textures[f"T_{layer_name}_Normal"],
            f"{layer_name}_Normal", detail_uv, -790, y, normal=True
        )
        roughness = texture_sample(
            material, textures[f"T_{layer_name}_Roughness"],
            f"{layer_name}_Roughness", detail_uv, -520, y, linear=True
        )
        connect_layer(base, "RGB", base_blend, layer_name)
        connect_layer(normal, "RGB", normal_blend, layer_name)
        connect_layer(roughness, "R", roughness_blend, layer_name)

    macro = texture_sample(
        material, textures["T_MacroVariation"], "MacroVariation", macro_uv, -130, -830,
        linear=True
    )
    tint = expression(material, unreal.MaterialExpressionMultiply, 80, -510)
    unreal.MaterialEditingLibrary.connect_material_expressions(base_blend, "", tint, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(macro, "R", tint, "B")

    unreal.MaterialEditingLibrary.connect_material_property(
        tint, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        normal_blend, "", unreal.MaterialProperty.MP_NORMAL
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness_blend, "", unreal.MaterialProperty.MP_ROUGHNESS
    )

    specular = expression(material, unreal.MaterialExpressionConstant, 80, 450)
    specular.set_editor_property("r", 0.24)
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )
    ao = expression(material, unreal.MaterialExpressionConstant, 80, 560)
    ao.set_editor_property("r", 1.0)
    unreal.MaterialEditingLibrary.connect_material_property(
        ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"Built {material.get_path_name()}")
    return material


def create_layer_info_assets() -> None:
    package = f"{PACKAGE}/LayerInfo"
    unreal.EditorAssetLibrary.make_directory(package)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory_class = getattr(unreal, "LandscapeLayerInfoObjectFactory", None)
    if factory_class is None:
        log("This engine build does not expose LandscapeLayerInfoObjectFactory; create layer infos in Paint mode.")
        return

    for layer_name in LAYERS:
        path = f"{package}/LI_{layer_name}.LI_{layer_name}"
        info = unreal.EditorAssetLibrary.load_asset(path)
        if not isinstance(info, unreal.LandscapeLayerInfoObject):
            info = asset_tools.create_asset(
                f"LI_{layer_name}", package, unreal.LandscapeLayerInfoObject, factory_class()
            )
        if isinstance(info, unreal.LandscapeLayerInfoObject):
            info.set_editor_property("layer_name", layer_name)
            unreal.EditorAssetLibrary.save_loaded_asset(info, only_if_is_dirty=False)
            log(f"Ready: LI_{layer_name}")


def main() -> None:
    textures = import_textures()
    build_material(textures)
    create_layer_info_assets()
    unreal.EditorDialog.show_message(
        "Aether Production Landscape",
        "Production terrain textures and M_Landscape_Production are ready.\n\n"
        "Next: follow PRODUCTION_LANDSCAPE_SETUP.md to import the 4033 heightmap.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
