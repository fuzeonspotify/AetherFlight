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

    essential_ready = bool(found["Primary conifer"] or found["Broadleaf tree"])
    essential_ready = essential_ready and bool(found["Primary boulder"])
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
