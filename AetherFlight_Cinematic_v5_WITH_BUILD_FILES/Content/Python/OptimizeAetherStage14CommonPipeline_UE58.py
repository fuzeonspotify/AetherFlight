"""Stage 14C: remove the duplicate visual transformer from the Common pipeline.

The Mesh Partition definition already uses the documented Highend + Common
variant pattern. Highend owns the visual static meshes; Common should own shared
collision. This guarded installer removes only the trailing StaticMeshTransformer
from TP_Compiled_Common_AetherWorld. It verifies the exact current layout,
preserves the Highend pipeline byte-for-byte, saves only the Common pipeline,
and restores the original Common array if any validation or save step fails.

No map, MPD, terrain actor, compiled section, preview section, cook, PIE session,
or Mesh Partition build is touched.
"""

from pathlib import Path
import unreal

COMMON_PATH = "/Game/Aether/MeshTerrain/TP_Compiled_Common_AetherWorld"
HIGHEND_PATH = "/Game/Aether/MeshTerrain/TP_Compiled_HighEnd_AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14CommonPipelineOptimization.txt"
LINES = []

EXPECTED_COMMON_TYPES = (
    "SubsectionTransformer",
    "CollisionTransformer",
    "WPActorPropertiesTransformer",
    "StaticMeshTransformer",
)
EXPECTED_OPTIMIZED_COMMON_TYPES = EXPECTED_COMMON_TYPES[:3]
EXPECTED_HIGHEND_TYPES = (
    "FarFieldTransformer",
    "SubsectionTransformer",
    "StaticMeshTransformer",
    "WPActorPropertiesTransformer",
)


def log(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def load_asset(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        raise RuntimeError(f"Could not load asset: {path}")
    return asset


def get_transformers(pipeline):
    try:
        return list(pipeline.get_editor_property("transformers"))
    except Exception as exc:
        raise RuntimeError(f"Could not read {pipeline.get_path_name()}.transformers: {exc}")


def export_entry(entry):
    try:
        return str(entry.export_text())
    except Exception as exc:
        raise RuntimeError(f"Could not export transformer InstancedStruct: {exc}")


def transformer_type(exported):
    head = str(exported).split("(", 1)[0]
    return head.rsplit(".", 1)[-1]


def snapshot(pipeline):
    entries = get_transformers(pipeline)
    exports = tuple(export_entry(entry) for entry in entries)
    types = tuple(transformer_type(value) for value in exports)
    return entries, exports, types


def copy_entry(entry):
    method = getattr(entry, "copy", None)
    if callable(method):
        return method()
    return entry


def set_transformers(pipeline, entries):
    values = [copy_entry(entry) for entry in entries]
    errors = []
    try:
        pipeline.set_editor_property("transformers", values)
        return
    except Exception as exc:
        errors.append(f"python list: {type(exc).__name__}: {exc}")

    array_type = getattr(unreal, "Array", None)
    instanced_struct_type = getattr(unreal, "InstancedStruct", None)
    if array_type and instanced_struct_type:
        try:
            array_value = array_type(instanced_struct_type)
            for value in values:
                array_value.append(value)
            pipeline.set_editor_property("transformers", array_value)
            return
        except Exception as exc:
            errors.append(f"unreal.Array: {type(exc).__name__}: {exc}")

    raise RuntimeError(f"Could not assign transformer array. Errors={errors}")


def save_asset(asset, path):
    modify = getattr(asset, "modify", None)
    if callable(modify):
        try:
            modify()
        except Exception:
            pass

    errors = []
    method = getattr(unreal.EditorAssetLibrary, "save_loaded_asset", None)
    if callable(method):
        for args in ((asset, False), (asset,)):
            try:
                result = method(*args)
                if result is None or bool(result):
                    return True
                errors.append(f"save_loaded_asset{args[1:]} returned {result}")
            except Exception as exc:
                errors.append(f"save_loaded_asset{args[1:]}: {type(exc).__name__}: {exc}")

    method = getattr(unreal.EditorAssetLibrary, "save_asset", None)
    if callable(method):
        for args in ((path, False), (path,)):
            try:
                result = method(*args)
                if result is None or bool(result):
                    return True
                errors.append(f"save_asset{args[1:]} returned {result}")
            except Exception as exc:
                errors.append(f"save_asset{args[1:]}: {type(exc).__name__}: {exc}")

    raise RuntimeError(f"Could not save {path}. Errors={errors}")


def log_pipeline(prefix, exports, types):
    log(f"{prefix}_TRANSFORMER_COUNT={len(exports)}")
    for index, (entry_type, exported) in enumerate(zip(types, exports)):
        log(f"{prefix}_TRANSFORMER_{index}_TYPE={entry_type}")
        log(f"{prefix}_TRANSFORMER_{index}_EXPORT_TEXT={exported}")


def validate_layout(name, types, expected):
    if tuple(types) != tuple(expected):
        raise RuntimeError(
            f"{name} transformer layout mismatch. Actual={tuple(types)} Expected={tuple(expected)}"
        )


def main():
    log("AETHER STAGE 14C - REMOVE DUPLICATE COMMON VISUAL PIPELINE")
    log("=" * 100)
    log("GUARDED_ASSET_EDIT=TRUE")
    log("Only TP_Compiled_Common_AetherWorld may be changed.")
    log("Highend visual quality, Common collision, MPD settings, maps, and terrain remain unchanged.")

    common = load_asset(COMMON_PATH)
    highend = load_asset(HIGHEND_PATH)

    common_entries, common_exports_before, common_types_before = snapshot(common)
    _, highend_exports_before, highend_types_before = snapshot(highend)

    log_pipeline("COMMON_BEFORE", common_exports_before, common_types_before)
    log_pipeline("HIGHEND_BEFORE", highend_exports_before, highend_types_before)

    validate_layout("Common before optimization", common_types_before, EXPECTED_COMMON_TYPES)
    validate_layout("Highend before optimization", highend_types_before, EXPECTED_HIGHEND_TYPES)

    collision_text = common_exports_before[1]
    if 'CollisionProfile=(Name="BlockAll")' not in collision_text:
        raise RuntimeError("Common CollisionTransformer is not configured with BlockAll")
    if "StaticMeshTransformer" not in common_exports_before[3]:
        raise RuntimeError("The trailing Common transformer is not the duplicate StaticMeshTransformer")

    backup_entries = [copy_entry(entry) for entry in common_entries]
    mutation_applied = False

    try:
        optimized_entries = common_entries[:3]
        set_transformers(common, optimized_entries)
        mutation_applied = True

        _, common_exports_memory, common_types_memory = snapshot(common)
        validate_layout(
            "Common in-memory optimized layout",
            common_types_memory,
            EXPECTED_OPTIMIZED_COMMON_TYPES,
        )
        if tuple(common_exports_memory) != tuple(common_exports_before[:3]):
            raise RuntimeError("A retained Common transformer changed while removing the duplicate visual entry")

        _, highend_exports_memory, highend_types_memory = snapshot(highend)
        validate_layout("Highend in-memory layout", highend_types_memory, EXPECTED_HIGHEND_TYPES)
        if tuple(highend_exports_memory) != tuple(highend_exports_before):
            raise RuntimeError("Highend pipeline changed unexpectedly")

        save_asset(common, COMMON_PATH)

        common_reloaded = load_asset(COMMON_PATH)
        _, common_exports_after, common_types_after = snapshot(common_reloaded)
        validate_layout("Common saved layout", common_types_after, EXPECTED_OPTIMIZED_COMMON_TYPES)
        if tuple(common_exports_after) != tuple(common_exports_before[:3]):
            raise RuntimeError("Saved Common pipeline does not exactly match the three retained transformers")

        highend_reloaded = load_asset(HIGHEND_PATH)
        _, highend_exports_after, highend_types_after = snapshot(highend_reloaded)
        validate_layout("Highend saved layout", highend_types_after, EXPECTED_HIGHEND_TYPES)
        if tuple(highend_exports_after) != tuple(highend_exports_before):
            raise RuntimeError("Highend pipeline changed after Common save")

        log_pipeline("COMMON_AFTER", common_exports_after, common_types_after)
        log("")
        log("COMMON_PIPELINE_OPTIMIZATION_RESULT=PASS")
        log("COMMON_DUPLICATE_STATIC_MESH_TRANSFORMER_REMOVED=TRUE")
        log("COMMON_COLLISION_TRANSFORMER_PRESERVED=TRUE")
        log("COMMON_WP_PROPERTIES_TRANSFORMER_PRESERVED=TRUE")
        log("HIGHEND_PIPELINE_UNCHANGED=TRUE")
        log("HIGHEND_VISUAL_LODS_UNCHANGED=TRUE")
        log("HIGHEND_NANITE_UNCHANGED=TRUE")
        log("ONLY_COMMON_PIPELINE_ASSET_SAVED=TRUE")
        log("NO_MAP_SAVED=TRUE")
        log("NO_MPD_SETTINGS_CHANGED=TRUE")
        log("NO_PIE_STARTED=TRUE")
        log("NO_BUILD_METHOD_CALLED=TRUE")
        log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    except Exception:
        if mutation_applied:
            log("ROLLBACK_STARTED=TRUE")
            try:
                set_transformers(common, backup_entries)
                save_asset(common, COMMON_PATH)
                restored = load_asset(COMMON_PATH)
                _, restored_exports, restored_types = snapshot(restored)
                if tuple(restored_exports) != tuple(common_exports_before):
                    raise RuntimeError(
                        f"Rollback validation mismatch. Restored types={restored_types}"
                    )
                log("ROLLBACK_FINISHED=TRUE")
                log("ROLLBACK_VALIDATED=TRUE")
            except Exception as rollback_exc:
                log(f"ROLLBACK_FAILED={type(rollback_exc).__name__}: {rollback_exc}")
        raise

    write_report()
    unreal.log_warning(f"AETHER_STAGE14_COMMON_PIPELINE_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    log("")
    log("COMMON_PIPELINE_OPTIMIZATION_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("NO_MAP_SAVED=TRUE")
    log("NO_MPD_SETTINGS_CHANGED=TRUE")
    log("NO_PIE_STARTED=TRUE")
    log("NO_BUILD_METHOD_CALLED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE14_COMMON_PIPELINE_OPTIMIZATION_FAILED={type(exc).__name__}: {exc}")
    raise
