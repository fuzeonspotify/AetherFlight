"""Restore MPD_AetherWorld to the original Aether Mesh Terrain material."""

import unreal


DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
ORIGINAL_MATERIAL_PATH = (
    "/Game/Aether/MeshTerrain/M_MeshTerrain_Aether.M_MeshTerrain_Aether"
)


def main() -> None:
    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    material = unreal.EditorAssetLibrary.load_asset(ORIGINAL_MATERIAL_PATH)
    if definition is None:
        raise RuntimeError(f"Missing definition: {DEFINITION_PATH}")
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"Missing original material: {ORIGINAL_MATERIAL_PATH}")

    definition.set_editor_property("material", material)
    try:
        definition.post_edit_change()
    except Exception:
        pass
    unreal.EditorAssetLibrary.save_loaded_asset(definition, False)
    unreal.EditorDialog.show_message(
        "Aether Terrain Material Restored",
        "MPD_AetherWorld now uses M_MeshTerrain_Aether again.\n\n"
        "Run Build > Build Mesh Partition to refresh compiled sections.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
