from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
MPD_PATH = "/Game/Aether/MeshTerrain/MPD_AetherWorld"
WETLAND_TEXTURE_PATH = "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Wetland_Weight"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherRiverbankWeightAPIAudit.txt"

REQUIRED_ACTORS = (
    "Aether_VideoStage09_SplineChannel",
    "Aether_VideoStage10_SplineRemesh",
    "Aether_VideoStage11_River",
    "Aether_VideoStage11_WaterZone",
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
        try:
            class_path = actor.get_class().get_path_name()
        except Exception:
            class_path = type(actor).__name__
        combined = f"{actor.get_name()} {class_path}"
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


def class_label(cls):
    if cls is None:
        return "NOT EXPOSED"
    return getattr(cls, "__name__", str(cls))


def enum_members(enum_type):
    members = []
    if not enum_type:
        return members
    for name in dir(enum_type):
        if name.startswith("_") or name in ("name", "value"):
            continue
        try:
            value = getattr(enum_type, name)
        except Exception:
            continue
        if callable(value):
            continue
        members.append(f"{name}={value}")
    return members


def inspect_channel_names(definition, lines):
    names = []
    if not definition:
        return names
    try:
        channel_map = definition.get_editor_property("channel_map")
        descriptions = channel_map.get_editor_property("channel_descs")
    except Exception as exc:
        record(lines, f"MPD channel-map inspection failed={exc}")
        return names

    for index, description in enumerate(descriptions):
        value = None
        for property_name in ("name", "channel_name"):
            try:
                value = description.get_editor_property(property_name)
                break
            except Exception:
                continue
        text = str(value) if value is not None else "UNKNOWN"
        names.append(text)
        record(lines, f"MPD channel {index}={text}")
    return names


def inspect_weight_entry(entry_class, lines):
    result = {
        "constructible": False,
        "channel_property": None,
        "value_property": None,
        "blend_property": None,
    }
    if not entry_class:
        return result

    try:
        entry = entry_class()
        result["constructible"] = True
        record(lines, f"Weight entry constructed={entry}")
    except Exception as exc:
        record(lines, f"Weight entry construction failed={exc}")
        return result

    checks = (
        ("channel_property", ("channel_name", "weight_channel_name", "name")),
        ("value_property", ("value", "weight", "weight_value", "channel_value", "target_value")),
        ("blend_property", ("blend_mode", "weight_blend_mode")),
    )
    for result_key, candidates in checks:
        prop_name, value = safe_property(entry, candidates)
        result[result_key] = prop_name
        record(
            lines,
            f"Weight entry {result_key}={prop_name if prop_name else 'NOT EXPOSED'} | value={value}",
        )

    relevant = sorted(
        name for name in dir(entry)
        if any(token in name.lower() for token in ("channel", "weight", "value", "blend", "name"))
    )
    record(lines, f"Weight entry relevant API={','.join(relevant)}")
    return result


def main():
    lines = []
    record(lines, "AETHER UE 5.8 RIVERBANK WEIGHT API AUDIT")
    record(lines, "=" * 96)
    record(lines, "Read-only: no actors are spawned, no packages are saved, and no Mesh Partition build is started.")

    world = load_world()
    actors = get_actors()
    mesh_partition = find_mesh_partition(actors)
    record(lines, f"Map={world.get_path_name() if world else 'None'}")
    record(lines, f"Authoritative Mesh Partition={'YES' if mesh_partition else 'NO'}")

    dependencies_ok = True
    record(lines, "")
    record(lines, "SAVED STAGE DEPENDENCIES")
    record(lines, "-" * 96)
    resolved_actors = {}
    for label in REQUIRED_ACTORS:
        actor = find_actor(actors, label)
        resolved_actors[label] = actor
        dependencies_ok = dependencies_ok and actor is not None
        record(lines, f"{label}={'YES' if actor else 'NO'}")

    source_actor = resolved_actors["Aether_VideoStage09_SplineChannel"]
    source_spline = None
    spline_component_class = getattr(unreal, "SplineComponent", None)
    if source_actor and spline_component_class:
        splines = list(source_actor.get_components_by_class(spline_component_class))
        source_spline = splines[0] if len(splines) == 1 else None
        record(lines, f"Stage09 spline components={len(splines)}")
        if source_spline:
            record(lines, f"Stage09 spline points={source_spline.get_number_of_spline_points()}")
            record(lines, f"Stage09 spline length cm={source_spline.get_spline_length()}")

    spline_modifier_class = getattr(unreal, "SplineModifier", None)
    modifier_actor_class = getattr(unreal, "ModifierActor", None)
    entry_class = getattr(unreal, "SplineModifierWeightEntry", None)
    channel_name_class = getattr(unreal, "ChannelName", None)
    blend_enum = getattr(unreal, "SplineWeightBlendMode", None)

    record(lines, "")
    record(lines, "CLASS AVAILABILITY")
    record(lines, "-" * 96)
    record(lines, f"SplineModifier={class_label(spline_modifier_class)}")
    record(lines, f"SplineComponent={class_label(spline_component_class)}")
    record(lines, f"ModifierActor={class_label(modifier_actor_class)}")
    record(lines, f"SplineModifierWeightEntry={class_label(entry_class)}")
    record(lines, f"ChannelName={class_label(channel_name_class)}")
    record(lines, f"SplineWeightBlendMode={class_label(blend_enum)}")
    record(lines, f"SplineWeightBlendMode members={','.join(enum_members(blend_enum)) or 'NONE'}")

    modifier_default = unreal.get_default_object(spline_modifier_class) if spline_modifier_class else None
    modifier_checks = {}
    record(lines, "")
    record(lines, "SPLINE MODIFIER WEIGHT OUTPUT")
    record(lines, "-" * 96)
    if modifier_default:
        for key, candidates in (
            ("affected", ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor")),
            ("priority", ("priority",)),
            ("disabled", ("is_disabled", "disabled")),
            ("spline", ("spline_ptr", "spline_component", "spline")),
            ("write_mode", ("write_mode",)),
            ("weight_channels", ("weight_channels",)),
            ("falloff", ("falloff_distance",)),
            ("plateau", ("plateau_distance",)),
            ("max_z", ("max_z_distance",)),
        ):
            prop_name, value = safe_property(modifier_default, candidates)
            modifier_checks[key] = prop_name
            record(lines, f"{key} property={prop_name if prop_name else 'NOT EXPOSED'} | value={value}")

        for method_name in (
            "bp_set_affected_mega_mesh",
            "bp_set_spline_component",
            "set_spline_component",
            "set_falloff_distance",
            "set_max_z_distance",
            "set_use_spline_scale_for_falloff",
            "update_spline_data",
        ):
            record(lines, f"{method_name}={'YES' if callable(getattr(modifier_default, method_name, None)) else 'NO'}")

    entry_info = inspect_weight_entry(entry_class, lines)

    definition = unreal.EditorAssetLibrary.load_asset(MPD_PATH)
    wetland_texture_exists = unreal.EditorAssetLibrary.does_asset_exist(WETLAND_TEXTURE_PATH)
    record(lines, "")
    record(lines, "MESH PARTITION CHANNELS")
    record(lines, "-" * 96)
    record(lines, f"MPD asset={'YES' if definition else 'NO'} | {MPD_PATH}")
    channel_names = inspect_channel_names(definition, lines)
    wetland_channel = any(name.lower() == "wetland" for name in channel_names)
    record(lines, f"Wetland channel={'YES' if wetland_channel else 'NO'}")
    record(lines, f"Wetland texture asset={'YES' if wetland_texture_exists else 'NO'} | {WETLAND_TEXTURE_PATH}")

    affected_assignable = bool(
        modifier_default
        and (
            modifier_checks.get("affected")
            or callable(getattr(modifier_default, "bp_set_affected_mega_mesh", None))
        )
    )
    spline_assignable = bool(
        modifier_default
        and (
            modifier_checks.get("spline")
            or callable(getattr(modifier_default, "bp_set_spline_component", None))
            or callable(getattr(modifier_default, "set_spline_component", None))
        )
    )
    weight_output_available = bool(
        modifier_checks.get("write_mode")
        and modifier_checks.get("weight_channels")
        and entry_info["constructible"]
        and entry_info["channel_property"]
        and entry_info["blend_property"]
    )
    source_ok = bool(
        source_spline
        and int(source_spline.get_number_of_spline_points()) == 5
        and 80000.0 <= float(source_spline.get_spline_length()) <= 170000.0
    )

    passed = bool(
        world
        and dependencies_ok
        and mesh_partition
        and source_ok
        and spline_modifier_class
        and spline_component_class
        and modifier_actor_class
        and affected_assignable
        and spline_assignable
        and weight_output_available
        and definition
        and wetland_channel
        and wetland_texture_exists
    )

    record(lines, "")
    record(lines, f"Affected Mesh Partition assignable={affected_assignable}")
    record(lines, f"Spline component assignable={spline_assignable}")
    record(lines, f"Weight-only output configurable={weight_output_available}")
    record(lines, f"Saved source spline valid={source_ok}")
    record(lines, f"AETHER_RIVERBANK_WEIGHT_API={'PASS' if passed else 'CHECK'}")
    record(lines, "NO_ACTORS_SPAWNED=TRUE")
    record(lines, "NO_PACKAGES_SAVED=TRUE")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_RIVERBANK_WEIGHT_API_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"AETHER_RIVERBANK_WEIGHT_API=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
