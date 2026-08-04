"""Stage 13 river-environment preflight with UE 5.8 compatibility checks."""

from pathlib import Path
import importlib
import sys

import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Patch the shared helpers before loading the original full audit.
import AetherRiverEnvironmentCommon_UE58_v2 as common

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherRiverEnvironmentAPIAudit.txt"


def append_line(lines, text=""):
    text = str(text)
    lines.append(text)
    unreal.log_warning(text)


def run_v2_checks():
    # Importing the original audit executes its complete read-only preflight and
    # writes the base report. V2 then tightens the asset and ChannelName checks.
    original = importlib.import_module("AuditAetherRiverEnvironmentAPI_UE58")

    extra = []
    append_line(extra, "")
    append_line(extra, "UE 5.8 STAGE 13 COMPATIBILITY CHECKS V2")
    append_line(extra, "-" * 96)

    channel_ok = False
    channel_error = None
    try:
        channel = common.make_channel_name("FoliageExclusion", extra)
        entry_class = getattr(unreal, "SplineModifierWeightEntry", None)
        if entry_class is None:
            raise RuntimeError("unreal.SplineModifierWeightEntry is unavailable")
        entry = entry_class()
        entry.set_editor_property("weight_channel_name", channel)
        stored = entry.get_editor_property("weight_channel_name")
        append_line(extra, f"FoliageExclusion ChannelName assignment={stored}")
        channel_ok = True
    except Exception as exc:
        channel_error = f"{type(exc).__name__}: {exc}"
        append_line(extra, f"FoliageExclusion ChannelName assignment FAILED={channel_error}")

    asset_paths = common.list_game_assets()
    rocks = common.discover_static_meshes(asset_paths, common.ROCK_TOKENS, 12)
    shrubs = common.discover_static_meshes(asset_paths, common.SHRUB_TOKENS, 12)
    ground = common.discover_static_meshes(asset_paths, common.GROUND_TOKENS, 12)

    append_line(extra, f"Strict production rock meshes={len(rocks)}")
    for path, _ in rocks:
        append_line(extra, f"  ROCK={path}")
    append_line(extra, f"Strict production shrub meshes={len(shrubs)}")
    for path, _ in shrubs:
        append_line(extra, f"  SHRUB={path}")
    append_line(extra, f"Strict production ground-cover meshes={len(ground)}")
    for path, _ in ground:
        append_line(extra, f"  GROUND={path}")

    icon_paths = [
        path
        for path, _ in shrubs
        if "sm_icon_" in str(path).lower() or "/globalfoliageactor/" in str(path).lower()
    ]
    append_line(extra, f"Editor/helper meshes selected as shrubs={len(icon_paths)}")

    assets_ok = bool(rocks and shrubs and ground and not icon_paths)
    status = "PASS" if channel_ok and assets_ok else "CHECK"
    append_line(extra, f"ChannelName construction valid={channel_ok}")
    append_line(extra, f"Strict environment asset selection valid={assets_ok}")
    append_line(extra, f"AETHER_RIVER_ENVIRONMENT_API={status}")
    append_line(extra, "NO_ACTORS_SPAWNED=TRUE")
    append_line(extra, "NO_INSTANCES_ADDED=TRUE")
    append_line(extra, "NO_PACKAGES_SAVED=TRUE")
    append_line(extra, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    base_text = REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.is_file() else ""
    base_text = base_text.replace(
        "AETHER_RIVER_ENVIRONMENT_API=PASS",
        "AETHER_RIVER_ENVIRONMENT_API_BASE=PASS",
    ).replace(
        "AETHER_RIVER_ENVIRONMENT_API=CHECK",
        "AETHER_RIVER_ENVIRONMENT_API_BASE=CHECK",
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(base_text.rstrip() + "\n" + "\n".join(extra) + "\n", encoding="utf-8")


try:
    run_v2_checks()
except Exception as exc:
    message = (
        "AETHER_RIVER_ENVIRONMENT_API=FAIL\n"
        f"ERROR={type(exc).__name__}: {exc}\n"
        "NO_ACTORS_SPAWNED=TRUE\n"
        "NO_INSTANCES_ADDED=TRUE\n"
        "NO_PACKAGES_SAVED=TRUE\n"
        "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE\n"
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
