"""Build Aether Flight's texture-free cinematic PBR material foundation in-editor.

Run from Tools > Execute Python Script after opening the project. The generated
assets are deliberately stored under /Game/Aether/Materials so C++ can load
them without relying on editor-only code.
"""

import unreal


PACKAGE = "/Game/Aether/Materials"
unreal.EditorAssetLibrary.make_directory(PACKAGE)


def log(message: str) -> None:
    unreal.log(f"[Aether Graphics] {message}")


def material_asset(name: str, rebuild: bool = False):
    path = f"{PACKAGE}/{name}.{name}"
    existing = unreal.EditorAssetLibrary.load_asset(path)
    if isinstance(existing, unreal.Material):
        if rebuild:
            unreal.MaterialEditingLibrary.delete_all_material_expressions(existing)
            log(f"Rebuilding generated material: {name}")
            return existing, True
        log(f"Keeping existing material: {name}")
        return existing, False

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, PACKAGE, unreal.Material, unreal.MaterialFactoryNew()
    )
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"Could not create {path}")
    return material, True


def expression(material, expression_class, x: int, y: int):
    return unreal.MaterialEditingLibrary.create_material_expression(
        material, expression_class, x, y
    )


def scalar(material, value: float, x: int, y: int):
    node = expression(material, unreal.MaterialExpressionConstant, x, y)
    node.set_editor_property("r", value)
    return node


def color(material, value, x: int, y: int):
    node = expression(material, unreal.MaterialExpressionConstant3Vector, x, y)
    node.set_editor_property("constant", unreal.LinearColor(*value, 1.0))
    return node


def output(material, node, material_property) -> None:
    unreal.MaterialEditingLibrary.connect_material_property(node, "", material_property)


def connect(source, target, input_name: str) -> None:
    unreal.MaterialEditingLibrary.connect_material_expressions(source, "", target, input_name)


def finish(material) -> None:
    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(f"Saved {material.get_path_name()}")


terrain, created = material_asset("M_Terrain_Cinematic")
if created:
    vertex_color = expression(terrain, unreal.MaterialExpressionVertexColor, -520, -80)
    output(terrain, vertex_color, unreal.MaterialProperty.MP_BASE_COLOR)
    output(terrain, scalar(terrain, 0.88, -240, 110), unreal.MaterialProperty.MP_ROUGHNESS)
    output(terrain, scalar(terrain, 0.22, -240, 190), unreal.MaterialProperty.MP_SPECULAR)
    output(terrain, scalar(terrain, 0.0, -240, 270), unreal.MaterialProperty.MP_METALLIC)
    finish(terrain)


# Preserve the dedicated Single Layer Water graph when the graphics installer is rerun.\n# Use InstallExtremeOceanMaterial_UE58.py when an ocean rebuild is intentional.\nocean, created = material_asset("M_Ocean_Cinematic", rebuild=False)
if created:
    deep = color(ocean, (0.0025, 0.018, 0.030), -700, -100)
    horizon = color(ocean, (0.045, 0.19, 0.22), -700, 30)
    fresnel = expression(ocean, unreal.MaterialExpressionFresnel, -700, 180)
    blend = expression(ocean, unreal.MaterialExpressionLinearInterpolate, -410, 0)
    unreal.MaterialEditingLibrary.connect_material_expressions(deep, "", blend, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(horizon, "", blend, "B")
    unreal.MaterialEditingLibrary.connect_material_expressions(fresnel, "", blend, "Alpha")
    output(ocean, blend, unreal.MaterialProperty.MP_BASE_COLOR)
    output(ocean, scalar(ocean, 0.075, -220, 130), unreal.MaterialProperty.MP_ROUGHNESS)
    output(ocean, scalar(ocean, 0.72, -220, 210), unreal.MaterialProperty.MP_SPECULAR)
    output(ocean, scalar(ocean, 0.04, -220, 290), unreal.MaterialProperty.MP_METALLIC)

    # Keep this generated graph intentionally compact and compiler-safe. A
    # licensed production water asset can replace it later without touching C++.
    ocean.set_editor_property("tangent_space_normal", True)
    ocean.set_editor_property("two_sided", True)
    finish(ocean)


runway, created = material_asset("M_Runway_Cinematic")
if created:
    output(runway, color(runway, (0.018, 0.020, 0.021), -350, -50), unreal.MaterialProperty.MP_BASE_COLOR)
    output(runway, scalar(runway, 0.82, -350, 80), unreal.MaterialProperty.MP_ROUGHNESS)
    output(runway, scalar(runway, 0.18, -350, 160), unreal.MaterialProperty.MP_SPECULAR)
    finish(runway)


markings, created = material_asset("M_RunwayMarkings_Cinematic")
if created:
    white = color(markings, (0.72, 0.72, 0.68), -420, -20)
    output(markings, white, unreal.MaterialProperty.MP_BASE_COLOR)
    output(markings, scalar(markings, 0.58, -420, 100), unreal.MaterialProperty.MP_ROUGHNESS)
    output(markings, scalar(markings, 0.25, -420, 180), unreal.MaterialProperty.MP_SPECULAR)
    finish(markings)


unreal.EditorDialog.show_message(
    "Aether Flight Graphics",
    "Cinematic PBR materials are installed. Restart Play if it is already running.",
    unreal.AppMsgType.OK,
)
