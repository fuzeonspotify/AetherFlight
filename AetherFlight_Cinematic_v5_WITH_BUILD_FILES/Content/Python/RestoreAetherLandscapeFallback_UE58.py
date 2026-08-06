"""Restore the v2 Landscape if the experimental Mesh Terrain needs rollback."""

import unreal


MESH_TAG = unreal.Name("AetherProductionTerrain")
PREVIEW_TAG = unreal.Name("AetherMeshTerrainPreview")
LANDSCAPE_ACTIVE_TAG = unreal.Name("AetherProductionLandscape")
LANDSCAPE_LEGACY_TAG = unreal.Name("AetherLegacyLandscape")


def optional_property(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:
        return False


def add_tag(actor, tag, remove=()):
    tags = [existing for existing in actor.tags if existing not in remove]
    if tag not in tags:
        tags.append(tag)
    actor.tags = tags


def is_mesh_partition_root(actor):
    name = actor.get_class().get_name().lower()
    return name == "meshpartition" or (
        "meshpartition" in name and "section" not in name and "modifier" not in name
    )


def landscape_score(actor):
    label = actor.get_actor_label().lower()
    score = 0
    if "production" in label:
        score += 100
    if "4033" in label:
        score += 100
    if actor.get_class().get_name() == "Landscape":
        score += 20
    return score


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before restoring the Landscape fallback.")
    except AttributeError:
        pass

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    landscapes = [actor for actor in actors if isinstance(actor, unreal.LandscapeProxy)]
    if not landscapes:
        raise RuntimeError("No Landscape actors are loaded in AetherWorld.")

    roots = [actor for actor in landscapes if actor.get_class().get_name() == "Landscape"]
    production_root = max(roots or landscapes, key=landscape_score)
    try:
        production_guid = str(production_root.get_editor_property("landscape_guid"))
    except Exception:
        production_guid = ""

    restored = []
    for actor in landscapes:
        try:
            same_guid = production_guid and str(actor.get_editor_property("landscape_guid")) == production_guid
        except Exception:
            same_guid = actor == production_root
        if actor != production_root and not same_guid:
            continue
        actor.set_actor_hidden_in_game(False)
        actor.set_actor_enable_collision(True)
        try:
            actor.set_is_temporarily_hidden_in_editor(False)
        except Exception:
            pass
        add_tag(actor, LANDSCAPE_ACTIVE_TAG, remove=(LANDSCAPE_LEGACY_TAG,))
        optional_property(actor, "is_editor_only_actor", False)
        actor.modify()
        restored.append(actor.get_actor_label())

    retired_meshes = 0
    for actor in actors:
        if not is_mesh_partition_root(actor):
            continue
        actor.set_actor_hidden_in_game(True)
        actor.set_actor_enable_collision(False)
        add_tag(actor, PREVIEW_TAG, remove=(MESH_TAG,))
        actor.modify()
        retired_meshes += 1

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    unreal.EditorDialog.show_message(
        "Aether Landscape Restored",
        f"Restored production Landscape actors: {len(restored)}\n"
        f"Mesh Partition roots moved back to preview: {retired_meshes}\n\n"
        "Nothing was deleted.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
