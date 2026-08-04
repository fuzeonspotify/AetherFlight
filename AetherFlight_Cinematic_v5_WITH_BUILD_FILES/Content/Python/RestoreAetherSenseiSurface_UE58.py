"""Restore the verified Sensei surface instance as AetherWorld's active material."""

from pathlib import Path

import unreal


DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
ROLLBACK_PATH = (
    "/Game/Aether/MeshTerrain/"
    "MI_AetherTerrain_Sensei_Surface.MI_AetherTerrain_Sensei_Surface"
)
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherBiomeRollbackReport.txt"


def main() -> None:
    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    rollback = unreal.EditorAssetLibrary.load_asset(ROLLBACK_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")
    if not isinstance(rollback, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Missing verified Sensei rollback material: {ROLLBACK_PATH}")

    before = definition.get_editor_property("material")
    definition.set_editor_property("material", rollback)
    try:
        definition.post_edit_change()
    except Exception:
        pass
    if not unreal.EditorAssetLibrary.save_loaded_asset(definition, False):
        raise RuntimeError(f"Failed to save Mesh Partition definition: {DEFINITION_PATH}")

    report = (
        "Aether Sensei surface rollback complete.\n\n"
        f"Before: {before.get_path_name() if before else 'None'}\n"
        f"After: {ROLLBACK_PATH}\n\n"
        "Terrain geometry, collision, Mesh Partition resolution, and streaming were not changed."
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    unreal.log(report.replace("\n", " | "))


if __name__ == "__main__":
    main()
