"""Read-only audit of AetherWorld Mesh Partition runtime-build cost settings.

Inspects MPD_AetherWorld, its compiled build variants, transformer pipelines,
and relevant transformer properties. It never changes assets, saves packages,
starts PIE, or invokes any Mesh Partition build method.
"""

from pathlib import Path
import unreal

MPD_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14MeshPartitionBuildCostAudit.txt"
LINES = []

KEYWORDS = (
    "build", "variant", "transform", "pipeline", "section", "grid", "cell",
    "complex", "subsection", "sub_section", "lod", "screen", "pixel", "error",
    "collision", "runtime", "platform", "preview", "nanite", "skirt", "far_field",
    "edge_length", "simplif", "mesh", "material_cache", "virtual_texture",
)

KNOWN_PROPERTIES = (
    "compiled_section_build_variants",
    "compiled_sections_build_variants",
    "build_variants",
    "platforms",
    "per_platform_runtime_settings",
    "default_platform_runtime_settings",
    "preview",
    "preview_settings",
    "preview_transformer_pipeline",
    "transformer_pipeline",
    "pipeline",
    "transformers",
    "transformer_stack",
    "entries",
    "name",
    "variant_name",
    "build_variant_names",
    "max_section_complexity",
    "max_section_size",
    "section_size",
    "subsection_size",
    "sub_section_size",
    "grid_settings",
    "cell_size",
    "grid_cell_size",
    "grid_name",
    "runtime_grid",
    "lod_mode",
    "pixel_error",
    "error_tolerance",
    "num_lods",
    "lod_count",
    "screen_size",
    "screen_sizes",
    "enable_nanite",
    "nanite_enabled",
    "collision_enabled",
    "generate_collision",
    "far_field_mesh_edge_length",
    "mesh_edge_length",
)


def log(text=""):
    text = str(text)
    LINES.append(text)
    unreal.log_warning(text)


def write_report():
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


def object_path(obj):
    try:
        return obj.get_path_name()
    except Exception:
        return None


def safe_get(obj, name):
    try:
        return obj.get_editor_property(name), True
    except Exception:
        try:
            return getattr(obj, name), True
        except Exception:
            return None, False


def short(value, limit=1000):
    try:
        text = str(value)
    except Exception:
        text = repr(value)
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def is_scalar(value):
    return value is None or isinstance(value, (str, int, float, bool, bytes))


def is_sequence(value):
    return isinstance(value, (list, tuple)) or type(value).__name__.startswith("Array")


def relevant_names(obj):
    names = set(KNOWN_PROPERTIES)
    try:
        for name in dir(obj):
            lower = str(name).lower()
            if any(token in lower for token in KEYWORDS):
                names.add(str(name))
    except Exception:
        pass
    return sorted(names)


def dump_value(value, label, depth, visited):
    indent = "  " * depth
    if is_scalar(value):
        log(f"{indent}{label}={short(value)}")
        return

    if is_sequence(value):
        try:
            values = list(value)
        except Exception:
            log(f"{indent}{label}={short(value)}")
            return
        log(f"{indent}{label}_COUNT={len(values)}")
        for index, item in enumerate(values):
            dump_value(item, f"{label}[{index}]", depth + 1, visited)
        return

    identity = id(value)
    path = object_path(value)
    identity_key = path or f"id:{identity}"
    log(f"{indent}{label}_TYPE={class_path(value)}")
    if path:
        log(f"{indent}{label}_PATH={path}")
    if depth >= 5 or identity_key in visited:
        log(f"{indent}{label}_VALUE={short(value)}")
        return

    visited.add(identity_key)
    exposed = 0
    for name in relevant_names(value):
        property_value, ok = safe_get(value, name)
        if not ok or callable(property_value):
            continue
        exposed += 1
        dump_value(property_value, name, depth + 1, visited)
    if exposed == 0:
        log(f"{indent}{label}_VALUE={short(value)}")


def main():
    log("AETHER STAGE 14 - MESH PARTITION PIE BUILD COST AUDIT")
    log("=" * 100)
    log("READ_ONLY=TRUE")
    log("No asset mutation, package save, PIE command, preview build, compiled build, cook, or commandlet is invoked.")

    asset = unreal.EditorAssetLibrary.load_asset(MPD_PATH)
    if not asset:
        raise RuntimeError(f"Could not load {MPD_PATH}")

    log(f"MPD_PATH={asset.get_path_name()}")
    log(f"MPD_CLASS={class_path(asset)}")
    dump_value(asset, "MPD", 0, set())

    log("")
    log("AUDIT_RESULT=PASS")
    log("NO_ASSET_PROPERTIES_CHANGED=TRUE")
    log("NO_PACKAGES_SAVED=TRUE")
    log("NO_PIE_STARTED=TRUE")
    log("NO_BUILD_METHOD_CALLED=TRUE")
    log("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    write_report()
    unreal.log_warning(f"AETHER_STAGE14_BUILD_COST_AUDIT_REPORT={REPORT_PATH}")


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
    unreal.log_error(f"AETHER_STAGE14_BUILD_COST_AUDIT_FAILED={type(exc).__name__}: {exc}")
    raise
