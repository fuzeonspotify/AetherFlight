"""Build Aether Flight's soft, lit aerodynamic-condensation material for UE 5.8."""

import unreal


ASSET_DIR = "/Game/Aether/Effects"
ASSET_NAME = "M_WingCondensation"
ASSET_PATH = f"{ASSET_DIR}/{ASSET_NAME}"
BACKUP_DIR = f"{ASSET_DIR}/Backups"
BACKUP_PATH = f"{BACKUP_DIR}/{ASSET_NAME}_RGBRibbonBackup"
LOG = "[Aether Vapor Material v2]"


def log(message):
    unreal.log(f"{LOG} {message}")


def expression(material, expression_class, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, expression_class, x, y
    )
    if node is None:
        raise RuntimeError(f"Could not create {expression_class.__name__}")
    return node


def connect(source, target, input_names, description, source_output=""):
    if isinstance(input_names, str):
        input_names = (input_names,)
    for input_name in input_names:
        try:
            result = unreal.MaterialEditingLibrary.connect_material_expressions(
                source, source_output, target, input_name
            )
            if result is not False:
                return
        except Exception:
            pass
    raise RuntimeError(f"Could not connect {description}; tried {tuple(input_names)}")


def output(material, source, material_property, description, source_output=""):
    result = unreal.MaterialEditingLibrary.connect_material_property(
        source, source_output, material_property
    )
    if result is False:
        raise RuntimeError(f"Could not connect {description}")


def set_optional(obj, property_name, value):
    try:
        obj.set_editor_property(property_name, value)
        return True
    except Exception:
        log(f"Optional property {property_name} is unavailable")
        return False


def resolve_enum(enum_type, candidates, tokens):
    for candidate in candidates:
        value = getattr(enum_type, candidate, None)
        if value is not None:
            return value
    normalized_tokens = tuple(token.upper() for token in tokens)
    for attribute_name in dir(enum_type):
        normalized = "".join(c for c in attribute_name.upper() if c.isalnum())
        if all(token in normalized for token in normalized_tokens):
            return getattr(enum_type, attribute_name)
    raise RuntimeError(f"Could not resolve enum from {enum_type.__name__}: {candidates}")


def scalar(material, value, x, y):
    node = expression(material, unreal.MaterialExpressionConstant, x, y)
    node.set_editor_property("r", value)
    return node


def color(material, rgb, x, y):
    node = expression(material, unreal.MaterialExpressionConstant3Vector, x, y)
    node.set_editor_property("constant", unreal.LinearColor(*rgb, 1.0))
    return node


def component_mask(material, source, channel, x, y, description, source_output=""):
    node = expression(material, unreal.MaterialExpressionComponentMask, x, y)
    node.set_editor_property("r", channel == "R")
    node.set_editor_property("g", channel == "G")
    node.set_editor_property("b", channel == "B")
    node.set_editor_property("a", channel == "A")
    connect(source, node, ("Input", ""), description, source_output)
    return node


def binary(material, node_class, a, b, x, y, description):
    node = expression(material, node_class, x, y)
    connect(a, node, ("A", "Input1", ""), f"{description} A")
    connect(b, node, ("B", "Input2"), f"{description} B")
    return node


def multiply(material, a, b, x, y, description):
    return binary(material, unreal.MaterialExpressionMultiply, a, b, x, y, description)


def add(material, a, b, x, y, description):
    return binary(material, unreal.MaterialExpressionAdd, a, b, x, y, description)


def build_material():
    unreal.EditorAssetLibrary.make_directory(ASSET_DIR)
    unreal.EditorAssetLibrary.make_directory(BACKUP_DIR)
    material = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if material and not unreal.EditorAssetLibrary.does_asset_exist(BACKUP_PATH):
        if unreal.EditorAssetLibrary.duplicate_asset(ASSET_PATH, BACKUP_PATH):
            log(f"Backed up the old RGB-ribbon material to {BACKUP_PATH}")
    if not material:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            ASSET_NAME, ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew()
        )
    if not material:
        raise RuntimeError(f"Could not create {ASSET_PATH}")

    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("two_sided", True)
    material.set_editor_property("tangent_space_normal", False)
    lighting_mode = resolve_enum(
        unreal.TranslucencyLightingMode,
        ("TLM_VOLUMETRIC_DIRECTIONAL", "VOLUMETRIC_DIRECTIONAL"),
        ("VOLUMETRIC", "DIRECTIONAL"),
    )
    set_optional(material, "translucency_lighting_mode", lighting_mode)
    set_optional(material, "apply_cloud_fogging", True)
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    vertex_color = expression(material, unreal.MaterialExpressionVertexColor, -1500, -50)
    vertex_alpha = component_mask(
        material, vertex_color, "A", -1300, 120,
        "vertex alpha only"
    )
    texcoord = expression(material, unreal.MaterialExpressionTextureCoordinate, -1500, 330)
    tex_v = component_mask(material, texcoord, "G", -1300, 330, "vapor cross-section V")

    centered_v = add(
        material, tex_v, scalar(material, -0.5, -1300, 440),
        -1100, 350, "center vapor cross-section"
    )
    absolute_v = expression(material, unreal.MaterialExpressionAbs, -900, 350)
    connect(centered_v, absolute_v, ("Input", ""), "absolute cross-section distance")
    doubled_v = multiply(
        material, absolute_v, scalar(material, 2.0, -900, 455),
        -700, 350, "scale cross-section distance"
    )
    one_minus = expression(material, unreal.MaterialExpressionOneMinus, -500, 350)
    connect(doubled_v, one_minus, ("Input", ""), "soft edge inversion")
    saturated_edge = expression(material, unreal.MaterialExpressionSaturate, -300, 350)
    connect(one_minus, saturated_edge, ("Input", ""), "soft edge saturation")
    soft_edge = expression(material, unreal.MaterialExpressionPower, -100, 350)
    connect(saturated_edge, soft_edge, ("Base", "Input", ""), "soft edge base")
    connect(scalar(material, 0.58, -300, 470), soft_edge, ("Exp", "Exponent"), "soft edge exponent")

    tex_u = component_mask(material, texcoord, "R", -1300, 610, "vapor flow U")
    flow_u = multiply(
        material, tex_u, scalar(material, 0.74, -1300, 720),
        -1100, 620, "flow spatial frequency"
    )
    game_time = expression(material, unreal.MaterialExpressionTime, -1300, 850)
    time_flow = multiply(
        material, game_time, scalar(material, -0.24, -1300, 960),
        -1100, 850, "vapor advection"
    )
    phase = add(material, flow_u, time_flow, -900, 700, "advected vapor phase")
    wave_noise = expression(material, unreal.MaterialExpressionSine, -700, 700)
    set_optional(wave_noise, "period", 1.0)
    connect(phase, wave_noise, ("Input", ""), "animated density breakup")
    scaled_noise = multiply(
        material, wave_noise, scalar(material, 0.16, -700, 810),
        -500, 700, "density variation"
    )
    density_noise = add(
        material, scaled_noise, scalar(material, 0.84, -500, 810),
        -300, 700, "positive density range"
    )

    shaped_alpha = multiply(material, vertex_alpha, soft_edge, 140, 230, "soft vertex density")
    moving_alpha = multiply(material, shaped_alpha, density_noise, 350, 260, "animated density")
    depth_fade = expression(material, unreal.MaterialExpressionDepthFade, 120, 560)
    depth_fade.set_editor_property("fade_distance_default", 165.0)
    depth_fade.set_editor_property("opacity_default", 1.0)
    faded_alpha = multiply(material, moving_alpha, depth_fade, 560, 300, "depth-softened density")
    final_alpha = multiply(
        material, faded_alpha, scalar(material, 0.94, 350, 450),
        770, 300, "final condensation opacity"
    )

    vapor_color = color(material, (0.78, 0.88, 0.94), 520, -120)
    output(material, vapor_color, unreal.MaterialProperty.MP_BASE_COLOR, "neutral vapor base color")
    emissive = multiply(
        material, vapor_color, scalar(material, 0.025, 520, 15),
        760, -60, "subtle vapor emissive"
    )
    output(material, emissive, unreal.MaterialProperty.MP_EMISSIVE_COLOR, "subtle vapor emissive output")
    output(material, final_alpha, unreal.MaterialProperty.MP_OPACITY, "soft volumetric opacity")
    output(material, scalar(material, 0.92, 770, 470), unreal.MaterialProperty.MP_ROUGHNESS, "vapor roughness")
    output(material, scalar(material, 0.08, 770, 550), unreal.MaterialProperty.MP_SPECULAR, "vapor specular")

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {ASSET_PATH}")
    log("Installed neutral, lit, soft-edged aerodynamic vapor material")


def main():
    build_material()
    unreal.EditorDialog.show_message(
        "Aether Aerodynamic Vapor v2",
        "The RGB ribbon material was replaced with soft, lit condensation.\n\n"
        "Wait for shaders, Save All, rebuild the C++ module, then pull a hard turn "
        "above 185 knots in humid weather.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
