"""Restore the verified Sensei surface instance as AetherWorld's active material."""

from pathlib import Path

import unreal


DEFINITION_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
ROLLBACK_PATH = (
    "/Game/Aether/MeshTerrain/"
    "MI_AetherTerrain_Sensei_Surface.MI_AetherTerrain_Sensei_Surface"
)
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherBiomeRollbackReport.txt"


def path_of(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def main():
    definition = unreal.EditorAssetLibrary.load_asset(DEFINITION_PATH)
    rollback = unreal.EditorAssetLibrary.load_asset(ROLLBACK_PATH)
    if definition is None:
        raise RuntimeError(f"Missing Mesh Partition definition: {DEFINITION_PATH}")
    if not isinstance(rollback, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Missing verified Sensei rollback material: {ROLLBACK_PATH}")

    before = path_of(definition.get_editor_property("material"))
    definition.set_editor_property("material", rollback)
    if not unreal.EditorAssetLibrary.save_loaded_asset(definition, False):
        raise RuntimeError(f"Failed to save Mesh Partition definition: {DEFINITION_PATH}")

    after = path_of(definition.get_editor_property("material"))
    if after != ROLLBACK_PATH:
        raise RuntimeError(f"Rollback verification failed: active material is {after}")

    report = (
        "Aether Sensei surface rollback complete.\n\n"
        f"Before: {before}\n"
        f"After: {after}\n\n"
        "The verified Sensei surface is active again.\n"
        "Terrain geometry, collision, Mesh Partition resolution, and streaming were not changed."
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    unreal.log_warning("AETHER_SENSEI_SURFACE_RESTORED=" + after)


if __name__ == "__main__":
    main()
