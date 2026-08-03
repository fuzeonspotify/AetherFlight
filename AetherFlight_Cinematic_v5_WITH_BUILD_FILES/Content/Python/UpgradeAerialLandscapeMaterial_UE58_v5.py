"""Upgrade Aether Flight's Landscape material for an aerial camera.

This material-only pass preserves the existing 4033 Landscape, Layer Info
assets, and imported Grass/Rock/Scree/Snow weightmaps. It reduces obvious
tiling by mixing two differently rotated color scales per biome, uses separate
normal scales, and strengthens broad macro variation. All graph connections
use UE 5.8-safe fixed A/B/Base/Layer pins.
"""

import unreal


PACKAGE = "/Game/Aether/ProductionTerrain"
TEXTURE_PACKAGE = f"{PACKAGE}/Textures"
MATERIAL_NAME = "M_Landscape_Production"
LAYERS = ("Grass", "Rock", "Scree", "Snow")
XY_VERTEX_SPACING_CM = 1190.476190

# Color tile sizes are intentionally much larger than the old 4.2 m value.
# This is an aerial flight game, so avoiding visible grids at altitude matters
# more than centimeter-scale ground detail. Mixing two non-aligned scales keeps
# the surface from becoming blurry when the camera gets closer.
LAYER_SETTINGS = {
    "Grass": {
        "near_cm": 3800.0,
        "broad_cm": 17500.0,
        "normal_cm": 1100.0,
        "near_rotation": 11.0,
        "broad_rotation": 73.0,
        "pan_u": 0.17,
        "pan_v": -0.29,
        "roughness": 0.86,
    },
    "Rock": {
        "near_cm": 6200.0,
        "broad_cm": 24000.0,
        "normal_cm": 1600.0,
        "near_rotation": -19.0,
        "broad_rotation": 41.0,
        "pan_u": -0.31,
        "pan_v": 0.12,
        "roughness": 0.72,
    },
    "Scree": {
        "near_cm": 3200.0,
        "broad_cm": 14500.0,
        "normal_cm": 950.0,
        "near_rotation": 27.0,
        "broad_rotation": -58.0,
        "pan_u": 0.43,
        "pan_v": 0.36,
        "roughness": 0.91,
    },
    "Snow": {
        "near_cm": 8500.0,
        "broad_cm": 32000.0,
        "normal_cm": 2200.0,
        "near_rotation": -8.0,
        "broad_rotation": 64.0,
        "pan_u": -0.14,
        "pan_v": -0.47,
        "roughness": 0.64,
    },
}


def log(message: str) -> None:
    unreal.log(f"[Aether UE5.8 Aerial Material v5] {message}")


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


def constant(material, value: float, x: int, y: int):
    node = expression(material, unreal.MaterialExpressionConstant, x, y)
    node.set_editor_property("r", value)
    return node


def load_texture(name: str) -> unreal.Texture2D:
    path = f"{TEXTURE_PACKAGE}/{name}.{name}"
    texture = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError(f"Missing required texture: {path}")
    return texture


def load_material() -> unreal.Material:
    path = f"{PACKAGE}/{MATERIAL_NAME}.{MATERIAL_NAME}"
    material = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(material, unreal.Material):
        raise RuntimeError(
            f"Missing {path}. Run the completed world repair before this upgrade."
        )
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    material.set_editor_property("two_sided", False)
    material.set_editor_property("tangent_space_normal", True)
    return material


def landscape_uv(material, tile_size_cm: float, rotation: float, pan_u: float,
                 pan_v: float, x: int, y: int):
    coords = expression(material, unreal.MaterialExpressionLandscapeLayerCoords, x, y)
    coords.set_editor_property(
        "mapping_scale", XY_VERTEX_SPACING_CM / tile_size_cm
    )
    coords.set_editor_property("mapping_rotation", rotation)
    coords.set_editor_property("mapping_pan_u", pan_u)
    coords.set_editor_property("mapping_pan_v", pan_v)
    return coords


def texture_sample(material, texture, parameter_name: str, uv, x: int, y: int,
                   normal=False, scalar=False):
    sample = expression(material, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    sample.set_editor_property("parameter_name", parameter_name)
    sample.set_editor_property("texture", texture)
    if normal:
        sample.set_editor_property(
            "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
        )
    elif scalar:
        sample.set_editor_property(
            "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
        )
    else:
        sample.set_editor_property(
            "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
        )
    connect(uv, "", sample, "UVs", f"UVs for {parameter_name}")
    return sample


def multiply(material, a, a_output: str, b, b_output: str, x: int, y: int,
             description: str):
    node = expression(material, unreal.MaterialExpressionMultiply, x, y)
    connect(a, a_output, node, "A", f"{description} A")
    connect(b, b_output, node, "B", f"{description} B")
    return node


def add(material, a, a_output: str, b, b_output: str, x: int, y: int,
        description: str):
    node = expression(material, unreal.MaterialExpressionAdd, x, y)
    connect(a, a_output, node, "A", f"{description} A")
    connect(b, b_output, node, "B", f"{description} B")
    return node


def weighted_sum(material, sources, x: int, y: int):
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


def missing_weight(material, x: int, y: int):
    one = constant(material, 1.0, x, y - 170)
    total = weighted_sum(
        material,
        [(layer_name, one, "") for layer_name in LAYERS],
        x + 180,
        y,
    )
    missing = expression(material, unreal.MaterialExpressionSubtract, x + 1160, y)
    connect(one, "", missing, "A", "one to missing-weight Subtract")
    connect(total, "", missing, "B", "painted weight to Subtract")
    return missing


def add_fallback(material, painted, fallback_source, fallback_output: str,
                 unpainted_weight, x: int, y: int):
    fallback = multiply(
        material,
        fallback_source,
        fallback_output,
        unpainted_weight,
        "",
        x,
        y,
        "unpainted Grass fallback",
    )
    return add(
        material,
        painted,
        "",
        fallback,
        "",
        x + 230,
        y,
        "painted layers plus fallback",
    )


def build_layer(material, layer_name: str, index: int, near_weight, broad_weight):
    settings = LAYER_SETTINGS[layer_name]
    column_x = -2300 + index * 540

    near_uv = landscape_uv(
        material,
        settings["near_cm"],
        settings["near_rotation"],
        settings["pan_u"],
        settings["pan_v"],
        column_x,
        -1280,
    )
    broad_uv = landscape_uv(
        material,
        settings["broad_cm"],
        settings["broad_rotation"],
        -settings["pan_v"],
        settings["pan_u"],
        column_x,
        -1080,
    )
    normal_uv = landscape_uv(
        material,
        settings["normal_cm"],
        settings["near_rotation"] + 31.0,
        settings["pan_v"],
        -settings["pan_u"],
        column_x,
        -880,
    )

    base_texture = load_texture(f"T_{layer_name}_BaseColor")
    near_sample = texture_sample(
        material,
        base_texture,
        f"{layer_name}_ColorNear",
        near_uv,
        column_x + 180,
        -1280,
    )
    broad_sample = texture_sample(
        material,
        base_texture,
        f"{layer_name}_ColorBroad",
        broad_uv,
        column_x + 180,
        -1060,
    )
    near_part = multiply(
        material,
        near_sample,
        "RGB",
        near_weight,
        "",
        column_x + 360,
        -1280,
        f"{layer_name} near color",
    )
    broad_part = multiply(
        material,
        broad_sample,
        "RGB",
        broad_weight,
        "",
        column_x + 360,
        -1060,
        f"{layer_name} broad color",
    )
    color = add(
        material,
        near_part,
        "",
        broad_part,
        "",
        column_x + 520,
        -1170,
        f"{layer_name} multiscale color",
    )

    normal = texture_sample(
        material,
        load_texture(f"T_{layer_name}_Normal"),
        f"{layer_name}_NormalAerial",
        normal_uv,
        column_x + 180,
        -820,
        normal=True,
    )
    roughness = constant(
        material,
        settings["roughness"],
        column_x + 360,
        -700,
    )
    return color, normal, roughness


def build_material() -> unreal.Material:
    material = load_material()
    near_weight = constant(material, 0.68, -2500, -1600)
    broad_weight = constant(material, 0.32, -2360, -1600)

    colors = {}
    normals = {}
    roughness_values = {}
    for index, layer_name in enumerate(LAYERS):
        color, normal, roughness = build_layer(
            material, layer_name, index, near_weight, broad_weight
        )
        colors[layer_name] = color
        normals[layer_name] = normal
        roughness_values[layer_name] = roughness

    color_painted = weighted_sum(
        material,
        [(name, colors[name], "") for name in LAYERS],
        0,
        -480,
    )
    normal_painted = weighted_sum(
        material,
        [(name, normals[name], "RGB") for name in LAYERS],
        0,
        100,
    )
    roughness_painted = weighted_sum(
        material,
        [(name, roughness_values[name], "") for name in LAYERS],
        0,
        680,
    )
    unpainted = missing_weight(material, -650, 1260)

    color_complete = add_fallback(
        material, color_painted, colors["Grass"], "", unpainted, 1050, -480
    )
    normal_complete = add_fallback(
        material, normal_painted, normals["Grass"], "RGB", unpainted, 1050, 100
    )
    roughness_complete = add_fallback(
        material,
        roughness_painted,
        roughness_values["Grass"],
        "",
        unpainted,
        1050,
        680,
    )

    macro_uv = landscape_uv(
        material, 120000.0, 17.0, 0.22, -0.38, 650, -1050
    )
    macro_sample = texture_sample(
        material,
        load_texture("T_MacroVariation"),
        "MacroVariationAerial",
        macro_uv,
        850,
        -1050,
        scalar=True,
    )
    macro_strength = constant(material, 0.38, 1040, -980)
    macro_floor = constant(material, 0.72, 1040, -880)
    macro_scaled = multiply(
        material,
        macro_sample,
        "R",
        macro_strength,
        "",
        1210,
        -1040,
        "macro strength",
    )
    macro_factor = add(
        material,
        macro_scaled,
        "",
        macro_floor,
        "",
        1390,
        -980,
        "macro floor",
    )
    final_color = multiply(
        material,
        color_complete,
        "",
        macro_factor,
        "",
        1580,
        -480,
        "final aerial color",
    )

    unreal.MaterialEditingLibrary.connect_material_property(
        final_color, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        normal_complete, "", unreal.MaterialProperty.MP_NORMAL
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness_complete, "", unreal.MaterialProperty.MP_ROUGHNESS
    )

    specular = constant(material, 0.22, 1580, 420)
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )
    ao = constant(material, 1.0, 1580, 540)
    unreal.MaterialEditingLibrary.connect_material_property(
        ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(
        f"Upgraded {material.get_path_name()} with multiscale aerial texture blending"
    )
    return material


def main() -> None:
    build_material()
    unreal.EditorDialog.show_message(
        "Aether UE5.8 Aerial Landscape Material v5",
        "The Landscape material was upgraded successfully.\n\n"
        "Your 4033 terrain, Layer Info assets, and four imported biome masks were preserved.\n"
        "Wait for shaders, Save All, then test the same camera view again.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
