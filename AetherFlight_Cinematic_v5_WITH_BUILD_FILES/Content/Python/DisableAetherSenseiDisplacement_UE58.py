"""Safety rollback for the experimental Sensei Terrain integration.

Directly assigning M_SenseiTerrain or its instance to AetherFlight's
MPD_AetherWorld can make Mesh Terrain sections render incorrectly or disappear.
Until an Aether-specific Mesh Terrain wrapper material is authored and tested,
this entry point restores the known-good M_MeshTerrain_Aether material.
"""

import unreal


DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
ORIGINAL_MATERIAL_PATH = (
    "/Game/Aether/MeshTerrain/M_MeshTerrain_Aether.M_MeshTerrain_Aether"
)


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop Play In Editor before restoring the terrain material")
    except AttributeError:
        pass

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    material = unreal.EditorAssetLibrary.load_asset(ORIGINAL_MATERIAL_PATH)

    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"Missing original Aether terrain material: {ORIGINAL_MATERIAL_PATH}")

    definition.set_editor_property("material", material)
    try:
        definition.post_edit_change()
    except Exception:
        pass

    if not unreal.EditorAssetLibrary.save_loaded_asset(definition, False):
        raise RuntimeError(f"Failed to save Mesh Partition definition: {DEFINITION_PATH}")

    unreal.EditorDialog.show_message(
        "Aether Terrain Material Restored",
        "The direct Sensei material assignment has been removed.\n\n"
        "MPD_AetherWorld now uses M_MeshTerrain_Aether again.\n\n"
        "Save All and test Play mode. Rebuild Mesh Partition only if the terrain "
        "does not return after reopening AetherWorld.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
