import os
import traceback
import unreal

PROJECT_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
PROJECT_SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
REPORT_PATH = os.path.join(PROJECT_SAVED, "AetherEnvironmentAssetAudit.txt")

TREE_WORDS = (
    "tree", "pine", "aspen", "oak", "conifer", "spruce", "fir", "birch",
    "maple", "willow", "poplar", "palm", "coconut", "cedar", "redwood",
    "trunk", "sapling",
)
ROCK_WORDS = (
    "rock", "boulder", "stone", "cliff", "crag", "pebble", "outcrop",
    "scree", "rubble",
)
SHRUB_WORDS = (
    "shrub", "bush", "fern", "groundcover", "ground_cover", "plant",
    "foliage", "grass", "weed", "flower",
)
ALL_ENV_WORDS = TREE_WORDS + ROCK_WORDS + SHRUB_WORDS
REJECT_WORDS = (
    "meshpartitionstaticmesh", "compiledsection", "farfield", "terrain",
    "landscape", "aircraft", "drone", "runway", "water", "ocean", "lake",
    "sky", "cloud", "volume", "collision", "proxy", "billboard", "impostor",
    "imposter", "cluster", "merged", "forest_group", "_lod", "lod_",
)


def object_path_of_asset(data):
    """Return a UE object path without relying on version-specific AssetData helpers."""
    package_name = str(data.package_name)
    asset_name = str(data.asset_name)
    if not package_name or package_name == "None":
        return asset_name
    if package_name.endswith("." + asset_name):
        return package_name
    return f"{package_name}.{asset_name}"


def text_of_asset(data):
    return " ".join(
        str(value)
        for value in (
            data.asset_name,
            data.package_name,
            data.package_path,
            object_path_of_asset(data),
        )
    ).lower()


def classify(text):
    if any(word in text for word in REJECT_WORDS):
        return None
    if any(word in text for word in TREE_WORDS):
        return "TREE"
    if any(word in text for word in ROCK_WORDS):
        return "ROCK"
    if any(word in text for word in SHRUB_WORDS):
        return "SHRUB"
    return None


def mesh_dimensions(mesh):
    try:
        bounds = mesh.get_bounds()
        extent = bounds.box_extent
        return float(extent.x * 2.0), float(extent.y * 2.0), float(extent.z * 2.0)
    except Exception:
        pass
    try:
        box = mesh.get_bounding_box()
        size = box.max - box.min
        return float(size.x), float(size.y), float(size.z)
    except Exception:
        return None


def score_candidate(kind, text, dimensions):
    score = 0.0
    score += sum(
        20.0
        for token in (
            "/foliage/", "/trees/", "/tree/", "/rocks/", "/rock/",
            "/vegetation/", "/nature/", "/environment/",
        )
        if token in text
    )
    if text.split("/")[-1].startswith("sm_"):
        score += 2.0
    if dimensions:
        width_x, width_y, height = dimensions
        width = max(width_x, width_y)
        if kind == "TREE":
            if 300.0 <= height <= 15000.0:
                score += 25.0
            score -= abs(height - 2400.0) / 600.0
            if height > 1.0:
                score -= max(0.0, width / height - 3.0) * 10.0
        elif kind == "ROCK":
            if 30.0 <= height <= 10000.0:
                score += 20.0
            score -= abs(height - 500.0) / 500.0
        else:
            if 10.0 <= height <= 1800.0:
                score += 20.0
            score -= abs(height - 180.0) / 250.0
    return score


def find_project_uassets():
    roots = [
        os.path.join(PROJECT_DIR, "Content"),
        os.path.join(PROJECT_DIR, "Plugins"),
    ]
    all_files = []
    likely_environment_files = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for current_root, _, filenames in os.walk(root):
            for filename in filenames:
                if not filename.lower().endswith(".uasset"):
                    continue
                full_path = os.path.normpath(os.path.join(current_root, filename))
                all_files.append(full_path)
                lowered = full_path.lower().replace("\\", "/")
                if any(word in lowered for word in ALL_ENV_WORDS):
                    likely_environment_files.append(full_path)
    return all_files, likely_environment_files


def scan_files_in_chunks(registry, paths, chunk_size=400):
    scanned = 0
    for index in range(0, len(paths), chunk_size):
        chunk = paths[index:index + chunk_size]
        try:
            registry.scan_files_synchronous(chunk, True)
            scanned += len(chunk)
        except Exception as exc:
            unreal.log_warning(
                f"AETHER_ENV_AUDIT_SCAN_FILES_WARNING chunk={index // chunk_size + 1}: {exc}"
            )
    return scanned


def force_complete_registry_scan(registry):
    notes = []

    try:
        registry.search_all_assets(True)
        notes.append("search_all_assets(True): success")
    except Exception as exc:
        notes.append(f"search_all_assets(True): {type(exc).__name__}: {exc}")

    try:
        registry.wait_for_completion()
        notes.append("wait_for_completion(): success")
    except Exception as exc:
        notes.append(f"wait_for_completion(): {type(exc).__name__}: {exc}")

    # Force /Game to be gathered even in commandlet mode, where startup asset
    # discovery can be synchronous/on-demand rather than a complete editor scan.
    try:
        registry.scan_paths_synchronous(["/Game"], True, True)
        notes.append("scan_paths_synchronous(/Game, force, ignore deny list): success")
    except TypeError:
        try:
            registry.scan_paths_synchronous(["/Game"], True)
            notes.append("scan_paths_synchronous(/Game, force): success")
        except Exception as exc:
            notes.append(f"scan_paths_synchronous(/Game): {type(exc).__name__}: {exc}")
    except Exception as exc:
        notes.append(f"scan_paths_synchronous(/Game): {type(exc).__name__}: {exc}")

    all_disk_uassets, likely_environment_uassets = find_project_uassets()
    scanned_files = scan_files_in_chunks(registry, likely_environment_uassets)
    notes.append(
        f"project disk scan: {len(all_disk_uassets)} .uasset files; "
        f"{len(likely_environment_uassets)} environment-name matches; "
        f"{scanned_files} files submitted to Asset Registry"
    )

    try:
        registry.search_all_assets(True)
        registry.wait_for_completion()
        notes.append("final search_all_assets/wait: success")
    except Exception as exc:
        notes.append(f"final search/wait: {type(exc).__name__}: {exc}")

    return notes, all_disk_uassets, likely_environment_uassets


def class_name_of_asset(data):
    try:
        return str(data.asset_class_path.asset_name)
    except Exception:
        try:
            return str(data.asset_class)
        except Exception:
            return ""


def main():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    scan_notes, disk_uassets, likely_disk_uassets = force_complete_registry_scan(registry)

    # Search every mounted project/plugin root, not only /Game. Fab and Marketplace
    # packs can be mounted beneath their own plugin content root.
    assets = registry.get_all_assets(include_only_on_disk_assets=True) or []

    static_mesh_assets = [data for data in assets if class_name_of_asset(data) == "StaticMesh"]
    project_static_mesh_assets = [
        data
        for data in static_mesh_assets
        if not str(data.package_name).startswith("/Engine/")
        and not str(data.package_name).startswith("/Script/")
    ]

    raw_candidates = {"TREE": [], "ROCK": [], "SHRUB": []}
    for data in project_static_mesh_assets:
        text = text_of_asset(data)
        kind = classify(text)
        if kind:
            raw_candidates[kind].append((data, text))

    evaluated = {"TREE": [], "ROCK": [], "SHRUB": []}
    load_limit = 360
    loaded = 0
    for kind in ("TREE", "ROCK", "SHRUB"):
        for data, text in raw_candidates[kind]:
            if loaded >= load_limit:
                break
            loaded += 1
            dimensions = None
            load_error = ""
            try:
                mesh = data.get_asset()
                if mesh:
                    dimensions = mesh_dimensions(mesh)
                else:
                    load_error = "get_asset returned None"
            except Exception as exc:
                load_error = str(exc)
            evaluated[kind].append(
                (
                    score_candidate(kind, text, dimensions),
                    object_path_of_asset(data),
                    dimensions,
                    load_error,
                )
            )

    for kind in evaluated:
        evaluated[kind].sort(key=lambda row: row[0], reverse=True)

    cached_paths = []
    try:
        cached_paths = [str(path) for path in (registry.get_all_cached_paths() or [])]
    except Exception:
        cached_paths = []

    mount_roots = sorted(
        {
            "/" + str(data.package_name).strip("/").split("/", 1)[0]
            for data in project_static_mesh_assets
            if str(data.package_name).startswith("/")
        }
    )

    lines = [
        "AETHER ENVIRONMENT ASSET AUDIT",
        "=" * 72,
        "Read-only audit. No asset was modified or saved.",
        f"Assets registered across all mounted roots: {len(assets)}",
        f"Static meshes across all mounted roots: {len(static_mesh_assets)}",
        f"Project/plugin static meshes after excluding /Engine and /Script: {len(project_static_mesh_assets)}",
        f"Project .uasset files found directly on disk: {len(disk_uassets)}",
        f"Environment-name .uasset files found directly on disk: {len(likely_disk_uassets)}",
        f"Probable tree names: {len(raw_candidates['TREE'])}",
        f"Probable rock names: {len(raw_candidates['ROCK'])}",
        f"Probable shrub/plant names: {len(raw_candidates['SHRUB'])}",
        f"Candidate assets loaded for bounds: {loaded}/{load_limit}",
        f"Static-mesh mount roots: {', '.join(mount_roots) if mount_roots else 'NONE'}",
        f"Asset Registry cached paths: {len(cached_paths)}",
        "",
        "REGISTRY SCAN NOTES",
        "-" * 72,
    ]
    lines.extend(scan_notes)
    lines.append("")

    if likely_disk_uassets:
        lines.extend(("LIKELY ENVIRONMENT FILES FOUND ON DISK", "-" * 72))
        for path in likely_disk_uassets[:120]:
            lines.append(path)
        if len(likely_disk_uassets) > 120:
            lines.append(f"... {len(likely_disk_uassets) - 120} more")
        lines.append("")

    for kind in ("TREE", "ROCK", "SHRUB"):
        lines.extend((f"TOP {kind} CANDIDATES", "-" * 72))
        rows = evaluated[kind][:50]
        if not rows:
            lines.append("NONE")
        for index, (score, path, dimensions, load_error) in enumerate(rows, 1):
            dims = "%.0f x %.0f x %.0f cm" % dimensions if dimensions else "bounds unavailable"
            suffix = f" | load={load_error}" if load_error else ""
            lines.append(f"{index:02d}. score={score:7.2f} | {dims} | {path}{suffix}")
        lines.append("")

    lines.extend((
        "NEXT STEP",
        "Use the highest-scoring individual TREE and ROCK object paths in the map-wide environment loader.",
        "Do not use cluster, merged, billboard, proxy, collision, or explicit LOD meshes.",
        "If registered static meshes remain near zero but disk .uasset counts are high, the assets are not mounted/loaded by this project configuration.",
        "If both registered and disk counts remain near zero, the tree/rock packs are not installed inside this Unreal project.",
    ))

    os.makedirs(PROJECT_SAVED, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as report:
        report.write("\n".join(lines) + "\n")

    unreal.log_warning(f"AETHER_ENVIRONMENT_ASSET_AUDIT_COMPLETE={REPORT_PATH}")
    for line in lines[:32]:
        unreal.log_warning(line)


try:
    main()
except Exception:
    error_text = traceback.format_exc()
    os.makedirs(PROJECT_SAVED, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as report:
        report.write("AETHER ENVIRONMENT ASSET AUDIT FAILED\n")
        report.write(error_text)
    unreal.log_error(error_text)
    raise
