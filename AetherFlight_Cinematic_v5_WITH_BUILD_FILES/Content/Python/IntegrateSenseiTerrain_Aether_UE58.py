"""Backward-compatible entry point for the Aether Sensei Terrain integration.

The complete installation and repair logic now lives in
DisableAetherSenseiDisplacement_UE58.py so both scripts use the same safe UE 5.8
material-instance creation path and always disable terrain displacement.
"""

from pathlib import Path
import runpy

import unreal


SCRIPT = Path(
    unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir()
        + "Python/DisableAetherSenseiDisplacement_UE58.py"
    )
)

if not SCRIPT.is_file():
    raise RuntimeError(f"Missing Aether Sensei repair script: {SCRIPT}")

runpy.run_path(str(SCRIPT), run_name="__main__")
