"""Retired compatibility entry point for Aether terrain biome tuning.

The previous replacement-material experiment could render white/gray terrain on
Mesh Terrain. It is permanently retired. Running this file now forwards to the
safe Sensei material-instance tuning pass.
"""

from pathlib import Path
import runpy

import unreal


replacement = Path(
    unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_content_dir() + "Python/TuneAetherSenseiBiomes_UE58.py"
    )
)
if not replacement.is_file():
    raise RuntimeError(f"Missing safe Sensei biome tuner: {replacement}")

unreal.log_warning(
    "[Aether Biome Distribution] Replacement-material pass retired; "
    "forwarding to safe Sensei tuning."
)
runpy.run_path(str(replacement), run_name="__main__")
