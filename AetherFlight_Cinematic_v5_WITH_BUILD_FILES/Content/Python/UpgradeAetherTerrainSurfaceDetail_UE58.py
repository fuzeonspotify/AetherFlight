"""Verify the existing Aether/Sensei terrain surface configuration.

The parameter-info audit proved that MI_AetherTerrain_Sensei already contains
all 15 desired Aether texture overrides. They are stored under the instance
override names "Color Texture", "Normal Texture", and "Roughness Texture",
not under the parent material display names previously targeted by this script.

This script is intentionally read-only. It validates the current overrides,
confirms displacement remains disabled, writes a completion report, and does
not modify or save any Unreal asset.
"""

from pathlib import Path

import unreal


LOG_PREFIX = "[Aether Surface Verification]"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
EXPECTED_INSTANCE_PATH = (
    "/Game/Aether/MeshTerrain/MI_AetherTerrain_Sensei.MI_AetherTerrain_Sensei"
)
TEXTURE_PACKAGE = "/Game/Aether/ProductionTerrain/Textures"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSurfaceDetailReport.txt"

LAYER_MAP = {
    "A": "Grass",
    "B": "Rock",
    "C": "Scree",
    "D": "ForestFloor",
    "E": "Snow",
}

EXPECTED_TEXTURES = {}
for slot, layer_name in LAYER_MAP.items():
    EXPECTED_TEXTURES[f"Color Texture {slot}"] = (
        f"{TEXTURE_PACKAGE}/T_{layer_name}_BaseColor.T_{layer_name}_BaseColor"
    )
    EXPECTED_TEXTURES[f"Normal Texture {slot}"] = (
        f"{TEXTURE_PACKAGE}/T_{layer_name}_Normal.T_{layer_name}_Normal"
    )
    EXPECTED_TEXTURES[f"Roughness Texture {slot}"] = (
        f"{TEXTURE_PACKAGE}/T_{layer_name}_Roughness.T_{layer_name}_Roughness"
    )

DISPLACEMENT_PREFIXES = (
    "Displacement Amount",
    "Displacement Strength",
    "Displacement Offset",
    "Displacement Scale",
    "Nanite Displacement Magnitude",
    "Displacement Contrast",
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


def parameter_name(entry) -> str:
    info = entry.get_editor_property("parameter_info")
    return str(info.get_editor_property("name"))


def texture_overrides(instance):
    result = {}
    for entry in list(instance.get_editor_property("texture_parameter_values") or []):
        result[parameter_name(entry)] = asset_path(
            entry.get_editor_property("parameter_value")
        )
    return result


def scalar_overrides(instance):
    result = {}
    for entry in list(instance.get_editor_property("scalar_parameter_values") or []):
        result[parameter_name(entry)] = float(
            entry.get_editor_property("parameter_value")
        )
    return result


def main() -> None:
    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")

    instance = definition.get_editor_property("material")
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError(
            f"MPD_AetherWorld is not using a material instance: {asset_path(instance)}"
        )
    if instance.get_path_name() != EXPECTED_INSTANCE_PATH:
        raise RuntimeError(
            f"Unexpected active terrain material: {instance.get_path_name()}"
        )

    actual_textures = texture_overrides(instance)
    texture_results = []
    passed = 0
    for name, expected_path in EXPECTED_TEXTURES.items():
        actual_path = actual_textures.get(name, "Missing")
        ok = actual_path == expected_path
        passed += int(ok)
        texture_results.append(
            f"  {'PASS' if ok else 'FAIL'} {name}: {actual_path}"
        )

    actual_scalars = scalar_overrides(instance)
    displacement_values = {
        name: value
        for name, value in actual_scalars.items()
        if name.startswith(DISPLACEMENT_PREFIXES)
    }
    unsafe_displacement = {
        name: value
        for name, value in displacement_values.items()
        if abs(value) > 0.0001
    }

    report = (
        "Aether terrain surface verification complete.\n\n"
        f"Material: {instance.get_path_name()}\n"
        f"Texture overrides verified: {passed}/{len(EXPECTED_TEXTURES)}\n"
        f"Displacement overrides checked: {len(displacement_values)}\n"
        f"Unsafe displacement values: {len(unsafe_displacement)}\n\n"
        "Texture override results:\n"
        + "\n".join(texture_results)
        + "\n\n"
        "Conclusion: the Aether BaseColor, Normal, and Roughness maps are already "
        "installed on all five Sensei layers. No material update or Mesh Partition "
        "rebuild is required for surface detail.\n\n"
        "No Unreal asset was modified or saved."
    )

    if passed != len(EXPECTED_TEXTURES):
        raise RuntimeError(
            f"Surface verification failed: {passed}/{len(EXPECTED_TEXTURES)} texture overrides"
        )
    if unsafe_displacement:
        details = ", ".join(
            f"{name}={value}" for name, value in sorted(unsafe_displacement.items())
        )
        raise RuntimeError(f"Unsafe displacement values found: {details}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))


if __name__ == "__main__":
    main()
