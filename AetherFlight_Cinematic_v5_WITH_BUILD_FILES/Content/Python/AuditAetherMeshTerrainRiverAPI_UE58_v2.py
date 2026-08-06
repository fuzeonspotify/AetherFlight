from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
STAGE09_LABEL = "Aether_VideoStage09_SplineChannel"
STAGE10_LABEL = "Aether_VideoStage10_SplineRemesh"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherMeshTerrainRiverAPIAudit.txt"

CLASS_CANDIDATES = {
    "WaterBodyRiver": ("WaterBodyRiver",),
    "WaterZone": ("WaterZone",),
    "WaterSplineComponent": ("WaterSplineComponent",),
    "WaterBodyRiverComponent": ("WaterBodyRiverComponent",),
    "WaterSplineCurveDefaults": ("WaterSplineCurveDefaults",),
    "WaterSplineMetadata": ("WaterSplineMetadata",),
    "RiverModifier": (
        "RiverModifier",
        "WaterBodyRiverModifier",
        "MeshPartitionRiverModifier",
    ),
    "WaterModifier": ("WaterModifier",),
}


def record(lines, text=""):
    text = str(text)
    lines.append(text)
    unreal.log_warning(text)


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def instance_class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


def wrapper_name(value):
    if value is None:
        return "None"
    name = getattr(value, "__name__", None)
    if name:
        return f"unreal.{name}"
    return str(value)


def load_world():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def get_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return list(subsystem.get_all_level_actors())


def find_actor(actors, label):
    matches = [actor for actor in actors if actor_label(actor) == label]
    return matches[0] if len(matches) == 1 else None


def actor_tags(actor):
    try:
        return [str(tag) for tag in actor.get_editor_property("tags")]
    except Exception:
        return []


def find_mesh_partition(actors):
    preferred = []
    fallback = []
    for actor in actors:
        combined = f"{actor.get_name()} {instance_class_path(actor)}"
        if "MeshPartition" not in combined and "MeshTerrain" not in combined:
            continue
        fallback.append(actor)
        tags = actor_tags(actor)
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in tags:
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def resolve_class(candidates):
    for name in candidates:
        cls = getattr(unreal, name, None)
        if cls is not None:
            return name, cls
    return None, None


def safe_property(obj, names):
    if obj is None:
        return None, None
    for name in names:
        try:
            return name, obj.get_editor_property(name)
        except Exception:
            continue
    return None, None


def method_status(obj, names):
    if obj is None:
        return {name: False for name in names}
    return {name: callable(getattr(obj, name, None)) for name in names}


def safe_default_object(cls, label, lines):
    if cls is None:
        return None
    try:
        value = unreal.get_default_object(cls)
        record(lines, f"{label} default object={instance_class_path(value)}")
        return value
    except Exception as exc:
        record(lines, f"{label} default object unavailable={type(exc).__name__}: {exc}")
        return None


def component_lines(owner, lines):
    found = []
    if owner is None:
        return found
    for base_class in (
        getattr(unreal, "ActorComponent", None),
        getattr(unreal, "SceneComponent", None),
    ):
        if base_class is None:
            continue
        try:
            components = owner.get_components_by_class(base_class)
        except Exception:
            continue
        for component in components:
            entry = f"{component.get_name()} | {instance_class_path(component)}"
            if entry not in found:
                found.append(entry)
    for entry in found:
        record(lines, f"  {entry}")
    return found


def write_report(lines):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    lines = []
    record(lines, "AETHER UE 5.8 MESH TERRAIN RIVER API AUDIT V2")
    record(lines, "=" * 96)
    record(lines, "Read-only: no actors are spawned, no packages are saved, and no Mesh Partition build is started.")

    world = load_world()
    actors = get_actors()
    stage09 = find_actor(actors, STAGE09_LABEL)
    stage10 = find_actor(actors, STAGE10_LABEL)
    mesh_partition = find_mesh_partition(actors)

    record(lines, f"Map={world.get_path_name() if world else 'None'}")
    record(lines, f"Stage09 dependency={'YES' if stage09 else 'NO'}")
    record(lines, f"Stage10 dependency={'YES' if stage10 else 'NO'}")
    record(lines, f"Authoritative Mesh Partition={'YES' if mesh_partition else 'NO'}")
    if mesh_partition:
        record(lines, f"Mesh Partition actor={actor_label(mesh_partition)} | {instance_class_path(mesh_partition)}")

    resolved = {}
    record(lines, "")
    record(lines, "CLASS AVAILABILITY")
    record(lines, "-" * 96)
    for label, candidates in CLASS_CANDIDATES.items():
        name, cls = resolve_class(candidates)
        resolved[label] = (name, cls)
        if cls is not None:
            record(lines, f"{label}=unreal.{name} | wrapper={wrapper_name(cls)}")
        else:
            record(lines, f"{label}=NOT EXPOSED | candidates={candidates}")

    river_class = resolved["WaterBodyRiver"][1]
    zone_class = resolved["WaterZone"][1]
    spline_class = resolved["WaterSplineComponent"][1]
    body_component_class = resolved["WaterBodyRiverComponent"][1]
    defaults_class = resolved["WaterSplineCurveDefaults"][1]
    modifier_class = resolved["RiverModifier"][1]

    record(lines, "")
    record(lines, "WATER BODY RIVER DEFAULT OBJECT")
    record(lines, "-" * 96)
    river_default = safe_default_object(river_class, "WaterBodyRiver", lines)
    river_methods = method_status(
        river_default,
        (
            "get_water_body_component",
            "get_water_spline",
            "get_water_spline_metadata",
            "on_water_body_changed",
            "set_water_material",
        ),
    )
    for method, present in river_methods.items():
        record(lines, f"{method}={'YES' if present else 'NO'}")
    if river_default:
        record(lines, "Default components:")
        component_lines(river_default, lines)

    record(lines, "")
    record(lines, "WATER SPLINE DEFAULT OBJECT")
    record(lines, "-" * 96)
    spline_default = safe_default_object(spline_class, "WaterSplineComponent", lines)
    for label, names in (
        ("Water Spline Defaults", ("water_spline_defaults",)),
        ("Previous Water Spline Defaults", ("previous_water_spline_defaults",)),
    ):
        prop, value = safe_property(spline_default, names)
        record(lines, f"{label}={value if prop else 'NOT EXPOSED'} | property={prop}")
    spline_methods = method_status(
        spline_default,
        (
            "reset_spline",
            "synchronize_water_properties",
            "k2_synchronize_and_broadcast_data_change",
            "clear_spline_points",
            "add_spline_point",
            "update_spline",
        ),
    )
    for method, present in spline_methods.items():
        record(lines, f"{method}={'YES' if present else 'NO'}")

    record(lines, "")
    record(lines, "RIVER COMPONENT DEFAULT OBJECT")
    record(lines, "-" * 96)
    body_default = safe_default_object(body_component_class, "WaterBodyRiverComponent", lines)
    body_methods = method_status(
        body_default,
        (
            "get_water_spline",
            "get_water_spline_metadata",
            "set_water_zone_override",
            "set_water_material",
            "on_water_body_changed",
        ),
    )
    for method, present in body_methods.items():
        record(lines, f"{method}={'YES' if present else 'NO'}")
    for label, names in (
        ("Affects terrain", ("affects_landscape", "affects_terrain")),
        ("Heightmap settings", ("heightmap_settings",)),
        ("Water material", ("water_material",)),
        ("Water zone override", ("water_zone_override",)),
    ):
        prop, value = safe_property(body_default, names)
        record(lines, f"{label}={value if prop else 'NOT EXPOSED'} | property={prop}")

    record(lines, "")
    record(lines, "WATER ZONE DEFAULT OBJECT")
    record(lines, "-" * 96)
    zone_default = safe_default_object(zone_class, "WaterZone", lines)
    for label, names in (
        ("Zone extent", ("zone_extent",)),
        ("Water mesh", ("water_mesh",)),
        ("Local tessellation", ("enable_local_only_tessellation", "b_enable_local_only_tessellation")),
    ):
        prop, value = safe_property(zone_default, names)
        record(lines, f"{label}={value if prop else 'NOT EXPOSED'} | property={prop}")
    zone_methods = method_status(
        zone_default,
        (
            "set_zone_extent",
            "get_water_mesh_component",
            "add_water_body_component",
        ),
    )
    for method, present in zone_methods.items():
        record(lines, f"{method}={'YES' if present else 'NO'}")

    record(lines, "")
    record(lines, "MESH TERRAIN RIVER MODIFIER DEFAULT OBJECT")
    record(lines, "-" * 96)
    modifier_default = safe_default_object(modifier_class, "RiverModifier", lines)
    affected_property, _ = safe_property(
        modifier_default,
        ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"),
    )
    priority_property, _ = safe_property(modifier_default, ("priority",))
    disabled_property, _ = safe_property(modifier_default, ("is_disabled", "disabled"))
    max_z_property, _ = safe_property(modifier_default, ("max_z_distance",))
    record(lines, f"Affected Mesh Partition property={affected_property}")
    record(lines, f"Priority property={priority_property}")
    record(lines, f"Disabled property={disabled_property}")
    record(lines, f"Max Z Distance property={max_z_property}")
    modifier_methods = method_status(
        modifier_default,
        (
            "bp_set_affected_mega_mesh",
            "set_affected_mega_mesh",
            "set_max_z_distance",
            "is_enabled",
        ),
    )
    for method, present in modifier_methods.items():
        record(lines, f"{method}={'YES' if present else 'NO'}")

    stage09_spline = None
    source_spline_class = getattr(unreal, "SplineComponent", None)
    record(lines, "")
    record(lines, "SAVED STAGE 09 SPLINE")
    record(lines, "-" * 96)
    if stage09 and source_spline_class:
        splines = list(stage09.get_components_by_class(source_spline_class))
        record(lines, f"Stage09 spline components={len(splines)}")
        stage09_spline = splines[0] if len(splines) == 1 else None
        if stage09_spline:
            try:
                record(lines, f"Stage09 spline points={stage09_spline.get_number_of_spline_points()}")
                record(lines, f"Stage09 spline length cm={stage09_spline.get_spline_length()}")
            except Exception as exc:
                record(lines, f"Stage09 spline inspection warning={exc}")

    affected_assignable = bool(
        modifier_default
        and (
            affected_property
            or modifier_methods.get("bp_set_affected_mega_mesh")
            or modifier_methods.get("set_affected_mega_mesh")
        )
    )
    water_spline_accessible = bool(
        spline_class
        and (
            river_methods.get("get_water_spline")
            or body_methods.get("get_water_spline")
            or spline_methods.get("reset_spline")
            or (
                spline_methods.get("clear_spline_points")
                and spline_methods.get("add_spline_point")
                and spline_methods.get("update_spline")
            )
        )
    )
    required = bool(
        world
        and stage09
        and stage10
        and stage09_spline
        and mesh_partition
        and river_class
        and zone_class
        and spline_class
        and body_component_class
        and defaults_class
        and modifier_class
        and affected_assignable
        and water_spline_accessible
    )

    record(lines, "")
    record(lines, f"Water spline accessible={water_spline_accessible}")
    record(lines, f"River modifier assignable={affected_assignable}")
    record(lines, f"AETHER_MESH_TERRAIN_RIVER_API={'PASS' if required else 'CHECK'}")
    record(lines, "NO_ACTORS_SPAWNED=TRUE")
    record(lines, "NO_PACKAGES_SAVED=TRUE")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    write_report(lines)
    unreal.log_warning(f"AETHER_MESH_TERRAIN_RIVER_API_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = (
        "AETHER_MESH_TERRAIN_RIVER_API=FAIL\n"
        f"ERROR={type(exc).__name__}: {exc}\n"
        "NO_ACTORS_SPAWNED=TRUE\n"
        "NO_PACKAGES_SAVED=TRUE\n"
        "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE\n"
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
