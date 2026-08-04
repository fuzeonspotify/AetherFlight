"""Add safe surface-normal detail to the currently active Aether Mesh Terrain material.

The script deliberately does not change terrain geometry, displacement, WPO,
Mesh Partition resolution, or transformer pipelines.

Behavior:
- When MPD_AetherWorld uses a material instance (for example the local Sensei
  instance), refresh the existing normal-texture parameters without replacing
  the active material.
- When MPD_AetherWorld uses an editable Aether material, duplicate it to
  M_MeshTerrain_Aether_Detail, add a performance-conscious world-space normal
  graph, compile it, and only then assign the duplicate to the MPD.

The Aether graph uses eight normal samples total:
- planar Grass and Snow normals for mostly horizontal surfaces;
- triplanar Scree and Rock normals for cliffs;
- slope and altitude blending;
- a tunable Aether Detail Normal Strength parameter;
- no displacement or World Position Offset.
"""

from pathlib import Path
import importlib.util

import unreal


LOG_PREFIX = "[Aether Surface Detail]"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
TEXTURE_PACKAGE = "/Game/Aether/ProductionTerrain/Textures"
DETAIL_PACKAGE_PATH = "/Game/Aether/MeshTerrain/M_MeshTerrain_Aether_Detail"
DETAIL_OBJECT_PATH = DETAIL_PACKAGE_PATH + ".M_MeshTerrain_Aether_Detail"
MARKER_PARAMETER = "Aether Detail Normal Strength"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSurfaceDetailReport.txt"
HELPER_PATH = Path(
    unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir()
        + "Python/InstallAetherMeshTerrain_UE58.py"
    )
)

INSTANCE_NORMALS = {
    "Normal Texture A": "T_Grass_Normal",
    "Normal Texture B": "T_Rock_Normal",
    "Normal Texture C": "T_Scree_Normal",
    "Normal Texture D": "T_ForestFloor_Normal",
    "Normal Texture E": "T_Snow_Normal",
}


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def load_helpers():
    if not HELPER_PATH.is_file():
        raise RuntimeError(f"Missing material helper script: {HELPER_PATH}")
    spec = importlib.util.spec_from_file_location(
        "aether_surface_detail_helpers", str(HELPER_PATH)
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


def set_instance_texture(instance, parameter_name: str, texture_name: str) -> bool:
    texture = load_texture(texture_name)
    try:
        result = unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
            instance, parameter_name, texture
        )
        return result is not False
    except Exception as exc:
        warn(f"Could not set {parameter_name}: {exc}")
        return False


def set_instance_scalar(instance, parameter_name: str, value: float) -> bool:
    try:
        result = unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, parameter_name, float(value)
        )
        return result is not False
    except Exception:
        return False


def refresh_material_instance(instance):
    mapped = sum(
        set_instance_texture(instance, parameter, texture)
        for parameter, texture in INSTANCE_NORMALS.items()
    )

    scalar_candidates = {
        "Normal Variation Strength": 0.62,
        "Normal Strength": 0.72,
        "Normal Intensity": 0.72,
        **{f"Normal Strength {layer}": 0.72 for layer in "ABCDE"},
        **{f"Normal Intensity {layer}": 0.72 for layer in "ABCDE"},
    }
    scalar_updates = sum(
        set_instance_scalar(instance, parameter, value)
        for parameter, value in scalar_candidates.items()
    )

    try:
        instance.post_edit_change()
    except Exception:
        pass
    unreal.EditorAssetLibrary.save_loaded_asset(instance, False)
    return mapped, scalar_updates


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


def append3(base, material, x_node, x_output, y_node, y_output, z_node, z_output, x=0, y=0):
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
            "sampler_source", unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS
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

    return vertex_normal, (weight_x, weight_y, weight_z), (sign_x, sign_y, sign_z), abs_z


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


def triplanar_normal(base, material, layer_name: str, planes, weights, signs, index: int):
    texture_name = f"T_{layer_name}_Normal"
    scale_cm = base.LAYER_TILE_CM[layer_name]
    x = -1200 + index * 850

    uv_yz = base.scaled_uv(material, planes[2], scale_cm, x, 1700)
    uv_xz = base.scaled_uv(material, planes[1], scale_cm, x, 1930)
    uv_xy = base.scaled_uv(material, planes[0], scale_cm, x, 2160)

    sample_x = normal_sample(
        base, material, texture_name, f"AetherNormal_{layer_name}_X", uv_yz, x + 210, 1700
    )
    sample_y = normal_sample(
        base, material, texture_name, f"AetherNormal_{layer_name}_Y", uv_xz, x + 210, 1930
    )
    sample_z = normal_sample(
        base, material, texture_name, f"AetherNormal_{layer_name}_Z", uv_xy, x + 210, 2160
    )

    world_x = reorient_x(base, material, sample_x, signs[0], x + 410, 1700)
    world_y = reorient_y(base, material, sample_y, signs[1], x + 410, 1930)
    world_z = reorient_z(base, material, sample_z, signs[2], x + 410, 2160)

    weighted_x = base.multiply(material, world_x, "", weights[0], "", x + 650, 1700)
    weighted_y = base.multiply(material, world_y, "", weights[1], "", x + 650, 1930)
    weighted_z = base.multiply(material, world_z, "", weights[2], "", x + 650, 2160)
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
        f"AetherNormal_{layer_name}_Planar",
        uv,
        x + 210,
        y,
    )
    world = reorient_z(base, material, sample, sign_z, x + 430, y)
    return normalize(base, material, world, "", x + 650, y)


def marker_exists(material) -> bool:
    getter = getattr(unreal.MaterialEditingLibrary, "get_scalar_parameter_names", None)
    if getter is None:
        return False
    try:
        return MARKER_PARAMETER in {str(name) for name in getter(material) or []}
    except Exception:
        return False


def duplicate_editable_material(active_material):
    active_package = active_material.get_path_name().split(".", 1)[0]
    if active_package.startswith("/Game/SenseiTerrain/"):
        raise RuntimeError(
            "The active material is the third-party Sensei master. Use a material instance; "
            "the updater will not edit vendor assets directly."
        )

    if active_package == DETAIL_PACKAGE_PATH:
        return active_material, False

    existing = unreal.EditorAssetLibrary.load_asset(DETAIL_OBJECT_PATH)
    if isinstance(existing, unreal.Material) and marker_exists(existing):
        return existing, False

    if unreal.EditorAssetLibrary.does_asset_exist(DETAIL_PACKAGE_PATH):
        unreal.EditorAssetLibrary.delete_asset(DETAIL_PACKAGE_PATH)

    duplicated = unreal.EditorAssetLibrary.duplicate_asset(
        active_package, DETAIL_PACKAGE_PATH
    )
    if not isinstance(duplicated, unreal.Material):
        raise RuntimeError(
            f"Could not duplicate {active_package} to {DETAIL_PACKAGE_PATH}"
        )
    return duplicated, True


def build_detail_graph(base, material):
    if marker_exists(material):
        return False

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
    snow = planar_normal(base, material, "Snow", xy, signs[2], -1200, 2700)
    scree = triplanar_normal(base, material, "Scree", (xy, xz, yz), weights, signs, 0)
    rock = triplanar_normal(base, material, "Rock", (xy, xz, yz), weights, signs, 1)

    steep_mask = base.range_mask(material, slope, 0.075, 0.36, 1550, 1500)
    very_steep = base.range_mask(material, slope, 0.24, 0.60, 1550, 1690)
    cliff = base.lerp(
        material, scree, "", rock, "", very_steep, x=1920, y=1760
    )
    terrain = base.lerp(
        material, grass, "", cliff, "", steep_mask, x=2160, y=1640
    )

    snow_altitude = base.range_mask(material, height, 145000.0, 205000.0, 1900, 2220)
    snow_slope = base.range_mask(material, slope, 0.22, 0.62, 1900, 2410)
    snow_slope_penalty = base.one_minus(material, snow_slope, "", 2160, 2410)
    snow_mask = base.multiply(
        material,
        snow_altitude,
        "",
        snow_slope_penalty,
        "",
        2380,
        2300,
    )
    detailed = base.lerp(
        material, terrain, "", snow, "", snow_mask, x=2600, y=1940
    )

    strength = scalar_parameter(
        base, material, MARKER_PARAMETER, 0.58, 2600, 2180
    )
    strengthened = base.lerp(
        material,
        vertex_normal,
        "",
        detailed,
        "",
        strength,
        x=2820,
        y=1940,
    )
    final_normal = normalize(base, material, strengthened, "", 3040, 1940)

    material.set_editor_property("tangent_space_normal", False)
    unreal.MaterialEditingLibrary.connect_material_property(
        final_normal, "", unreal.MaterialProperty.MP_NORMAL
    )
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
        raise RuntimeError(f"Failed to save detailed terrain material: {material.get_path_name()}")
    return True


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before updating terrain detail")
    except AttributeError:
        pass

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")

    active_material = definition.get_editor_property("material")
    if active_material is None:
        raise RuntimeError("MPD_AetherWorld has no active material")

    active_before = active_material.get_path_name()
    mode = ""
    details = ""

    if isinstance(active_material, unreal.MaterialInstanceConstant):
        mapped, scalar_updates = refresh_material_instance(active_material)
        mode = "Material-instance normal parameters refreshed"
        details = (
            f"Normal textures mapped: {mapped}/{len(INSTANCE_NORMALS)}\n"
            f"Compatible strength parameters updated: {scalar_updates}\n"
            "The active material assignment was not replaced."
        )
        active_after = active_before
    elif isinstance(active_material, unreal.Material):
        base = load_helpers()
        detail_material, duplicated = duplicate_editable_material(active_material)
        graph_added = build_detail_graph(base, detail_material)

        definition.set_editor_property("material", detail_material)
        try:
            definition.post_edit_change()
        except Exception:
            pass
        if not unreal.EditorAssetLibrary.save_loaded_asset(definition, False):
            raise RuntimeError(f"Failed to save Mesh Partition definition: {DEFINITION_PATH}")

        mode = "Aether world-space normal graph installed"
        details = (
            f"Material duplicate created: {duplicated}\n"
            f"Normal graph added: {graph_added}\n"
            "Normal samples: 8\n"
            "Displacement / WPO: unchanged and disabled"
        )
        active_after = detail_material.get_path_name()
    else:
        raise RuntimeError(
            f"Unsupported active terrain material type: {active_material.get_class().get_name()}"
        )

    report = (
        "Aether surface detail update complete.\n\n"
        f"Mode: {mode}\n"
        f"Before: {active_before}\n"
        f"After: {active_after}\n"
        f"{details}\n\n"
        "Terrain geometry, collision, Mesh Partition resolution, and streaming settings were not changed.\n"
        "Save All, reopen AetherWorld, and test Play before rebuilding Mesh Partition."
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))
    unreal.EditorDialog.show_message(
        "Aether Surface Detail Updated", report, unreal.AppMsgType.OK
    )


if __name__ == "__main__":
    main()
