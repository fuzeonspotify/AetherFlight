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
    "RiverModifier": ("RiverModifier", "WaterBodyRiverModifier", "MeshPartitionRiverModifier"),
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


def find_mesh_partition(actors):
    preferred = []
    fallback = []
    for actor in actors:
        combined = f"{actor.get_name()} {actor.get_class().get_path_name()}"
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


def resolve_class(candidates):
    for name in candidates:
        cls = getattr(unreal, name, None)
        if cls:
            return name, cls
    return None, None


def safe_property(obj, names):
    for name in names:
        try:
            return name, obj.get_editor_property(name)
        except Exception:
            continue
    return None, None


def method_status(obj, names):
    return {name: callable(getattr(obj, name, None)) for name in names}


def component_lines(owner, lines):
    found = []
    if owner is None:
        return found
    for base_class in (getattr(unreal, "ActorComponent", None), getattr(unreal, "SceneComponent", None)):
        if not base_class:
            continue
        try:
            for component in owner.get_components_by_class(base_class):
                path = component.get_class().get_path_name()
                entry = f"{component.get_name()} | {path}"
                if entry not in found:
                    found.append(entry)
        except Exception:
            continue
    for entry in found:
        record(lines, f"  {entry}")
    return found


def main():
    lines = []
    record(lines, "AETHER UE 5.8 MESH TERRAIN RIVER API AUDIT")
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

    resolved = {}
    record(lines, "")
    record(lines, "CLASS AVAILABILITY")
    record(lines, "-" * 96)
    for label, candidates in CLASS_CANDIDATES.items():
        name, cls = resolve_class(candidates)
        resolved[label] = (name, cls)
        if cls:
            record(lines, f"{label}=unreal.{name} | {cls.get_path_name()}")
        else:
            record(lines, f"{label}=NOT EXPOSED | candidates={candidates}")

    river_name, river_class = resolved["WaterBodyRiver"]
    zone_name, zone_class = resolved["WaterZone"]
    spline_name, spline_class = resolved["WaterSplineComponent"]
    body_component_name, body_component_class = resolved["WaterBodyRiverComponent"]
    defaults_name, defaults_class = resolved["WaterSplineCurveDefaults"]
    modifier_name, modifier_class = resolved["RiverModifier"]

    record(lines, "")
    record(lines, "WATER BODY RIVER DEFAULT OBJECT")
    record(lines, "-" * 96)
    river_default = unreal.get_default_object(river_class) if river_class else None
    if river_default:
        record(lines, f"Class={river_default.get_class().get_path_name()}")
        methods = method_status(
            river_default,
            (
                "get_water_body_component",
                "get_water_spline",
                "get_water_spline_metadata",
                "on_water_body_changed",
                "set_water_material",
            ),
        )
        for method, present in methods.items():
            record(lines, f"{method}={'YES' if present else 'NO'}")
        record(lines, "Default components:")
        component_lines(river_default, lines)
    else:
        methods = {}

    record(lines, "")
    record(lines, "WATER SPLINE DEFAULT OBJECT")
    record(lines, "-" * 96)
    spline_default = unreal.get_default_object(spline_class) if spline_class else None
    if spline_default:
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
    else:
        spline_methods = {}

    record(lines, "")
    record(lines, "RIVER COMPONENT DEFAULT OBJECT")
    record(lines, "-" * 96)
    body_default = unreal.get_default_object(body_component_class) if body_component_class else None
    if body_default:
        for method, present in method_status(
            body_default,
            (
                "get_water_spline",
                "get_water_spline_metadata",
                "set_water_zone_override",
                "set_water_material",
                "on_water_body_changed",
            ),
        ).items():
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
    zone_default = unreal.get_default_object(zone_class) if zone_class else None
    if zone_default:
        for label, names in (
            ("Zone extent", ("zone_extent",)),
            ("Water mesh", ("water_mesh",)),
            ("Local tessellation", ("enable_local_only_tessellation", "b_enable_local_only_tessellation")),
        ):
            prop, value = safe_property(zone_default, names)
            record(lines, f"{label}={value if prop else 'NOT EXPOSED'} | property={prop}")
        for method, present in method_status(
            zone_default,
            (
                "set_zone_extent",
                "get_water_mesh_component",
                "add_water_body_component",
            ),
        ).items():
            record(lines, f"{method}={'YES' if present else 'NO'}")

    record(lines, "")
    record(lines, "MESH TERRAIN RIVER MODIFIER DEFAULT OBJECT")
    record(lines, "-" * 96)
    modifier_default = unreal.get_default_object(modifier_class) if modifier_class else None
    if modifier_default:
        for label, names in (
            ("Affected Mesh Partition", ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor")),
            ("Priority", ("priority",)),
            ("Disabled", ("is_disabled", "disabled")),
            ("Max Z Distance", ("max_z_distance",)),
        ):
            prop, value = safe_property(modifier_default, names)
            record(lines, f"{label}={value if prop else 'NOT EXPOSED'} | property={prop}")
        for method, present in method_status(
            modifier_default,
            (
                "bp_set_affected_mega_mesh",
                "set_affected_mega_mesh",
                "set_max_z_distance",
                "is_enabled",
            ),
        ).items():
            record(lines, f"{method}={'YES' if present else 'NO'}")

    stage09_spline = None
    source_spline_class = getattr(unreal, "SplineComponent", None)
    if stage09 and source_spline_class:
        splines = list(stage09.get_components_by_class(source_spline_class))
        stage09_spline = splines[0] if len(splines) == 1 else None
        record(lines, "")
        record(lines, f"Stage09 spline components={len(splines)}")
        if stage09_spline:
            try:
                record(lines, f"Stage09 spline points={stage09_spline.get_number_of_spline_points()}")
                record(lines, f"Stage09 spline length cm={stage09_spline.get_spline_length()}")
            except Exception as exc:
                record(lines, f"Stage09 spline inspection warning={exc}")

    affected_assignable = bool(
        modifier_default
        and (
            safe_property(
                modifier_default,
                ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"),
            )[0]
            or callable(getattr(modifier_default, "bp_set_affected_mega_mesh", None))
            or callable(getattr(modifier_default, "set_affected_mega_mesh", None))
        )
    )
    water_spline_accessible = bool(
        spline_class
        and (
            methods.get("get_water_spline")
            or spline_methods.get("reset_spline")
            or spline_methods.get("clear_spline_points")
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

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_MESH_TERRAIN_RIVER_API_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"AETHER_MESH_TERRAIN_RIVER_API=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
