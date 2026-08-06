"""Check whether AetherFlight's production foliage and rock meshes are installed."""

import unreal


ASSET_GROUPS = {
    "Primary conifer": [
        "/Game/Aether/Environment/Foliage/SM_Conifer_A",
        "/Game/Aether/Environment/Foliage/SM_Conifer",
    ],
    "Secondary conifer": [
        "/Game/Aether/Environment/Foliage/SM_Conifer_B",
        "/Game/Aether/Environment/Foliage/SM_Conifer_02",
    ],
    "Broadleaf tree": [
        "/Game/Aether/Environment/Foliage/SM_Broadleaf_A",
        "/Game/Aether/Environment/Foliage/SM_Broadleaf",
    ],
    "Shrub": [
        "/Game/Aether/Environment/Foliage/SM_Shrub_A",
        "/Game/Aether/Environment/Foliage/SM_Shrub",
    ],
    "Ground cover": [
        "/Game/Aether/Environment/Foliage/SM_GroundCover_A",
        "/Game/Aether/Environment/Foliage/SM_Fern",
    ],
    "Primary boulder": [
        "/Game/Aether/Environment/Rocks/SM_Boulder_A",
        "/Game/Aether/Environment/Rocks/SM_CliffRock",
    ],
    "Secondary boulder": [
        "/Game/Aether/Environment/Rocks/SM_Boulder_B",
        "/Game/Aether/Environment/Rocks/SM_CliffRock_B",
    ],
}


def find_first(paths):
    for path in paths:
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            return path
    return None


def static_meshes_under(package_path):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    meshes = []
    for asset_data in registry.get_assets_by_path(package_path, recursive=True):
        asset = asset_data.get_asset()
        if isinstance(asset, unreal.StaticMesh):
            meshes.append(asset.get_path_name())
    return meshes


def main():
    found = {}
    lines = []
    for label, paths in ASSET_GROUPS.items():
        resolved = find_first(paths)
        found[label] = resolved
        if resolved:
            lines.append(f"FOUND  {label}: {resolved}")
            unreal.log(f"[Aether Environment Audit] FOUND {label}: {resolved}")
        else:
            lines.append(f"MISSING  {label}: expected {paths[0]}")
            unreal.log_warning(
                f"[Aether Environment Audit] MISSING {label}: expected {paths[0]}"
            )

    pine_meshes = static_meshes_under("/Game/DZ_Assets/DZ_Trees/Meshes/Pine")
    aspen_meshes = static_meshes_under("/Game/DZ_Assets/DZ_Trees/Meshes/Aspen")
    imported_rocks = static_meshes_under("/Game/Aether/Environment/Rocks")
    for index in range(1, 8):
        imported_rocks.extend(static_meshes_under(f"/Game/Rock_{index:02d}"))

    lines.append(f"AUTO  DZ Pine meshes found: {len(pine_meshes)}")
    lines.append(f"AUTO  DZ Aspen meshes found: {len(aspen_meshes)}")
    lines.append(f"AUTO  SM_Rock-compatible meshes found: {len(imported_rocks)}")
    unreal.log(
        f"[Aether Environment Audit] Auto-discovery: {len(pine_meshes)} pine, "
        f"{len(aspen_meshes)} aspen, {len(imported_rocks)} rock meshes"
    )

    trees_ready = bool(found["Primary conifer"] or found["Broadleaf tree"])
    trees_ready = trees_ready or bool(pine_meshes or aspen_meshes)
    rocks_ready = bool(found["Primary boulder"] or imported_rocks)
    essential_ready = trees_ready and rocks_ready
    heading = (
        "Essential environment assets are ready."
        if essential_ready
        else "Environment assets still need to be installed."
    )
    unreal.EditorDialog.show_message(
        "AetherFlight Environment Audit",
        heading + "\n\n" + "\n".join(lines)
        + "\n\nSee HIGH_QUALITY_ENVIRONMENT_SETUP.md for the exact setup.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
