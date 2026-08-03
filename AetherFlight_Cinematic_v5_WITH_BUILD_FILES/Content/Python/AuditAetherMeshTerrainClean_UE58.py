"""Read-only audit for the clean AetherFlight UE 5.8 Mesh Terrain world."""

from pathlib import Path

import unreal


MAP_PATH = "/Game/Maps/AetherWorld"
PACKAGE = "/Game/Aether/MeshTerrain"
HEIGHTMAP = (
    Path(unreal.Paths.project_dir())
    / "SourceAssets"
    / "ProductionTerrain"
    / "Heightmaps"
    / "AetherFlight_4033_16bit.png"
)
ASSETS = (
    "M_MeshTerrain_Aether",
    "MPD_AetherWorld",
    "TP_Preview_AetherWorld",
    "TP_Compiled_HighEnd_AetherWorld",
    "TP_Compiled_Common_AetherWorld",
)
AUTHORITY_TAG = unreal.Name("AetherProductionTerrain")


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


def safe_len(obj, property_name: str):
    try:
        return len(obj.get_editor_property(property_name))
    except Exception:
        return None


def main() -> None:
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(MAP_PATH)
    lines = []
    ready = True

    if HEIGHTMAP.is_file():
        lines.append("OK       AetherFlight_4033_16bit.png")
    else:
        lines.append("MISSING  AetherFlight_4033_16bit.png")
        ready = False

    loaded = {}
    for asset_name in ASSETS:
        asset = unreal.EditorAssetLibrary.load_asset(
            f"{PACKAGE}/{asset_name}.{asset_name}"
        )
        loaded[asset_name] = asset
        if asset is None:
            lines.append(f"MISSING  {asset_name}")
            ready = False
        else:
            lines.append(f"OK       {asset_name}")

    for pipeline_name in ASSETS[2:]:
        pipeline = loaded.get(pipeline_name)
        if pipeline is None:
            continue
        transformer_count = safe_len(pipeline, "transformers")
        if transformer_count == 0:
            lines.append(f"MISSING  {pipeline_name}: transformer stack is empty")
            ready = False
        elif transformer_count is None:
            lines.append(f"CHECK    {pipeline_name}: verify transformer stack manually")
        else:
            lines.append(f"OK       {pipeline_name}: {transformer_count} transformers")

    actors = list(
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    )
    landscapes = [actor for actor in actors if is_landscape(actor)]
    roots = [actor for actor in actors if is_mesh_partition_root(actor)]
    authoritative = [actor for actor in roots if AUTHORITY_TAG in actor.tags]

    lines.append(f"INFO     Classic Landscape actors: {len(landscapes)}")
    lines.append(f"INFO     Mesh Partition roots: {len(roots)}")
    lines.append(f"INFO     Authoritative roots: {len(authoritative)}")

    if landscapes:
        ready = False
        lines.append("FAIL     Re-run ResetAetherTerrain_UE58.py")
    if len(roots) != 1:
        ready = False
        lines.append("FAIL     Import the heightmap exactly once")
    if roots and len(authoritative) != 1:
        lines.append("NEXT     Build Mesh Partition, then run ActivateAetherMeshTerrain_UE58.py")

    title = "Aether Mesh Terrain — Clean and Ready" if ready else "Aether Mesh Terrain — Action Required"
    unreal.EditorDialog.show_message(title, "\n".join(lines), unreal.AppMsgType.OK)


if __name__ == "__main__":
    main()
