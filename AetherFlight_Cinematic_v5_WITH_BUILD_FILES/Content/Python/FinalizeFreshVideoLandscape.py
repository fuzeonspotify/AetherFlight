"""Apply and validate the fresh Heightmap_Out landscape in the open level."""

import unreal


MATERIAL_PATH = "/Game/Aether/ProductionTerrain/M_Landscape_Production.M_Landscape_Production"
EXPECTED_MAP_NAME = "AetherWorld"
EXPECTED_SCALE = 400.0


def set_if_available(obj, property_name: str, value) -> None:
    try:
        obj.set_editor_property(property_name, value)
    except Exception:
        unreal.log_warning(
            f"[Aether Fresh Landscape] Optional property unavailable: {property_name}"
        )


def main() -> None:
    material = unreal.EditorAssetLibrary.load_asset(MATERIAL_PATH)
    if not isinstance(material, unreal.MaterialInterface):
        raise RuntimeError(
            "M_Landscape_Production is missing. Run InstallFreshVideoLandscape.py first."
        )

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = [
        actor for actor in actor_subsystem.get_all_level_actors()
        if isinstance(actor, unreal.LandscapeProxy)
    ]
    if not landscapes:
        unreal.EditorDialog.show_message(
            "Fresh Heightmap Landscape",
            "No Landscape exists in the current level. Import the supplied 2017 heightmap first.",
            unreal.AppMsgType.OK,
        )
        return

    for landscape in landscapes:
        landscape.set_editor_property("landscape_material", material)
        set_if_available(landscape, "nanite_skirt_enabled", True)
        set_if_available(landscape, "nanite_skirt_depth", 1.0)
        set_if_available(landscape, "collision_mip_level", 0)
        set_if_available(landscape, "simple_collision_mip_level", 1)
        landscape.modify()

    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()

    world = unreal.EditorLevelLibrary.get_editor_world()
    world_name = world.get_name() if world else "Unknown"
    warnings = []
    if world_name != EXPECTED_MAP_NAME:
        warnings.append(
            f"Current map is {world_name}; save/open the finished map as {EXPECTED_MAP_NAME}."
        )

    root_landscapes = [
        actor for actor in landscapes
        if actor.get_class().get_name() == "Landscape"
    ]
    if len(root_landscapes) > 1:
        warnings.append(
            f"Found {len(root_landscapes)} root Landscape actors; the clean base should have one."
        )

    warning_text = ""
    if warnings:
        warning_text = "\n\nChecks to fix:\n" + "\n".join(warnings)

    unreal.EditorDialog.show_message(
        "Fresh Heightmap Landscape Finalized",
        f"Applied the production material to {len(landscapes)} Landscape actor/proxy object(s).\n"
        f"Expected import scale: X/Y/Z {EXPECTED_SCALE:g}.\n\n"
        "Next, use Landscape > Build Nanite Only, wait for shaders, then Save All."
        f"{warning_text}",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
