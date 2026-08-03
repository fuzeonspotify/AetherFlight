"""Create the translucent vertex-colour material used by aerodynamic condensation."""

import unreal


ASSET_DIR = "/Game/Aether/Effects"
ASSET_NAME = "M_WingCondensation"
ASSET_PATH = f"{ASSET_DIR}/{ASSET_NAME}"
LOG = "[Aether Vapor Material]"


def connect(source, source_output, target, target_input, description):
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(f"Could not connect {description}")


def main():
    unreal.EditorAssetLibrary.make_directory(ASSET_DIR)
    material = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if not material:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            ASSET_NAME, ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew()
        )
    if not material:
        raise RuntimeError(f"Could not create {ASSET_PATH}")

    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("two_sided", True)
    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)

    vertex_color = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVertexColor, -560, 0
    )
    tint = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -560, -210
    )
    tint.set_editor_property("constant", unreal.LinearColor(0.72, 0.86, 1.0, 1.0))
    emissive = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -260, -120
    )
    opacity_scale = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -560, 240
    )
    opacity_scale.set_editor_property("r", 0.82)
    opacity = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -260, 170
    )

    connect(vertex_color, "RGB", emissive, "A", "vertex colour to emissive")
    connect(tint, "", emissive, "B", "vapour tint to emissive")
    connect(vertex_color, "A", opacity, "A", "vertex alpha to opacity")
    connect(opacity_scale, "", opacity, "B", "opacity scale")
    if not unreal.MaterialEditingLibrary.connect_material_property(
        emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    ):
        raise RuntimeError("Could not connect vapour emissive output")
    if not unreal.MaterialEditingLibrary.connect_material_property(
        opacity, "", unreal.MaterialProperty.MP_OPACITY
    ):
        raise RuntimeError("Could not connect vapour opacity output")

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    unreal.log(f"{LOG} Created {ASSET_PATH}")
    unreal.EditorDialog.show_message(
        "Aether Wing Condensation",
        "The translucent wing-condensation material was installed.\n\n"
        "Save All, stop Play if it is running, and press Play again.\n"
        "Pull a hard turn above 185 knots; the vapour builds progressively above about 2.25 G.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
