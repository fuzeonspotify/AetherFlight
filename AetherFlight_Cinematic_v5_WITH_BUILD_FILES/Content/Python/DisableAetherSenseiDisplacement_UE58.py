"""Repair the local Sensei Terrain instance for AetherFlight Mesh Terrain.

This script is intentionally standalone so it works from Unreal's Output Log or
from -ExecutePythonScript. It creates MI_AetherTerrain_Sensei when missing,
maps the existing Aether terrain textures, disables all known displacement
controls, and assigns the safe instance to MPD_AetherWorld.
"""

import unreal


LOG_PREFIX = "[Aether Sensei Repair]"
SENSEI_MASTER_PATH = "/Game/SenseiTerrain/Materials/M_SenseiTerrain.M_SenseiTerrain"
AETHER_PACKAGE = "/Game/Aether/MeshTerrain"
INSTANCE_NAME = "MI_AetherTerrain_Sensei"
INSTANCE_PATH = f"{AETHER_PACKAGE}/{INSTANCE_NAME}.{INSTANCE_NAME}"
DEFINITION_PATH = f"{AETHER_PACKAGE}/MPD_AetherWorld.MPD_AetherWorld"
TEXTURE_PACKAGE = "/Game/Aether/ProductionTerrain/Textures"

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

SCALAR_PARAMETERS = {
    "Color Variation Amount": 0.28,
    "Normal Variation Strength": 0.35,
    "Distance Variation Blend": 0.55,
    "Triplanar Sharpness A": 4.0,
    "Triplanar Sharpness B": 4.0,
    "Triplanar Sharpness C": 4.0,
    "Triplanar Sharpness D": 4.0,
    "Triplanar Sharpness E": 4.0,
    **{f"Displacement Amount {layer}": 0.0 for layer in "ABCDE"},
    **{f"Displacement Strength {layer}": 0.0 for layer in "ABCDE"},
    **{f"Displacement Offset {layer}": 0.0 for layer in "ABCDE"},
    **{f"Displacement Scale {layer}": 0.0 for layer in "ABCDE"},
    "Displacement Amount": 0.0,
    "Displacement Strength": 0.0,
    "Displacement Offset": 0.0,
    "Displacement Scale": 0.0,
    "Nanite Displacement Magnitude": 0.0,
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
    "Displacement": False,
    "Use Displacement?": False,
    "Enable Displacement?": False,
    "Nanite Displacement": False,
    "Use Nanite Displacement?": False,
}


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def stop_if_playing() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before running the Sensei repair")
    except AttributeError:
        return


def create_or_load_instance(master):
    unreal.EditorAssetLibrary.make_directory(AETHER_PACKAGE)
    instance = unreal.EditorAssetLibrary.load_asset(INSTANCE_PATH)
    created = not isinstance(instance, unreal.MaterialInstanceConstant)

    if created:
        factory = unreal.MaterialInstanceConstantFactoryNew()
        instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            INSTANCE_NAME,
            AETHER_PACKAGE,
            unreal.MaterialInstanceConstant,
            factory,
        )

    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Could not create material instance: {INSTANCE_PATH}")

    # UE 5.8 does not expose InitialParent on this factory through Python in all
    # builds, so create the asset first and assign Parent on the instance.
    instance.set_editor_property("parent", master)
    return instance, created


def set_texture(instance, name: str, texture_name: str) -> bool:
    texture_path = f"{TEXTURE_PACKAGE}/{texture_name}.{texture_name}"
    texture = unreal.EditorAssetLibrary.load_asset(texture_path)
    if not isinstance(texture, unreal.Texture2D):
        warn(f"Texture missing; skipped {name}: {texture_path}")
        return False
    try:
        result = unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
            instance, name, texture
        )
        return result is not False
    except Exception as exc:
        warn(f"Could not set texture parameter {name}: {exc}")
        return False


def set_scalar(instance, name: str, value: float) -> bool:
    try:
        result = unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, name, float(value)
        )
        return result is not False
    except Exception as exc:
        warn(f"Could not set scalar parameter {name}: {exc}")
        return False


def set_switch(instance, name: str, value: bool) -> bool:
    setter = getattr(
        unreal.MaterialEditingLibrary,
        "set_material_instance_static_switch_parameter_value",
        None,
    )
    if setter is None:
        warn("Static-switch editing is unavailable in this Unreal Python build")
        return False
    try:
        result = setter(instance, name, bool(value))
        return result is not False
    except Exception as exc:
        warn(f"Could not set static switch {name}: {exc}")
        return False


def add_discovered_displacement_parameters(instance) -> None:
    scalar_getter = getattr(
        unreal.MaterialEditingLibrary, "get_scalar_parameter_names", None
    )
    if scalar_getter is not None:
        try:
            for raw_name in scalar_getter(instance) or []:
                name = str(raw_name)
                lowered = name.lower()
                if "displacement" in lowered or "world position offset" in lowered:
                    SCALAR_PARAMETERS[name] = 0.0
        except Exception as exc:
            warn(f"Could not discover scalar parameters: {exc}")

    switch_getter = getattr(
        unreal.MaterialEditingLibrary, "get_static_switch_parameter_names", None
    )
    if switch_getter is not None:
        try:
            for raw_name in switch_getter(instance) or []:
                name = str(raw_name)
                lowered = name.lower()
                if "displacement" in lowered or "world position offset" in lowered:
                    STATIC_SWITCH_PARAMETERS[name] = False
        except Exception as exc:
            warn(f"Could not discover static switches: {exc}")


def main() -> None:
    stop_if_playing()

    master = unreal.EditorAssetLibrary.load_asset(SENSEI_MASTER_PATH)
    if not isinstance(master, unreal.Material):
        raise RuntimeError(
            "Sensei master material could not load. Close Unreal, pull the latest "
            "scripts, and rerun INSTALL_SENSEI_TERRAIN_ASSETS.ps1 -Force so all "
            "Sensei asset dependencies are copied locally. Missing/invalid asset: "
            f"{SENSEI_MASTER_PATH}"
        )

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")

    instance, created = create_or_load_instance(master)
    add_discovered_displacement_parameters(instance)

    mapped_textures = sum(
        set_texture(instance, parameter, texture)
        for parameter, texture in TEXTURE_PARAMETERS.items()
    )
    mapped_scalars = sum(
        set_scalar(instance, parameter, value)
        for parameter, value in SCALAR_PARAMETERS.items()
    )
    mapped_switches = sum(
        set_switch(instance, parameter, value)
        for parameter, value in STATIC_SWITCH_PARAMETERS.items()
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

    if not unreal.EditorAssetLibrary.save_loaded_asset(instance, False):
        raise RuntimeError(f"Failed to save material instance: {INSTANCE_PATH}")
    if not unreal.EditorAssetLibrary.save_loaded_asset(definition, False):
        raise RuntimeError(f"Failed to save Mesh Partition definition: {DEFINITION_PATH}")

    message = (
        "Sensei Terrain was repaired for AetherFlight.\n\n"
        f"Created missing material instance: {created}\n"
        f"Aether textures mapped: {mapped_textures}/{len(TEXTURE_PARAMETERS)}\n"
        f"Scalar settings applied: {mapped_scalars}/{len(SCALAR_PARAMETERS)}\n"
        f"Static switches applied: {mapped_switches}/{len(STATIC_SWITCH_PARAMETERS)}\n"
        f"Assigned material: {INSTANCE_PATH}\n\n"
        "Save All, then test Play mode before rebuilding Mesh Partition."
    )
    log(message.replace("\n", " | "))
    unreal.EditorDialog.show_message(
        "Aether Sensei Terrain Repaired",
        message,
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
