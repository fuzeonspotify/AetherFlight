"""Make a built UE 5.8 Mesh Partition authoritative in AetherWorld.

The operation is reversible and never deletes a Landscape.  It refuses to do
anything when no Mesh Partition root exists, asks for an explicit confirmation,
tags the new terrain for the runtime guard, and retires every Landscape proxy so
World Partition cannot stream a second surface underneath it.
"""

import unreal


LOG_PREFIX = "[Aether Mesh Terrain Finalizer]"
DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
MESH_TAG = unreal.Name("AetherProductionTerrain")
PREVIEW_TAG = unreal.Name("AetherMeshTerrainPreview")
LANDSCAPE_ACTIVE_TAG = unreal.Name("AetherProductionLandscape")
LANDSCAPE_LEGACY_TAG = unreal.Name("AetherLegacyLandscape")


def log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def optional_property(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:
        return False


def class_name(actor):
    return actor.get_class().get_name()


def is_mesh_partition_root(actor):
    name = class_name(actor).lower()
    # AMeshPartition is the root.  Compiled/preview/base section actors must not
    # be tagged as the world terrain authority.
    return name == "meshpartition" or (
        "meshpartition" in name
        and "section" not in name
        and "modifier" not in name
        and "volume" not in name
    )


def is_landscape_actor(actor):
    try:
        return isinstance(actor, unreal.LandscapeProxy)
    except Exception:
        return "landscape" in class_name(actor).lower()


def add_tag(actor, tag, remove=()):
    tags = [existing for existing in actor.tags if existing not in remove]
    if tag not in tags:
        tags.append(tag)
    actor.tags = tags


def score_partition(actor):
    label = actor.get_actor_label().lower()
    score = 0
    if "aether" in label:
        score += 100
    if "terrain" in label:
        score += 50
    if MESH_TAG in actor.tags:
        score += 1000
    return score


def assign_definition(actor, definition):
    for property_name in ("mega_mesh_definition", "mesh_partition_definition"):
        try:
            current = actor.get_editor_property(property_name)
            if current is None:
                actor.set_editor_property(property_name, definition)
            return True
        except Exception:
            continue
    setter = getattr(actor, "set_mesh_partition_definition", None)
    if callable(setter):
        setter(definition)
        return True
    return False


def compiled_section_count(actors):
    count = 0
    for actor in actors:
        name = class_name(actor).lower()
        if "compiledsection" in name or "compiled_section" in name:
            count += 1
    return count


def retire_landscape(actor):
    actor.set_actor_enable_collision(False)
    actor.set_actor_hidden_in_game(True)
    try:
        actor.set_is_temporarily_hidden_in_editor(True)
    except Exception:
        pass
    add_tag(
        actor,
        LANDSCAPE_LEGACY_TAG,
        remove=(LANDSCAPE_ACTIVE_TAG,),
    )
    optional_property(actor, "is_editor_only_actor", True)
    actor.modify()


def activate_mesh_partition(actor, definition):
    assign_definition(actor, definition)
    actor.set_actor_hidden_in_game(False)
    actor.set_actor_enable_collision(True)
    try:
        actor.set_is_temporarily_hidden_in_editor(False)
    except Exception:
        pass
    add_tag(actor, MESH_TAG, remove=(PREVIEW_TAG,))
    optional_property(actor, "is_editor_only_actor", False)
    actor.set_actor_label("MeshTerrain_AetherWorld", mark_dirty=True)
    actor.modify()


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before finalizing the Mesh Terrain migration.")
    except AttributeError:
        pass

    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    if definition is None:
        raise RuntimeError(
            "MPD_AetherWorld is missing. Run InstallAetherMeshTerrain_UE58.py first."
        )

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    partitions = [actor for actor in actors if is_mesh_partition_root(actor)]
    if not partitions:
        raise RuntimeError(
            "No Mesh Partition root exists in this level. Import the 4033 heightmap in Mesh Terrain mode first."
        )

    partition = max(partitions, key=score_partition)
    section_count = compiled_section_count(actors)
    section_note = (
        f"{section_count} loaded compiled-section actors were detected."
        if section_count
        else "No compiled-section actors are currently loaded; World Partition may have them unloaded."
    )
    prompt = (
        f"Mesh Partition: {partition.get_actor_label()}\n"
        f"{section_note}\n\n"
        "Continue ONLY if Build > Build Mesh Partition completed successfully and the terrain "
        "is visible with collision.\n\n"
        "Continuing hides all old Landscape actors in game and the editor, but does not delete them."
    )
    result = unreal.EditorDialog.show_message(
        "Finalize Aether Mesh Terrain", prompt, unreal.AppMsgType.YES_NO
    )
    if result != unreal.AppReturnType.YES:
        log("Cancelled; no actors were changed.")
        return

    activate_mesh_partition(partition, definition)
    retired = []
    for actor in actors:
        if not is_landscape_actor(actor):
            continue
        retire_landscape(actor)
        retired.append(actor.get_actor_label())

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    try:
        actor_subsystem.set_selected_level_actors([partition])
    except Exception:
        pass

    message = (
        f"Authoritative terrain: {partition.get_actor_label()}\n"
        f"Landscape actors retired (not deleted): {len(retired)}\n"
        f"Loaded compiled sections detected: {section_count}\n\n"
        "Rebuild the AetherFlight C++ module, press Play, then press R once.\n"
        "If the Mesh Terrain needs to be rolled back, run RestoreAetherLandscapeFallback_UE58.py."
    )
    log(message.replace("\n", " | "))
    unreal.EditorDialog.show_message(
        "Aether Mesh Terrain Is Active", message, unreal.AppMsgType.OK
    )


if __name__ == "__main__":
    main()
