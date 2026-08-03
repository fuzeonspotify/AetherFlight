"""Assign the generated production material to Landscape actors in the open level."""

import unreal


MATERIAL_PATH = "/Game/Aether/ProductionTerrain/M_Landscape_Production.M_Landscape_Production"


def main() -> None:
    material = unreal.EditorAssetLibrary.load_asset(MATERIAL_PATH)
    if not isinstance(material, unreal.MaterialInterface):
        raise RuntimeError(
            "M_Landscape_Production is missing. Run InstallProductionLandscape.py first."
        )

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = [
        actor for actor in actor_subsystem.get_all_level_actors()
        if isinstance(actor, unreal.LandscapeProxy)
    ]
    if not landscapes:
        unreal.EditorDialog.show_message(
            "Aether Production Landscape",
            "No Landscape exists in the current level. Import the 4033 heightmap first.",
            unreal.AppMsgType.OK,
        )
        return

    for landscape in landscapes:
        landscape.set_editor_property("landscape_material", material)
        # Nanite Landscape properties differ slightly between installed UE
        # versions, so set only properties this build actually exposes.
        for property_name, value in (
            ("nanite_skirt_enabled", True),
            ("nanite_skirt_depth", 1.0),
        ):
            try:
                landscape.set_editor_property(property_name, value)
            except Exception:
                pass
        landscape.modify()

    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    unreal.EditorDialog.show_message(
        "Aether Production Landscape",
        f"Applied M_Landscape_Production to {len(landscapes)} Landscape actor(s).\n\n"
        "Build Landscape Nanite Data from the Landscape menu after the shader compile finishes.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
