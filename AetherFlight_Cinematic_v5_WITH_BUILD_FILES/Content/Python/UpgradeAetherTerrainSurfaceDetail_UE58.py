"""Repair the Aether/Sensei terrain texture overrides on a safe duplicate.

The UE 5.8 parameter-info audit found the exact problem:
- Sensei expects: Albedo Color A-E, Normal A-E, Roughness A-E.
- MI_AetherTerrain_Sensei contains the correct Aether textures, but its stored
  override names are stale: Color Texture A-E, Normal Texture A-E, and
  Roughness Texture A-E.

Because the normal MaterialEditingLibrary setter rejects these nested Sensei
parameters, this script duplicates the material instance, renames the existing
FMaterialParameterInfo entries on the duplicate, verifies all 15 values through
Sensei's real parameter names, and only then assigns the duplicate to
MPD_AetherWorld. The original instance remains untouched as rollback.
"""

from pathlib import Path

import unreal


LOG_PREFIX = "[Aether Sensei Surface Repair]"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
SOURCE_INSTANCE_PACKAGE = "/Game/Aether/MeshTerrain/MI_AetherTerrain_Sensei"
SOURCE_INSTANCE_PATH = SOURCE_INSTANCE_PACKAGE + ".MI_AetherTerrain_Sensei"
TARGET_INSTANCE_PACKAGE = "/Game/Aether/MeshTerrain/MI_AetherTerrain_Sensei_Surface"
TARGET_INSTANCE_PATH = TARGET_INSTANCE_PACKAGE + ".MI_AetherTerrain_Sensei_Surface"
TEXTURE_PACKAGE = "/Game/Aether/ProductionTerrain/Textures"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSurfaceDetailReport.txt"

LAYER_MAP = {
    "A": "Grass",
    "B": "Rock",
    "C": "Scree",
    "D": "ForestFloor",
    "E": "Snow",
}

RENAME_MAP = {}
EXPECTED_TEXTURES = {}
for slot, layer_name in LAYER_MAP.items():
    RENAME_MAP[f"Color Texture {slot}"] = f"Albedo Color {slot}"
    RENAME_MAP[f"Normal Texture {slot}"] = f"Normal {slot}"
    RENAME_MAP[f"Roughness Texture {slot}"] = f"Roughness {slot}"

    EXPECTED_TEXTURES[f"Albedo Color {slot}"] = (
        f"{TEXTURE_PACKAGE}/T_{layer_name}_BaseColor.T_{layer_name}_BaseColor"
    )
    EXPECTED_TEXTURES[f"Normal {slot}"] = (
        f"{TEXTURE_PACKAGE}/T_{layer_name}_Normal.T_{layer_name}_Normal"
    )
    EXPECTED_TEXTURES[f"Roughness {slot}"] = (
        f"{TEXTURE_PACKAGE}/T_{layer_name}_Roughness.T_{layer_name}_Roughness"
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


def rename_texture_override_entries(instance) -> tuple[int, list[str]]:
    entries = list(instance.get_editor_property("texture_parameter_values") or [])
    renamed = 0
    seen = []

    for entry in entries:
        old_name = parameter_name(entry)
        new_name = RENAME_MAP.get(old_name)
        if not new_name:
            continue

        info = entry.get_editor_property("parameter_info")
        info.set_editor_property("name", new_name)
        info.set_editor_property(
            "association", unreal.MaterialParameterAssociation.GLOBAL_PARAMETER
        )
        info.set_editor_property("index", -1)
        entry.set_editor_property("parameter_info", info)
        renamed += 1
        seen.append(f"{old_name} -> {new_name}")

    if renamed != len(RENAME_MAP):
        raise RuntimeError(
            f"Expected {len(RENAME_MAP)} stale texture overrides but found {renamed}"
        )

    instance.set_editor_property("texture_parameter_values", entries)
    try:
        instance.post_edit_change()
    except Exception:
        pass

    updater = getattr(unreal.MaterialEditingLibrary, "update_material_instance", None)
    if updater is not None:
        updater(instance)

    return renamed, seen


def verify_texture_parameters(instance) -> tuple[int, list[str]]:
    passed = 0
    lines = []
    for parameter_name_value, expected_path in EXPECTED_TEXTURES.items():
        actual = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
            instance,
            parameter_name_value,
            unreal.MaterialParameterAssociation.GLOBAL_PARAMETER,
        )
        actual_path = asset_path(actual)
        ok = actual_path == expected_path
        passed += int(ok)
        lines.append(
            f"  {'PASS' if ok else 'FAIL'} {parameter_name_value}: {actual_path}"
        )
    return passed, lines


def unsafe_displacement_values(instance) -> dict[str, float]:
    prefixes = (
        "Displacement Amount",
        "Displacement Strength",
        "Displacement Offset",
        "Displacement Scale",
        "Nanite Displacement Magnitude",
        "Displacement Contrast",
    )
    result = {}
    for entry in list(instance.get_editor_property("scalar_parameter_values") or []):
        name = parameter_name(entry)
        if not name.startswith(prefixes):
            continue
        value = float(entry.get_editor_property("parameter_value"))
        if abs(value) > 0.0001:
            result[name] = value
    return result


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before repairing terrain textures")
    except AttributeError:
        pass

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    source = unreal.EditorAssetLibrary.load_asset(SOURCE_INSTANCE_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")
    if not isinstance(source, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Missing source material instance: {SOURCE_INSTANCE_PATH}")

    active_before = definition.get_editor_property("material")
    active_before_path = asset_path(active_before)
    if active_before_path not in (SOURCE_INSTANCE_PATH, TARGET_INSTANCE_PATH):
        raise RuntimeError(
            f"Unexpected active terrain material: {active_before_path}. No changes were made."
        )

    # Recreate the target from the known source every run so the operation is
    # deterministic and the original remains an untouched rollback asset.
    if unreal.EditorAssetLibrary.does_asset_exist(TARGET_INSTANCE_PACKAGE):
        if active_before_path == TARGET_INSTANCE_PATH:
            definition.set_editor_property("material", source)
            try:
                definition.post_edit_change()
            except Exception:
                pass
            unreal.EditorAssetLibrary.save_loaded_asset(definition, False)
        unreal.EditorAssetLibrary.delete_asset(TARGET_INSTANCE_PACKAGE)

    target = unreal.EditorAssetLibrary.duplicate_asset(
        SOURCE_INSTANCE_PACKAGE, TARGET_INSTANCE_PACKAGE
    )
    if not isinstance(target, unreal.MaterialInstanceConstant):
        raise RuntimeError(
            f"Could not duplicate {SOURCE_INSTANCE_PACKAGE} to {TARGET_INSTANCE_PACKAGE}"
        )

    assigned = False
    try:
        renamed, rename_lines = rename_texture_override_entries(target)
        passed, verification_lines = verify_texture_parameters(target)
        if passed != len(EXPECTED_TEXTURES):
            raise RuntimeError(
                f"Texture verification failed: {passed}/{len(EXPECTED_TEXTURES)}"
            )

        unsafe = unsafe_displacement_values(target)
        if unsafe:
            details = ", ".join(
                f"{name}={value}" for name, value in sorted(unsafe.items())
            )
            raise RuntimeError(f"Unsafe displacement values found: {details}")

        if not unreal.EditorAssetLibrary.save_loaded_asset(target, False):
            raise RuntimeError(f"Failed to save repaired instance: {TARGET_INSTANCE_PATH}")

        definition.set_editor_property("material", target)
        try:
            definition.post_edit_change()
        except Exception:
            pass
        if not unreal.EditorAssetLibrary.save_loaded_asset(definition, False):
            raise RuntimeError(f"Failed to save Mesh Partition definition: {DEFINITION_PATH}")
        assigned = True
    except Exception:
        if assigned or asset_path(definition.get_editor_property("material")) == TARGET_INSTANCE_PATH:
            definition.set_editor_property("material", source)
            try:
                definition.post_edit_change()
            except Exception:
                pass
            unreal.EditorAssetLibrary.save_loaded_asset(definition, False)
        if unreal.EditorAssetLibrary.does_asset_exist(TARGET_INSTANCE_PACKAGE):
            unreal.EditorAssetLibrary.delete_asset(TARGET_INSTANCE_PACKAGE)
        raise

    report = (
        "Aether Sensei surface repair complete.\n\n"
        f"Before: {active_before_path}\n"
        f"After: {TARGET_INSTANCE_PATH}\n"
        f"Override entries renamed: {renamed}/{len(RENAME_MAP)}\n"
        f"Texture parameters verified: {passed}/{len(EXPECTED_TEXTURES)}\n"
        "Unsafe displacement values: 0\n\n"
        "Renamed overrides:\n"
        + "\n".join(f"  {line}" for line in rename_lines)
        + "\n\nVerification:\n"
        + "\n".join(verification_lines)
        + "\n\n"
        "The original MI_AetherTerrain_Sensei remains untouched as rollback.\n"
        "Terrain geometry, collision, Mesh Partition resolution, and streaming were not changed.\n"
        "Open AetherWorld, wait for shaders to finish, Save All, and test Play."
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))


if __name__ == "__main__":
    main()
