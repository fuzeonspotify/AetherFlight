# Aether Flight production landscape setup

This upgrade replaces the intentionally low-detail runtime terrain with a real
4033 x 4033 Unreal Landscape covering 48 km. The source includes a 16-bit
heightmap, four biome masks, tileable PBR ground textures, a landscape-material
installer, and runtime detection that automatically disables the old terrain.

The aircraft, flight model, HUD, weather, runway, and controls are preserved.

## 1. Build and open the upgraded project

1. Close Unreal Editor.
2. Run `BUILD_ME_FIRST.cmd` from the project root.
3. Open `AetherFlight.uproject` after the build succeeds.
4. If Unreal offers to enable Water or PCG and restart, accept it.

## 2. Install the production material

In Unreal, choose **Tools > Execute Python Script** and run:

`Content/Python/InstallProductionLandscape.py`

Wait for texture import and shader compilation to finish. The script creates:

`/Game/Aether/ProductionTerrain/M_Landscape_Production`

## 3. Create the World Partition level

1. Choose **File > New Level**.
2. Select **Open World**. This provides World Partition, One File Per Actor,
   Data Layers, and HLOD support.
3. Save it as `/Game/Maps/AetherWorld`.
4. Switch to **Landscape Mode** and select **Manage > New**.
5. Choose **Import from File** and select:

   `SourceAssets/ProductionTerrain/Heightmaps/AetherFlight_4033_16bit.png`

6. Set the Landscape material to
   `/Game/Aether/ProductionTerrain/M_Landscape_Production`.
7. Use these exact transform values:

| Setting | Value |
|---|---:|
| Location X / Y / Z | 0 / 0 / 0 |
| Scale X | 1190.476190 |
| Scale Y | 1190.476190 |
| Scale Z | 1093.750000 |
| Heightmap resolution | 4033 x 4033 |

The import should resolve to 32 x 32 components with 2 x 2 sections and
63 quads per section. Importing may take several minutes.

The heightmap encoding deliberately places sea level at value 32768, so the
Landscape stays at Z=0 and aligns with the existing runway and ocean.

## 4. Import the biome masks

Open the Landscape **Paint** tab. The material exposes these layers:

| Layer | Weightmap file |
|---|---|
| Grass | `SourceAssets/ProductionTerrain/Weightmaps/AetherFlight_Grass_4033.png` |
| Rock | `SourceAssets/ProductionTerrain/Weightmaps/AetherFlight_Rock_4033.png` |
| Scree | `SourceAssets/ProductionTerrain/Weightmaps/AetherFlight_Scree_4033.png` |
| Snow | `SourceAssets/ProductionTerrain/Weightmaps/AetherFlight_Snow_4033.png` |

For each layer:

1. Click the **+** beside the layer and select **Weight-Blended Layer**.
2. Save the Layer Info under `/Game/Aether/ProductionTerrain/LayerInfo`.
3. Right-click the layer and choose **Import from File**.
4. Select its matching 4033 PNG above.

After all four masks import, choose **Landscape > Build Nanite Only** (wording
can vary slightly by engine point release), then save the level.

## 5. Make the level the default

Open **Project Settings > Maps & Modes** and set both **Editor Startup Map** and
**Game Default Map** to `AetherWorld`.

Press Play. Output should contain:

`[Aether] Production Landscape detected; runtime placeholder terrain is disabled.`

If it instead says no Landscape was found, verify you pressed Play while
`AetherWorld` was the active level.

## 6. Add high-quality environment assets legally

Marketplace/Fab assets cannot be redistributed inside this project. Add free
or owned assets to your project through Fab, then provide two Nanite meshes at
these exact paths:

| Purpose | Required asset path |
|---|---|
| Conifer | `/Game/Aether/Environment/Foliage/SM_Conifer` |
| Cliff rock | `/Game/Aether/Environment/Rocks/SM_CliffRock` |

The runtime scatter system will automatically populate up to 6,500 trees and
1,800 rocks using height, slope, moisture, exposure, and runway-exclusion rules.
The production-landscape path uses collision traces, so instances follow the
new terrain instead of the old noise function.

Recommended sources are free Quixel Megascans surfaces/rocks through Fab and a
free conifer pack whose license permits use in your project. Enable Nanite on
rock meshes. For trees, use Nanite only when the foliage asset and material are
designed for it; otherwise keep masked foliage conventional and use aggressive
instance culling.

Two verified free starting points:

- [Quixel Megascans Rock Cliff](https://www.fab.com/listings/22762313-071f-4017-a721-b29c5a2f1a87) for a scanned cliff surface.
- [Water Materials](https://www.fab.com/listings/063155ea-d9d2-4f29-b09f-33270b0bc861) for ocean, river, and waterfall material options.

Fab pricing and license terms can change, so confirm the listing still shows
**Free** and review its license before adding it to the project.

## 7. Upgrade the water

Water support is enabled in the project. You have two safe options:

- Add an Unreal **Water Body Ocean** actor and shape its spline around the land.
- Install the free Fab **Water Materials** pack and apply one of its ocean
  materials to your water actor.

The runtime director detects `WaterBodyOcean` and `WaterBodyLake` actors and
automatically disables its flat fallback ocean. A custom water actor can get
the same behavior by adding the actor tag `AetherWater`.

## Quality/performance notes

- The new Landscape spacing is about 11.9 m, versus roughly 94 m in the old
  fallback mesh: nearly eight times finer along each axis.
- Lumen, Virtual Shadow Maps, Nanite, volumetric clouds, volumetric fog, DX12,
  and SM6 remain enabled.
- Non-Nanite Virtual Shadow Map coarse pages are disabled in `DefaultEngine.ini`
  to remove the foliage/ocean coarse-page warning seen in the prior logs.
- Keep the old runtime terrain as a fallback until `AetherWorld` is saved and
  opens reliably. It is disabled automatically; no existing content is deleted.
