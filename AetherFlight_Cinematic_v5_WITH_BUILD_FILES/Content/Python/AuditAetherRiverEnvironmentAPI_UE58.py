from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
MPD_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherRiverEnvironmentAPIAudit.txt"

REQUIRED_LABELS = (
    "Aether_VideoStage09_SplineChannel",
    "Aether_VideoStage10_SplineRemesh",
    "Aether_VideoStage11_River",
    "Aether_VideoStage11_WaterZone",
    "Aether_VideoStage12_RiverbankWetland",
)

ROCK_TOKENS = (
    "rock_collection_04",
    "rock collection 04",
    "environment_rock",
    "/rocks/",
    "rock04",
)
SHRUB_TOKENS = (
    "abelia",
    "shrub",
    "bush",
)
GROUND_TOKENS = (
    "ophiopogon",
    "lolium",
    "groundcover",
    "ground_cover",
    "ground cover",
    "fern",
)


def record(lines, text=""):
    text = str(text)
    lines.append(text)
    unreal.log_warning(text)


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


def load_world():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def get_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return subsystem, list(subsystem.get_all_level_actors())


def find_actor(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    return matches[0] if len(matches) == 1 else None


def find_mesh_partition(actors):
    preferred = []
    fallback = []
    for actor in actors:
        combined = f"{actor.get_name()} {class_path(actor)}"
        if "MeshPartition" not in combined and "MeshTerrain" not in combined:
            continue
        fallback.append(actor)
        tags = []
        try:
            tags = [str(tag) for tag in actor.get_editor_property("tags")]
        except Exception:
            pass
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in tags:
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def safe_property(obj, names):
    for name in names:
        try:
            return name, obj.get_editor_property(name)
        except Exception:
            continue
    return None, None


def channel_names(definition):
    names = []
    if not definition:
        return names
    try:
        channel_map = definition.get_editor_property("channel_map")
        descriptions = list(channel_map.get_editor_property("channel_descs"))
    except Exception:
        return names
    for description in descriptions:
        try:
            names.append(str(description.get_editor_property("name")))
        except Exception:
            names.append(str(description))
    return names


def list_game_assets():
    try:
        return list(unreal.EditorAssetLibrary.list_assets("/Game", True, False))
    except TypeError:
        return list(unreal.EditorAssetLibrary.list_assets("/Game", recursive=True, include_folder=False))


def discover_static_meshes(asset_paths, tokens, limit=12):
    results = []
    static_mesh_class = getattr(unreal, "StaticMesh", None)
    if not static_mesh_class:
        return results
    for path in asset_paths:
        lower = path.lower().replace("-", "_")
        if not any(token in lower for token in tokens):
            continue
        if any(skip in lower for skip in ("/material", "/texture", "/mi_", "/m_", "/t_")):
            continue
        try:
            asset = unreal.EditorAssetLibrary.load_asset(path)
        except Exception:
            asset = None
        if isinstance(asset, static_mesh_class):
            results.append(path)
            if len(results) >= limit:
                break
    return results


def method_status(obj, names):
    return {name: callable(getattr(obj, name, None)) for name in names}


def main():
    lines = []
    record(lines, "AETHER UE 5.8 RIVER ENVIRONMENT API AUDIT")
    record(lines, "=" * 96)
    record(lines, "Read-only: no actors are spawned, no instances are added, no packages are saved, and no Mesh Partition build is started.")

    world = load_world()
    _, actors = get_actors()
    record(lines, f"Map={world.get_path_name() if world else 'None'}")

    mesh_partition = find_mesh_partition(actors)
    record(lines, f"Authoritative Mesh Partition={'YES' if mesh_partition else 'NO'}")

    dependencies_ok = True
    record(lines, "")
    record(lines, "SAVED STAGE DEPENDENCIES")
    record(lines, "-" * 96)
    dependency_actors = {}
    for label in REQUIRED_LABELS:
        actor = find_actor(actors, label)
        dependency_actors[label] = actor
        dependencies_ok = dependencies_ok and bool(actor)
        record(lines, f"{label}={'YES' if actor else 'NO'}")

    source_actor = dependency_actors[REQUIRED_LABELS[0]]
    source_spline = None
    source_valid = False
    spline_class = getattr(unreal, "SplineComponent", None)
    if source_actor and spline_class:
        splines = list(source_actor.get_components_by_class(spline_class))
        record(lines, f"Stage09 spline components={len(splines)}")
        if len(splines) == 1:
            source_spline = splines[0]
            count = int(source_spline.get_number_of_spline_points())
            length = float(source_spline.get_spline_length())
            source_valid = count == 5 and 80000.0 <= length <= 170000.0
            record(lines, f"Stage09 spline points={count}")
            record(lines, f"Stage09 spline length cm={length}")

    classes = {
        "SplineModifier": getattr(unreal, "SplineModifier", None),
        "SplineModifierWeightEntry": getattr(unreal, "SplineModifierWeightEntry", None),
        "ChannelName": getattr(unreal, "ChannelName", None),
        "SplineWeightBlendMode": getattr(unreal, "SplineWeightBlendMode", None),
        "SplineComponent": spline_class,
        "ModifierActor": getattr(unreal, "ModifierActor", None),
        "HierarchicalInstancedStaticMeshComponent": getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None),
        "StaticMesh": getattr(unreal, "StaticMesh", None),
        "Transform": getattr(unreal, "Transform", None),
    }
    record(lines, "")
    record(lines, "CLASS AVAILABILITY")
    record(lines, "-" * 96)
    for name, cls in classes.items():
        record(lines, f"{name}={'YES' if cls else 'NO'}")

    exclusion_ok = False
    modifier_class = classes["SplineModifier"]
    if modifier_class:
        modifier = unreal.get_default_object(modifier_class)
        affected_prop, _ = safe_property(
            modifier,
            ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"),
        )
        spline_prop, _ = safe_property(modifier, ("spline_ptr", "spline_component", "spline"))
        write_prop, write_value = safe_property(modifier, ("write_mode",))
        weights_prop, weights_value = safe_property(modifier, ("weight_channels",))
        priority_prop, priority_value = safe_property(modifier, ("priority",))
        record(lines, "")
        record(lines, "FOLIAGE EXCLUSION SPLINE OUTPUT")
        record(lines, "-" * 96)
        record(lines, f"affected property={affected_prop}")
        record(lines, f"spline property={spline_prop}")
        record(lines, f"write_mode property={write_prop} | default={write_value}")
        record(lines, f"weight_channels property={weights_prop} | default={weights_value}")
        record(lines, f"priority property={priority_prop} | default={priority_value}")
        bp_affected = callable(getattr(modifier, "bp_set_affected_mega_mesh", None))
        bp_spline = callable(getattr(modifier, "bp_set_spline_component", None))
        record(lines, f"bp_set_affected_mega_mesh={'YES' if bp_affected else 'NO'}")
        record(lines, f"bp_set_spline_component={'YES' if bp_spline else 'NO'}")
        exclusion_ok = bool(
            write_prop
            and weights_prop
            and (affected_prop or bp_affected)
            and (spline_prop or bp_spline)
            and classes["SplineModifierWeightEntry"]
            and classes["ChannelName"]
            and classes["SplineWeightBlendMode"]
        )

    mpd = unreal.EditorAssetLibrary.load_asset(MPD_PATH)
    channels = channel_names(mpd)
    exclusion_channel_ok = "FoliageExclusion" in channels
    record(lines, "")
    record(lines, "MESH PARTITION CHANNELS")
    record(lines, "-" * 96)
    record(lines, f"MPD asset={'YES' if mpd else 'NO'} | {MPD_PATH}")
    for index, name in enumerate(channels):
        record(lines, f"MPD channel {index}={name}")
    record(lines, f"FoliageExclusion channel={'YES' if exclusion_channel_ok else 'NO'}")

    hism_ok = False
    hism_class = classes["HierarchicalInstancedStaticMeshComponent"]
    if hism_class:
        hism = unreal.get_default_object(hism_class)
        methods = method_status(
            hism,
            (
                "set_static_mesh",
                "add_instance",
                "add_instance_world_space",
                "clear_instances",
                "set_cull_distances",
            ),
        )
        record(lines, "")
        record(lines, "HISM INSTANCE API")
        record(lines, "-" * 96)
        for name, present in methods.items():
            record(lines, f"{name}={'YES' if present else 'NO'}")
        static_mesh_prop, _ = safe_property(hism, ("static_mesh",))
        record(lines, f"static_mesh property={static_mesh_prop}")
        hism_ok = bool(
            (methods["set_static_mesh"] or static_mesh_prop)
            and (methods["add_instance"] or methods["add_instance_world_space"])
            and methods["clear_instances"]
        )

    asset_paths = list_game_assets()
    rocks = discover_static_meshes(asset_paths, ROCK_TOKENS, 12)
    shrubs = discover_static_meshes(asset_paths, SHRUB_TOKENS, 8)
    ground = discover_static_meshes(asset_paths, GROUND_TOKENS, 8)
    environment_assets_ok = bool(rocks and (shrubs or ground))

    record(lines, "")
    record(lines, "RIVER ENVIRONMENT ASSETS")
    record(lines, "-" * 96)
    record(lines, f"Asset paths scanned={len(asset_paths)}")
    record(lines, f"Rock static meshes={len(rocks)}")
    for path in rocks:
        record(lines, f"  ROCK={path}")
    record(lines, f"Shrub static meshes={len(shrubs)}")
    for path in shrubs:
        record(lines, f"  SHRUB={path}")
    record(lines, f"Ground-cover static meshes={len(ground)}")
    for path in ground:
        record(lines, f"  GROUND={path}")

    trace_ok = callable(getattr(unreal.SystemLibrary, "line_trace_single", None))
    spline_sampling_ok = bool(
        source_spline
        and callable(getattr(source_spline, "get_location_at_distance_along_spline", None))
        and callable(getattr(source_spline, "get_right_vector_at_distance_along_spline", None))
    )
    record(lines, "")
    record(lines, "PLACEMENT API")
    record(lines, "-" * 96)
    record(lines, f"line_trace_single={'YES' if trace_ok else 'NO'}")
    record(lines, f"Spline distance sampling={'YES' if spline_sampling_ok else 'NO'}")

    status = "PASS" if all((
        world,
        mesh_partition,
        dependencies_ok,
        source_valid,
        exclusion_ok,
        exclusion_channel_ok,
        hism_ok,
        environment_assets_ok,
        trace_ok,
        spline_sampling_ok,
        classes["ModifierActor"],
        classes["Transform"],
    )) else "CHECK"

    record(lines, "")
    record(lines, f"Saved dependencies valid={dependencies_ok and source_valid}")
    record(lines, f"FoliageExclusion output configurable={exclusion_ok and exclusion_channel_ok}")
    record(lines, f"HISM environment configurable={hism_ok}")
    record(lines, f"River environment assets usable={environment_assets_ok}")
    record(lines, f"AETHER_RIVER_ENVIRONMENT_API={status}")
    record(lines, "NO_ACTORS_SPAWNED=TRUE")
    record(lines, "NO_INSTANCES_ADDED=TRUE")
    record(lines, "NO_PACKAGES_SAVED=TRUE")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_RIVER_ENVIRONMENT_API_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"AETHER_RIVER_ENVIRONMENT_API=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
