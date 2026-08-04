"""Create and activate a safely tuned copy of Aether's working Sensei terrain instance.

This pass keeps the verified Aether texture overrides and changes only audited,
global scalar controls on a duplicate material instance. The working
MI_AetherTerrain_Sensei_Surface asset remains untouched as rollback.

UE 5.8's MaterialEditingLibrary setter rejects several Sensei parameters even
though the parent reports them as valid Global parameters. This script therefore
authors normal FScalarParameterValue override structs directly on the duplicate,
then asks the compiled material instance for every value and aborts unless all
values round-trip correctly.

No terrain geometry, collision, Mesh Partition resolution, channels,
displacement, WPO, transformer pipelines, or streaming settings are changed.
"""

from pathlib import Path

import unreal


LOG_PREFIX = "[Aether Sensei Biome Tuning]"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
SOURCE_PACKAGE = "/Game/Aether/MeshTerrain/MI_AetherTerrain_Sensei_Surface"
SOURCE_PATH = SOURCE_PACKAGE + ".MI_AetherTerrain_Sensei_Surface"
TARGET_PACKAGE = "/Game/Aether/MeshTerrain/MI_AetherTerrain_Sensei_BiomeTuned"
TARGET_PATH = TARGET_PACKAGE + ".MI_AetherTerrain_Sensei_BiomeTuned"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSenseiBiomeTuningReport.txt"
TEXTURE_PACKAGE = "/Game/Aether/ProductionTerrain/Textures"
GLOBAL = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER

# Conservative profile based only on controls proven by the read-only audit.
# It sharpens slope-driven rock/scree separation, broadens the forest/snow
# transitions, reduces visible large-scale repetition, and balances normals.
TUNING_PROFILE = {
    "AB Blend Contrast": 0.22,
    "BC Blend Contrast": 0.18,
    "CD Blend Contrast": 0.10,
    "DE Blend Contrast": 0.16,
    "Angle Contrast B": 1.35,
    "Angle Contrast C": 1.20,
    "Blend Falloff A": 1400.0,
    "Blend Falloff B": 900.0,
    "Blend Falloff C": 1050.0,
    "Blend Falloff D": 1700.0,
    "Blend Falloff E": 1900.0,
    "MacroVariationAmount": 0.62,
    "MacroVariationSize": 0.75,
    "Color Variation Amount": 0.34,
    "Normal Variation Strength": 0.30,
    "Normal Strength A": 0.82,
    "Normal Strength B": 0.88,
    "Normal Strength C": 0.84,
    "Normal Strength D": 0.80,
    "Normal Strength E": 0.76,
    "Triplanar Sharpness A": 4.50,
    "Triplanar Sharpness B": 5.50,
    "Triplanar Sharpness C": 5.00,
    "Triplanar Sharpness D": 4.25,
    "Triplanar Sharpness E": 4.75,
}

EXPECTED_TEXTURES = {
    "Albedo Color A": f"{TEXTURE_PACKAGE}/T_Grass_BaseColor.T_Grass_BaseColor",
    "Normal A": f"{TEXTURE_PACKAGE}/T_Grass_Normal.T_Grass_Normal",
    "Roughness A": f"{TEXTURE_PACKAGE}/T_Grass_Roughness.T_Grass_Roughness",
    "Albedo Color B": f"{TEXTURE_PACKAGE}/T_Rock_BaseColor.T_Rock_BaseColor",
    "Normal B": f"{TEXTURE_PACKAGE}/T_Rock_Normal.T_Rock_Normal",
    "Roughness B": f"{TEXTURE_PACKAGE}/T_Rock_Roughness.T_Rock_Roughness",
    "Albedo Color C": f"{TEXTURE_PACKAGE}/T_Scree_BaseColor.T_Scree_BaseColor",
    "Normal C": f"{TEXTURE_PACKAGE}/T_Scree_Normal.T_Scree_Normal",
    "Roughness C": f"{TEXTURE_PACKAGE}/T_Scree_Roughness.T_Scree_Roughness",
    "Albedo Color D": f"{TEXTURE_PACKAGE}/T_ForestFloor_BaseColor.T_ForestFloor_BaseColor",
    "Normal D": f"{TEXTURE_PACKAGE}/T_ForestFloor_Normal.T_ForestFloor_Normal",
    "Roughness D": f"{TEXTURE_PACKAGE}/T_ForestFloor_Roughness.T_ForestFloor_Roughness",
    "Albedo Color E": f"{TEXTURE_PACKAGE}/T_Snow_BaseColor.T_Snow_BaseColor",
    "Normal E": f"{TEXTURE_PACKAGE}/T_Snow_Normal.T_Snow_Normal",
    "Roughness E": f"{TEXTURE_PACKAGE}/T_Snow_Roughness.T_Snow_Roughness",
}

DISPLACEMENT_PREFIXES = (
    "Displacement Amount",
    "Displacement Strength",
    "Displacement Offset",
    "Displacement Scale",
    "Displacement Contrast",
    "Nanite Displacement Magnitude",
)


def log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def path_of(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def parameter_name(entry):
    info = entry.get_editor_property("parameter_info")
    return str(info.get_editor_property("name"))


def verify_textures(instance):
    lines = []
    passed = 0
    for name, expected_path in EXPECTED_TEXTURES.items():
        actual = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
            instance, name, GLOBAL
        )
        actual_path = path_of(actual)
        ok = actual_path == expected_path
        passed += int(ok)
        lines.append(f"  {'PASS' if ok else 'FAIL'} {name}: {actual_path}")
    return passed, lines


def verify_displacement(instance):
    checked = 0
    unsafe = {}
    for entry in list(instance.get_editor_property("scalar_parameter_values") or []):
        name = parameter_name(entry)
        if not name.startswith(DISPLACEMENT_PREFIXES):
            continue
        checked += 1
        value = float(entry.get_editor_property("parameter_value"))
        if abs(value) > 0.0001:
            unsafe[name] = value
    return checked, unsafe


def make_scalar_override(name, value):
    info = unreal.MaterialParameterInfo(
        name=unreal.Name(name),
        association=GLOBAL,
        index=-1,
    )
    return unreal.ScalarParameterValue(
        parameter_info=info,
        parameter_value=float(value),
    )


def apply_scalar_override_structs(instance):
    """Replace only profile-owned scalar overrides on the duplicate.

    Sensei's parent exposes these names, but MaterialEditingLibrary returns
    False for some of them. Writing Unreal's normal ScalarParameterValue array
    is equivalent to checking the override box in the Material Instance editor.
    """
    existing = list(instance.get_editor_property("scalar_parameter_values") or [])
    preserved = [entry for entry in existing if parameter_name(entry) not in TUNING_PROFILE]
    authored = [make_scalar_override(name, value) for name, value in TUNING_PROFILE.items()]
    instance.set_editor_property("scalar_parameter_values", preserved + authored)

    try:
        instance.post_edit_change()
    except Exception:
        pass
    updater = getattr(unreal.MaterialEditingLibrary, "update_material_instance", None)
    if updater is not None:
        updater(instance)

    return len(existing), len(preserved), len(authored)


def verify_scalar_profile(instance):
    verified = {}
    failures = []
    for name, expected in TUNING_PROFILE.items():
        actual = float(
            unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
                instance,
                name,
                GLOBAL,
            )
        )
        if abs(actual - float(expected)) > 0.0001:
            failures.append(f"{name}: expected {expected}, got {actual}")
        else:
            verified[name] = actual
    if failures:
        raise RuntimeError(
            "Direct scalar override verification failed: " + "; ".join(failures)
        )
    return verified


def save_asset(asset, description):
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, False):
        raise RuntimeError(f"Failed to save {description}: {path_of(asset)}")


def reload_saved_asset(asset, object_path, description):
    """Reload a saved package with the UE 5.8 editor loading API."""
    reload_method = getattr(unreal.EditorLoadingAndSavingUtils, "reload_packages", None)
    if reload_method is None:
        raise RuntimeError("EditorLoadingAndSavingUtils.reload_packages is unavailable")

    package = asset.get_outermost()
    result = reload_method(
        [package],
        unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE,
    )

    if isinstance(result, tuple):
        reloaded = bool(result[0])
        error_message = str(result[1]) if len(result) > 1 else ""
    else:
        reloaded = bool(result)
        error_message = ""

    if not reloaded:
        suffix = f": {error_message}" if error_message else ""
        raise RuntimeError(f"Failed to reload {description}{suffix}")

    reloaded_asset = unreal.EditorAssetLibrary.load_asset(object_path)
    if reloaded_asset is None:
        raise RuntimeError(f"Reloaded {description} could not be loaded: {object_path}")
    return reloaded_asset


def restore_definition(definition, source):
    definition.set_editor_property("material", source)
    save_asset(definition, "Mesh Partition definition rollback")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before tuning terrain biomes")
    except AttributeError:
        pass

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    source = unreal.EditorAssetLibrary.load_asset(SOURCE_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")
    if not isinstance(source, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Missing working Sensei surface instance: {SOURCE_PATH}")

    active_before = definition.get_editor_property("material")
    active_before_path = path_of(active_before)
    if active_before_path not in (SOURCE_PATH, TARGET_PATH):
        raise RuntimeError(
            f"Unexpected active terrain material: {active_before_path}. "
            "Restore MI_AetherTerrain_Sensei_Surface before tuning."
        )

    # Deterministic rerun: restore the known-good source before replacing an
    # older tuned copy.
    if unreal.EditorAssetLibrary.does_asset_exist(TARGET_PACKAGE):
        if active_before_path == TARGET_PATH:
            restore_definition(definition, source)
        if not unreal.EditorAssetLibrary.delete_asset(TARGET_PACKAGE):
            raise RuntimeError(f"Could not replace previous tuned copy: {TARGET_PACKAGE}")

    target = unreal.EditorAssetLibrary.duplicate_asset(SOURCE_PACKAGE, TARGET_PACKAGE)
    if not isinstance(target, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Could not duplicate {SOURCE_PACKAGE} to {TARGET_PACKAGE}")

    assigned = False
    try:
        texture_passed, texture_lines = verify_textures(target)
        if texture_passed != len(EXPECTED_TEXTURES):
            raise RuntimeError(
                f"Source texture verification failed: {texture_passed}/{len(EXPECTED_TEXTURES)}"
            )

        existing_count, preserved_count, authored_count = apply_scalar_override_structs(target)
        applied = verify_scalar_profile(target)

        displacement_checked, unsafe = verify_displacement(target)
        if unsafe:
            detail = ", ".join(
                f"{name}={value}" for name, value in sorted(unsafe.items())
            )
            raise RuntimeError(f"Unsafe displacement values found: {detail}")

        save_asset(target, "tuned Sensei material instance")

        # Reload and verify from the serialized package before assigning it.
        target = reload_saved_asset(
            target,
            TARGET_PATH,
            "tuned Sensei material instance",
        )
        if not isinstance(target, unreal.MaterialInstanceConstant):
            raise RuntimeError(f"Reloaded asset has the wrong type: {TARGET_PATH}")
        applied = verify_scalar_profile(target)
        texture_passed, texture_lines = verify_textures(target)
        if texture_passed != len(EXPECTED_TEXTURES):
            raise RuntimeError(
                f"Reloaded texture verification failed: {texture_passed}/{len(EXPECTED_TEXTURES)}"
            )

        definition.set_editor_property("material", target)
        save_asset(definition, "Mesh Partition definition")
        assigned = True
    except Exception:
        if assigned or path_of(definition.get_editor_property("material")) == TARGET_PATH:
            restore_definition(definition, source)
        if unreal.EditorAssetLibrary.does_asset_exist(TARGET_PACKAGE):
            unreal.EditorAssetLibrary.delete_asset(TARGET_PACKAGE)
        raise

    tuning_lines = [f"  {name}: {value}" for name, value in applied.items()]
    report = (
        "Aether Sensei biome tuning complete.\n\n"
        f"Before: {active_before_path}\n"
        f"After: {TARGET_PATH}\n"
        f"Rollback preserved: {SOURCE_PATH}\n"
        f"Texture parameters verified: {texture_passed}/{len(EXPECTED_TEXTURES)}\n"
        f"Scalar controls verified after reload: {len(applied)}/{len(TUNING_PROFILE)}\n"
        f"Previous scalar overrides: {existing_count}\n"
        f"Preserved scalar overrides: {preserved_count}\n"
        f"Profile overrides authored: {authored_count}\n"
        f"Displacement overrides checked: {displacement_checked}\n"
        "Unsafe displacement values: 0\n\n"
        "Applied balanced profile:\n"
        + "\n".join(tuning_lines)
        + "\n\nTexture verification:\n"
        + "\n".join(texture_lines)
        + "\n\n"
        "Expected visible change: more defined rock/scree slopes, broader natural "
        "forest and snow transitions, reduced macro repetition, and balanced surface normals.\n"
        "No terrain geometry, collision, Mesh Partition resolution, channels, displacement, "
        "or streaming setting was changed."
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))


if __name__ == "__main__":
    main()
