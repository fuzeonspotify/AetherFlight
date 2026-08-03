"""Install Aether Flight's physically based cinematic ocean material in Unreal 5.8.

Run with Tools > Execute Python Script while not in PIE. The script backs up the
existing material once, then rebuilds M_Ocean_Cinematic as opaque Single Layer
Water with an analytical five-band wave spectrum. Runtime weather drives the
SeaState, OceanRoughness, and FoamAmount parameters.
"""

import math
import unreal


PACKAGE = "/Game/Aether/Materials"
NAME = "M_Ocean_Cinematic"
ASSET_PATH = f"{PACKAGE}/{NAME}.{NAME}"
BACKUP_PACKAGE = f"{PACKAGE}/Backups"
BACKUP_PATH = f"{BACKUP_PACKAGE}/{NAME}_PreExtreme"


def log(message: str) -> None:
    unreal.log(f"[Aether Water] {message}")


def make_expression(material, expression_class, x: int, y: int):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, expression_class, x, y
    )
    if node is None:
        raise RuntimeError(f"Could not create {expression_class.__name__}")
    return node


def set_property(obj, name: str, value, required: bool = True) -> None:
    try:
        obj.set_editor_property(name, value)
    except Exception as exc:
        if required:
            raise RuntimeError(f"Could not set {name} on {obj}: {exc}") from exc
        log(f"Optional property {name} is unavailable in this engine build")


def resolve_enum_value(enum_type, candidates, semantic_tokens):
    """Resolve Unreal enum spellings that changed between Python API versions."""
    for candidate in candidates:
        value = getattr(enum_type, candidate, None)
        if value is not None:
            log(f"Using {enum_type.__name__}.{candidate}")
            return value

    normalized_tokens = tuple(token.upper() for token in semantic_tokens)
    for attribute_name in dir(enum_type):
        normalized_name = "".join(character for character in attribute_name.upper() if character.isalnum())
        if all(token in normalized_name for token in normalized_tokens):
            value = getattr(enum_type, attribute_name, None)
            if value is not None:
                log(f"Resolved UE enum spelling as {enum_type.__name__}.{attribute_name}")
                return value

    available = [name for name in dir(enum_type) if name.isupper()]
    raise RuntimeError(
        f"Could not find the Single Layer Water shading model in {enum_type.__name__}. "
        f"Available enum values: {available}"
    )


def connect(source, target, input_names, description: str) -> None:
    if isinstance(input_names, str):
        input_names = (input_names,)
    for input_name in input_names:
        try:
            result = unreal.MaterialEditingLibrary.connect_material_expressions(
                source, "", target, input_name
            )
            if result is not False:
                return
        except Exception:
            pass
    raise RuntimeError(f"Could not connect {description}; tried {tuple(input_names)}")


def output(material, source, material_property, description: str) -> None:
    result = unreal.MaterialEditingLibrary.connect_material_property(
        source, "", material_property
    )
    if result is False:
        raise RuntimeError(f"Could not connect material output: {description}")


def scalar(material, value: float, x: int, y: int):
    node = make_expression(material, unreal.MaterialExpressionConstant, x, y)
    set_property(node, "r", value)
    return node


def scalar_parameter(material, name: str, value: float, x: int, y: int):
    node = make_expression(material, unreal.MaterialExpressionScalarParameter, x, y)
    set_property(node, "parameter_name", name)
    set_property(node, "default_value", value)
    return node


def constant2(material, value, x: int, y: int):
    node = make_expression(material, unreal.MaterialExpressionConstant2Vector, x, y)
    set_property(node, "r", value[0])
    set_property(node, "g", value[1])
    return node


def vector_parameter(material, name: str, value, x: int, y: int):
    node = make_expression(material, unreal.MaterialExpressionVectorParameter, x, y)
    set_property(node, "parameter_name", name)
    set_property(node, "default_value", unreal.LinearColor(*value, 1.0))
    return node


def binary(material, node_class, a, b, x: int, y: int, name: str):
    node = make_expression(material, node_class, x, y)
    connect(a, node, ("A", "Input1", ""), f"{name} A")
    connect(b, node, ("B", "Input2"), f"{name} B")
    return node


def add(material, a, b, x: int, y: int, name: str):
    return binary(material, unreal.MaterialExpressionAdd, a, b, x, y, name)


def multiply(material, a, b, x: int, y: int, name: str):
    return binary(material, unreal.MaterialExpressionMultiply, a, b, x, y, name)


def append(material, a, b, x: int, y: int, name: str):
    return binary(material, unreal.MaterialExpressionAppendVector, a, b, x, y, name)


def sum_nodes(material, nodes, x: int, y: int, name: str):
    result = nodes[0]
    for index, node in enumerate(nodes[1:], 1):
        result = add(material, result, node, x + index * 150, y, f"{name} {index}")
    return result


def make_wave(material, world_xy, game_time, sea_state, spec, row: int):
    """Return height, dHeight/dX, dHeight/dY for one sinusoidal wave band."""
    wavelength, amplitude, speed, direction_x, direction_y = spec
    direction_length = math.sqrt(direction_x * direction_x + direction_y * direction_y)
    direction_x /= direction_length
    direction_y /= direction_length
    inv_x = direction_x / wavelength
    inv_y = direction_y / wavelength
    y = -1250 + row * 330

    direction = constant2(material, (inv_x, inv_y), -2400, y)
    dot = make_expression(material, unreal.MaterialExpressionDotProduct, -2200, y)
    connect(world_xy, dot, ("A", "Input1", ""), f"wave {row} world position")
    connect(direction, dot, ("B", "Input2"), f"wave {row} direction")

    time_speed = multiply(
        material, game_time, scalar(material, speed, -2400, y + 100),
        -2200, y + 100, f"wave {row} time speed"
    )
    phase = add(material, dot, time_speed, -2000, y, f"wave {row} phase")

    sine = make_expression(material, unreal.MaterialExpressionSine, -1800, y - 45)
    cosine = make_expression(material, unreal.MaterialExpressionCosine, -1800, y + 65)
    set_property(sine, "period", 1.0, required=False)
    set_property(cosine, "period", 1.0, required=False)
    connect(phase, sine, ("Input", ""), f"wave {row} sine")
    connect(phase, cosine, ("Input", ""), f"wave {row} cosine")

    scaled_amplitude = multiply(
        material, sea_state, scalar(material, amplitude, -1800, y + 170),
        -1600, y + 170, f"wave {row} amplitude"
    )
    height = multiply(material, sine, scaled_amplitude, -1400, y - 40, f"wave {row} height")
    cosine_amplitude = multiply(
        material, cosine, scaled_amplitude, -1400, y + 70, f"wave {row} cosine amplitude"
    )
    tau_slope = multiply(
        material, cosine_amplitude, scalar(material, math.tau, -1400, y + 175),
        -1200, y + 70, f"wave {row} slope"
    )
    dx = multiply(
        material, tau_slope, scalar(material, inv_x, -1200, y + 150),
        -1000, y + 40, f"wave {row} dX"
    )
    dy = multiply(
        material, tau_slope, scalar(material, inv_y, -1200, y + 225),
        -1000, y + 120, f"wave {row} dY"
    )
    return height, dx, dy


def get_or_create_material():
    unreal.EditorAssetLibrary.make_directory(PACKAGE)
    unreal.EditorAssetLibrary.make_directory(BACKUP_PACKAGE)
    material = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if isinstance(material, unreal.Material):
        if not unreal.EditorAssetLibrary.does_asset_exist(BACKUP_PATH):
            if unreal.EditorAssetLibrary.duplicate_asset(ASSET_PATH, BACKUP_PATH):
                log(f"Backed up the previous ocean material to {BACKUP_PATH}")
            else:
                log("Warning: the optional material backup could not be created")
        unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
        return material

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        NAME, PACKAGE, unreal.Material, unreal.MaterialFactoryNew()
    )
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"Could not create {ASSET_PATH}")
    return material


def build_material():
    material = get_or_create_material()
    single_layer_water_model = resolve_enum_value(
        unreal.MaterialShadingModel,
        (
            "MSM_SINGLE_LAYER_WATER",
            "MSM_SINGLELAYER_WATER",
            "MSM_SINGLELAYERWATER",
            "SINGLE_LAYER_WATER",
            "SINGLELAYERWATER",
        ),
        ("SINGLE", "LAYER", "WATER"),
    )
    set_property(material, "shading_model", single_layer_water_model)
    set_property(material, "blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    set_property(material, "two_sided", True)
    set_property(material, "tangent_space_normal", False)
    set_property(material, "used_with_water", True, required=False)

    world_position = make_expression(material, unreal.MaterialExpressionWorldPosition, -3000, -100)
    world_xy = make_expression(material, unreal.MaterialExpressionComponentMask, -2800, -100)
    set_property(world_xy, "r", True)
    set_property(world_xy, "g", True)
    connect(world_position, world_xy, ("Input", ""), "absolute world position XY")
    game_time = make_expression(material, unreal.MaterialExpressionTime, -2800, 50)
    sea_state = scalar_parameter(material, "SeaState", 0.68, -2800, 190)

    # Wavelength and amplitude are centimetres; speed is cycles per second.
    wave_specs = (
        (160000.0, 240.0, 0.018, 0.94, 0.34),
        (62000.0, 92.0, 0.032, -0.24, 0.97),
        (22000.0, 31.0, 0.070, 0.72, -0.69),
        (6800.0, 8.5, 0.150, -0.87, -0.50),
        (1400.0, 1.4, 0.340, 0.43, 0.90),
    )
    wave_results = [
        make_wave(material, world_xy, game_time, sea_state, spec, index)
        for index, spec in enumerate(wave_specs)
    ]
    height = sum_nodes(material, [result[0] for result in wave_results], -700, -900, "height sum")
    slope_x = sum_nodes(material, [result[1] for result in wave_results], -700, -300, "slope X sum")
    slope_y = sum_nodes(material, [result[2] for result in wave_results], -700, 40, "slope Y sum")

    zero_xy = constant2(material, (0.0, 0.0), 100, -950)
    world_offset = append(material, zero_xy, height, 320, -900, "world position offset")
    output(material, world_offset, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET, "wave displacement")

    minus_one = scalar(material, -1.0, 80, -360)
    negative_x = multiply(material, slope_x, minus_one, 270, -330, "negative slope X")
    negative_y = multiply(material, slope_y, minus_one, 270, -210, "negative slope Y")
    normal_xy = append(material, negative_x, negative_y, 480, -280, "normal XY")
    normal_xyz = append(material, normal_xy, scalar(material, 1.0, 480, -130), 690, -250, "normal XYZ")
    normal = make_expression(material, unreal.MaterialExpressionNormalize, 900, -250)
    connect(normal_xyz, normal, ("VectorInput", "Input", ""), "normalized analytical water normal")
    output(material, normal, unreal.MaterialProperty.MP_NORMAL, "world-space wave normal")

    foam_bias = add(
        material,
        multiply(material, height, scalar(material, 0.006, 80, 230), 280, 210, "crest scale"),
        scalar(material, 0.18, 80, 310), 480, 220, "crest bias"
    )
    crest = make_expression(material, unreal.MaterialExpressionSaturate, 680, 220)
    connect(foam_bias, crest, ("Input", ""), "crest saturation")
    foam_power = make_expression(material, unreal.MaterialExpressionPower, 880, 220)
    connect(crest, foam_power, ("Base", "Input", ""), "foam power base")
    connect(scalar(material, 3.2, 680, 340), foam_power, ("Exp", "Exponent"), "foam power exponent")
    foam_amount = scalar_parameter(material, "FoamAmount", 0.18, 880, 350)
    foam_mask = multiply(material, foam_power, foam_amount, 1080, 240, "weather foam")

    deep = vector_parameter(material, "DeepWaterColor", (0.0015, 0.010, 0.022), 100, 500)
    horizon = vector_parameter(material, "HorizonWaterColor", (0.018, 0.125, 0.185), 100, 610)
    fresnel = make_expression(material, unreal.MaterialExpressionFresnel, 310, 570)
    water_color = make_expression(material, unreal.MaterialExpressionLinearInterpolate, 520, 550)
    connect(deep, water_color, "A", "deep water color")
    connect(horizon, water_color, "B", "horizon water color")
    connect(fresnel, water_color, "Alpha", "Fresnel water color")
    foam_color = vector_parameter(material, "FoamColor", (0.72, 0.80, 0.82), 720, 650)
    final_color = make_expression(material, unreal.MaterialExpressionLinearInterpolate, 1250, 540)
    connect(water_color, final_color, "A", "water base color")
    connect(foam_color, final_color, "B", "foam color")
    connect(foam_mask, final_color, "Alpha", "foam mask")
    output(material, final_color, unreal.MaterialProperty.MP_BASE_COLOR, "ocean base color")

    ocean_roughness = scalar_parameter(material, "OceanRoughness", 0.075, 1050, 720)
    foam_roughness = scalar(material, 0.52, 1050, 800)
    roughness = make_expression(material, unreal.MaterialExpressionLinearInterpolate, 1270, 760)
    connect(ocean_roughness, roughness, "A", "water roughness")
    connect(foam_roughness, roughness, "B", "foam roughness")
    connect(foam_mask, roughness, "Alpha", "roughness foam mask")
    output(material, roughness, unreal.MaterialProperty.MP_ROUGHNESS, "weather roughness")
    output(material, scalar(material, 0.255, 1280, 870), unreal.MaterialProperty.MP_SPECULAR, "water dielectric specular")
    output(material, scalar(material, 0.0, 1280, 940), unreal.MaterialProperty.MP_METALLIC, "non-metal water")
    output(material, scalar_parameter(material, "WaterOpacity", 0.72, 1280, 1010), unreal.MaterialProperty.MP_OPACITY, "water opacity")
    output(material, scalar(material, 1.333, 1280, 1080), unreal.MaterialProperty.MP_REFRACTION, "water IOR")

    single_layer = make_expression(
        material, unreal.MaterialExpressionSingleLayerWaterMaterialOutput, 1550, 300
    )
    scattering = vector_parameter(material, "ScatteringCoefficients", (0.0035, 0.012, 0.020), 1150, -10)
    absorption = vector_parameter(material, "AbsorptionCoefficients", (0.075, 0.028, 0.010), 1150, 70)
    phase_g = scalar_parameter(material, "PhaseG", 0.12, 1150, 150)
    behind = vector_parameter(material, "ColorScaleBehindWater", (0.46, 0.72, 0.88), 1150, 230)
    connect(scattering, single_layer, "ScatteringCoefficients", "water scattering coefficients")
    connect(absorption, single_layer, "AbsorptionCoefficients", "water absorption coefficients")
    connect(phase_g, single_layer, "PhaseG", "water phase anisotropy")
    connect(behind, single_layer, "ColorScaleBehindWater", "underwater scene color scale")

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {ASSET_PATH}")
    log("Extreme Single Layer Water ocean material installed successfully")
    return material


def main() -> None:
    try:
        build_material()
        unreal.EditorDialog.show_message(
            "Aether Extreme Water",
            "The physically based ocean was installed successfully.\n\n"
            "Wait for shaders to finish, Save All, then press Play.\n"
            "Press T in flight to compare calm, broken, storm, and blue-hour seas.",
            unreal.AppMsgType.OK,
        )
    except Exception as exc:
        unreal.log_error(f"[Aether Water] Installation failed: {exc}")
        raise


if __name__ == "__main__":
    main()
