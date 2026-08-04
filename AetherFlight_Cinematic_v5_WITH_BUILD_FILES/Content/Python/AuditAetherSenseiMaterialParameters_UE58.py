"""Inventory the actual parameters exposed by AetherWorld's active terrain material.

This script is read-only. It does not change the material instance, its parent,
MPD_AetherWorld, terrain geometry, collision, Mesh Partition data, or shaders.
The report is used to replace guessed Sensei parameter names with the names that
UE 5.8 actually exposes for the installed asset version.
"""

from pathlib import Path

import unreal


LOG_PREFIX = "[Aether Sensei Parameter Audit]"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSenseiParameterAudit.txt"


def safe_path(value) -> str:
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def safe_source(getter_name: str, material, parameter_name) -> str:
    getter = getattr(unreal.MaterialEditingLibrary, getter_name, None)
    if getter is None:
        return "Unavailable"
    try:
        source = getter(material, parameter_name)
        return str(source) if source else "Unknown"
    except Exception as exc:
        return f"Error: {exc}"


def safe_override(instance, parameter_name) -> str:
    getter = getattr(
        unreal.MaterialEditingLibrary,
        "is_material_instance_parameter_overridden",
        None,
    )
    if getter is None or not isinstance(instance, unreal.MaterialInstanceConstant):
        return "N/A"
    try:
        return str(bool(getter(instance, parameter_name)))
    except Exception:
        return "Unknown"


def texture_value(material, parameter_name) -> str:
    try:
        if isinstance(material, unreal.MaterialInstanceConstant):
            value = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
                material, parameter_name
            )
        elif isinstance(material, unreal.Material):
            value = unreal.MaterialEditingLibrary.get_material_default_texture_parameter_value(
                material, parameter_name
            )
        else:
            value = None
        return safe_path(value)
    except Exception as exc:
        return f"Error: {exc}"


def scalar_value(material, parameter_name) -> str:
    try:
        if isinstance(material, unreal.MaterialInstanceConstant):
            value = unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(
                material, parameter_name
            )
        elif isinstance(material, unreal.Material):
            value = unreal.MaterialEditingLibrary.get_material_default_scalar_parameter_value(
                material, parameter_name
            )
        else:
            return "Unavailable"
        return f"{float(value):.6g}"
    except Exception as exc:
        return f"Error: {exc}"


def vector_value(material, parameter_name) -> str:
    try:
        if isinstance(material, unreal.MaterialInstanceConstant):
            value = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(
                material, parameter_name
            )
        elif isinstance(material, unreal.Material):
            value = unreal.MaterialEditingLibrary.get_material_default_vector_parameter_value(
                material, parameter_name
            )
        else:
            return "Unavailable"
        return f"R={value.r:.5g}, G={value.g:.5g}, B={value.b:.5g}, A={value.a:.5g}"
    except Exception as exc:
        return f"Error: {exc}"


def switch_value(material, parameter_name) -> str:
    try:
        if isinstance(material, unreal.MaterialInstanceConstant):
            value = unreal.MaterialEditingLibrary.get_material_instance_static_switch_parameter_value(
                material, parameter_name
            )
        elif isinstance(material, unreal.Material):
            value = unreal.MaterialEditingLibrary.get_material_default_static_switch_parameter_value(
                material, parameter_name
            )
        else:
            return "Unavailable"
        return str(bool(value))
    except Exception as exc:
        return f"Error: {exc}"


def parameter_names(material, getter_name: str):
    getter = getattr(unreal.MaterialEditingLibrary, getter_name, None)
    if getter is None:
        return []
    try:
        return sorted((str(name) for name in (getter(material) or [])), key=str.lower)
    except Exception:
        return []


def parent_chain(material):
    chain = []
    current = material
    seen = set()
    while current is not None:
        path = safe_path(current)
        if path in seen:
            chain.append((current, "Cycle detected"))
            break
        seen.add(path)
        chain.append((current, ""))
        if not isinstance(current, unreal.MaterialInstanceConstant):
            break
        try:
            current = current.get_editor_property("parent")
        except Exception:
            break
    return chain


def append_material_section(lines, index: int, material) -> None:
    material_path = safe_path(material)
    class_name = material.get_class().get_name() if material else "None"
    lines.extend(
        [
            "",
            f"=== MATERIAL LEVEL {index} ===",
            f"Path: {material_path}",
            f"Class: {class_name}",
        ]
    )

    texture_names = parameter_names(material, "get_texture_parameter_names")
    scalar_names = parameter_names(material, "get_scalar_parameter_names")
    vector_names = parameter_names(material, "get_vector_parameter_names")
    switch_names = parameter_names(material, "get_static_switch_parameter_names")

    lines.append(f"Texture parameters: {len(texture_names)}")
    for name in texture_names:
        lines.append(
            f"  [Texture] {name} | Value={texture_value(material, name)} | "
            f"Overridden={safe_override(material, name)} | "
            f"Source={safe_source('get_texture_parameter_source', material, name)}"
        )

    lines.append(f"Scalar parameters: {len(scalar_names)}")
    for name in scalar_names:
        lines.append(
            f"  [Scalar] {name} | Value={scalar_value(material, name)} | "
            f"Overridden={safe_override(material, name)} | "
            f"Source={safe_source('get_scalar_parameter_source', material, name)}"
        )

    lines.append(f"Vector parameters: {len(vector_names)}")
    for name in vector_names:
        lines.append(
            f"  [Vector] {name} | Value={vector_value(material, name)} | "
            f"Overridden={safe_override(material, name)} | "
            f"Source={safe_source('get_vector_parameter_source', material, name)}"
        )

    lines.append(f"Static switch parameters: {len(switch_names)}")
    for name in switch_names:
        lines.append(
            f"  [Switch] {name} | Value={switch_value(material, name)} | "
            f"Overridden={safe_override(material, name)} | "
            f"Source={safe_source('get_static_switch_parameter_source', material, name)}"
        )


def main() -> None:
    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")

    active_material = definition.get_editor_property("material")
    if active_material is None:
        raise RuntimeError("MPD_AetherWorld has no active material")

    chain = parent_chain(active_material)
    lines = [
        "Aether Sensei material parameter audit",
        "",
        f"Mesh Partition definition: {DEFINITION_PATH}",
        f"Active material: {safe_path(active_material)}",
        f"Parent-chain levels: {len(chain)}",
        "",
        "This report is read-only. No asset or terrain setting was changed.",
    ]

    for index, (material, note) in enumerate(chain):
        append_material_section(lines, index, material)
        if note:
            lines.append(f"Note: {note}")

    all_lines = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(all_lines, encoding="utf-8")
    unreal.log(f"{LOG_PREFIX} Wrote {REPORT_PATH}")

    unreal.EditorDialog.show_message(
        "Aether Sensei Parameter Audit",
        "Parameter inventory completed.\n\n"
        f"Active material: {safe_path(active_material)}\n"
        f"Parent-chain levels: {len(chain)}\n\n"
        "No material or terrain asset was changed. The report is in Saved/AetherSenseiParameterAudit.txt.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
