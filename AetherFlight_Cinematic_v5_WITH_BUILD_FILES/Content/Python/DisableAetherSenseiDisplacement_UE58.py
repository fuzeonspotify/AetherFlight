"""Disable Sensei Terrain displacement for AetherFlight Mesh Terrain.

Sensei Terrain enables displacement features intended for conventional Nanite
surfaces. On AetherFlight's very large Mesh Terrain sections those defaults can
produce extreme section-edge walls, mesas, and spikes. This patch preserves the
Sensei surface shading while forcing all displacement contribution to zero.
"""

import unreal


LOG_PREFIX = "[Aether Sensei Displacement Fix]"
INSTANCE_PATH = "/Game/Aether/MeshTerrain/MI_AetherTerrain_Sensei.MI_AetherTerrain_Sensei"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"

DISPLACEMENT_SCALARS = {
    **{f"Displacement Amount {layer}": 0.0 for layer in "ABCDE"},
    **{f"Displacement Strength {layer}": 0.0 for layer in "ABCDE"},
    **{f"Displacement Offset {layer}": 0.0 for layer in "ABCDE"},
}


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def set_scalar(instance, name: str, value: float) -> bool:
    try:
        result = unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, name, float(value)
        )
        if result is False:
            warn(f"Parameter not accepted: {name}")
            return False
        return True
    except Exception as exc:
        warn(f"Could not set {name}: {exc}")
        return False


def set_switch(instance, name: str, value: bool) -> bool:
    setter = getattr(
        unreal.MaterialEditingLibrary,
        "set_material_instance_static_switch_parameter_value",
        None,
    )
    if setter is None:
        warn("Static-switch editing is unavailable; scalar zeroing will still disable movement")
        return False
    try:
        result = setter(instance, name, bool(value))
        if result is False:
            warn(f"Static switch not accepted: {name}")
            return False
        return True
    except Exception as exc:
        warn(f"Could not set static switch {name}: {exc}")
        return False


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before applying the displacement fix")
    except AttributeError:
        pass

    instance = unreal.EditorAssetLibrary.load_asset(INSTANCE_PATH)
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Missing Sensei material instance: {INSTANCE_PATH}")

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")

    scalar_success = sum(
        set_scalar(instance, name, value)
        for name, value in DISPLACEMENT_SCALARS.items()
    )
    switch_success = set_switch(instance, "Displacement", False)

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

    message = (
        "Sensei displacement disabled for AetherFlight.\n\n"
        f"Zeroed displacement parameters: {scalar_success}/{len(DISPLACEMENT_SCALARS)}\n"
        f"Displacement static switch disabled: {switch_success}\n\n"
        "Test Play mode first. Rebuild Mesh Partition only if the old geometry artifacts remain."
    )
    log(message.replace("\n", " | "))
    unreal.EditorDialog.show_message(
        "Aether Sensei Displacement Fixed",
        message,
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
