"""Build and activate Aether's deterministic biome material with matched normals.

This pass uses the known-good Aether-owned Mesh Terrain material as its base.
That material already separates sand/grass/wetland/forest/scree/rock/snow from
world height, world-space slope, and macro variation. This script duplicates it,
adds a matching world-space normal graph, verifies the result, and assigns the
duplicate to MPD_AetherWorld only after the material saves successfully.

The currently active Sensei surface instance is preserved as rollback.
Terrain geometry, collision, Mesh Partition resolution, channels, and streaming
settings are not changed.
"""

from pathlib import Path
import importlib.util

import unreal


LOG_PREFIX = "[Aether Biome Distribution]"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
SOURCE_PACKAGE = "/Game/Aether/MeshTerrain/M_MeshTerrain_Aether"
SOURCE_PATH = SOURCE_PACKAGE + ".M_MeshTerrain_Aether"
TARGET_PACKAGE = "/Game/Aether/MeshTerrain/M_MeshTerrain_Aether_Biomes"
TARGET_PATH = TARGET_PACKAGE + ".M_MeshTerrain_Aether_Biomes"
SENSEI_ROLLBACK_PATH = (
    "/Game/Aether/MeshTerrain/"
    "MI_AetherTerrain_Sensei_Surface.MI_AetherTerrain_Sensei_Surface"
)
TEXTURE_PACKAGE = "/Game/Aether/ProductionTerrain/Textures"
MARKER_PARAMETER = "Aether Biome Normal Strength"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherBiomeDistributionReport.txt"
HELPER_PATH = Path(
    unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir()
        + "Python/InstallAetherMeshTerrain_UE58.py"
    )
)


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def asset_path(value) -> str:
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def load_helpers():
    if not HELPER_PATH.is_file():
        raise RuntimeError(f"Missing material helper script: {HELPER_PATH}")
    spec = importlib.util.spec_from_file_location(
        "aether_biome_material_helpers", str(HELPER_PATH)
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load material helpers: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_texture(name: str):
    path = f"{TEXTURE_PACKAGE}/{name}.{name}"
    texture = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError(f"Missing terrain texture: {path}")
    return texture


def normalize(base, material, source, output="", x=0, y=0):
    normalize_class = getattr(unreal, "MaterialExpressionNormalize", None)
    if normalize_class is None:
        raise RuntimeError("MaterialExpressionNormalize is unavailable in this UE build")
    node = base.expression(material, normalize_class, x, y)
    base.connect(source, output, node, "Input", "Normalize Input")
    return node


def append(base, material, a, a_output, b, b_output, x=0, y=0):
    node = base.expression(material, unreal.MaterialExpressionAppendVector, x, y)
    base.connect(a, a_output, node, "A", "Append A")
    base.connect(b, b_output, node, "B", "Append B")
    return node


def append3(
    base,
    material,
    x_node,
    x_output,
    y_node,
    y_output,
    z_node,
    z_output,
    x=0,
    y=0,
):
    xy = append(base, material, x_node, x_output, y_node, y_output, x, y)
    return append(base, material, xy, "", z_node, z_output, x + 170, y)


def scalar_parameter(base, material, name: str, default_value: float, x=0, y=0):
    node = base.expression(material, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", float(default_value))
    try:
        node.set_editor_property("slider_min", 0.0)
        node.set_editor_property("slider_max", 1.0)
    except Exception:
        pass
    return node


def normal_sample(base, material, texture_name: str, parameter_name: str, uv, x, y):
    sample = base.expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, x, y
    )
    sample.set_editor_property("parameter_name", parameter_name)
    sample.set_editor_property("texture", load_texture(texture_name))
    sample.set_editor_property(
        "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
    )
    try:
        sample.set_editor_property(
            "sampler_source",
            unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS,
        )
    except Exception:
        pass
    base.connect(uv, "", sample, "UVs", f"UVs for {parameter_name}")
    return sample


def build_vertex_projection(base, material):
    vertex_normal_class = getattr(unreal, "MaterialExpressionVertexNormalWS", None)
    if vertex_normal_class is None:
        raise RuntimeError("MaterialExpressionVertexNormalWS is unavailable")

    vertex_normal = base.expression(material, vertex_normal_class, -3300, 1000)
    abs_normal = base.expression(material, unreal.MaterialExpressionAbs, -3110, 1000)
    base.connect(vertex_normal, "", abs_normal, "Input", "absolute vertex normal")

    raw_x = base.mask(material, vertex_normal, r=True, x=-3100, y=720)
    raw_y = base.mask(material, vertex_normal, g=True, x=-3100, y=830)
    raw_z = base.mask(material, vertex_normal, b=True, x=-3100, y=940)
    abs_x = base.mask(material, abs_normal, r=True, x=-2900, y=720)
    abs_y = base.mask(material, abs_normal, g=True, x=-2900, y=830)
    abs_z = base.mask(material, abs_normal, b=True, x=-2900, y=940)

    x2 = base.multiply(material, abs_x, "", abs_x, "", -2710, 720)
    y2 = base.multiply(material, abs_y, "", abs_y, "", -2710, 830)
    z2 = base.multiply(material, abs_z, "", abs_z, "", -2710, 940)
    x4 = base.multiply(material, x2, "", x2, "", -2520, 720)
    y4 = base.multiply(material, y2, "", y2, "", -2520, 830)
    z4 = base.multiply(material, z2, "", z2, "", -2520, 940)
    sum_xy = base.add(material, x4, "", y4, "", -2330, 780)
    sum_xyz = base.add(material, sum_xy, "", z4, "", -2140, 840)
    epsilon = base.constant(material, 0.0001, -2330, 1030)
    denominator = base.add(material, sum_xyz, "", epsilon, "", -1950, 840)
    weight_x = base.divide(material, x4, "", denominator, "", -1760, 720)
    weight_y = base.divide(material, y4, "", denominator, "", -1760, 830)
    weight_z = base.divide(material, z4, "", denominator, "", -1760, 940)

    sign_epsilon = base.constant(material, 0.001, -2710, 1140)
    denom_x = base.maximum(material, abs_x, "", sign_epsilon, "", -2520, 1110)
    denom_y = base.maximum(material, abs_y, "", sign_epsilon, "", -2520, 1220)
    denom_z = base.maximum(material, abs_z, "", sign_epsilon, "", -2520, 1330)
    sign_x = base.divide(material, raw_x, "", denom_x, "", -2330, 1110)
    sign_y = base.divide(material, raw_y, "", denom_y, "", -2330, 1220)
    sign_z = base.divide(material, raw_z, "", denom_z, "", -2330, 1330)

    return (
        vertex_normal,
        (weight_x, weight_y, weight_z),
        (sign_x, sign_y, sign_z),
        abs_z,
    )


def reorient_x(base, material, sample, sign_x, x, y):
    world_x = base.multiply(material, sample, "B", sign_x, "", x, y)
    return append3(
        base, material, world_x, "", sample, "R", sample, "G", x + 170, y
    )


def reorient_y(base, material, sample, sign_y, x, y):
    world_y = base.multiply(material, sample, "B", sign_y, "", x, y)
    return append3(
        base, material, sample, "R", world_y, "", sample, "G", x + 170, y
    )


def reorient_z(base, material, sample, sign_z, x, y):
    world_z = base.multiply(material, sample, "B", sign_z, "", x, y)
    return append3(
        base, material, sample, "R", sample, "G", world_z, "", x + 170, y
    )


def triplanar_normal(
    base,
    material,
    layer_name: str,
    planes,
    weights,
    signs,
    index: int,
):
    texture_name = f"T_{layer_name}_Normal"
    scale_cm = base.LAYER_TILE_CM[layer_name]
    x = -1200 + index * 900

    uv_yz = base.scaled_uv(material, planes[2], scale_cm, x, 1700)
    uv_xz = base.scaled_uv(material, planes[1], scale_cm, x, 1930)
    uv_xy = base.scaled_uv(material, planes[0], scale_cm, x, 2160)

    sample_x = normal_sample(
        base,
        material,
        texture_name,
        f"AetherBiomeNormal_{layer_name}_X",
        uv_yz,
        x + 210,
        1700,
    )
    sample_y = normal_sample(
        base,
        material,
        texture_name,
        f"AetherBiomeNormal_{layer_name}_Y",
        uv_xz,
        x + 210,
        1930,
    )
    sample_z = normal_sample(
        base,
        material,
        texture_name,
        f"AetherBiomeNormal_{layer_name}_Z",
        uv_xy,
        x + 210,
        2160,
    )

    world_x = reorient_x(base, material, sample_x, signs[0], x + 410, 1700)
    world_y = reorient_y(base, material, sample_y, signs[1], x + 410, 1930)
    world_z = reorient_z(base, material, sample_z, signs[2], x + 410, 2160)

    weighted_x = base.multiply(
        material, world_x, "", weights[0], "", x + 650, 1700
    )
    weighted_y = base.multiply(
        material, world_y, "", weights[1], "", x + 650, 1930
    )
    weighted_z = base.multiply(
        material, world_z, "", weights[2], "", x + 650, 2160
    )
    sum_xy = base.add(material, weighted_x, "", weighted_y, "", x + 850, 1815)
    total = base.add(material, sum_xy, "", weighted_z, "", x + 1030, 1930)
    return normalize(base, material, total, "", x + 1210, 1930)


def planar_normal(base, material, layer_name: str, xy_plane, sign_z, x, y):
    uv = base.scaled_uv(
        material, xy_plane, base.LAYER_TILE_CM[layer_name], x, y
    )
    sample = normal_sample(
        base,
        material,
        f"T_{layer_name}_Normal",
        f"AetherBiomeNormal_{layer_name}_Planar",
        uv,
        x + 210,
        y,
    )
    world = reorient_z(base, material, sample, sign_z, x + 430, y)
    return normalize(base, material, world, "", x + 650, y)


def build_biome_normal_graph(base, material):
    world_position = base.expression(
        material, unreal.MaterialExpressionWorldPosition, -3300, 1530
    )
    xy = base.mask(material, world_position, r=True, g=True, x=-3100, y=1530)
    xz = base.mask(material, world_position, r=True, b=True, x=-3100, y=1640)
    yz = base.mask(material, world_position, g=True, b=True, x=-3100, y=1750)
    height = base.mask(material, world_position, b=True, x=-3100, y=1860)

    vertex_normal, weights, signs, abs_z = build_vertex_projection(base, material)
    slope = base.one_minus(material, abs_z, "", -1450, 1080)

    grass = planar_normal(base, material, "Grass", xy, signs[2], -1200, 2480)
    forest = planar_normal(
        base, material, "ForestFloor", xy, signs[2], -1200, 2700
    )
    snow = planar_normal(base, material, "Snow", xy, signs[2], -1200, 2920)
    scree = triplanar_normal(
        base, material, "Scree", (xy, xz, yz), weights, signs, 0
    )
    rock = triplanar_normal(
        base, material, "Rock", (xy, xz, yz), weights, signs, 1
    )

    shore_to_grass = base.range_mask(
        material, height, 0.0, 28000.0, 1320, 2500
    )
    low_normal = base.lerp(
        material,
        vertex_normal,
        "",
        grass,
        "",
        shore_to_grass,
        x=1700,
        y=2500,
    )

    macro_uv = base.scaled_uv(material, xy, 185000.0, 1320, 2720)
    macro = base.expression(
        material, unreal.MaterialExpressionTextureSampleParameter2D, 1530, 2720
    )
    macro.set_editor_property("parameter_name", "AetherBiomeMacroVariation")
    macro.set_editor_property("texture", load_texture("T_MacroVariation"))
    macro.set_editor_property(
        "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
    )
    base.connect(macro_uv, "", macro, "UVs", "biome macro variation UVs")

    macro_forest = base.range_mask(
        material, macro, 0.34, 0.70, 1760, 2700, "R"
    )
    forest_strength = base.constant(material, 0.72, 1760, 2860)
    forest_mask = base.multiply(
        material, macro_forest, "", forest_strength, "", 1970, 2740
    )
    mid_normal = base.lerp(
        material, grass, "", forest, "", forest_mask, x=2180, y=2700
    )

    low_altitude = base.one_minus(
        material,
        base.range_mask(material, height, 2500.0, 24000.0, 1760, 3060),
        "",
        1980,
        3060,
    )
    macro_wet = base.range_mask(
        material, macro, 0.52, 0.78, 1760, 3220, "R"
    )
    wetland_mask = base.multiply(
        material, low_altitude, "", macro_wet, "", 2190, 3140
    )
    low_wet_normal = base.lerp(
        material,
        low_normal,
        "",
        vertex_normal,
        "",
        wetland_mask,
        x=2410,
        y=3020,
    )
    inland_mask = base.range_mask(
        material, height, 6000.0, 36000.0, 2190, 3380
    )
    vegetated_normal = base.lerp(
        material,
        low_wet_normal,
        "",
        mid_normal,
        "",
        inland_mask,
        x=2630,
        y=2860,
    )

    steep_mask = base.range_mask(material, slope, 0.075, 0.36, 1550, 1500)
    very_steep = base.range_mask(material, slope, 0.24, 0.60, 1550, 1690)
    cliff = base.lerp(
        material, scree, "", rock, "", very_steep, x=1920, y=1760
    )
    high_altitude_rock = base.range_mask(
        material, height, 90000.0, 165000.0, 1900, 1440
    )
    high_strength = base.constant(material, 0.58, 2140, 1440)
    high_rock_mask = base.multiply(
        material,
        high_altitude_rock,
        "",
        high_strength,
        "",
        2360,
        1440,
    )
    combined_rock = base.maximum(
        material, steep_mask, "", high_rock_mask, "", 2580, 1560
    )
    rocky_normal = base.lerp(
        material,
        vegetated_normal,
        "",
        cliff,
        "",
        combined_rock,
        x=2820,
        y=1900,
    )

    snow_altitude = base.range_mask(
        material, height, 145000.0, 205000.0, 2600, 2220
    )
    snow_slope = base.range_mask(
        material, slope, 0.22, 0.62, 2600, 2410
    )
    snow_slope_penalty = base.one_minus(
        material, snow_slope, "", 2840, 2410
    )
    snow_mask = base.multiply(
        material,
        snow_altitude,
        "",
        snow_slope_penalty,
        "",
        3060,
        2300,
    )
    biome_normal = base.lerp(
        material, rocky_normal, "", snow, "", snow_mask, x=3300, y=2050
    )

    strength = scalar_parameter(
        base, material, MARKER_PARAMETER, 0.58, 3300, 2300
    )
    strengthened = base.lerp(
        material,
        vertex_normal,
        "",
        biome_normal,
        "",
        strength,
        x=3520,
        y=2050,
    )
    final_normal = normalize(base, material, strengthened, "", 3740, 2050)

    material.set_editor_property("tangent_space_normal", False)
    unreal.MaterialEditingLibrary.connect_material_property(
        final_normal, "", unreal.MaterialProperty.MP_NORMAL
    )
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)


def marker_exists(material) -> bool:
    getter = getattr(unreal.MaterialEditingLibrary, "get_scalar_parameter_names", None)
    if getter is None:
        return False
    try:
        return MARKER_PARAMETER in {str(name) for name in getter(material) or []}
    except Exception:
        return False


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before applying biome distribution")
    except AttributeError:
        pass

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    source = unreal.EditorAssetLibrary.load_asset(SOURCE_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")
    if not isinstance(source, unreal.Material):
        raise RuntimeError(f"Missing known-good Aether material: {SOURCE_PATH}")

    active_before = definition.get_editor_property("material")
    active_before_path = asset_path(active_before)

    if active_before_path == TARGET_PATH:
        rollback = unreal.EditorAssetLibrary.load_asset(SENSEI_ROLLBACK_PATH)
    else:
        rollback = active_before
    if rollback is None:
        rollback = source

    if unreal.EditorAssetLibrary.does_asset_exist(TARGET_PACKAGE):
        if active_before_path == TARGET_PATH:
            definition.set_editor_property("material", rollback)
            try:
                definition.post_edit_change()
            except Exception:
                pass
            unreal.EditorAssetLibrary.save_loaded_asset(definition, False)
        unreal.EditorAssetLibrary.delete_asset(TARGET_PACKAGE)

    target = unreal.EditorAssetLibrary.duplicate_asset(
        SOURCE_PACKAGE, TARGET_PACKAGE
    )
    if not isinstance(target, unreal.Material):
        raise RuntimeError(
            f"Could not duplicate {SOURCE_PACKAGE} to {TARGET_PACKAGE}"
        )

    assigned = False
    try:
        base = load_helpers()
        build_biome_normal_graph(base, target)

        if not marker_exists(target):
            raise RuntimeError(
                f"Biome normal marker was not found after compiling {TARGET_PATH}"
            )

        normal_input = unreal.MaterialEditingLibrary.get_material_property_input_node(
            target, unreal.MaterialProperty.MP_NORMAL
        )
        if normal_input is None:
            raise RuntimeError("The new material has no connected Normal input")

        if not unreal.EditorAssetLibrary.save_loaded_asset(target, False):
            raise RuntimeError(f"Failed to save biome material: {TARGET_PATH}")

        definition.set_editor_property("material", target)
        try:
            definition.post_edit_change()
        except Exception:
            pass
        if not unreal.EditorAssetLibrary.save_loaded_asset(definition, False):
            raise RuntimeError(
                f"Failed to save Mesh Partition definition: {DEFINITION_PATH}"
            )
        assigned = True
    except Exception:
        if assigned or asset_path(
            definition.get_editor_property("material")
        ) == TARGET_PATH:
            definition.set_editor_property("material", rollback)
            try:
                definition.post_edit_change()
            except Exception:
                pass
            unreal.EditorAssetLibrary.save_loaded_asset(definition, False)
        if unreal.EditorAssetLibrary.does_asset_exist(TARGET_PACKAGE):
            unreal.EditorAssetLibrary.delete_asset(TARGET_PACKAGE)
        raise

    report = (
        "Aether biome distribution update complete.\n\n"
        f"Before: {active_before_path}\n"
        f"After: {TARGET_PATH}\n"
        f"Rollback preserved: {asset_path(rollback)}\n\n"
        "Biome rules now active:\n"
        "  Sand: shoreline and lowest elevations\n"
        "  Grass: low and moderate flat terrain\n"
        "  Wetland: selected low/moist macro regions\n"
        "  Forest floor: inland macro clusters\n"
        "  Scree: moderate slopes and mountain transitions\n"
        "  Rock: steep cliffs and high exposed terrain\n"
        "  Snow: high, relatively flat mountain surfaces\n\n"
        "Matched world-space normal detail was added for Grass, ForestFloor, "
        "Scree, Rock, and Snow.\n"
        "Terrain geometry, collision, Mesh Partition resolution, channels, "
        "and streaming were not changed.\n\n"
        "Open AetherWorld, wait for shaders to finish, Save All, reopen the "
        "map, and test Play. Do not rebuild Mesh Partition."
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))


if __name__ == "__main__":
    main()
