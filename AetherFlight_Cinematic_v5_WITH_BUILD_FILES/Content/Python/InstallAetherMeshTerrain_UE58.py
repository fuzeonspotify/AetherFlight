"""Install Aether Flight's UE 5.8 Mesh Terrain authoring assets.

This is deliberately a safe, non-destructive bootstrap.  It enables an
automatic triplanar material, creates the Mesh Partition Definition and the
three transformer-pipeline shells, and imports the existing biome weightmaps.
It does not hide the working Landscape.  The Landscape is retired only by
FinalizeAetherMeshTerrainMigration_UE58.py after the Mesh Partition has been
created and its runtime sections have been built.

The transformer arrays are TInstancedStruct arrays.  Unreal's Python bridge
cannot author those arrays reliably, so the small pipeline stack is completed
once in the Details panel as documented in MESH_TERRAIN_UE58_SETUP.md.
"""

from pathlib import Path

import unreal


LOG_PREFIX = "[Aether Mesh Terrain Installer]"
PACKAGE = "/Game/Aether/MeshTerrain"
MATERIAL_NAME = "M_MeshTerrain_Aether"
DEFINITION_NAME = "MPD_AetherWorld"
PIPELINE_NAMES = (
    "TP_Preview_AetherWorld",
    "TP_Compiled_HighEnd_AetherWorld",
    "TP_Compiled_Common_AetherWorld",
)
TEXTURE_PACKAGE = "/Game/Aether/ProductionTerrain/Textures"
WEIGHT_PACKAGE = f"{PACKAGE}/Weightmaps"
LAYERS = ("Grass", "ForestFloor", "Rock", "Scree", "Snow", "Sand", "Wetland")
CHANNELS = LAYERS + ("Water", "Forest", "FoliageExclusion")
PRIORITY_LAYERS = ("Base", "Erosion", "Hydrology", "LocalDetail", "Paint")
PROJECT_DIR = Path(unreal.Paths.project_dir())
WEIGHT_SOURCE = PROJECT_DIR / "SourceAssets" / "ProductionTerrain" / "Weightmaps"

LAYER_TILE_CM = {
    "Grass": 3800.0,
    "ForestFloor": 4600.0,
    "Rock": 6200.0,
    "Scree": 3200.0,
    "Snow": 8500.0,
    "Sand": 5400.0,
    "Wetland": 4100.0,
}


def log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def warn(message):
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def expression(material, expression_class, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, expression_class, x, y
    )
    if node is None:
        raise RuntimeError(f"Could not create material node {expression_class}")
    return node


def connect(source, source_output, target, target_input, description):
    """Connect material pins across UE Python API naming differences.

    UE 5.8 exposes the sole input on several unary material expressions as an
    unnamed pin even though earlier builds accepted ``Input``.  ComponentMask,
    Abs, Saturate and OneMinus are all used by this graph, so handling the
    alias centrally prevents the installer from failing one node at a time.
    """
    source_outputs = (
        tuple(source_output)
        if isinstance(source_output, (tuple, list))
        else (source_output,)
    )
    target_inputs = (
        list(target_input)
        if isinstance(target_input, (tuple, list))
        else [target_input]
    )
    if target_input == "Input" and "" not in target_inputs:
        target_inputs.append("")

    attempted = []
    for output_name in source_outputs:
        for input_name in target_inputs:
            attempted.append((output_name, input_name))
            try:
                connected = unreal.MaterialEditingLibrary.connect_material_expressions(
                    source, output_name, target, input_name
                )
                if connected:
                    return
            except Exception:
                pass

    raise RuntimeError(
        f"Could not connect {description}; tried pin pairs {tuple(attempted)}"
    )


def constant(material, value, x=0, y=0):
    node = expression(material, unreal.MaterialExpressionConstant, x, y)
    node.set_editor_property("r", float(value))
    return node


def constant2(material, x_value, y_value, x=0, y=0):
    node = expression(material, unreal.MaterialExpressionConstant2Vector, x, y)
    node.set_editor_property("r", float(x_value))
    node.set_editor_property("g", float(y_value))
    return node


def binary(material, expression_class, a, a_output, b, b_output, x=0, y=0):
    node = expression(material, expression_class, x, y)
    node_name = getattr(expression_class, "__name__", str(expression_class))
    connect(a, a_output, node, "A", f"{node_name} A")
    connect(b, b_output, node, "B", f"{node_name} B")
    return node


def add(material, a, a_output, b, b_output, x=0, y=0):
    return binary(material, unreal.MaterialExpressionAdd, a, a_output, b, b_output, x, y)


def subtract(material, a, a_output, b, b_output, x=0, y=0):
    return binary(material, unreal.MaterialExpressionSubtract, a, a_output, b, b_output, x, y)


def multiply(material, a, a_output, b, b_output, x=0, y=0):
    return binary(material, unreal.MaterialExpressionMultiply, a, a_output, b, b_output, x, y)


def divide(material, a, a_output, b, b_output, x=0, y=0):
    return binary(material, unreal.MaterialExpressionDivide, a, a_output, b, b_output, x, y)


def maximum(material, a, a_output, b, b_output, x=0, y=0):
    return binary(material, unreal.MaterialExpressionMax, a, a_output, b, b_output, x, y)


def lerp(material, a, a_output, b, b_output, alpha, alpha_output="", x=0, y=0):
    node = expression(material, unreal.MaterialExpressionLinearInterpolate, x, y)
    connect(a, a_output, node, "A", "Lerp A")
    connect(b, b_output, node, "B", "Lerp B")
    connect(alpha, alpha_output, node, "Alpha", "Lerp Alpha")
    return node


def saturate(material, source, output="", x=0, y=0):
    node = expression(material, unreal.MaterialExpressionSaturate, x, y)
    connect(source, output, node, "Input", "Saturate Input")
    return node


def one_minus(material, source, output="", x=0, y=0):
    node = expression(material, unreal.MaterialExpressionOneMinus, x, y)
    connect(source, output, node, "Input", "OneMinus Input")
    return node


def mask(material, source, r=False, g=False, b=False, a=False, x=0, y=0):
    node = expression(material, unreal.MaterialExpressionComponentMask, x, y)
    node.set_editor_property("r", r)
    node.set_editor_property("g", g)
    node.set_editor_property("b", b)
    node.set_editor_property("a", a)
    connect(source, "", node, "Input", "ComponentMask Input")
    return node


def range_mask(material, value, minimum, maximum_value, x=0, y=0, value_output=""):
    minimum_node = constant(material, minimum, x - 360, y + 80)
    span_node = constant(material, maximum_value - minimum, x - 360, y + 160)
    shifted = subtract(material, value, value_output, minimum_node, "", x - 170, y)
    normalized = divide(material, shifted, "", span_node, "", x, y)
    return saturate(material, normalized, "", x + 170, y)


def load_texture(name):
    path = f"{TEXTURE_PACKAGE}/{name}.{name}"
    texture = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError(
            f"Missing {path}. Run InstallProductionLandscape.py before this installer."
        )
    return texture


def create_or_load_material():
    unreal.EditorAssetLibrary.make_directory(PACKAGE)
    path = f"{PACKAGE}/{MATERIAL_NAME}.{MATERIAL_NAME}"
    material = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(material, unreal.Material):
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            MATERIAL_NAME, PACKAGE, unreal.Material, unreal.MaterialFactoryNew()
        )
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"Could not create {path}")
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    material.set_editor_property("two_sided", False)
    # No tangent-space normal is authored here.  The Mesh Terrain/Nanite
    # geometry supplies the true surface normal, including cliffs/overhangs.
    material.set_editor_property("tangent_space_normal", False)
    return material


def build_projection_basis(material):
    world_position = expression(material, unreal.MaterialExpressionWorldPosition, -2800, -900)
    xy = mask(material, world_position, r=True, g=True, x=-2600, y=-1040)
    xz = mask(material, world_position, r=True, b=True, x=-2600, y=-900)
    yz = mask(material, world_position, g=True, b=True, x=-2600, y=-760)

    pixel_normal = expression(material, unreal.MaterialExpressionPixelNormalWS, -2800, -500)
    abs_normal = expression(material, unreal.MaterialExpressionAbs, -2600, -500)
    connect(pixel_normal, "", abs_normal, "Input", "absolute world normal")
    nx = mask(material, abs_normal, r=True, x=-2400, y=-610)
    ny = mask(material, abs_normal, g=True, x=-2400, y=-500)
    nz = mask(material, abs_normal, b=True, x=-2400, y=-390)

    # Fourth-power weights keep cliff/top transitions crisp without seams.
    nx2 = multiply(material, nx, "", nx, "", -2210, -610)
    ny2 = multiply(material, ny, "", ny, "", -2210, -500)
    nz2 = multiply(material, nz, "", nz, "", -2210, -390)
    nx4 = multiply(material, nx2, "", nx2, "", -2020, -610)
    ny4 = multiply(material, ny2, "", ny2, "", -2020, -500)
    nz4 = multiply(material, nz2, "", nz2, "", -2020, -390)
    sum_xy = add(material, nx4, "", ny4, "", -1840, -550)
    sum_xyz = add(material, sum_xy, "", nz4, "", -1660, -500)
    epsilon = constant(material, 0.0001, -1840, -350)
    denominator = add(material, sum_xyz, "", epsilon, "", -1480, -500)
    wx = divide(material, nx4, "", denominator, "", -1290, -610)
    wy = divide(material, ny4, "", denominator, "", -1290, -500)
    wz = divide(material, nz4, "", denominator, "", -1290, -390)
    return world_position, (xy, xz, yz), (wx, wy, wz), nz


def scaled_uv(material, plane, scale_cm, x, y):
    divisor = constant2(material, scale_cm, scale_cm, x, y + 90)
    return divide(material, plane, "", divisor, "", x + 180, y)


def color_sample(material, texture, parameter_name, uv, x, y):
    sample = expression(material, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    sample.set_editor_property("parameter_name", parameter_name)
    sample.set_editor_property("texture", texture)
    sample.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
    connect(uv, "", sample, "UVs", f"UVs for {parameter_name}")
    return sample


def triplanar_color(material, layer_name, planes, weights, index):
    texture = load_texture(f"T_{layer_name}_BaseColor")
    scale_cm = LAYER_TILE_CM[layer_name]
    base_x = -900 + index * 520
    uv_yz = scaled_uv(material, planes[2], scale_cm, base_x, -1500)
    uv_xz = scaled_uv(material, planes[1], scale_cm, base_x, -1280)
    uv_xy = scaled_uv(material, planes[0], scale_cm, base_x, -1060)
    sample_yz = color_sample(material, texture, f"{layer_name}_TriX", uv_yz, base_x + 210, -1500)
    sample_xz = color_sample(material, texture, f"{layer_name}_TriY", uv_xz, base_x + 210, -1280)
    sample_xy = color_sample(material, texture, f"{layer_name}_TriZ", uv_xy, base_x + 210, -1060)
    weighted_x = multiply(material, sample_yz, "RGB", weights[0], "", base_x + 390, -1500)
    weighted_y = multiply(material, sample_xz, "RGB", weights[1], "", base_x + 390, -1280)
    weighted_z = multiply(material, sample_xy, "RGB", weights[2], "", base_x + 390, -1060)
    xy_sum = add(material, weighted_x, "", weighted_y, "", base_x + 570, -1390)
    return add(material, xy_sum, "", weighted_z, "", base_x + 750, -1240)


def build_material():
    material = create_or_load_material()
    world_position, planes, weights, normal_z = build_projection_basis(material)
    colors = {
        layer: triplanar_color(material, layer, planes, weights, index)
        for index, layer in enumerate(LAYERS)
    }

    height = mask(material, world_position, b=True, x=-1000, y=-500)
    abs_normal_z = normal_z
    slope = one_minus(material, abs_normal_z, "", -760, -390)

    shore_to_grass = range_mask(material, height, 0.0, 28000.0, -460, -900)
    low_color = lerp(material, colors["Sand"], "", colors["Grass"], "", shore_to_grass, x=-220, y=-900)

    macro_uv = scaled_uv(material, planes[0], 185000.0, -850, 120)
    macro_texture = load_texture("T_MacroVariation")
    macro = expression(material, unreal.MaterialExpressionTextureSampleParameter2D, -610, 120)
    macro.set_editor_property("parameter_name", "TerrainMacroVariation")
    macro.set_editor_property("texture", macro_texture)
    macro.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    connect(macro_uv, "", macro, "UVs", "macro variation UVs")
    macro_forest = range_mask(material, macro, 0.34, 0.70, -310, -120, "R")
    forest_strength = constant(material, 0.72, -310, 40)
    forest_mask = multiply(material, macro_forest, "", forest_strength, "", -100, -120)
    mid_color = lerp(material, colors["Grass"], "", colors["ForestFloor"], "", forest_mask, x=120, y=-120)

    low_altitude = one_minus(material, range_mask(material, height, 2500.0, 24000.0, -350, 340), x=-100, y=340)
    macro_wet = range_mask(material, macro, 0.52, 0.78, -350, 520, "R")
    wetland_mask = multiply(material, low_altitude, "", macro_wet, "", -100, 450)
    low_wet_color = lerp(material, low_color, "", colors["Wetland"], "", wetland_mask, x=120, y=430)
    inland_mask = range_mask(material, height, 6000.0, 36000.0, 330, 240)
    vegetated_color = lerp(material, low_wet_color, "", mid_color, "", inland_mask, x=560, y=160)

    steep_mask = range_mask(material, slope, 0.075, 0.36, 520, -520)
    very_steep_mask = range_mask(material, slope, 0.24, 0.60, 520, -340)
    rock_color = lerp(material, colors["Scree"], "", colors["Rock"], "", very_steep_mask, x=760, y=-390)
    high_altitude_rock = range_mask(material, height, 90000.0, 165000.0, 520, -690)
    high_strength = constant(material, 0.58, 760, -730)
    high_rock_mask = multiply(material, high_altitude_rock, "", high_strength, "", 950, -690)
    combined_rock_mask = maximum(material, steep_mask, "", high_rock_mask, "", 1140, -520)
    rocky_color = lerp(material, vegetated_color, "", rock_color, "", combined_rock_mask, x=1360, y=-300)

    snow_altitude = range_mask(material, height, 145000.0, 205000.0, 1120, 120)
    snow_slope = range_mask(material, slope, 0.22, 0.62, 1120, 300)
    snow_slope_penalty = one_minus(material, snow_slope, "", 1370, 300)
    snow_mask = multiply(material, snow_altitude, "", snow_slope_penalty, "", 1570, 180)
    biome_color = lerp(material, rocky_color, "", colors["Snow"], "", snow_mask, x=1800, y=-120)

    macro_strength_node = constant(material, 0.24, 1420, -760)
    macro_floor = constant(material, 0.82, 1420, -650)
    macro_scaled = multiply(material, macro, "R", macro_strength_node, "", 1630, -730)
    macro_factor = add(material, macro_scaled, "", macro_floor, "", 1810, -680)
    final_color = multiply(material, biome_color, "", macro_factor, "", 2020, -120)

    # Match roughness to the same physically motivated biome masks.
    rough_sand = constant(material, 0.78, 750, 600)
    rough_grass = constant(material, 0.86, 750, 680)
    rough_forest = constant(material, 0.91, 750, 760)
    rough_wet = constant(material, 0.94, 750, 840)
    rough_scree = constant(material, 0.90, 750, 920)
    rough_rock = constant(material, 0.72, 750, 1000)
    rough_snow = constant(material, 0.64, 750, 1080)
    rough_low = lerp(material, rough_sand, "", rough_grass, "", shore_to_grass, x=980, y=650)
    rough_low_wet = lerp(material, rough_low, "", rough_wet, "", wetland_mask, x=1180, y=700)
    rough_mid = lerp(material, rough_grass, "", rough_forest, "", forest_mask, x=980, y=820)
    rough_vegetated = lerp(material, rough_low_wet, "", rough_mid, "", inland_mask, x=1390, y=760)
    rough_rock_mix = lerp(material, rough_scree, "", rough_rock, "", very_steep_mask, x=1180, y=980)
    rough_terrain = lerp(material, rough_vegetated, "", rough_rock_mix, "", combined_rock_mask, x=1600, y=850)
    rough_final = lerp(material, rough_terrain, "", rough_snow, "", snow_mask, x=1830, y=920)

    unreal.MaterialEditingLibrary.connect_material_property(
        final_color, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        rough_final, "", unreal.MaterialProperty.MP_ROUGHNESS
    )
    specular = constant(material, 0.20, 2050, 720)
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )
    ao = constant(material, 1.0, 2050, 820)
    unreal.MaterialEditingLibrary.connect_material_property(
        ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"Built {material.get_path_name()} with automatic triplanar biome blending")
    return material


def data_asset_class(*candidate_names):
    for name in candidate_names:
        cls = getattr(unreal, name, None)
        if cls is not None:
            return cls
    return None


def create_data_asset(asset_name, asset_class):
    path = f"{PACKAGE}/{asset_name}.{asset_name}"
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is not None:
        return asset
    factory = unreal.DataAssetFactory()
    try:
        factory.set_editor_property("data_asset_class", asset_class)
    except Exception:
        pass
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, PACKAGE, asset_class, factory
    )
    if asset is None:
        raise RuntimeError(f"Could not create {path}")
    return asset


def configure_channels(definition):
    channel_desc_class = data_asset_class("ChannelDesc")
    if channel_desc_class is None:
        warn("ChannelDesc is not exposed to Python; add the documented channels in the MPD Details panel.")
        return False
    try:
        channel_map = definition.get_editor_property("channel_map")
        descriptions = []
        for channel_name in CHANNELS:
            description = channel_desc_class()
            description.set_editor_property("name", unreal.Name(channel_name))
            descriptions.append(description)
        channel_map.set_editor_property("channel_descs", descriptions)
        definition.set_editor_property("channel_map", channel_map)
        return True
    except Exception as exc:
        warn(f"Could not author channel map through Python ({exc}); add the documented channels manually.")
        return False


def configure_definition(material):
    definition_class = data_asset_class("MeshPartitionDefinition")
    if definition_class is None:
        raise RuntimeError(
            "MeshPartitionDefinition is unavailable. Enable the four Mesh Terrain plugins and restart Unreal Editor."
        )
    definition = create_data_asset(DEFINITION_NAME, definition_class)
    definition.set_editor_property("material", material)
    definition.set_editor_property("channel_texel_size", 400.0)
    definition.set_editor_property("material_cache_texel_size", 800.0)
    definition.set_editor_property(
        "modifier_type_priorities", [unreal.Name(name) for name in PRIORITY_LAYERS]
    )
    channels_ready = configure_channels(definition)

    # Plane projection is stable for the imported heightfield and avoids the
    # section seam artifact seen with the default fast box projection.  The
    # material itself is triplanar, so cliffs and later overhangs still shade
    # without stretching.
    enum_class = data_asset_class("ChannelCollectionUVLayoutMethod")
    if enum_class is not None:
        for attribute_name in dir(enum_class):
            if "PLANE" in attribute_name.upper() and "PROJECT" in attribute_name.upper():
                try:
                    definition.set_editor_property(
                        "channel_uv_layout_method", getattr(enum_class, attribute_name)
                    )
                    break
                except Exception:
                    pass

    definition.modify()
    unreal.EditorAssetLibrary.save_loaded_asset(definition, only_if_is_dirty=False)
    log(f"Configured {definition.get_path_name()}")
    return definition, channels_ready


def create_pipeline_shells():
    pipeline_class = data_asset_class("TransformerPipeline")
    if pipeline_class is None:
        raise RuntimeError(
            "TransformerPipeline is unavailable. Enable MeshPartition and restart Unreal Editor."
        )
    assets = []
    for asset_name in PIPELINE_NAMES:
        asset = create_data_asset(asset_name, pipeline_class)
        unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
        assets.append(asset)
        log(f"Ready: {asset.get_path_name()}")
    return assets


def import_weightmaps():
    if not WEIGHT_SOURCE.is_dir():
        warn(f"Weightmap source folder is missing: {WEIGHT_SOURCE}")
        return 0
    unreal.EditorAssetLibrary.make_directory(WEIGHT_PACKAGE)
    tasks = []
    expected_names = []
    for layer_name in LAYERS:
        source = WEIGHT_SOURCE / f"AetherFlight_{layer_name}_4033.png"
        if not source.is_file():
            warn(f"Missing weightmap: {source.name}")
            continue
        asset_name = f"T_MT_{layer_name}_Weight"
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(source))
        task.set_editor_property("destination_path", WEIGHT_PACKAGE)
        task.set_editor_property("destination_name", asset_name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        tasks.append(task)
        expected_names.append(asset_name)
    if tasks:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    imported = 0
    for asset_name in expected_names:
        texture = unreal.EditorAssetLibrary.load_asset(
            f"{WEIGHT_PACKAGE}/{asset_name}.{asset_name}"
        )
        if not isinstance(texture, unreal.Texture2D):
            continue
        texture.set_editor_property("srgb", False)
        texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_MASKS
        )
        texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
        texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
        texture.modify()
        unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False)
        imported += 1
    log(f"Imported {imported} Mesh Terrain biome weightmaps")
    return imported


def plugin_preflight():
    required_types = ("MeshPartitionDefinition", "TransformerPipeline")
    missing = [name for name in required_types if getattr(unreal, name, None) is None]
    if missing:
        raise RuntimeError(
            "Mesh Terrain classes are not loaded: "
            + ", ".join(missing)
            + ". Close Unreal, rebuild once after pulling, then reopen the project."
        )


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before installing Mesh Terrain assets.")
    except AttributeError:
        pass

    plugin_preflight()
    unreal.EditorAssetLibrary.make_directory(PACKAGE)
    material = build_material()
    definition, channels_ready = configure_definition(material)
    create_pipeline_shells()
    weight_count = import_weightmaps()
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)

    channel_status = "created" if channels_ready else "listed in the setup guide for one-time entry"
    message = (
        "Aether Mesh Terrain authoring assets are installed.\n\n"
        f"Material: {material.get_path_name()}\n"
        f"Definition: {definition.get_path_name()}\n"
        f"Weightmaps imported: {weight_count}/7\n"
        f"Weight channels: {channel_status}\n\n"
        "The working Landscape has NOT been hidden.\n"
        "Next, follow MESH_TERRAIN_UE58_SETUP.md from Step 3 to fill the three "
        "pipeline shells and import AetherFlight_4033.r16."
    )
    unreal.EditorDialog.show_message(
        "Aether UE5.8 Mesh Terrain", message, unreal.AppMsgType.OK
    )


if __name__ == "__main__":
    main()
