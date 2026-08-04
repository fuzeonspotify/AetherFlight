import os
import traceback
import unreal

PROJECT_SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
REPORT_PATH = os.path.join(PROJECT_SAVED, "AetherEnvironmentAssetAudit.txt")

TREE_WORDS = ("tree", "pine", "aspen", "oak", "conifer", "spruce", "fir", "birch", "maple", "willow", "poplar", "palm", "coconut", "cedar", "redwood", "trunk", "sapling")
ROCK_WORDS = ("rock", "boulder", "stone", "cliff", "crag", "pebble", "outcrop", "scree", "rubble")
SHRUB_WORDS = ("shrub", "bush", "fern", "groundcover", "ground_cover", "plant", "foliage", "grass", "weed", "flower")
REJECT_WORDS = ("meshpartitionstaticmesh", "compiledsection", "farfield", "terrain", "landscape", "aircraft", "drone", "runway", "water", "ocean", "lake", "sky", "cloud", "volume", "collision", "proxy", "billboard", "impostor", "imposter", "cluster", "merged", "forest_group", "_lod", "lod_")


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
            "/foliage/",
            "/trees/",
            "/tree/",
            "/rocks/",
            "/rock/",
            "/vegetation/",
            "/nature/",
            "/environment/",
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


def main():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.wait_for_completion()
    assets = registry.get_assets_by_path(
        unreal.Name("/Game"),
        recursive=True,
        include_only_on_disk_assets=True,
    )

    static_mesh_assets = []
    for data in assets:
        try:
            class_name = str(data.asset_class_path.asset_name)
        except Exception:
            class_name = str(data.asset_class)
        if class_name == "StaticMesh":
            static_mesh_assets.append(data)

    raw_candidates = {"TREE": [], "ROCK": [], "SHRUB": []}
    for data in static_mesh_assets:
        text = text_of_asset(data)
        kind = classify(text)
        if kind:
            raw_candidates[kind].append((data, text))

    evaluated = {"TREE": [], "ROCK": [], "SHRUB": []}
    load_limit = 240
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

    lines = [
        "AETHER ENVIRONMENT ASSET AUDIT",
        "=" * 72,
        "Read-only audit. No asset was modified or saved.",
        f"Static meshes registered under /Game: {len(static_mesh_assets)}",
        f"Probable tree names: {len(raw_candidates['TREE'])}",
        f"Probable rock names: {len(raw_candidates['ROCK'])}",
        f"Probable shrub/plant names: {len(raw_candidates['SHRUB'])}",
        f"Candidate assets loaded for bounds: {loaded}/{load_limit}",
        "",
    ]

    for kind in ("TREE", "ROCK", "SHRUB"):
        lines.extend((f"TOP {kind} CANDIDATES", "-" * 72))
        rows = evaluated[kind][:40]
        if not rows:
            lines.append("NONE")
        for index, (score, path, dimensions, load_error) in enumerate(rows, 1):
            dims = "%.0f x %.0f x %.0f cm" % dimensions if dimensions else "bounds unavailable"
            suffix = f" | load={load_error}" if load_error else ""
            lines.append(f"{index:02d}. score={score:7.2f} | {dims} | {path}{suffix}")
        lines.append("")

    lines.extend(
        (
            "NEXT STEP",
            "Use the highest-scoring individual TREE and ROCK object paths in the map-wide environment loader.",
            "Do not use cluster, merged, billboard, proxy, collision, or explicit LOD meshes.",
        )
    )

    os.makedirs(PROJECT_SAVED, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as report:
        report.write("\n".join(lines) + "\n")

    unreal.log_warning(f"AETHER_ENVIRONMENT_ASSET_AUDIT_COMPLETE={REPORT_PATH}")
    for line in lines[:18]:
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
