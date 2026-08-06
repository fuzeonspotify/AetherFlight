# Aether Production World v2

This upgrade replaces the broken terrain source without deleting the existing
experience. Old Landscapes remain recoverable but are hidden and have collision
disabled after the repair pass.

## What changes

- 4033 x 4033 / 48 km World Partition Landscape with a submerged safety border
- tectonic mountain belts instead of uniform noise hills
- linearly resampled 16-bit height data (no cubic overshoot needles)
- four carved lake basins and three connected river corridors
- Grass, ForestFloor, Rock, Scree, Snow, Sand, and Wetland weightmaps
- multiscale rotated landscape textures and broad color variation
- river/lake Water Body actors generated from the same terrain source
- hydrology-aware HISM foliage that avoids open water and favors riparian forest

## 1. Generate the source world

Close Unreal Editor, then double-click:

`GENERATE_PRODUCTION_WORLD.cmd`

The command writes all generated source files below:

`SourceAssets/ProductionTerrain`

It never touches the `.umap`.

## 2. Install the seven-biome material

Open `Content/Maps/AetherWorld` and make sure PIE is stopped.

Run these from **Tools > Execute Python Script**, in order:

1. `Content/Python/InstallProductionLandscape.py`
2. `Content/Python/UpgradeProductionLandscapeMaterial_UE58_v6.py`

Wait for shaders to finish before importing the Landscape.

## 3. Import a clean Landscape

Open **Landscape > Manage > New > Import from File** and use:

- Heightmap: `SourceAssets/ProductionTerrain/Heightmaps/AetherFlight_4033.r16`
- Resolution: `4033 x 4033`
- Section Size: `63 x 63 Quads`
- Sections per Component: `2 x 2`
- Components: `32 x 32`
- Location: `0, 0, 0`
- Scale X: `1190.476190`
- Scale Y: `1190.476190`
- Scale Z: `1093.75`
- Material: `/Game/Aether/ProductionTerrain/M_Landscape_Production`

Assign these Layer Info assets and weightmaps in the import panel:

| Layer | Layer Info | Weightmap |
|---|---|---|
| Grass | `LI_Grass` | `AetherFlight_Grass_4033.png` |
| ForestFloor | `LI_ForestFloor` | `AetherFlight_ForestFloor_4033.png` |
| Rock | `LI_Rock` | `AetherFlight_Rock_4033.png` |
| Scree | `LI_Scree` | `AetherFlight_Scree_4033.png` |
| Snow | `LI_Snow` | `AetherFlight_Snow_4033.png` |
| Sand | `LI_Sand` | `AetherFlight_Sand_4033.png` |
| Wetland | `LI_Wetland` | `AetherFlight_Wetland_4033.png` |

The weightmaps are in `SourceAssets/ProductionTerrain/Weightmaps`.

If Unreal says the import will be padded or clipped, click **Cancel**. The
selected Landscape or resolution is wrong; never accept that warning.

After import, rename the new root actor to:

`Landscape_Production_V2_4033`

Do not delete any older Landscape.

## 4. Make v2 authoritative and add water

Run:

1. `Content/Python/RepairProductionWorld_UE58_v6.py`
2. `Content/Python/InstallAetherHydrology_UE58.py`

The repair script selects the v2 Landscape, disables every legacy
Landscape/proxy in game, disables legacy collision, and puts all active proxies
in the same LOD group. The hydrology script adds the lakes and rivers without
carving the terrain a second time.

## 5. Rebuild and test

1. Select `Landscape_Production_V2_4033`.
2. If **Enable Nanite** is checked, use **Build > Build Landscape**.
3. Wait for Landscape and shader tasks to finish.
4. Save All.
5. Press Play and press `R` once to reset the aircraft.

If the huge rectangular wall is still visible, uncheck **Enable Nanite** on the
selected production Landscape and test once. If that fixes it, the geometry was
stale Nanite data; re-enable Nanite and run **Build Landscape** again.

## 6. Repair ocean and aerodynamic vapor materials

Run once after pulling this upgrade:

1. `Content/Python/InstallExtremeOceanMaterial_UE58.py`
2. `Content/Python/InstallWingCondensationMaterial_UE58.py`

Both installers now recreate only their generated material asset after making a
backup, validate every graph connection, and stop instead of saving a fallback
material if Unreal rejects a pin.
