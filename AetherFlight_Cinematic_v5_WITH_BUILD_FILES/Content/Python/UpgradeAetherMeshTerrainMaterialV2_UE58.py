"""Build and assign AetherFlight's channel-aware Mesh Terrain material V2.

This is the safe continuation of the Sensei Terrain workflow. It does not use
Sensei's master material directly because that material is not authored for
AetherFlight's Mesh Partition definition and previously caused disappearing
sections, extreme walls, and long shader stalls.

V2 preserves the known-good Mesh Terrain geometry and creates a separate
Aether-owned material with:

* automatic slope/height biome blending;
* triplanar projection for the five core mountain layers;
* planar lowland sampling for sand and wetland;
* two scales of macro variation for flight-distance breakup;
* optional Mesh Partition weight-channel overrides by stable channel index;
* no World Position Offset, tessellation, or displacement.

M_MeshTerrain_Aether is preserved as the rollback material. MPD_AetherWorld is
updated only after V2 compiles and saves successfully.
"""

from pathlib import Path
import importlib.util

import unreal


LOG_PREFIX = "[Aether Terrain V2]"
PACKAGE = "/Game/Aether/MeshTerrain"
MATERIAL_NAME = "M_MeshTerrain_Aether_V2"
MATERIAL_PATH = f"{PACKAGE}/{MATERIAL_NAME}.{MATERIAL_NAME}"
DEFINITION_PATH = f"{PACKAGE}/MPD_AetherWorld.MPD_AetherWorld"
BASE_SCRIPT_PATH = Path(
    unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir()
        + "Python/InstallAetherMeshTerrain_UE58.py"
    )
)
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherTerrainV2Report.txt"

LAYERS = ("Grass", "ForestFloor", "Rock", "Scree", "Snow", "Sand", "Wetland")
TRIPLANAR_LAYERS = ("Grass", "ForestFloor", "Rock", "Scree", "Snow")
PLANAR_LAYERS = ("Sand", "Wetland")
CHANNEL_INDEX = {
    "Grass": 0,
    "ForestFloor": 1,
    "Rock": 2,
    "Scree": 3,
    "Snow": 4,
    "Sand": 5,
    "Wetland": 6,
}
PAINT_PRIORITY = ("Sand", "Wetland", "Grass", "ForestFloor", "Scree", "Rock", "Snow")


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def load_base_module():
    if not BASE_SCRIPT_PATH.is_file():
        raise RuntimeError(f"Missing Mesh Terrain installer helpers: {BASE_SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location(
        "aether_mesh_terrain_v1_helpers", str(BASE_SCRIPT_PATH)
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper module: {BASE_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MATERIAL_NAME = MATERIAL_NAME
    return module


def constant3(base, material, color, x=0, y=0):
    node = base.expression(material, unreal.MaterialExpressionConstant3Vector, x, y)
    node.set_editor_property("constant", unreal.LinearColor(*color, 1.0))
    return node


def generic_texture_sample(base, material, texture, parameter_name, uv, sampler_type, x, y):
    sample = base.expression(material, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    sample.set_editor_property("parameter_name", parameter_name)
    sample.set_editor_property("texture", texture)
    sample.set_editor_property("sampler_type", sampler_type)
    try:
        sample.set_editor_property("sampler_source", unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS)
    except Exception:
        pass
    base.connect(uv, "", sample, "UVs", f"UVs for {parameter_name}")
    return sample


def planar_color(base, material, layer_name, xy_plane, index):
    texture = base.load_texture(f"T_{layer_name}_BaseColor")
    scale_cm = base.LAYER_TILE_CM[layer_name]
    x = -900 + index * 520
    uv = base.scaled_uv(material, xy_plane, scale_cm, x, -780)
    return generic_texture_sample(
        base,
        material,
        texture,
        f"{layer_name}_Planar",
        uv,
        unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
        x + 220,
        -780,
    )


def macro_sample(base, material, xy_plane, scale_cm, parameter_name, x, y):
    uv = base.scaled_uv(material, xy_plane, scale_cm, x, y)
    texture = base.load_texture("T_MacroVariation")
    return generic_texture_sample(
        base,
        material,
        texture,
        parameter_name,
        uv,
        unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,
        x + 220,
        y,
    )


def connect_resource_to_sample(base, resource, sample, description):
    base.connect(
        resource,
        ("", "Resource", "Channel Texture", "ChannelTexture"),
        sample,
        (
            "ChannelTextureInput",
            "Channel Texture Input",
            "Channel Texture",
            "Texture",
        ),
        description,
    )


def build_channel_samples(base, material, definition):
    resource_class = getattr(unreal, "MaterialExpressionMeshPartitionResource", None)
    sample_class = getattr(
        unreal, "MaterialExpressionMeshPartitionChannelSampleIndex", None
    )
    if resource_class is None or sample_class is None:
        warn("Mesh Partition material channel expressions are unavailable; automatic biome blending will remain active.")
        return {}, False

    channels_ready = base.configure_channels(definition)
    if not channels_ready:
        warn("The channel map could not be rewritten through Python; V2 will use automatic biome blending until channels are confirmed manually.")
        return {}, False

    resource = base.expression(material, resource_class, -2900, 1150)
    samples = {}
    try:
        for row, layer_name in enumerate(LAYERS):
            sample = base.expression(material, sample_class, -2620, 1080 + row * 130)
            sample.set_editor_property("const_channel_index", CHANNEL_INDEX[layer_name])
            connect_resource_to_sample(
                base, resource, sample, f"Mesh Partition channel {layer_name}"
            )
            samples[layer_name] = sample
    except Exception as exc:
        warn(f"Could not build Mesh Partition channel readers ({exc}); automatic biome blending will remain active.")
        return {}, channels_ready

    return samples, channels_ready


def apply_channel_overrides(base, material, current_value, layer_values, channel_samples, x, y):
    if not channel_samples:
        return current_value

    strength = base.constant(material, 0.92, x - 220, y - 120)
    result = current_value
    for index, layer_name in enumerate(PAINT_PRIORITY):
        channel = channel_samples.get(layer_name)
        layer_value = layer_values.get(layer_name)
        if channel is None or layer_value is None:
            continue
        alpha = base.multiply(
            material,
            channel,
            "",
            strength,
            "",
            x + index * 220,
            y + 120,
        )
        alpha = base.saturate(material, alpha, "", x + index * 220 + 90, y + 120)
        result = base.lerp(
            material,
            result,
            "",
            layer_value,
            "",
            alpha,
            x=x + index * 220 + 130,
            y=y,
        )
    return result


def build_material(base, definition):
    material = base.create_or_load_material()
    world_position, planes, weights, normal_z = base.build_projection_basis(material)

    colors = {}
    for index, layer_name in enumerate(TRIPLANAR_LAYERS):
        colors[layer_name] = base.triplanar_color(
            material, layer_name, planes, weights, index
        )
    for index, layer_name in enumerate(PLANAR_LAYERS, start=len(TRIPLANAR_LAYERS)):
        colors[layer_name] = planar_color(base, material, layer_name, planes[0], index)

    height = base.mask(material, world_position, b=True, x=-1000, y=-500)
    slope = base.one_minus(material, normal_z, "", -760, -390)

    near_macro = macro_sample(
        base, material, planes[0], 185000.0, "TerrainMacroNear", -900, 80
    )
    far_macro = macro_sample(
        base, material, planes[0], 720000.0, "TerrainMacroFar", -900, 330
    )

    shore_to_grass = base.range_mask(material, height, 0.0, 28000.0, -460, -900)
    low_color = base.lerp(
        material,
        colors["Sand"],
        "",
        colors["Grass"],
        "",
        shore_to_grass,
        x=-220,
        y=-900,
    )

    macro_forest = base.range_mask(material, near_macro, 0.34, 0.70, -310, -120, "R")
    forest_strength = base.constant(material, 0.72, -310, 40)
    forest_mask = base.multiply(
        material, macro_forest, "", forest_strength, "", -100, -120
    )
    mid_color = base.lerp(
        material,
        colors["Grass"],
        "",
        colors["ForestFloor"],
        "",
        forest_mask,
        x=120,
        y=-120,
    )

    low_altitude = base.one_minus(
        material,
        base.range_mask(material, height, 2500.0, 24000.0, -350, 340),
        x=-100,
        y=340,
    )
    macro_wet = base.range_mask(material, near_macro, 0.52, 0.78, -350, 520, "R")
    wetland_mask = base.multiply(
        material, low_altitude, "", macro_wet, "", -100, 450
    )
    low_wet_color = base.lerp(
        material,
        low_color,
        "",
        colors["Wetland"],
        "",
        wetland_mask,
        x=120,
        y=430,
    )
    inland_mask = base.range_mask(material, height, 6000.0, 36000.0, 330, 240)
    vegetated_color = base.lerp(
        material,
        low_wet_color,
        "",
        mid_color,
        "",
        inland_mask,
        x=560,
        y=160,
    )

    steep_mask = base.range_mask(material, slope, 0.075, 0.36, 520, -520)
    very_steep_mask = base.range_mask(material, slope, 0.24, 0.60, 520, -340)
    rock_color = base.lerp(
        material,
        colors["Scree"],
        "",
        colors["Rock"],
        "",
        very_steep_mask,
        x=760,
        y=-390,
    )
    high_altitude_rock = base.range_mask(material, height, 90000.0, 165000.0, 520, -690)
    high_strength = base.constant(material, 0.58, 760, -730)
    high_rock_mask = base.multiply(
        material, high_altitude_rock, "", high_strength, "", 950, -690
    )
    combined_rock_mask = base.maximum(
        material, steep_mask, "", high_rock_mask, "", 1140, -520
    )
    rocky_color = base.lerp(
        material,
        vegetated_color,
        "",
        rock_color,
        "",
        combined_rock_mask,
        x=1360,
        y=-300,
    )

    snow_altitude = base.range_mask(material, height, 145000.0, 205000.0, 1120, 120)
    snow_slope = base.range_mask(material, slope, 0.22, 0.62, 1120, 300)
    snow_slope_penalty = base.one_minus(material, snow_slope, "", 1370, 300)
    snow_mask = base.multiply(
        material, snow_altitude, "", snow_slope_penalty, "", 1570, 180
    )
    automatic_color = base.lerp(
        material,
        rocky_color,
        "",
        colors["Snow"],
        "",
        snow_mask,
        x=1800,
        y=-120,
    )

    channel_samples, channels_ready = build_channel_samples(base, material, definition)
    painted_color = apply_channel_overrides(
        base,
        material,
        automatic_color,
        colors,
        channel_samples,
        2280,
        -160,
    )

    near_strength = base.constant(material, 0.24, 1510, -760)
    near_floor = base.constant(material, 0.84, 1510, -650)
    near_scaled = base.multiply(
        material, near_macro, "R", near_strength, "", 1730, -730
    )
    near_factor = base.add(
        material, near_scaled, "", near_floor, "", 1910, -680
    )

    far_strength = base.constant(material, 0.16, 1510, -540)
    far_floor = base.constant(material, 0.92, 1510, -430)
    far_scaled = base.multiply(
        material, far_macro, "G", far_strength, "", 1730, -510
    )
    far_factor = base.add(
        material, far_scaled, "", far_floor, "", 1910, -460
    )

    varied_color = base.multiply(
        material, painted_color, "", near_factor, "", 2130, -120
    )
    varied_color = base.multiply(
        material, varied_color, "", far_factor, "", 2350, -120
    )
    final_color = base.saturate(material, varied_color, "", 2560, -120)

    roughness_values = {
        "Sand": base.constant(material, 0.78, 750, 600),
        "Grass": base.constant(material, 0.86, 750, 680),
        "ForestFloor": base.constant(material, 0.91, 750, 760),
        "Wetland": base.constant(material, 0.94, 750, 840),
        "Scree": base.constant(material, 0.90, 750, 920),
        "Rock": base.constant(material, 0.72, 750, 1000),
        "Snow": base.constant(material, 0.64, 750, 1080),
    }
    rough_low = base.lerp(
        material,
        roughness_values["Sand"],
        "",
        roughness_values["Grass"],
        "",
        shore_to_grass,
        x=980,
        y=650,
    )
    rough_low_wet = base.lerp(
        material,
        rough_low,
        "",
        roughness_values["Wetland"],
        "",
        wetland_mask,
        x=1180,
        y=700,
    )
    rough_mid = base.lerp(
        material,
        roughness_values["Grass"],
        "",
        roughness_values["ForestFloor"],
        "",
        forest_mask,
        x=980,
        y=820,
    )
    rough_vegetated = base.lerp(
        material,
        rough_low_wet,
        "",
        rough_mid,
        "",
        inland_mask,
        x=1390,
        y=760,
    )
    rough_rock_mix = base.lerp(
        material,
        roughness_values["Scree"],
        "",
        roughness_values["Rock"],
        "",
        very_steep_mask,
        x=1180,
        y=980,
    )
    rough_terrain = base.lerp(
        material,
        rough_vegetated,
        "",
        rough_rock_mix,
        "",
        combined_rock_mask,
        x=1600,
        y=850,
    )
    automatic_roughness = base.lerp(
        material,
        rough_terrain,
        "",
        roughness_values["Snow"],
        "",
        snow_mask,
        x=1830,
        y=920,
    )
    final_roughness = apply_channel_overrides(
        base,
        material,
        automatic_roughness,
        roughness_values,
        channel_samples,
        2280,
        900,
    )

    unreal.MaterialEditingLibrary.connect_material_property(
        final_color, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        final_roughness, "", unreal.MaterialProperty.MP_ROUGHNESS
    )
    specular = base.constant(material, 0.18, 2760, 720)
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )
    ao = base.constant(material, 1.0, 2760, 820)
    unreal.MaterialEditingLibrary.connect_material_property(
        ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
        raise RuntimeError(f"Failed to save V2 terrain material: {MATERIAL_PATH}")

    return material, channels_ready, bool(channel_samples)


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before upgrading the terrain material")
    except AttributeError:
        pass

    base = load_base_module()
    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")

    previous_material = None
    try:
        previous_material = definition.get_editor_property("material")
    except Exception:
        pass

    material, channels_ready, channel_graph_ready = build_material(base, definition)

    definition.set_editor_property("material", material)
    try:
        definition.post_edit_change()
    except Exception:
        pass
    if not unreal.EditorAssetLibrary.save_loaded_asset(definition, False):
        raise RuntimeError(f"Failed to save Mesh Partition definition: {DEFINITION_PATH}")

    previous_path = previous_material.get_path_name() if previous_material else "None"
    report = (
        "Aether Mesh Terrain Material V2 installed.\n"
        f"Previous material: {previous_path}\n"
        f"Active material: {material.get_path_name()}\n"
        f"Channel map repaired: {channels_ready}\n"
        f"Channel-aware material graph: {channel_graph_ready}\n"
        "Core triplanar layers: Grass, ForestFloor, Rock, Scree, Snow\n"
        "Planar lowland layers: Sand, Wetland\n"
        "Displacement / WPO: disabled by design\n"
        "Rollback: RestoreAetherMeshTerrainMaterial_UE58.py\n"
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))

    unreal.EditorDialog.show_message(
        "Aether Terrain V2 Installed",
        report
        + "\nSave All, reopen AetherWorld, and test Play mode before rebuilding Mesh Partition.\n"
        + "Only rebuild once if streamed sections continue showing the previous material.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
