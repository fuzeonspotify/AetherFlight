"""Run the Stage 13 installer with the UE 5.8 V2 compatibility patches."""

from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Importing this module patches the original Stage 13 helper module in-place.
import AetherRiverEnvironmentCommon_UE58_v2  # noqa: F401

ORIGINAL_INSTALLER = SCRIPT_DIR / "InstallAetherVideoRiverEnvironmentStage_UE58.py"
if not ORIGINAL_INSTALLER.is_file():
    raise RuntimeError(f"Original Stage 13 installer is missing: {ORIGINAL_INSTALLER}")

source = ORIGINAL_INSTALLER.read_text(encoding="utf-8")
namespace = {
    "__file__": str(ORIGINAL_INSTALLER),
    "__name__": "__main__",
}
exec(compile(source, str(ORIGINAL_INSTALLER), "exec"), namespace, namespace)
