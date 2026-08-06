"""Install one clean UE 5.8 Mesh Terrain authoring stack for AetherFlight.

This wrapper imports reusable terrain textures when needed, then calls the tested
Aether Mesh Terrain material/MPD/pipeline bootstrap without invoking the obsolete
Landscape migration dialog. It does not create the Mesh Partition actor because
UE 5.8's heightmap importer and TInstancedStruct transformer arrays still require
editor-side setup.
"""

from pathlib import Path
import sys

import unreal


LOG_PREFIX = "[Aether Clean Mesh Terrain Installer]"
SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherMeshTerrainInstall.txt"
HEIGHTMAP_SOURCE = (
    Path(unreal.Paths.project_dir())
    / "SourceAssets"
    / "ProductionTerrain"
    / "Heightmaps"
    / "AetherFlight_4033_16bit.png"
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import InstallAetherMeshTerrain_UE58 as mesh_bootstrap  # noqa: E402
import InstallProductionLandscape as texture_bootstrap  # noqa: E402


def log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def ensure_source_heightmap() -> None:
    if not HEIGHTMAP_SOURCE.is_file():
        raise RuntimeError(f"Missing required 16-bit PNG: {HEIGHTMAP_SOURCE}")
    log(f"Verified heightmap: {HEIGHTMAP_SOURCE.name}")


def ensure_reusable_textures() -> None:
    required = [
        f"T_{layer}_BaseColor"
        for layer in mesh_bootstrap.LAYERS
    ] + ["T_MacroVariation"]
    missing = []
    for name in required:
        path = f"{mesh_bootstrap.TEXTURE_PACKAGE}/{name}.{name}"
        if unreal.EditorAssetLibrary.load_asset(path) is None:
            missing.append(name)
    if missing:
        log(
            "Reusable terrain textures are missing; importing them from "
            "SourceAssets/ProductionTerrain/Textures"
        )
        texture_bootstrap.import_textures()


def main() -> None:
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before installing Mesh Terrain assets")
    except AttributeError:
        pass

    ensure_source_heightmap()
    mesh_bootstrap.plugin_preflight()
    ensure_reusable_textures()

    unreal.EditorAssetLibrary.make_directory(mesh_bootstrap.PACKAGE)
    material = mesh_bootstrap.build_material()
    definition, channels_ready = mesh_bootstrap.configure_definition(material)
    pipelines = mesh_bootstrap.create_pipeline_shells()
    weight_count = mesh_bootstrap.import_weightmaps()
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)

    report = (
        "Aether clean Mesh Terrain authoring assets installed.\n"
        f"Material: {material.get_path_name()}\n"
        f"Definition: {definition.get_path_name()}\n"
        f"Pipeline shells: {len(pipelines)}\n"
        f"Weightmaps: {weight_count}/7\n"
        f"Channels authored through Python: {channels_ready}\n"
        "Required heightmap: AetherFlight_4033_16bit.png\n"
        "Next: complete the transformer arrays in the Details panel, then import "
        "the PNG through Mesh Terrain > Create > Import Heightmap.\n"
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log(report.replace("\n", " | "))


if __name__ == "__main__":
    main()
