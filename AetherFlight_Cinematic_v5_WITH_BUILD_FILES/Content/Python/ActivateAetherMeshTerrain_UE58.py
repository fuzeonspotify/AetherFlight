"""Make the single clean Mesh Partition root authoritative in AetherWorld."""

import unreal


LOG_PREFIX = "[Aether Mesh Terrain Activation]"
MAP_PATH = "/Game/Maps/AetherWorld"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
AUTHORITY_TAG = unreal.Name("AetherProductionTerrain")
PREVIEW_TAG = unreal.Name("AetherMeshTerrainPreview")


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def class_name(actor) -> str:
    return actor.get_class().get_name()


def is_landscape(actor) -> bool:
    try:
        return isinstance(actor, unreal.LandscapeProxy)
    except Exception:
        return "landscape" in class_name(actor).lower()


def is_mesh_partition_root(actor) -> bool:
    name = class_name(actor).lower()
    return name == "meshpartition" or (
        "meshpartition" in name
        and "section" not in name
        and "modifier" not in name
        and "volume" not in name
    )


def assign_definition(actor, definition) -> None:
    for property_name in ("mega_mesh_definition", "mesh_partition_definition"):
        try:
            actor.set_editor_property(property_name, definition)
            return
        except Exception:
            continue
    setter = getattr(actor, "set_mesh_partition_definition", None)
    if callable(setter):
        setter(definition)
        return
    raise RuntimeError("Could not assign MPD_AetherWorld to the Mesh Partition root")


def main() -> None:
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    level_subsystem.load_level(MAP_PATH)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(actor_subsystem.get_all_level_actors())

    landscapes = [actor for actor in actors if is_landscape(actor)]
    if landscapes:
        labels = ", ".join(actor.get_actor_label() for actor in landscapes)
        raise RuntimeError(
            "Classic Landscape actors still exist. Run ResetAetherTerrain_UE58.py first: "
            + labels
        )

    roots = [actor for actor in actors if is_mesh_partition_root(actor)]
    if len(roots) != 1:
        raise RuntimeError(
            f"Expected exactly one Mesh Partition root, found {len(roots)}. "
            "Delete duplicates or re-run the clean reset and import once."
        )

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(
            "MPD_AetherWorld is missing. Run InstallAetherMeshTerrainClean_UE58.py first."
        )

    root = roots[0]
    assign_definition(root, definition)
    tags = [tag for tag in root.tags if tag != PREVIEW_TAG]
    if AUTHORITY_TAG not in tags:
        tags.append(AUTHORITY_TAG)
    root.tags = tags
    root.set_actor_label("MeshTerrain_AetherWorld", mark_dirty=True)
    root.set_actor_hidden_in_game(False)
    root.set_actor_enable_collision(True)
    try:
        root.set_is_temporarily_hidden_in_editor(False)
    except Exception:
        pass
    try:
        root.set_editor_property("is_editor_only_actor", False)
    except Exception:
        pass
    root.modify()

    level_subsystem.save_current_level()
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    actor_subsystem.set_selected_level_actors([root])
    log(
        "MeshTerrain_AetherWorld is authoritative. The runtime procedural fallback "
        "will remain disabled and the game will use Mesh Terrain collision traces."
    )


if __name__ == "__main__":
    main()
