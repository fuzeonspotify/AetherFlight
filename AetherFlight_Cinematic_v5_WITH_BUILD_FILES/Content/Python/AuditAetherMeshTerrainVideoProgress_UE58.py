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
    "Rock Collection 04 #1": "/Game/Rock_Collection_04/Meshes/Rock_01/StaticMeshes/SM_Rock_01",
    "Rock Collection 04 #2": "/Game/Rock_Collection_04/Meshes/Rock_02/StaticMeshes/SM_Rock_02",
    "Rock Collection 04 #3": "/Game/Rock_Collection_04/Meshes/Rock_03/StaticMeshes/SM_Rock_03",
    "Rock Collection 04 #4": "/Game/Rock_Collection_04/Meshes/Rock_04/StaticMeshes/SM_Rock_04",
    "Rock Collection 04 #5": "/Game/Rock_Collection_04/Meshes/Rock_05/StaticMeshes/SM_Rock_05",
    "Rock Collection 04 #6": "/Game/Rock_Collection_04/Meshes/Rock_06/StaticMeshes/SM_Rock_06",
    "Rock Collection 04 #7": "/Game/Rock_Collection_04/Meshes/Rock_07/StaticMeshes/SM_Rock_07",
}

MODIFIER_CLASS_NAMES = [
    "RemeshModifier",
    "SplineRemeshModifier",
    "BooleanModifier",
    "SplineModifier",
    "TexturePatchModifier",
    "PatchModifier",
    "NoiseModifier",
    "MeshProjectModifier",
]

MODIFIER_KEYWORDS = {
    "Local Remesh/Tessellate": ("RemeshModifier",),
    "Spline Remesh/Tessellate": ("SplineRemeshModifier",),
    "Sculpt/Paint": ("Sculpt", "EditableModifier", "ProjectMeshLayers"),
    "Boolean": ("BooleanModifier",),
    "Spline": ("SplineModifier",),
    "Texture": ("TexturePatchModifier",),
    "Water": ("LakeModifier", "RiverModifier", "WaterModifier"),
}


def log(lines, text=""):
    lines.append(str(text))
    unreal.log_warning(str(text))


def class_path(obj):
    try:
        return obj.get_class().get_path_name()
    except Exception:
        return type(obj).__name__


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

    authoritative = [
        actor for actor in mesh_partition_actors
        if actor.get_name() == "MeshTerrain_AetherWorld"
        or actor.actor_has_tag("AetherProductionTerrain")
    ]

    log(lines, "")
    log(lines, "BASE TERRAIN")
    log(lines, "-" * 96)
    log(lines, f"Mesh Partition-like actors={len(mesh_partition_actors)}")
    for actor in mesh_partition_actors[:20]:
        log(lines, f"  {actor.get_name()} | {class_path(actor)}")
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
    log(lines, "UE 5.8 MODIFIER CLASS AVAILABILITY")
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
    log(lines, "MODIFIERS CURRENTLY PLACED IN AETHERWORLD")
    log(lines, "-" * 96)
    placed_by_category = {category: [] for category in MODIFIER_KEYWORDS}
    for actor, component, component_type in discovered_components:
        combined = f"{component.get_name()} {component_type}"
        for category, keywords in MODIFIER_KEYWORDS.items():
            if any(keyword.lower() in combined.lower() for keyword in keywords):
                placed_by_category[category].append(
                    f"{actor.get_name()}.{component.get_name()} | {component_type}"
                )

    for category, matches in placed_by_category.items():
        log(lines, f"{category}: {len(matches)}")
        for match in matches[:30]:
            log(lines, f"  {match}")

    local_remesh_count = len(placed_by_category["Local Remesh/Tessellate"])
    spline_remesh_count = len(placed_by_category["Spline Remesh/Tessellate"])
    sculpt_count = len(placed_by_category["Sculpt/Paint"])
    boolean_count = len(placed_by_category["Boolean"])
    spline_count = len(placed_by_category["Spline"])
    texture_count = len(placed_by_category["Texture"])
    water_count = len(placed_by_category["Water"])

    log(lines, "")
    log(lines, "FULL VIDEO CHECKPOINT")
    log(lines, "-" * 96)
    log(lines, f"01 Setup/plugins/open-world map        = {'COMPLETE' if base_pass else 'CHECK'}")
    log(lines, f"02 Heightmap/Mesh Partition base       = {'COMPLETE' if base_pass else 'CHECK'}")
    log(lines, f"03 MPD/material/weight assets          = {'COMPLETE' if asset_pass else 'CHECK'}")
    log(lines, f"04 Local Remesh/Tessellate modifier    = {'COMPLETE' if local_remesh_count else 'NEXT'}")
    log(lines, f"05 Sculpt and Paint modifier           = {'COMPLETE' if sculpt_count else 'NOT STARTED'}")
    log(lines, f"06 Static Mesh / Boolean terrain work  = {'COMPLETE' if boolean_count else 'NOT STARTED'}")
    log(lines, f"07 Texture Patch modifier              = {'COMPLETE' if texture_count else 'NOT STARTED'}")
    log(lines, f"08 Spline terrain modifier             = {'COMPLETE' if spline_count else 'NOT STARTED'}")
    log(lines, f"09 Spline Remesh modifier              = {'COMPLETE' if spline_remesh_count else 'NOT STARTED'}")
    log(lines, f"10 Water terrain modifiers             = {'STARTED' if water_count else 'NOT STARTED'}")
    log(lines, "11 Convert to classic Landscape         = DEFERRED BY DESIGN")

    next_stage = "LOCAL_REMESH_TESSELLATE" if local_remesh_count == 0 else (
        "SCULPT_PAINT" if sculpt_count == 0 else (
            "BOOLEAN_CAVE" if boolean_count == 0 else (
                "TEXTURE_MODIFIER" if texture_count == 0 else (
                    "SPLINE_MODIFIER" if spline_count == 0 else (
                        "SPLINE_REMESH" if spline_remesh_count == 0 else (
                            "WATER_TERRAIN" if water_count == 0 else "VIDEO_WORKFLOW_COMPLETE"
                        )
                    )
                )
            )
        )
    )
    log(lines, "")
    log(lines, f"AETHER_VIDEO_NEXT_STAGE={next_stage}")
    log(lines, "Modifier stages intentionally remain local until their editor preview is verified; no audit starts a whole-world compiled build.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_PROGRESS_REPORT={REPORT_PATH}")


main()
