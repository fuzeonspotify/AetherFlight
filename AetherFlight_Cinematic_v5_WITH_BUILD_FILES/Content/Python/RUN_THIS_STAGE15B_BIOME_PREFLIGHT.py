"""Read-only Stage 15B preflight for routing installed environment assets into Mesh Terrain biomes.

Run in the Unreal Editor with AetherWorld open and PIE stopped. The audit does not
create actors, PCG graphs, instances, packages, or builds. It inventories the
installed Static Mesh assets, Mesh Terrain weight channels, PCG/Mesh Partition
Python exposure, and existing biome/PCG actors before the production installer is
written against this exact UE 5.8 project state.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BBiomePreflight.txt"
MPD_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld.MPD_AetherWorld"
WEIGHT_ROOT = "/Game/Aether/MeshTerrain/Weightmaps"
EXPECTED_CHANNELS = (
    "Grass",
    "ForestFloor",
    "Rock",
    "Scree",
    "Snow",
    "Sand",
    "Wetland",
    "Water",
    "Forest",
    "FoliageExclusion",
)

CATEGORY_KEYWORDS = {
    "CONIFER_TREES": ("pine", "conifer", "spruce", "fir"),
    "TEMPERATE_TREES": ("aspen", "acer", "maple", "broadleaf"),
    "DRY_WOODLAND_TREES": ("cork_oak", "cork oak", "oak"),
    "PALMS": ("palm", "coconut", "windmill"),
    "SHRUBS_BUSHES": ("shrub", "bush", "abelia", "sapling"),
    "GRASS_GROUND_COVER": (
        "grass",
        "lolium",
        "ophiopogon",
        "groundcover",
        "ground_cover",
        "fern",
        "reed",
    ),
    "ROCKS_BOULDERS": ("rock", "boulder", "cliff", "stone"),
}


def log(text=""):
    unreal.log_warning(str(text))


def class_name(asset_data):
    for getter in (
        lambda: str(asset_data.asset_class_path.asset_name),
        lambda: str(asset_data.asset_class),
        lambda: str(asset_data.get_class()),
    ):
        try:
            value = getter()
            if value:
                return value
        except Exception:
            pass
    return "Unknown"


def asset_path(asset_data):
    for getter in (
        lambda: str(asset_data.get_soft_object_path()),
        lambda: str(asset_data.object_path),
        lambda: f"{asset_data.package_name}.{asset_data.asset_name}",
    ):
        try:
            value = getter()
            if value and value != "None":
                return value
        except Exception:
            pass
    return str(asset_data.asset_name)


def all_static_mesh_paths():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    results = []
    try:
        assets = registry.get_all_assets()
    except Exception:
        assets = registry.get_assets_by_path("/Game", recursive=True)
    for data in assets:
        if "staticmesh" not in class_name(data).replace("_", "").lower():
            continue
        path = asset_path(data)
        if path.startswith("/Game/"):
            results.append(path)
    return sorted(set(results), key=str.lower)


def categorize_meshes(mesh_paths):
    categories = {name: [] for name in CATEGORY_KEYWORDS}
    for path in mesh_paths:
        normalized = path.lower().replace("-", "_")
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                categories[category].append(path)
    return categories


def read_channel_names(definition):
    if definition is None:
        return []
    containers = []
    for property_name in ("channel_map", "channels", "channel_collection"):
        try:
            value = definition.get_editor_property(property_name)
            if value is not None:
                containers.append(value)
        except Exception:
            pass
    names = []
    for container in containers:
        for property_name in ("channel_descs", "channels", "descriptions"):
            try:
                descriptions = container.get_editor_property(property_name)
            except Exception:
                continue
            for description in descriptions:
                for name_property in ("name", "channel_name"):
                    try:
                        value = str(description.get_editor_property(name_property))
                        if value and value != "None":
                            names.append(value)
                            break
                    except Exception:
                        pass
    return sorted(set(names), key=str.lower)


def exposed_unreal_types():
    tokens = ("pcg", "meshpartition", "meshterrain", "spawner", "pointdata")
    names = [name for name in dir(unreal) if any(token in name.lower() for token in tokens)]
    return sorted(set(names), key=str.lower)


def existing_pcg_assets():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    found = []
    try:
        assets = registry.get_all_assets()
    except Exception:
        assets = registry.get_assets_by_path("/Game", recursive=True)
    for data in assets:
        cls = class_name(data).lower()
        if "pcggraph" in cls or "pcgassembly" in cls or "pcgdataasset" in cls:
            found.append(f"{class_name(data)} | {asset_path(data)}")
    return sorted(set(found), key=str.lower)


def actor_inventory():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for actor in subsystem.get_all_level_actors():
        try:
            actor_class = actor.get_class().get_name()
            label = actor.get_actor_label()
        except Exception:
            continue
        normalized = f"{actor_class} {label}".lower()
        component_classes = []
        try:
            components = actor.get_components_by_class(unreal.ActorComponent)
        except Exception:
            components = []
        for component in components:
            try:
                component_classes.append(component.get_class().get_name())
            except Exception:
                pass
        component_text = ",".join(sorted(set(component_classes)))
        if (
            "pcg" in normalized
            or "biome" in normalized
            or "foliage" in normalized
            or "environment" in normalized
            or "meshpartition" in normalized
            or any("pcg" in name.lower() for name in component_classes)
        ):
            rows.append(f"{actor_class} | {label} | components={component_text}")
    return sorted(set(rows), key=str.lower)


def write_section(lines, title, values, limit=None):
    lines.append("")
    lines.append(title)
    lines.append("-" * 100)
    if not values:
        lines.append("NONE")
        return
    selected = values if limit is None else values[:limit]
    lines.extend(selected)
    if limit is not None and len(values) > limit:
        lines.append(f"... {len(values) - limit} additional entries omitted from this report")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running the Stage 15B biome preflight.")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - MESH TERRAIN BIOME ROUTING PREFLIGHT",
        "=" * 100,
        "READ_ONLY=TRUE",
        "TUTORIAL_REFERENCE=Unreal Sensei Mesh Terrain workflow: painted/derived weight channels route PCG scattering.",
        "NO_ACTORS_CREATED=TRUE",
        "NO_ASSETS_CREATED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    ]

    mesh_paths = all_static_mesh_paths()
    categories = categorize_meshes(mesh_paths)
    lines.append(f"STATIC_MESH_ASSETS_SCANNED={len(mesh_paths)}")
    for category, paths in categories.items():
        lines.append(f"{category}_CANDIDATES={len(paths)}")

    definition = unreal.EditorAssetLibrary.load_asset(MPD_PATH)
    channel_names = read_channel_names(definition)
    lines.append(f"MPD_FOUND={definition is not None}")
    lines.append(f"MPD_CHANNELS_EXPOSED={len(channel_names)}")
    for channel in EXPECTED_CHANNELS:
        texture_path = f"{WEIGHT_ROOT}/T_MT_{channel}_Weight.T_MT_{channel}_Weight"
        texture_exists = unreal.EditorAssetLibrary.does_asset_exist(texture_path)
        channel_exists = channel in channel_names
        lines.append(
            f"CHANNEL_{channel}=definition:{channel_exists} source_texture:{texture_exists}"
        )

    exposed_types = exposed_unreal_types()
    required_tokens = {
        "PCG_GRAPH": ("PCGGraph",),
        "PCG_COMPONENT": ("PCGComponent",),
        "MESH_PARTITION_QUERY": ("MeshPartition", "Query"),
        "MESH_PARTITION_TO_POINT": ("MeshPartition", "Point"),
        "STATIC_MESH_SPAWNER": ("StaticMesh", "Spawner"),
    }
    for label, tokens in required_tokens.items():
        matches = [name for name in exposed_types if all(token.lower() in name.lower() for token in tokens)]
        lines.append(f"{label}_PYTHON_TYPES={','.join(matches) if matches else 'NONE'}")

    for category, paths in categories.items():
        write_section(lines, category, paths, limit=40)
    write_section(lines, "EXISTING_PCG_GRAPH_ASSETS", existing_pcg_assets(), limit=80)
    write_section(lines, "EXISTING_RELEVANT_LEVEL_ACTORS", actor_inventory(), limit=120)
    write_section(lines, "PCG_MESH_TERRAIN_PYTHON_TYPES", exposed_types, limit=240)

    essential = {
        "trees": sum(len(categories[name]) for name in (
            "CONIFER_TREES", "TEMPERATE_TREES", "DRY_WOODLAND_TREES", "PALMS"
        )),
        "shrubs": len(categories["SHRUBS_BUSHES"]),
        "ground_cover": len(categories["GRASS_GROUND_COVER"]),
        "rocks": len(categories["ROCKS_BOULDERS"]),
    }
    ready_assets = all(value > 0 for value in essential.values())
    ready_channels = definition is not None and all(
        channel in channel_names for channel in ("Grass", "ForestFloor", "Rock", "Wetland", "FoliageExclusion")
    )
    lines.extend((
        "",
        "SUMMARY",
        "-" * 100,
        f"TREE_CANDIDATES={essential['trees']}",
        f"SHRUB_CANDIDATES={essential['shrubs']}",
        f"GROUND_COVER_CANDIDATES={essential['ground_cover']}",
        f"ROCK_CANDIDATES={essential['rocks']}",
        f"ESSENTIAL_ASSET_CATEGORIES_READY={ready_assets}",
        f"CORE_MESH_TERRAIN_CHANNELS_READY={ready_channels}",
        "PREFLIGHT_RESULT=PASS",
        "NEXT=Use this exact inventory to author the guarded river-biome vertical-slice installer.",
    ))

    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        log(line)
    log(f"AETHER_STAGE15B_BIOME_PREFLIGHT_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    failure = "\n".join((
        "AETHER STAGE 15B - MESH TERRAIN BIOME ROUTING PREFLIGHT",
        "=" * 100,
        "PREFLIGHT_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "NO_ACTORS_CREATED=TRUE",
        "NO_ASSETS_CREATED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    )) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(failure, encoding="utf-8")
    unreal.log_error(failure)
    raise
