"""Stage 14 build-cost audit V2: unwrap Mesh Partition InstancedStruct payloads.

Read-only. Uses StructBase.export_text(), StructBase.to_tuple(), exposed
properties, and safe no-argument type queries to reveal the concrete settings
inside MPD_AetherWorld transformer entries and platform runtime settings.
No assets are changed or saved and no Mesh Partition build is invoked.
"""

from pathlib import Path
import unreal

MPD_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14MeshPartitionBuildCostAuditV2.txt"
LINES = []

INTERESTING_TOKENS = (
    "struct", "script", "type", "value", "data", "memory", "transform",
    "section", "subsection", "sub_section", "grid", "cell", "runtime",
    "lod", "screen", "pixel", "error", "collision", "complex", "nanite",
    "simpl", "edge", "far", "platform", "build", "variant", "pipeline",
)

DIRECT_PROPERTIES = (
    "compiled_section_build_variants",
    "per_platform_runtime_settings",
    "default_platform_runtime_settings",
    "preview_transformer_pipeline",
    "transformers",
    "name",
    "max_section_complexity",
    "transformer_pipeline",
    "section_size",
    "subsection_size",
    "sub_section_size",
    "cell_size",
    "grid_cell_size",
    "runtime_grid",
    "grid_name",
    "num_lods",
    "lod_count",
    "pixel_error",
    "error_tolerance",
    "screen_size",
    "screen_sizes",
    "generate_collision",
    "collision_enabled",
    "enable_nanite",
    "nanite_enabled",
    "far_field_mesh_edge_length",
    "mesh_edge_length",
    "script_struct",
    "struct_type",
    "value",
    "data",
    "memory",
)


def log(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def safe_class_path(value):
    try:
        return value.get_class().get_path_name()
    except Exception:
        return type(value).__name__


def safe_object_path(value):
    try:
        return value.get_path_name()
    except Exception:
        return None


def safe_get(value, name):
    try:
        return value.get_editor_property(name), True
    except Exception:
        try:
            return getattr(value, name), True
        except Exception:
            return None, False


def shorten(value, limit=12000):
    try:
        text = str(value)
    except Exception:
        text = repr(value)
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def export_struct(value, label):
    method = getattr(value, "export_text", None)
    if callable(method):
        try:
            text = method()
            log(f"{label}_EXPORT_TEXT={shorten(text)}")
            return text
        except Exception as exc:
            log(f"{label}_EXPORT_TEXT_ERROR={type(exc).__name__}: {exc}")
    else:
        log(f"{label}_EXPORT_TEXT_UNAVAILABLE=TRUE")
    return None


def tuple_struct(value, label):
    method = getattr(value, "to_tuple", None)
    if not callable(method):
        log(f"{label}_TO_TUPLE_UNAVAILABLE=TRUE")
        return []
    try:
        items = list(method())
    except Exception as exc:
        log(f"{label}_TO_TUPLE_ERROR={type(exc).__name__}: {exc}")
        return []
    log(f"{label}_TUPLE_COUNT={len(items)}")
    for index, item in enumerate(items):
        item_label = f"{label}_TUPLE_{index}"
        log(f"{item_label}_TYPE={safe_class_path(item)}")
        path = safe_object_path(item)
        if path:
            log(f"{item_label}_PATH={path}")
        log(f"{item_label}_VALUE={shorten(item, 4000)}")
        if item is not value and hasattr(item, "export_text"):
            export_struct(item, item_label)
    return items


def relevant_dir_names(value):
    result = []
    try:
        names = dir(value)
    except Exception:
        names = []
    for name in names:
        lower = str(name).lower()
        if any(token in lower for token in INTERESTING_TOKENS):
            result.append(str(name))
    return sorted(set(result))


def probe_exposed_properties(value, label):
    names = set(DIRECT_PROPERTIES)
    names.update(relevant_dir_names(value))
    exposed = 0
    for name in sorted(names):
        property_value, ok = safe_get(value, name)
        if not ok or callable(property_value):
            continue
        exposed += 1
        log(f"{label}_PROPERTY_{name}_TYPE={safe_class_path(property_value)}")
        path = safe_object_path(property_value)
        if path:
            log(f"{label}_PROPERTY_{name}_PATH={path}")
        log(f"{label}_PROPERTY_{name}_VALUE={shorten(property_value, 5000)}")
        if property_value is not value and hasattr(property_value, "export_text"):
            export_struct(property_value, f"{label}_PROPERTY_{name}")
    log(f"{label}_EXPOSED_PROPERTY_COUNT={exposed}")


def probe_safe_noarg_methods(value, label):
    # Only introspection methods are attempted. Mutating/reset/import methods are
    # deliberately excluded even if present in dir().
    candidates = (
        "get_script_struct",
        "get_struct_type",
        "get_type",
        "is_valid",
    )
    for name in candidates:
        method = getattr(value, name, None)
        if not callable(method):
            continue
        try:
            result = method()
            log(f"{label}_METHOD_{name}_TYPE={safe_class_path(result)}")
            path = safe_object_path(result)
            if path:
                log(f"{label}_METHOD_{name}_PATH={path}")
            log(f"{label}_METHOD_{name}_VALUE={shorten(result, 5000)}")
        except Exception as exc:
            log(f"{label}_METHOD_{name}_ERROR={type(exc).__name__}: {exc}")


def probe_instanced_struct(value, label):
    log("")
    log(f"{label}_TYPE={safe_class_path(value)}")
    log(f"{label}_RAW={shorten(value, 4000)}")
    try:
        valid = unreal.BlueprintInstancedStructLibrary.is_valid_instanced_struct(value)
        log(f"{label}_BLUEPRINT_LIBRARY_VALID={valid}")
    except Exception as exc:
        log(f"{label}_BLUEPRINT_LIBRARY_VALID_ERROR={type(exc).__name__}: {exc}")
    export_struct(value, label)
    tuple_struct(value, label)
    probe_safe_noarg_methods(value, label)
    probe_exposed_properties(value, label)
    log(f"{label}_RELEVANT_DIR_NAMES={','.join(relevant_dir_names(value))}")


def probe_runtime_settings(value):
    label = "PER_PLATFORM_RUNTIME_SETTINGS"
    log("")
    log(f"{label}_TYPE={safe_class_path(value)}")
    log(f"{label}_RAW={shorten(value, 5000)}")
    export_struct(value, label)
    tuple_struct(value, label)
    probe_exposed_properties(value, label)


def main():
    log("AETHER STAGE 14 - MESH PARTITION BUILD COST AUDIT V2")
    log("=" * 100)
    log("READ_ONLY=TRUE")
    log("Unwraps transformer InstancedStruct data using export_text/to_tuple and reflection only.")
    log("No asset mutation, package save, PIE command, preview build, compiled build, cook, or commandlet is invoked.")

    mpd = unreal.EditorAssetLibrary.load_asset(MPD_PATH)
    if not mpd:
        raise RuntimeError(f"Could not load {MPD_PATH}")
    log(f"MPD_PATH={mpd.get_path_name()}")
    log(f"MPD_CLASS={safe_class_path(mpd)}")

    variants, ok = safe_get(mpd, "compiled_section_build_variants")
    if not ok:
        raise RuntimeError("MPD does not expose compiled_section_build_variants")
    variants = list(variants)
    log(f"COMPILED_VARIANT_COUNT={len(variants)}")

    total_transformers = 0
    for variant_index, variant in enumerate(variants):
        variant_label = f"VARIANT_{variant_index}"
        name, _ = safe_get(variant, "name")
        complexity, _ = safe_get(variant, "max_section_complexity")
        pipeline, _ = safe_get(variant, "transformer_pipeline")
        log("")
        log(f"{variant_label}_NAME={name}")
        log(f"{variant_label}_MAX_SECTION_COMPLEXITY={complexity}")
        log(f"{variant_label}_EXPORT_TEXT={shorten(variant.export_text() if hasattr(variant, 'export_text') else variant)}")
        if not pipeline:
            log(f"{variant_label}_PIPELINE=MISSING")
            continue
        log(f"{variant_label}_PIPELINE={pipeline.get_path_name()}")
        transformers, ok = safe_get(pipeline, "transformers")
        if not ok:
            log(f"{variant_label}_TRANSFORMERS=UNEXPOSED")
            continue
        transformers = list(transformers)
        log(f"{variant_label}_TRANSFORMER_COUNT={len(transformers)}")
        for transformer_index, transformer in enumerate(transformers):
            total_transformers += 1
            probe_instanced_struct(
                transformer,
                f"{variant_label}_TRANSFORMER_{transformer_index}",
            )

    runtime_settings, ok = safe_get(mpd, "per_platform_runtime_settings")
    if ok:
        probe_runtime_settings(runtime_settings)
    else:
        log("PER_PLATFORM_RUNTIME_SETTINGS=UNEXPOSED")

    log("")
    log("SUMMARY")
    log("-" * 100)
    log(f"COMPILED_VARIANTS={len(variants)}")
    log(f"TRANSFORMER_INSTANCED_STRUCTS_PROBED={total_transformers}")
    log("AUDIT_RESULT=PASS")
    log("NO_ASSET_PROPERTIES_CHANGED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PIE_STARTED=TRUE")
    log("NO_BUILD_METHOD_CALLED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_warning(f"AETHER_STAGE14_BUILD_COST_AUDIT_V2_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    log("")
    log("AUDIT_RESULT=FAIL")
    log(f"ERROR={type(exc).__name__}: {exc}")
    log("NO_ASSET_PROPERTIES_CHANGED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PIE_STARTED=TRUE")
    log("NO_BUILD_METHOD_CALLED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_error(f"AETHER_STAGE14_BUILD_COST_AUDIT_V2_FAILED={type(exc).__name__}: {exc}")
    raise
