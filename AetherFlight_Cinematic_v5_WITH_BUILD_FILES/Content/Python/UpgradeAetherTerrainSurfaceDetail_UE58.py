"""Apply verified Aether textures to the installed Sensei Terrain instance.

The exact parameter names in this file come from the read-only UE 5.8 audit of
MI_AetherTerrain_Sensei. The previous updater guessed names such as
"Normal Texture A"; those parameters do not exist in the installed asset and
therefore changed nothing.

This update changes only material-instance texture/scalar overrides. It does
not change terrain geometry, collision, Mesh Partition resolution, transformer
pipelines, displacement, tessellation, or World Position Offset.
"""

from pathlib import Path

import unreal


LOG_PREFIX = "[Aether Verified Surface]"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
EXPECTED_INSTANCE_PATH = (
    "/Game/Aether/MeshTerrain/MI_AetherTerrain_Sensei.MI_AetherTerrain_Sensei"
)
TEXTURE_PACKAGE = "/Game/Aether/ProductionTerrain/Textures"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSurfaceDetailReport.txt"

# Verified A-E layer order used by the existing Aether Sensei integration.
LAYER_MAP = {
    "A": "Grass",
    "B": "Rock",
    "C": "Scree",
    "D": "ForestFloor",
    "E": "Snow",
}

# These exact names were returned by MaterialEditingLibrary in the audit.
TEXTURE_PARAMETER_FORMATS = {
    "Albedo": "Albedo Color {slot}",
    "Normal": "Normal {slot}",
    "Roughness": "Roughness {slot}",
}
NORMAL_STRENGTH = 0.78


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def load_texture(layer_name: str, texture_type: str):
    suffix = {
        "Albedo": "BaseColor",
        "Normal": "Normal",
        "Roughness": "Roughness",
    }[texture_type]
    asset_name = f"T_{layer_name}_{suffix}"
    path = f"{TEXTURE_PACKAGE}/{asset_name}.{asset_name}"
    texture = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError(f"Missing required texture: {path}")
    return texture


def get_texture(instance, parameter_name: str):
    return unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
        instance, parameter_name
    )


def get_scalar(instance, parameter_name: str) -> float:
    return float(
        unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
            instance, parameter_name
        )
    )


def set_texture(instance, parameter_name: str, texture) -> None:
    result = unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
        instance, parameter_name, texture
    )
    if result is False:
        raise RuntimeError(f"Sensei rejected texture parameter: {parameter_name}")


def set_scalar(instance, parameter_name: str, value: float) -> None:
    result = unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
        instance, parameter_name, float(value)
    )
    if result is False:
        raise RuntimeError(f"Sensei rejected scalar parameter: {parameter_name}")


def same_asset(left, right) -> bool:
    if left is None or right is None:
        return left is right
    return left.get_path_name() == right.get_path_name()


def restore_previous(instance, previous_textures, previous_scalars) -> None:
    for parameter_name, texture in previous_textures.items():
        if texture is not None:
            unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
                instance, parameter_name, texture
            )
    for parameter_name, value in previous_scalars.items():
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, parameter_name, float(value)
        )
    try:
        instance.post_edit_change()
    except Exception:
        pass
    unreal.EditorAssetLibrary.save_loaded_asset(instance, False)


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before updating terrain textures")
    except AttributeError:
        pass

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")

    instance = definition.get_editor_property("material")
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError(
            "MPD_AetherWorld is not using a MaterialInstanceConstant; no changes were made"
        )
    if instance.get_path_name() != EXPECTED_INSTANCE_PATH:
        raise RuntimeError(
            "Unexpected active terrain material: "
            f"{instance.get_path_name()}. Expected {EXPECTED_INSTANCE_PATH}; no changes were made."
        )

    desired_textures = {}
    for slot, layer_name in LAYER_MAP.items():
        for texture_type, parameter_format in TEXTURE_PARAMETER_FORMATS.items():
            parameter_name = parameter_format.format(slot=slot)
            desired_textures[parameter_name] = load_texture(layer_name, texture_type)

    desired_scalars = {
        f"Normal Strength {slot}": NORMAL_STRENGTH for slot in LAYER_MAP
    }

    # Capture current values so a rejected parameter can be rolled back in the
    # same run instead of leaving a partially configured material instance.
    previous_textures = {
        name: get_texture(instance, name) for name in desired_textures
    }
    previous_scalars = {
        name: get_scalar(instance, name) for name in desired_scalars
    }

    try:
        for parameter_name, texture in desired_textures.items():
            set_texture(instance, parameter_name, texture)
        for parameter_name, value in desired_scalars.items():
            set_scalar(instance, parameter_name, value)

        try:
            instance.post_edit_change()
        except Exception:
            pass

        texture_verified = sum(
            same_asset(get_texture(instance, name), texture)
            for name, texture in desired_textures.items()
        )
        scalar_verified = sum(
            abs(get_scalar(instance, name) - value) <= 0.0001
            for name, value in desired_scalars.items()
        )

        if texture_verified != len(desired_textures):
            raise RuntimeError(
                f"Texture verification failed: {texture_verified}/{len(desired_textures)}"
            )
        if scalar_verified != len(desired_scalars):
            raise RuntimeError(
                f"Scalar verification failed: {scalar_verified}/{len(desired_scalars)}"
            )

        if not unreal.EditorAssetLibrary.save_loaded_asset(instance, False):
            raise RuntimeError(f"Failed to save {EXPECTED_INSTANCE_PATH}")
    except Exception:
        restore_previous(instance, previous_textures, previous_scalars)
        raise

    mapping_lines = [
        f"  {slot}: {layer_name}" for slot, layer_name in LAYER_MAP.items()
    ]
    report = (
        "Aether verified Sensei surface update complete.\n\n"
        f"Material: {instance.get_path_name()}\n"
        f"Texture parameters verified: {texture_verified}/{len(desired_textures)}\n"
        f"Normal-strength parameters verified: {scalar_verified}/{len(desired_scalars)}\n"
        f"Normal strength: {NORMAL_STRENGTH}\n\n"
        "Layer mapping:\n"
        + "\n".join(mapping_lines)
        + "\n\n"
        "Updated maps: Albedo, Normal, Roughness\n"
        "Displacement parameters: unchanged at their existing safe values\n"
        "Terrain geometry, collision, MPD resolution, and streaming: unchanged\n\n"
        "Open AetherWorld, wait for shaders to finish, Save All, and test Play. "
        "Do not rebuild Mesh Partition unless reopened streamed sections still use old textures."
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))
    unreal.EditorDialog.show_message(
        "Aether Verified Surface Updated", report, unreal.AppMsgType.OK
    )


if __name__ == "__main__":
    main()
