"""Create/repair the Sensei instance and disable terrain displacement safely.

This repair handles both the complete and incomplete integration states:

* reuse MI_AetherTerrain_Sensei when it exists;
* otherwise create it from the local Sensei master material;
* reapply Aether's texture/layer/variation mapping from the integration script;
* discover displacement-related parameters when the UE Python API exposes them;
* force every discovered/known displacement scalar to zero;
* disable every discovered/known displacement static switch;
* assign the repaired instance to MPD_AetherWorld.

The original M_MeshTerrain_Aether asset is not changed.
"""

from pathlib import Path
import sys

import unreal


LOG_PREFIX = "[Aether Sensei Displacement Fix]"
SCRIPT_PATH = Path(
    globals().get(
        "__file__",
        unreal.Paths.convert_relative_path_to_full(
            unreal.Paths.project_content_dir()
            + "Python/DisableAetherSenseiDisplacement_UE58.py"
        ),
    )
).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import IntegrateSenseiTerrain_Aether_UE58 as integration  # noqa: E402

AETHER_PACKAGE = "/Game/Aether/MeshTerrain"
INSTANCE_NAME = "MI_AetherTerrain_Sensei"
INSTANCE_PATH = f"{AETHER_PACKAGE}/{INSTANCE_NAME}.{INSTANCE_NAME}"
SENSEI_MASTER_PATH = (
    "/Game/SenseiTerrain/Materials/M_SenseiTerrain.M_SenseiTerrain"
)
DEFINITION_PATH = f"{AETHER_PACKAGE}/MPD_AetherWorld.MPD_AetherWorld"

KNOWN_DISPLACEMENT_SCALARS = {
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

KNOWN_DISPLACEMENT_SWITCHES = (
    "Displacement",
    "Use Displacement?",
    "Enable Displacement?",
    "Nanite Displacement",
    "Use Nanite Displacement?",
)


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def parameter_text(value) -> str:
    try:
        return str(value)
    except Exception:
        return ""


def get_parameter_names(function_name: str, instance):
    getter = getattr(unreal.MaterialEditingLibrary, function_name, None)
    if getter is None:
        return []
    try:
        return list(getter(instance) or [])
    except Exception as exc:
        warn(f"Could not query {function_name}: {exc}")
        return []


def create_or_load_instance(master):
    existing = unreal.EditorAssetLibrary.load_asset(INSTANCE_PATH)
    created = not isinstance(existing, unreal.MaterialInstanceConstant)
    instance = integration.create_or_load_instance(master)
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Could not create Sensei material instance: {INSTANCE_PATH}")
    return instance, created


def set_scalar(instance, name: str, value: float) -> bool:
    try:
        result = unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, name, float(value)
        )
        return result is not False
    except Exception as exc:
        warn(f"Could not set scalar {name}: {exc}")
        return False


def set_switch(instance, name: str, value: bool) -> bool:
    setter = getattr(
        unreal.MaterialEditingLibrary,
        "set_material_instance_static_switch_parameter_value",
        None,
    )
    if setter is None:
        return False
    try:
        result = setter(instance, name, bool(value))
        return result is not False
    except Exception as exc:
        warn(f"Could not set static switch {name}: {exc}")
        return False


def displacement_scalar_names(instance):
    names = set(KNOWN_DISPLACEMENT_SCALARS)
    for raw_name in get_parameter_names("get_scalar_parameter_names", instance):
        name = parameter_text(raw_name)
        lowered = name.lower()
        if "displacement" in lowered or "world position offset" in lowered:
            names.add(name)
    return sorted(names)


def displacement_switch_names(instance):
    names = set(KNOWN_DISPLACEMENT_SWITCHES)
    for raw_name in get_parameter_names("get_static_switch_parameter_names", instance):
        name = parameter_text(raw_name)
        lowered = name.lower()
        if "displacement" in lowered or "world position offset" in lowered:
            names.add(name)
    return sorted(names)


def apply_aether_mapping(instance):
    texture_success = sum(
        integration.set_texture_parameter(instance, parameter, texture)
        for parameter, texture in integration.TEXTURE_PARAMETERS.items()
    )
    scalar_success = sum(
        integration.set_scalar_parameter(instance, parameter, value)
        for parameter, value in integration.SCALAR_PARAMETERS.items()
    )
    switch_success = sum(
        integration.set_static_switch(instance, parameter, enabled)
        for parameter, enabled in integration.STATIC_SWITCH_PARAMETERS.items()
    )
    return texture_success, scalar_success, switch_success


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before applying the displacement fix")
    except AttributeError:
        pass

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")

    master = unreal.EditorAssetLibrary.load_asset(SENSEI_MASTER_PATH)
    if not isinstance(master, unreal.Material):
        current_material = None
        try:
            current_material = definition.get_editor_property("material")
        except Exception:
            pass
        if isinstance(current_material, unreal.Material):
            master = current_material
            warn(
                "The expected Sensei master path was not found; using the material "
                "currently assigned to MPD_AetherWorld as the instance parent"
            )
        else:
            raise RuntimeError(
                "Missing Sensei master material. Re-run INSTALL_SENSEI_TERRAIN_ASSETS.ps1 "
                f"and verify: {SENSEI_MASTER_PATH}"
            )

    instance, created = create_or_load_instance(master)
    mapped_textures, mapped_scalars, mapped_switches = apply_aether_mapping(instance)

    scalar_names = displacement_scalar_names(instance)
    switch_names = displacement_switch_names(instance)
    displacement_scalars = sum(
        set_scalar(instance, name, 0.0) for name in scalar_names
    )
    displacement_switches = sum(
        set_switch(instance, name, False) for name in switch_names
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
        "Sensei material instance created and repaired.\n\n"
        f"Created missing instance: {created}\n"
        f"Aether textures mapped: "
        f"{mapped_textures}/{len(integration.TEXTURE_PARAMETERS)}\n"
        f"Aether scalar settings applied: "
        f"{mapped_scalars}/{len(integration.SCALAR_PARAMETERS)}\n"
        f"Aether layer switches applied: "
        f"{mapped_switches}/{len(integration.STATIC_SWITCH_PARAMETERS)}\n"
        f"Displacement scalars forced to zero: "
        f"{displacement_scalars}/{len(scalar_names)}\n"
        f"Displacement switches disabled: "
        f"{displacement_switches}/{len(switch_names)}\n"
        f"Assigned material: {INSTANCE_PATH}\n\n"
        "Close this dialog and test Play mode before rebuilding Mesh Partition."
    )
    log(message.replace("\n", " | "))
    unreal.EditorDialog.show_message(
        "Aether Sensei Instance Repaired",
        message,
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
