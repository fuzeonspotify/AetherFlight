"""Build the UE 5.8 landscape material for the supplied Heightmap_Out terrain.

The project already contains a tested material installer and aerial anti-tiling
upgrade. This entry point runs those proven builders, but retunes the material
for the fresh 2017 landscape's 400 cm vertex spacing.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import unreal


PROJECT_DIR = Path(unreal.Paths.project_dir())
PYTHON_DIR = PROJECT_DIR / "Content" / "Python"
VIDEO_SOURCE_DIR = PROJECT_DIR / "SourceAssets" / "VideoLandscape"
HEIGHTMAP_FILE = VIDEO_SOURCE_DIR / "Heightmaps" / "Heightmap_Out_2017_16bit.png"
WEIGHTMAP_DIR = VIDEO_SOURCE_DIR / "Weightmaps"
LAYERS = ("Grass", "Rock", "Scree", "Snow")
XY_VERTEX_SPACING_CM = 400.0


def load_module(module_name: str, file_name: str):
    file_path = PYTHON_DIR / file_name
    if not file_path.is_file():
        raise RuntimeError(f"Missing required project script: {file_path}")
    spec = spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Python module from {file_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_source_files() -> None:
    if not HEIGHTMAP_FILE.is_file():
        raise RuntimeError(f"Missing processed heightmap: {HEIGHTMAP_FILE}")
    missing = [
        WEIGHTMAP_DIR / f"Heightmap_Out_{layer_name}_2017.png"
        for layer_name in LAYERS
        if not (WEIGHTMAP_DIR / f"Heightmap_Out_{layer_name}_2017.png").is_file()
    ]
    if missing:
        raise RuntimeError("Missing weightmaps:\n" + "\n".join(str(path) for path in missing))


def main() -> None:
    validate_source_files()

    installer = load_module(
        "aether_production_landscape_installer",
        "InstallProductionLandscape.py",
    )
    textures = installer.import_textures()
    installer.build_material(textures)
    installer.create_layer_info_assets()

    aerial = load_module(
        "aether_fresh_landscape_aerial_material",
        "UpgradeAerialLandscapeMaterial_UE58_v5.py",
    )
    aerial.XY_VERTEX_SPACING_CM = XY_VERTEX_SPACING_CM
    aerial.build_material()

    unreal.EditorDialog.show_message(
        "Fresh Heightmap Landscape Assets Ready",
        "The tested production PBR material was rebuilt and retuned for the fresh 2017 terrain.\n\n"
        "Import SourceAssets/VideoLandscape/Heightmaps/Heightmap_Out_2017_16bit.png\n"
        "with 63 quads, 2x2 sections, 16x16 components, and XYZ scale 400.\n\n"
        "Then import the four 2017 weightmaps and run\n"
        "Content/Python/FinalizeFreshVideoLandscape.py.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
