"""One-click Unreal Editor import for Aether Flight's licensed drone model."""

from pathlib import Path
import unreal


DESTINATION = "/Game/Aircraft/StealthDrone"
EXPECTED_ASSET = f"{DESTINATION}/SM_StealthDrone.SM_StealthDrone"


def log(message: str) -> None:
    unreal.log(f"[Aether Setup] {message}")


project_dir = Path(unreal.Paths.project_dir())
source_file = project_dir / "SourceAssets" / "StealthDrone" / "stealth_drone_combined.glb"

if not source_file.is_file():
    raise FileNotFoundError(f"Drone source is missing: {source_file}")


def find_existing_mesh():
    expected = unreal.EditorAssetLibrary.load_asset(EXPECTED_ASSET)
    if isinstance(expected, unreal.StaticMesh):
        return expected

    for asset_path in unreal.EditorAssetLibrary.list_assets(DESTINATION, recursive=True, include_folder=False):
        obj = unreal.EditorAssetLibrary.load_asset(asset_path)
        if isinstance(obj, unreal.StaticMesh) and obj.get_name() == "SM_StealthDrone":
            return obj
    return None


mesh = find_existing_mesh()
if mesh is None:
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source_file))
    task.set_editor_property("destination_path", DESTINATION)
    task.set_editor_property("destination_name", "SM_StealthDrone")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("replace_existing_settings", False)
    task.set_editor_property("save", True)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = find_existing_mesh()
    if mesh is None:
        raise RuntimeError(
            "Unreal did not produce a Static Mesh. Confirm that the Interchange glTF importer is enabled, then run this script again."
        )

if mesh.get_path_name() != EXPECTED_ASSET:
    original_path = mesh.get_path_name()
    rename = unreal.AssetRenameData(mesh, DESTINATION, "SM_StealthDrone")
    if not unreal.AssetToolsHelpers.get_asset_tools().rename_assets([rename]):
        raise RuntimeError(f"Found {original_path}, but could not move it to {EXPECTED_ASSET}")
    mesh = unreal.EditorAssetLibrary.load_asset(EXPECTED_ASSET)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError(f"The airframe move completed, but {EXPECTED_ASSET} could not be loaded")
    log(f"Moved existing airframe from {original_path} to {EXPECTED_ASSET}")
else:
    log("SM_StealthDrone is already at the runtime path. Nothing was overwritten.")

try:
    nanite = mesh.get_editor_property("nanite_settings")
    # This mesh uses a translucent sticker material, which Nanite does not
    # support. At ~27k triangles conventional rendering is inexpensive and
    # preserves every material slot correctly.
    nanite.set_editor_property("enabled", False)
    mesh.set_editor_property("nanite_settings", nanite)
except Exception as exc:
    unreal.log_warning(f"[Aether Setup] Nanite compatibility setting could not be applied: {exc}")

try:
    static_mesh_tools = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    build = static_mesh_tools.get_lod_build_settings(mesh, 0)
    build.set_editor_property("recompute_normals", True)
    build.set_editor_property("recompute_tangents", True)
    build.set_editor_property("compute_weighted_normals", True)
    build.set_editor_property("remove_degenerates", True)
    build.set_editor_property("use_mikk_t_space", False)
    build.set_editor_property("use_high_precision_tangent_basis", True)
    static_mesh_tools.set_lod_build_settings(mesh, 0, build)
    log("Rebuilt airframe normals and tangents for clean shading")
except Exception as exc:
    unreal.log_warning(f"[Aether Setup] Airframe tangent rebuild was skipped: {exc}")

try:
    mesh.set_editor_property("light_map_resolution", 256)
except Exception as exc:
    unreal.log_warning(f"[Aether Setup] Light-map resolution was left at the importer default: {exc}")

unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False)
log(f"Production airframe ready: {mesh.get_path_name()}")

unreal.EditorDialog.show_message(
    "Aether Flight",
    "Stealth drone import is ready. Press Play; the aircraft pawn will load it automatically.",
    unreal.AppMsgType.OK,
)
