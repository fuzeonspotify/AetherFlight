"""Install and configure AetherFlight's procedural biome actor in the open level."""

from __future__ import annotations

import unreal


ACTOR_LABEL = "Aether Procedural Biomes"
LEGACY_TREE_PATH = "/Game/Aether/Environment/Foliage/SM_Conifer.SM_Conifer"
LEGACY_ROCK_PATH = "/Game/Aether/Environment/Rocks/SM_CliffRock.SM_CliffRock"
MAX_ASSETS_PER_GROUP = 8

EXCLUDED_PATH_PARTS = (
    "/aircraft/",
    "/characters/",
    "/maps/",
    "/materials/",
    "/textures/",
    "/heightmaps/",
    "/weightmaps/",
    "/python/",
)

TREE_KEYWORDS = ("tree", "pine", "conifer", "spruce", "fir", "cedar", "birch", "oak")
GROUND_KEYWORDS = ("grass", "fern", "bush", "shrub", "flower", "reed", "heather")
ROCK_KEYWORDS = ("rock", "cliff", "boulder", "stone", "scree")


def _is_static_mesh(asset_data: unreal.AssetData) -> bool:
    try:
        return str(asset_data.asset_class_path.asset_name) == "StaticMesh"
    except Exception:
        return str(asset_data.asset_class) == "StaticMesh"


def _asset_text(asset_data: unreal.AssetData) -> str:
    return f"{asset_data.package_name}/{asset_data.asset_name}".lower()


def _candidate_score(asset_data: unreal.AssetData, keywords: tuple[str, ...]) -> int:
    text = _asset_text(asset_data)
    if any(part in text for part in EXCLUDED_PATH_PARTS):
        return -1
    if not any(keyword in text for keyword in keywords):
        return -1

    score = 1
    if "/environment/" in text:
        score += 5
    if "/foliage/" in text or "/rocks/" in text:
        score += 5
    if str(asset_data.asset_name).lower().startswith("sm_"):
        score += 2
    score += sum(2 for keyword in keywords if keyword in text)
    return score


def _discover_meshes(keywords: tuple[str, ...]) -> list[unreal.StaticMesh]:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = registry.get_assets_by_path(unreal.Name("/Game"), recursive=True)
    ranked = []

    for asset_data in assets:
        if not _is_static_mesh(asset_data):
            continue
        score = _candidate_score(asset_data, keywords)
        if score >= 0:
            ranked.append((score, str(asset_data.package_name), asset_data))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    meshes = []
    seen_paths = set()
    for _, _, asset_data in ranked:
        if len(meshes) >= MAX_ASSETS_PER_GROUP:
            break
        path = str(asset_data.package_name)
        if path in seen_paths:
            continue
        mesh = asset_data.get_asset()
        if isinstance(mesh, unreal.StaticMesh):
            meshes.append(mesh)
            seen_paths.add(path)
    return meshes


def _prepend_legacy(meshes: list[unreal.StaticMesh], object_path: str) -> list[unreal.StaticMesh]:
    legacy = unreal.EditorAssetLibrary.load_asset(object_path)
    if isinstance(legacy, unreal.StaticMesh) and legacy not in meshes:
        return [legacy, *meshes]
    return meshes


def _make_mesh_entries(
    meshes: list[unreal.StaticMesh],
    minimum_scale: float,
    maximum_scale: float,
    z_offset: float,
) -> list:
    entry_type = getattr(unreal, "ProceduralBiomeMesh")
    entries = []
    for index, mesh in enumerate(meshes[:MAX_ASSETS_PER_GROUP]):
        entry = entry_type()
        entry.set_editor_property("mesh", mesh)
        entry.set_editor_property("weight", max(0.35, 1.0 - index * 0.08))
        entry.set_editor_property(
            "uniform_scale_range",
            unreal.Vector2D(minimum_scale, maximum_scale),
        )
        entry.set_editor_property("z_offset_centimeters", z_offset)
        entry.set_editor_property("align_to_surface", True)
        entry.set_editor_property("random_yaw", True)
        entries.append(entry)
    return entries


def _find_or_spawn_director():
    actor_type = getattr(unreal, "ProceduralBiomeDirector", None)
    if actor_type is None:
        raise RuntimeError(
            "ProceduralBiomeDirector is unavailable. Build the C++ project, reopen Unreal, "
            "then run this script again."
        )

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actor_subsystem.get_all_level_actors():
        if isinstance(actor, actor_type):
            return actor

    actor = actor_subsystem.spawn_actor_from_class(
        actor_type,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
    )
    actor.set_actor_label(ACTOR_LABEL)
    return actor


def main() -> None:
    director = _find_or_spawn_director()
    director.set_editor_property("is_spatially_loaded", False)
    director.reset_default_biomes()

    trees = _prepend_legacy(_discover_meshes(TREE_KEYWORDS), LEGACY_TREE_PATH)
    ground_cover = _discover_meshes(GROUND_KEYWORDS)
    rocks = _prepend_legacy(_discover_meshes(ROCK_KEYWORDS), LEGACY_ROCK_PATH)

    biomes = list(director.get_editor_property("biomes"))
    for biome in biomes:
        biome_name = str(biome.get_editor_property("biome_name"))
        if biome_name == "Meadow":
            biome.set_editor_property(
                "meshes",
                _make_mesh_entries(ground_cover, 0.75, 1.35, 0.0),
            )
        elif biome_name == "EvergreenForest":
            biome.set_editor_property(
                "meshes",
                _make_mesh_entries(trees, 0.78, 1.55, -12.0),
            )
        elif biome_name == "RockyHighlands":
            biome.set_editor_property(
                "meshes",
                _make_mesh_entries(rocks, 0.70, 2.20, -30.0),
            )
        elif biome_name == "AlpineSnow":
            biome.set_editor_property(
                "meshes",
                _make_mesh_entries(rocks, 0.55, 1.65, -25.0),
            )

    director.set_editor_property("biomes", biomes)
    discovered_count = len(trees) + len(ground_cover) + len(rocks)

    generated_count = 0
    if discovered_count > 0:
        director.build_biomes()
        generated_count = int(director.get_editor_property("last_generated_instance_count"))
        if generated_count > 0:
            # Preserve the editor-built HISM components and avoid tens of thousands
            # of Landscape traces every time PIE or the packaged game starts.
            director.set_editor_property("build_on_begin_play", False)

    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()

    if generated_count > 0:
        message = (
            "Procedural biomes are installed and built.\n\n"
            f"Tree meshes: {len(trees)}\n"
            f"Ground-cover meshes: {len(ground_cover)}\n"
            f"Rock meshes: {len(rocks)}\n"
            f"Generated instances: {generated_count}\n\n"
            "Select 'Aether Procedural Biomes' in the Outliner to tune density, "
            "noise, ranges, and mesh weights."
        )
    elif discovered_count > 0:
        message = (
            "Biome meshes were found, but no instances were generated.\n\n"
            "In the World Partition window, load the full Landscape region, then run this "
            "script again. You can also select the biome actor and reduce Sample Count "
            "while testing."
        )
    else:
        message = (
            "The biome actor was installed, but no vegetation or rock Static Mesh assets "
            "were found in /Game.\n\n"
            "Add your Fab/Megascans tree, ground-cover, and rock packs, then run this "
            "same script again. It will discover them and build the biomes automatically."
        )

    unreal.EditorDialog.show_message(
        "Aether Procedural Biomes",
        message,
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
