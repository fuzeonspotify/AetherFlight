from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherMeshTerrainVideoProgress.txt"

EXPECTED_ASSETS = {
    "Mesh Partition Definition": "/Game/Aether/MeshTerrain/MPD_AetherWorld",
    "Sensei biome material": "/Game/Aether/MeshTerrain/MI_AetherTerrain_Sensei_BiomeTuned",
    "Grass weight": "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Grass_Weight",
    "Forest-floor weight": "/Game/Aether/MeshTerrain/Weightmaps/T_MT_ForestFloor_Weight",
    "Rock weight": "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Rock_Weight",
    "Sand weight": "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Sand_Weight",
    "Scree weight": "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Scree_Weight",
    "Snow weight": "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Snow_Weight",
    "Wetland weight": "/Game/Aether/MeshTerrain/Weightmaps/T_MT_Wetland_Weight",
}

STAGE_LABELS = {
    "05 Local Remesh/Tessellate": "Aether_VideoStage05_LocalRemesh",
    "06 Sculpt/Paint": "Aether_VideoStage06_SculptPaint",
    "07 Boolean Cave": "Aether_VideoStage07_BooleanCave",
    "08 Texture Patch": "Aether_VideoStage08_TexturePatch",
    "09 Spline Channel": "Aether_VideoStage09_SplineChannel",
    "10 Spline Remesh": "Aether_VideoStage10_SplineRemesh",
    "11 River": "Aether_VideoStage11_River",
    "11 Water Zone": "Aether_VideoStage11_WaterZone",
    "12 Riverbank Wetland": "Aether_VideoStage12_RiverbankWetland",
}

MODIFIER_CLASS_NAMES = [
    "RemeshModifier",
    "SplineRemeshModifier",
    "BooleanModifier",
    "SplineModifier",
    "SplineModifierWeightEntry",
    "TexturePatchModifier",
    "RiverModifier",
    "WaterModifier",
    "WaterBodyRiver",
    "WaterZone",
]

MODIFIER_KEYWORDS = {
    "Local Remesh/Tessellate": ("RemeshModifier",),
    "Spline Remesh/Tessellate": ("SplineRemeshModifier",),
    "Sculpt/Paint": ("Sculpt", "EditableModifier", "ProjectMeshLayers"),
    "Boolean": ("BooleanModifier",),
    "Spline": ("SplineModifier",),
    "Texture": ("TexturePatchModifier",),
    "Water": ("LakeModifier", "RiverModifier", "WaterModifier", "WaterBodyRiver"),
}


def log(lines, text=""):
    text = str(text)
    lines.append(text)
    unreal.log_warning(text)


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def get_all_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return list(subsystem.get_all_level_actors())


def load_world():
    current = unreal.EditorLevelLibrary.get_editor_world()
    if current and current.get_path_name().startswith(MAP_PATH):
        return current
    unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    return unreal.EditorLevelLibrary.get_editor_world()


def actor_components(actor):
    components = []
    for base_class in (unreal.SceneComponent, unreal.ActorComponent):
        try:
            for component in actor.get_components_by_class(base_class):
                if component not in components:
                    components.append(component)
        except Exception:
            pass
    return components


def stage12_configuration(actor):
    result = {
        "modifier_found": False,
        "write_mode": None,
        "weight_entries": 0,
        "priority": None,
        "valid": False,
    }
    if not actor:
        return result

    for component in actor_components(actor):
        if "SplineModifier" not in class_path(component):
            continue
        result["modifier_found"] = True
        try:
            result["write_mode"] = int(component.get_editor_property("write_mode"))
        except Exception:
            pass
        try:
            result["weight_entries"] = len(list(component.get_editor_property("weight_channels")))
        except Exception:
            pass
        try:
            result["priority"] = float(component.get_editor_property("priority"))
        except Exception:
            pass
        break

    result["valid"] = bool(
        result["modifier_found"]
        and result["write_mode"] == 2
        and result["weight_entries"] == 1
        and result["priority"] is not None
        and abs(result["priority"] - 55.0) <= 0.01
    )
    return result


def main():
    lines = []
    log(lines, "AETHER MESH TERRAIN — FULL VIDEO PROGRESS AUDIT")
    log(lines, "=" * 96)

    world = load_world()
    log(lines, f"Map={world.get_path_name() if world else 'None'}")

    actors = get_all_actors()
    mesh_partition_actors = []
    classic_landscape_actors = []
    discovered_components = []

    for actor in actors:
        actor_type = class_path(actor)
        combined = f"{actor.get_name()} {actor_type}"
        if "MeshPartition" in combined or "MeshTerrain" in combined:
            mesh_partition_actors.append(actor)
        if "Landscape" in actor_type:
            classic_landscape_actors.append(actor)
        for component in actor_components(actor):
            discovered_components.append((actor, component, class_path(component)))

    authoritative = []
    for actor in mesh_partition_actors:
        tags = []
        try:
            tags = [str(tag) for tag in actor.get_editor_property("tags")]
        except Exception:
            pass
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in tags:
            authoritative.append(actor)

    log(lines, "")
    log(lines, "BASE TERRAIN")
    log(lines, "-" * 96)
    log(lines, f"Mesh Partition-like actors={len(mesh_partition_actors)}")
    log(lines, f"Authoritative Aether roots={len(authoritative)}")
    log(lines, f"Classic Landscape actors={len(classic_landscape_actors)}")
    base_pass = len(authoritative) == 1 and len(classic_landscape_actors) == 0
    log(lines, f"VIDEO_STAGE_BASE_TERRAIN={'PASS' if base_pass else 'CHECK'}")

    log(lines, "")
    log(lines, "ASSETS AND WEIGHT CHANNEL INPUTS")
    log(lines, "-" * 96)
    asset_pass = True
    for label, path in EXPECTED_ASSETS.items():
        exists = unreal.EditorAssetLibrary.does_asset_exist(path)
        asset_pass = asset_pass and exists
        log(lines, f"{'YES' if exists else 'NO '} | {label:30s} | {path}")
    log(lines, f"VIDEO_STAGE_ASSETS={'PASS' if asset_pass else 'CHECK'}")

    log(lines, "")
    log(lines, "UE 5.8 CLASS AVAILABILITY")
    log(lines, "-" * 96)
    for class_name in MODIFIER_CLASS_NAMES:
        cls = getattr(unreal, class_name, None)
        log(lines, f"{'YES' if cls else 'NO '} | unreal.{class_name}")

    exposed_names = list(dir(unreal))
    for category, keywords in MODIFIER_KEYWORDS.items():
        matches = sorted(
            name for name in exposed_names
            if any(keyword.lower() in name.lower() for keyword in keywords)
        )
        log(lines, f"{category:26s} exposed names={', '.join(matches[:30]) if matches else 'None'}")

    log(lines, "")
    log(lines, "EXPECTED STAGE ACTORS")
    log(lines, "-" * 96)
    labels_present = {actor_label(actor): actor for actor in actors}
    stage_present = {}
    for stage, label in STAGE_LABELS.items():
        present = label in labels_present
        stage_present[stage] = present
        log(lines, f"{'YES' if present else 'NO '} | {stage:28s} | {label}")

    log(lines, "")
    log(lines, "MODIFIERS CURRENTLY PLACED IN AETHERWORLD")
    log(lines, "-" * 96)
    placed_by_category = {category: [] for category in MODIFIER_KEYWORDS}
    for actor, component, component_type in discovered_components:
        combined = f"{component.get_name()} {component_type}"
        for category, keywords in MODIFIER_KEYWORDS.items():
            if any(keyword.lower() in combined.lower() for keyword in keywords):
                placed_by_category[category].append(
                    f"{actor_label(actor)}.{component.get_name()} | {component_type}"
                )

    for category, matches in placed_by_category.items():
        log(lines, f"{category}: {len(matches)}")
        for match in matches[:30]:
            log(lines, f"  {match}")

    local_remesh = stage_present["05 Local Remesh/Tessellate"]
    sculpt = stage_present["06 Sculpt/Paint"]
    boolean = stage_present["07 Boolean Cave"]
    texture = stage_present["08 Texture Patch"]
    spline = stage_present["09 Spline Channel"]
    spline_remesh = stage_present["10 Spline Remesh"]
    river = stage_present["11 River"]
    water_zone = stage_present["11 Water Zone"]
    riverbank_actor = labels_present.get(STAGE_LABELS["12 Riverbank Wetland"])
    riverbank_config = stage12_configuration(riverbank_actor)
    water_components = len(placed_by_category["Water"])

    log(lines, "")
    log(lines, "STAGE 12 RIVERBANK CONFIGURATION")
    log(lines, "-" * 96)
    log(lines, f"Actor present={'YES' if riverbank_actor else 'NO'}")
    log(lines, f"SplineModifier present={riverbank_config['modifier_found']}")
    log(lines, f"Write mode={riverbank_config['write_mode']} | expected=2 (Weights only)")
    log(lines, f"Weight-channel entries={riverbank_config['weight_entries']} | expected=1")
    log(lines, f"Priority={riverbank_config['priority']} | expected=55")
    log(lines, f"Stage12 configuration valid={riverbank_config['valid']}")

    log(lines, "")
    log(lines, "FULL VIDEO CHECKPOINT")
    log(lines, "-" * 96)
    log(lines, f"01 Setup/plugins/open-world map        = {'COMPLETE' if base_pass else 'CHECK'}")
    log(lines, f"02 Heightmap/Mesh Partition base       = {'COMPLETE' if base_pass else 'CHECK'}")
    log(lines, f"03 MPD/material/weight assets          = {'COMPLETE' if asset_pass else 'CHECK'}")
    log(lines, f"04 Local Remesh/Tessellate modifier    = {'COMPLETE' if local_remesh else 'NEXT'}")
    log(lines, f"05 Sculpt and Paint modifier           = {'COMPLETE' if sculpt else 'NOT STARTED'}")
    log(lines, f"06 Static Mesh / Boolean terrain work  = {'COMPLETE' if boolean else 'NOT STARTED'}")
    log(lines, f"07 Texture Patch modifier              = {'COMPLETE' if texture else 'NOT STARTED'}")
    log(lines, f"08 Spline terrain modifier             = {'COMPLETE' if spline else 'NOT STARTED'}")
    log(lines, f"09 Spline Remesh modifier              = {'COMPLETE' if spline_remesh else 'NOT STARTED'}")
    water_complete = river and water_zone and water_components > 0
    log(lines, f"10 Local river water integration       = {'COMPLETE' if water_complete else ('STARTED' if river or water_zone or water_components else 'NOT STARTED')}")
    log(lines, f"11 Riverbank wetland weight integration = {'COMPLETE' if riverbank_config['valid'] else ('STARTED' if riverbank_actor else 'NOT STARTED')}")
    log(lines, "12 River environment integration        = NOT STARTED")
    log(lines, "13 Convert to classic Landscape         = DEFERRED BY DESIGN")

    if not local_remesh:
        next_stage = "LOCAL_REMESH_TESSELLATE"
    elif not sculpt:
        next_stage = "SCULPT_PAINT"
    elif not boolean:
        next_stage = "BOOLEAN_CAVE"
    elif not texture:
        next_stage = "TEXTURE_MODIFIER"
    elif not spline:
        next_stage = "SPLINE_MODIFIER"
    elif not spline_remesh:
        next_stage = "SPLINE_REMESH"
    elif not water_complete:
        next_stage = "LOCAL_RIVER_WATER"
    elif not riverbank_config["valid"]:
        next_stage = "RIVERBANK_WETLAND_WEIGHT"
    else:
        next_stage = "RIVER_ENVIRONMENT_INTEGRATION"

    log(lines, "")
    log(lines, f"AETHER_VIDEO_NEXT_STAGE={next_stage}")
    log(lines, "Modifier stages intentionally remain local until their editor preview is verified; no audit starts a whole-world compiled build.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_PROGRESS_REPORT={REPORT_PATH}")


main()
