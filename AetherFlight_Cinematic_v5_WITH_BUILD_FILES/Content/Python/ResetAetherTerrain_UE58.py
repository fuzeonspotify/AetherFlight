"""Destructively reset AetherWorld's terrain state for a clean UE 5.8 Mesh Terrain build.

This script deletes classic Landscape actors, Mesh Partition roots/sections/modifiers,
and generated Mesh Terrain authoring assets. It preserves the aircraft, runway, HUD,
weather, water actors, source heightmaps, source weightmaps, and reusable terrain
textures. Run only with Unreal Editor closed through RESET_AETHER_TERRAIN_UE58.ps1,
or manually through Tools > Execute Python Script while AetherWorld is open.
"""

from pathlib import Path

import unreal


LOG_PREFIX = "[Aether Terrain Reset]"
MAP_PATH = "/Game/Maps/AetherWorld"
MESH_TERRAIN_PACKAGE = "/Game/Aether/MeshTerrain"
PRODUCTION_PACKAGE = "/Game/Aether/ProductionTerrain"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherTerrainReset.txt"

TERRAIN_TAGS = {
    unreal.Name("AetherProductionTerrain"),
    unreal.Name("AetherMeshTerrainPreview"),
    unreal.Name("AetherProductionLandscape"),
    unreal.Name("AetherLegacyLandscape"),
}


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def class_name(actor) -> str:
    try:
        return actor.get_class().get_name()
    except Exception:
        return type(actor).__name__


def actor_label(actor) -> str:
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def has_property(obj, property_name: str) -> bool:
    try:
        obj.get_editor_property(property_name)
        return True
    except Exception:
        return False


def is_classic_landscape(actor) -> bool:
    try:
        if isinstance(actor, unreal.LandscapeProxy):
            return True
    except Exception:
        pass
    return "landscape" in class_name(actor).lower()


def is_mesh_partition_actor(actor) -> bool:
    name = class_name(actor).lower()
    label = actor_label(actor).lower()
    tags = set(getattr(actor, "tags", []))

    if "meshpartition" in name or "meshterrain" in name:
        return True
    if tags.intersection(TERRAIN_TAGS):
        return True
    if label.startswith("meshterrain_") or label.startswith("meshpartition"):
        return True

    # Brush, sculpt, remesh, spline, texture, boolean, and water modifiers can
    # have generic class names. Detect only modifier actors that expose a Mesh
    # Partition reference so unrelated level-design modifiers are preserved.
    if "modifier" in name:
        for property_name in (
            "affected_mesh_partition",
            "mesh_partition",
            "mega_mesh",
            "mega_mesh_actor",
        ):
            if has_property(actor, property_name):
                return True
    return False


def load_aether_world() -> None:
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    loaded = level_subsystem.load_level(MAP_PATH)
    if loaded is False:
        raise RuntimeError(f"Could not load {MAP_PATH}")
    log(f"Loaded {MAP_PATH}")


def destroy_terrain_actors() -> list[str]:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(actor_subsystem.get_all_level_actors())
    targets = [
        actor
        for actor in actors
        if is_classic_landscape(actor) or is_mesh_partition_actor(actor)
    ]

    # Delete modifiers/sections before roots. This avoids stale references in
    # experimental Mesh Partition builds and gives OFPA a clean save pass.
    targets.sort(
        key=lambda actor: (
            1 if class_name(actor).lower() in {"landscape", "meshpartition"} else 0,
            actor_label(actor).lower(),
        )
    )

    removed = []
    for actor in targets:
        label = actor_label(actor)
        actor_type = class_name(actor)
        try:
            if actor_subsystem.destroy_actor(actor):
                removed.append(f"{label} [{actor_type}]")
                log(f"Deleted actor: {label} [{actor_type}]")
            else:
                warn(f"Editor refused to delete actor: {label} [{actor_type}]")
        except Exception as exc:
            warn(f"Failed to delete {label} [{actor_type}]: {exc}")
    return removed


def disable_procedural_fallback() -> int:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    changed = 0
    for actor in actor_subsystem.get_all_level_actors():
        if "proceduralworlddirector" not in class_name(actor).lower():
            continue
        updated = False
        for property_name in (
            "allow_runtime_placeholder_terrain",
            "b_allow_runtime_placeholder_terrain",
            "bAllowRuntimePlaceholderTerrain",
        ):
            try:
                actor.set_editor_property(property_name, False)
                updated = True
                break
            except Exception:
                continue
        if updated:
            actor.modify()
            changed += 1
            log(f"Disabled procedural fallback terrain on {actor_label(actor)}")
        else:
            warn(
                f"Could not resolve the fallback flag on {actor_label(actor)}; "
                "the C++ class default remains false"
            )
    return changed


def delete_asset_tree(package_path: str) -> list[str]:
    deleted = []
    try:
        assets = unreal.EditorAssetLibrary.list_assets(
            package_path, recursive=True, include_folder=False
        )
    except TypeError:
        assets = unreal.EditorAssetLibrary.list_assets(package_path, recursive=True)

    # Delete child assets before their folders.
    for asset_path in sorted(assets, key=len, reverse=True):
        try:
            if unreal.EditorAssetLibrary.delete_asset(asset_path):
                deleted.append(asset_path)
                log(f"Deleted asset: {asset_path}")
        except Exception as exc:
            warn(f"Could not delete asset {asset_path}: {exc}")

    try:
        unreal.EditorAssetLibrary.delete_directory(package_path)
    except Exception:
        pass
    return deleted


def delete_legacy_landscape_assets() -> list[str]:
    deleted = []
    try:
        assets = unreal.EditorAssetLibrary.list_assets(
            PRODUCTION_PACKAGE, recursive=True, include_folder=False
        )
    except TypeError:
        assets = unreal.EditorAssetLibrary.list_assets(PRODUCTION_PACKAGE, recursive=True)

    # Reusable /Textures are intentionally preserved. Only Landscape-specific
    # materials, layer infos, and generated Landscape/Nanite assets are removed.
    for asset_path in sorted(assets, key=len, reverse=True):
        lowered = asset_path.lower()
        if "/textures/" in lowered:
            continue
        leaf = lowered.rsplit("/", 1)[-1]
        should_delete = (
            "/layerinfo/" in lowered
            or "landscape" in leaf
            or "layer_info" in leaf
            or "layerinfo" in leaf
        )
        if not should_delete:
            continue
        try:
            if unreal.EditorAssetLibrary.delete_asset(asset_path):
                deleted.append(asset_path)
                log(f"Deleted legacy Landscape asset: {asset_path}")
        except Exception as exc:
            warn(f"Could not delete legacy asset {asset_path}: {exc}")
    return deleted


def verify_clean_world() -> None:
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    leftovers = []
    for actor in actor_subsystem.get_all_level_actors():
        if is_classic_landscape(actor) or is_mesh_partition_actor(actor):
            leftovers.append(f"{actor_label(actor)} [{class_name(actor)}]")
    if leftovers:
        raise RuntimeError(
            "Terrain reset is incomplete. Remaining terrain actors: "
            + ", ".join(leftovers)
        )


def save_world() -> None:
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level_subsystem.save_current_level():
        raise RuntimeError("AetherWorld could not be saved after terrain deletion")
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("Saved AetherWorld and dirty external actor packages")


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before resetting terrain")
    except AttributeError:
        pass

    load_aether_world()
    removed_actors = destroy_terrain_actors()
    fallback_actors_updated = disable_procedural_fallback()
    save_world()

    try:
        unreal.SystemLibrary.collect_garbage()
    except Exception:
        pass

    deleted_mesh_assets = delete_asset_tree(MESH_TERRAIN_PACKAGE)
    deleted_landscape_assets = delete_legacy_landscape_assets()
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    verify_clean_world()
    save_world()

    report = (
        "AetherWorld terrain reset completed.\n"
        f"Terrain actors deleted: {len(removed_actors)}\n"
        f"Mesh Terrain assets deleted: {len(deleted_mesh_assets)}\n"
        f"Legacy Landscape assets deleted: {len(deleted_landscape_assets)}\n"
        f"Procedural fallback actors disabled: {fallback_actors_updated}\n"
        "Reusable source heightmaps, weightmaps, textures, aircraft, runway, HUD, "
        "weather, and water actors were preserved.\n"
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))


if __name__ == "__main__":
    main()
