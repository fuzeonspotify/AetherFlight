"""Read-only audit for the actual FMaterialParameterInfo used by Sensei.

The normal setter rejected the audited names for Global, Layer, and Blend
associations. This script inspects the full parameter-info structs, including
layer/blend indices, and the material instance's current override arrays.
It does not modify or save any asset.
"""

from pathlib import Path

import unreal


DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherSenseiParameterInfoAudit.txt"

TARGET_TEXTURES = [
    "Albedo Color A",
    "Albedo Color B",
    "Albedo Color C",
    "Albedo Color D",
    "Albedo Color E",
    "Normal A",
    "Normal B",
    "Normal C",
    "Normal D",
    "Normal E",
    "Roughness A",
    "Roughness B",
    "Roughness C",
    "Roughness D",
    "Roughness E",
]

TARGET_SCALARS = [f"Normal Strength {slot}" for slot in "ABCDE"]

ASSOCIATIONS = (
    ("Global", unreal.MaterialParameterAssociation.GLOBAL_PARAMETER),
    ("Layer", unreal.MaterialParameterAssociation.LAYER_PARAMETER),
    ("Blend", unreal.MaterialParameterAssociation.BLEND_PARAMETER),
)


def path_of(value) -> str:
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def info_text(info) -> str:
    try:
        return (
            f"name={info.get_editor_property('name')} | "
            f"association={info.get_editor_property('association')} | "
            f"index={info.get_editor_property('index')}"
        )
    except Exception as exc:
        return f"unreadable info: {exc}"


def inspect_get_parameter_info(material, parameter_name: str, lines) -> None:
    getter = getattr(material, "get_parameter_info", None)
    if getter is None:
        lines.append("    get_parameter_info unavailable")
        return
    for association_name, association in ASSOCIATIONS:
        try:
            info = getter(association, parameter_name, None)
            lines.append(f"    {association_name}: {info_text(info)}")
        except Exception as exc:
            lines.append(f"    {association_name}: ERROR {exc}")


def dump_override_array(instance, property_name: str, lines) -> None:
    try:
        values = list(instance.get_editor_property(property_name) or [])
    except Exception as exc:
        lines.append(f"{property_name}: ERROR {exc}")
        return

    lines.append(f"{property_name}: {len(values)} entries")
    for index, entry in enumerate(values):
        try:
            info = entry.get_editor_property("parameter_info")
        except Exception:
            info = None
        try:
            value = entry.get_editor_property("parameter_value")
        except Exception as exc:
            value = f"ERROR {exc}"
        lines.append(
            f"  [{index}] {info_text(info) if info is not None else 'no parameter_info'} | "
            f"value={path_of(value) if property_name == 'texture_parameter_values' else value}"
        )


def main() -> None:
    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")

    instance = definition.get_editor_property("material")
    if not isinstance(instance, unreal.MaterialInstanceConstant):
        raise RuntimeError(
            f"Active material is not a MaterialInstanceConstant: {path_of(instance)}"
        )

    try:
        parent = instance.get_editor_property("parent")
    except Exception:
        parent = None

    lines = [
        "Aether Sensei parameter-info audit",
        "",
        f"Instance: {path_of(instance)}",
        f"Parent: {path_of(parent)}",
        "",
        "This report is read-only. No asset was modified or saved.",
        "",
        "=== TARGET TEXTURE PARAMETER INFO ===",
    ]

    for name in TARGET_TEXTURES:
        lines.append(f"  {name}")
        inspect_get_parameter_info(instance, name, lines)

    lines.append("")
    lines.append("=== TARGET SCALAR PARAMETER INFO ===")
    for name in TARGET_SCALARS:
        lines.append(f"  {name}")
        inspect_get_parameter_info(instance, name, lines)

    lines.append("")
    lines.append("=== CURRENT INSTANCE OVERRIDE ARRAYS ===")
    dump_override_array(instance, "texture_parameter_values", lines)
    dump_override_array(instance, "scalar_parameter_values", lines)

    if parent is not None:
        lines.append("")
        lines.append("=== PARENT CHECK: ALBEDO COLOR A ===")
        inspect_get_parameter_info(parent, "Albedo Color A", lines)

    report = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    unreal.log(f"[Aether Sensei Parameter Info Audit] Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
