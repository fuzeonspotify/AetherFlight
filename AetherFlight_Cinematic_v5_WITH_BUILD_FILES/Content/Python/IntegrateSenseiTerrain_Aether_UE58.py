"""Create and assign an AetherFlight material instance from Sensei Terrain.

The third-party Sensei assets are installed locally by
INSTALL_SENSEI_TERRAIN_ASSETS.ps1 and intentionally remain outside Git. This
script creates only Aether-owned assets and updates MPD_AetherWorld. The
original M_MeshTerrain_Aether asset is preserved as a rollback target.
"""

from pathlib import Path

import unreal


LOG_PREFIX = "[Aether Sensei Terrain]"
SENSEI_MASTER = "/Game/SenseiTerrain/Materials/M_SenseiTerrain.M_SenseiTerrain"
AETHER_PACKAGE = "/Game/Aether/MeshTerrain"
INSTANCE_NAME = "MI_AetherTerrain_Sensei"
INSTANCE_PATH = f"{AETHER_PACKAGE}/{INSTANCE_NAME}.{INSTANCE_NAME}"
DEFINITION_PATH = f"{AETHER_PACKAGE}/MPD_AetherWorld.MPD_AetherWorld"
ORIGINAL_MATERIAL_PATH = (
    f"{AETHER_PACKAGE}/M_MeshTerrain_Aether.M_MeshTerrain_Aether"
)
TEXTURE_PACKAGE = "/Game/Aether/ProductionTerrain/Textures"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSenseiTerrainIntegration.txt"

TEXTURE_PARAMETERS = {
    "Color Texture A": "T_Grass_BaseColor",
    "Color Texture B": "T_Rock_BaseColor",
    "Color Texture C": "T_Scree_BaseColor",
    "Color Texture D": "T_ForestFloor_BaseColor",
    "Color Texture E": "T_Snow_BaseColor",
    "Normal Texture A": "T_Grass_Normal",
    "Normal Texture B": "T_Rock_Normal",
    "Normal Texture C": "T_Scree_Normal",
    "Normal Texture D": "T_ForestFloor_Normal",
    "Normal Texture E": "T_Snow_Normal",
    "Roughness Texture A": "T_Grass_Roughness",
    "Roughness Texture B": "T_Rock_Roughness",
    "Roughness Texture C": "T_Scree_Roughness",
    "Roughness Texture D": "T_ForestFloor_Roughness",
    "Roughness Texture E": "T_Snow_Roughness",
}

STATIC_SWITCH_PARAMETERS = {
    "2nd Material Layer B?": True,
    "3rd Material Layer C?": True,
    "4th Material Layer D?": True,
    "5th Material Layer E?": True,
    "Use Auto Blend? B": True,
    "Use Auto Blend? C": True,
    "Triplanar? A": True,
    "Triplanar? B": True,
    "Triplanar? C": True,
    "Triplanar? D": True,
    "Triplanar? E": True,
    "Variation Color?": True,
    "Variation Normal?": True,
}

# These values are deliberately conservative. They improve flight-distance
# breakup while leaving the Sensei master's detailed defaults intact.
SCALAR_PARAMETERS = {
    "Color Variation Amount": 0.28,
    "Normal Variation Strength": 0.35,
    "Distance Variation Blend": 0.55,
    "Triplanar Sharpness A": 4.0,
    "Triplanar Sharpness B": 4.0,
    "Triplanar Sharpness C": 4.0,
    "Triplanar Sharpness D": 4.0,
    "Triplanar Sharpness E": 4.0,
}


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def load_required(path: str, expected_type, label: str):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(asset, expected_type):
        raise RuntimeError(f"Missing or invalid {label}: {path}")
    return asset


def create_or_load_instance(master):
    unreal.EditorAssetLibrary.make_directory(AETHER_PACKAGE)
    instance = unreal.EditorAssetLibrary.load_asset(INSTANCE_PATH)
    if instance is None:
        factory = unreal.MaterialInstanceConstantFactoryNew()
        factory.set_editor_property("initial_parent", master)
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            INSTANCE_NAME,
            AETHER_PACKAGE,
            unreal.MaterialInstanceConstant,
            factory,
        )
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Could not create {INSTANCE_PATH}")
    instance.set_editor_property("parent", master)
    return instance


def set_texture_parameter(instance, parameter_name: str, texture_name: str) -> bool:
    texture_path = f"{TEXTURE_PACKAGE}/{texture_name}.{texture_name}"
    texture = unreal.EditorAssetLibrary.load_asset(texture_path)
    if not isinstance(texture, unreal.Texture2D):
        warn(f"Texture unavailable; skipped {parameter_name}: {texture_path}")
        return False
    try:
        result = unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
            instance, parameter_name, texture
        )
        if result is False:
            warn(f"Sensei master did not accept texture parameter: {parameter_name}")
            return False
        return True
    except Exception as exc:
        warn(f"Could not set {parameter_name}: {exc}")
        return False


def set_scalar_parameter(instance, parameter_name: str, value: float) -> bool:
    try:
        result = unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, parameter_name, float(value)
        )
        if result is False:
            warn(f"Sensei master did not accept scalar parameter: {parameter_name}")
            return False
        return True
    except Exception as exc:
        warn(f"Could not set {parameter_name}: {exc}")
        return False


def set_static_switch(instance, parameter_name: str, enabled: bool) -> bool:
    setter = getattr(
        unreal.MaterialEditingLibrary,
        "set_material_instance_static_switch_parameter_value",
        None,
    )
    if setter is None:
        warn("Static-switch editing is unavailable in this Unreal Python build")
        return False
    try:
        result = setter(instance, parameter_name, bool(enabled))
        if result is False:
            warn(f"Sensei master did not accept static switch: {parameter_name}")
            return False
        return True
    except Exception as exc:
        warn(f"Could not set static switch {parameter_name}: {exc}")
        return False


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before integrating the material")
    except AttributeError:
        pass

    master = load_required(SENSEI_MASTER, unreal.Material, "Sensei master material")
    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Aether Mesh Partition Definition: {DEFINITION_PATH}")
    load_required(ORIGINAL_MATERIAL_PATH, unreal.Material, "Aether rollback material")

    instance = create_or_load_instance(master)

    texture_success = sum(
        set_texture_parameter(instance, parameter, texture)
        for parameter, texture in TEXTURE_PARAMETERS.items()
    )
    scalar_success = sum(
        set_scalar_parameter(instance, parameter, value)
        for parameter, value in SCALAR_PARAMETERS.items()
    )
    switch_success = sum(
        set_static_switch(instance, parameter, enabled)
        for parameter, enabled in STATIC_SWITCH_PARAMETERS.items()
    )

    try:
        instance.post_edit_change()
    except Exception:
        pass

    definition.set_editor_property("material", instance)
    try:
        definition.post_edit_change()
    except Exception:
        pass

    unreal.EditorAssetLibrary.save_loaded_asset(instance, False)
    unreal.EditorAssetLibrary.save_loaded_asset(definition, False)

    report = (
        "Aether Sensei Terrain integration complete.\n"
        f"Master: {SENSEI_MASTER}\n"
        f"Instance: {INSTANCE_PATH}\n"
        f"Definition: {DEFINITION_PATH}\n"
        f"Texture parameters applied: {texture_success}/{len(TEXTURE_PARAMETERS)}\n"
        f"Scalar parameters applied: {scalar_success}/{len(SCALAR_PARAMETERS)}\n"
        f"Static switches applied: {switch_success}/{len(STATIC_SWITCH_PARAMETERS)}\n"
        f"Rollback material preserved: {ORIGINAL_MATERIAL_PATH}\n"
        "Next: open AetherWorld and use Build > Build Mesh Partition so compiled "
        "runtime sections use the new material.\n"
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))
    unreal.EditorDialog.show_message(
        "Aether Sensei Terrain Installed",
        report,
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
