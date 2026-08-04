"""Apply verified Aether textures to the installed Sensei Terrain instance.

The exact parameter names in this file come from the read-only UE 5.8 audit of
MI_AetherTerrain_Sensei. The updater now discovers the association used by each
parameter (Global, Layer, or Blend) before applying an override. This is needed
because the audited Sensei parameters are not writable through UE's default
GLOBAL_PARAMETER association.

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

LAYER_MAP = {
    "A": "Grass",
    "B": "Rock",
    "C": "Scree",
    "D": "ForestFloor",
    "E": "Snow",
}

TEXTURE_PARAMETER_FORMATS = {
    "Albedo": "Albedo Color {slot}",
    "Normal": "Normal {slot}",
    "Roughness": "Roughness {slot}",
}
NORMAL_STRENGTH = 0.78

ASSOCIATIONS = (
    ("Global", unreal.MaterialParameterAssociation.GLOBAL_PARAMETER),
    ("Layer", unreal.MaterialParameterAssociation.LAYER_PARAMETER),
    ("Blend", unreal.MaterialParameterAssociation.BLEND_PARAMETER),
)


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


def texture_value(instance, parameter_name: str, association):
    return unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
        instance, parameter_name, association
    )


def scalar_value(instance, parameter_name: str, association) -> float:
    return float(
        unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
            instance, parameter_name, association
        )
    )


def is_overridden(instance, parameter_name: str, association) -> bool:
    getter = getattr(
        unreal.MaterialEditingLibrary,
        "is_material_instance_parameter_overridden",
        None,
    )
    if getter is None:
        return False
    try:
        return bool(getter(instance, parameter_name, association))
    except Exception:
        return False


def set_override(instance, parameter_name: str, enabled: bool, association) -> None:
    setter = getattr(
        unreal.MaterialEditingLibrary,
        "set_material_instance_parameter_override",
        None,
    )
    if setter is not None:
        setter(instance, parameter_name, bool(enabled), association)


def same_asset(left, right) -> bool:
    if left is None or right is None:
        return left is right
    return left.get_path_name() == right.get_path_name()


def apply_texture(instance, parameter_name: str, desired_texture):
    attempts = []
    for association_name, association in ASSOCIATIONS:
        previous = texture_value(instance, parameter_name, association)
        previous_override = is_overridden(instance, parameter_name, association)
        result = unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
            instance, parameter_name, desired_texture, association
        )
        attempts.append(f"{association_name}={result}")
        if result:
            return {
                "kind": "texture",
                "name": parameter_name,
                "association_name": association_name,
                "association": association,
                "previous": previous,
                "previous_override": previous_override,
                "desired": desired_texture,
            }
    raise RuntimeError(
        f"Sensei rejected texture parameter {parameter_name} for all associations "
        f"({', '.join(attempts)})"
    )


def apply_scalar(instance, parameter_name: str, desired_value: float):
    attempts = []
    for association_name, association in ASSOCIATIONS:
        previous = scalar_value(instance, parameter_name, association)
        previous_override = is_overridden(instance, parameter_name, association)
        result = unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            instance, parameter_name, float(desired_value), association
        )
        attempts.append(f"{association_name}={result}")
        if result:
            return {
                "kind": "scalar",
                "name": parameter_name,
                "association_name": association_name,
                "association": association,
                "previous": previous,
                "previous_override": previous_override,
                "desired": float(desired_value),
            }
    raise RuntimeError(
        f"Sensei rejected scalar parameter {parameter_name} for all associations "
        f"({', '.join(attempts)})"
    )


def verify_state(instance, state) -> bool:
    if state["kind"] == "texture":
        return same_asset(
            texture_value(instance, state["name"], state["association"]),
            state["desired"],
        )
    return (
        abs(
            scalar_value(instance, state["name"], state["association"])
            - state["desired"]
        )
        <= 0.0001
    )


def restore_states(instance, states) -> None:
    for state in reversed(states):
        name = state["name"]
        association = state["association"]
        if state["previous_override"]:
            if state["kind"] == "texture":
                previous = state["previous"]
                if previous is not None:
                    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
                        instance, name, previous, association
                    )
            else:
                unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
                    instance, name, float(state["previous"]), association
                )
            set_override(instance, name, True, association)
        else:
            set_override(instance, name, False, association)

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

    applied_states = []
    try:
        for parameter_name, texture in desired_textures.items():
            applied_states.append(apply_texture(instance, parameter_name, texture))
        for parameter_name, value in desired_scalars.items():
            applied_states.append(apply_scalar(instance, parameter_name, value))

        try:
            instance.post_edit_change()
        except Exception:
            pass

        verified = sum(verify_state(instance, state) for state in applied_states)
        if verified != len(applied_states):
            raise RuntimeError(
                f"Parameter verification failed: {verified}/{len(applied_states)}"
            )

        if not unreal.EditorAssetLibrary.save_loaded_asset(instance, False):
            raise RuntimeError(f"Failed to save {EXPECTED_INSTANCE_PATH}")
    except Exception:
        restore_states(instance, applied_states)
        raise

    association_counts = {}
    for state in applied_states:
        key = state["association_name"]
        association_counts[key] = association_counts.get(key, 0) + 1
    association_lines = [
        f"  {name}: {count}" for name, count in sorted(association_counts.items())
    ]
    mapping_lines = [
        f"  {slot}: {layer_name}" for slot, layer_name in LAYER_MAP.items()
    ]

    report = (
        "Aether verified Sensei surface update complete.\n\n"
        f"Material: {instance.get_path_name()}\n"
        f"Parameters verified: {verified}/{len(applied_states)}\n"
        f"Texture parameters: {len(desired_textures)}\n"
        f"Normal-strength parameters: {len(desired_scalars)}\n"
        f"Normal strength: {NORMAL_STRENGTH}\n\n"
        "Resolved parameter associations:\n"
        + "\n".join(association_lines)
        + "\n\nLayer mapping:\n"
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
