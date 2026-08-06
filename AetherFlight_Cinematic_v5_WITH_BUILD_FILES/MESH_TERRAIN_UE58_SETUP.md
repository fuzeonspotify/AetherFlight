# Aether Flight — UE 5.8 Mesh Terrain Migration

This is the AetherFlight implementation of the UE 5.8 Mesh Terrain workflow in
Unreal Sensei's video. It replaces the old heightfield renderer with a
World-Partitioned, Nanite-backed mesh terrain that supports non-destructive
modifiers, local remeshing, cliffs, overhangs, caves, water interaction, weight
channels, and PCG.

Mesh Terrain is **Experimental in UE 5.8**. The migration therefore keeps the
working `Landscape_Production_V2_4033` recoverable until the new runtime sections
and collision have been verified. No script in this workflow deletes a Landscape.

## What this patch installs

- the four required Mesh Terrain plugins
- `M_MeshTerrain_Aether`, a Nanite-safe automatic triplanar biome material
- `MPD_AetherWorld`, with Aether biome channels and modifier priorities
- three correctly named transformer-pipeline shells
- the seven existing production biome masks as Mesh Terrain weight textures
- runtime recognition of an authoritative Mesh Partition actor
- a guarded finalizer and one-click Landscape rollback

The automatic material uses world-space triplanar projection, height/slope biome
selection, and kilometer-scale breakup. It does not depend on the paid/downloaded
material shown in the video and does not stretch on vertical cliff faces.

## 1. Pull and rebuild once

Close Unreal Editor. In PowerShell:

```powershell
cd C:\Projects\AetherFlight
git pull origin agent/high-quality-biome-scatter
cd .\AetherFlight_Cinematic_v5_WITH_BUILD_FILES
.\BUILD_ME_FIRST.cmd
```

Open `AetherFlight.uproject`. The first launch can take longer while the four new
experimental plugins load.

## 2. Install the Aether authoring assets

Open `/Game/Maps/AetherWorld`, stop PIE, then run:

`Content/Python/InstallAetherMeshTerrain_UE58.py`

The installer is idempotent. It creates or refreshes:

| Asset | Purpose |
|---|---|
| `M_MeshTerrain_Aether` | automatic triplanar material |
| `MPD_AetherWorld` | material, channels, modifier priorities, build variants |
| `TP_Preview_AetherWorld` | fast editor preview |
| `TP_Compiled_HighEnd_AetherWorld` | Nanite visual runtime sections |
| `TP_Compiled_Common_AetherWorld` | shared runtime collision |

If it says `MeshPartitionDefinition is unavailable`, close and reopen Unreal once.
The plugins are loaded only after an editor restart.

## 3. Fill the three transformer pipelines

Python cannot create Unreal's `TInstancedStruct` transformer entries. This is the
only data-asset setup that must be done in the Details panel.

Open `/Game/Aether/MeshTerrain/TP_Preview_AetherWorld` and add, in order:

1. **Subsection Transformer** — `Sub Section Size = 65536`
2. **Static Mesh Transformer** — enable **Nanite** and **Skirts**
3. **Collision Transformer** — `Error Tolerance = 100 cm`
4. **WP Actor Properties Transformer** — use the main World Partition runtime grid

Open `TP_Compiled_HighEnd_AetherWorld` and add, in order:

1. **Far Field Transformer** — `Far Field Mesh Edge Length = 10000 cm`
2. **Subsection Transformer** — `Sub Section Size = 65536`
3. **Static Mesh Transformer** — enable **Nanite** and **Skirts**
4. **WP Actor Properties Transformer** — use the main runtime grid

For the Static Mesh Transformer, use the terrain-style LOD mode **Derive Screen
Size from Error**, `Pixel Error = 8`, with:

| LOD | Error tolerance | Maximum triangle fraction |
|---|---:|---:|
| 0 | source geometry | 1.00 |
| 1 | 4 cm | 0.50 |
| 2 | 16 cm | 0.25 |
| 3 | 64 cm | 0.10 |

Open `TP_Compiled_Common_AetherWorld` and add, in order:

1. **Subsection Transformer** — `Sub Section Size = 65536`
2. **Collision Transformer** — `Error Tolerance = 100 cm`
3. **WP Actor Properties Transformer** — use the main runtime grid

Do not add the deprecated Mesh Skirt Transformer. Skirts are enabled inside the
Static Mesh Transformer.

## 4. Finish `MPD_AetherWorld`

Open `/Game/Aether/MeshTerrain/MPD_AetherWorld` and confirm:

- Material: `M_MeshTerrain_Aether`
- Channel Texel Size: `400 cm`
- Material Cache Texel Size: `800 cm`
- Channel UV Layout Method: **Plane Project**
- Modifier Layer Priorities, in order:
  `Base`, `Erosion`, `Hydrology`, `LocalDetail`, `Paint`

The installer normally creates these channels. If the log said Python could not
author the channel map, add them manually in this exact order:

1. `Grass`
2. `ForestFloor`
3. `Rock`
4. `Scree`
5. `Snow`
6. `Sand`
7. `Wetland`
8. `Water`
9. `Forest`
10. `FoliageExclusion`

Set the Preview section to:

- Max Section Complexity: `250000`
- Transformer Pipeline: `TP_Preview_AetherWorld`

Add these Compiled Section Build Variants:

| Name | Max section complexity | Pipeline |
|---|---:|---|
| `HighEnd` | 250000 | `TP_Compiled_HighEnd_AetherWorld` |
| `Common` | 250000 | `TP_Compiled_Common_AetherWorld` |

Under **Platforms > Default > Build Variant Names**, add both `HighEnd` and
`Common`.

## 5. Import the production heightmap as Mesh Terrain

The current map is already a World Partition level, which Mesh Terrain requires.

1. Switch the editor mode to **Mesh Terrain**.
2. Open **Create > Import Heightmap**.
3. Select:
   `SourceAssets/ProductionTerrain/Heightmaps/AetherFlight_4033.r16`
4. Set the mesh to:

| Setting | Value |
|---|---:|
| Resolution | `4033 x 4033` vertices |
| Size X | `4,800,000 cm` |
| Size Y | `4,800,000 cm` |
| Size Z | `560,000 cm` |
| Sections | explicit `32 x 32` when available |
| Per-section resolution | `127 x 127` vertices / `126 x 126` quads |
| Save and Unload | enabled |
| Definition | `MPD_AetherWorld` |

If your build labels Resolution as **quads**, enter `4032 x 4032`; the source is
4033 samples and therefore contains 4032 quads. Do not accept a padded/clipped
import.

The R16 source encodes sea level at value 32768 and a physical range of
`-2800 m` to `+2800 m`. If the importer places the minimum height at world Z=0,
set the new Mesh Partition actor's Z location to `-280000 cm`. If its coastline
already meets the ocean at world Z=0, leave its Z location unchanged.

Rename the root actor:

`MeshTerrain_AetherWorld`

At this point the old Landscape should still be enabled. Hide it temporarily
with the eye icon only while visually inspecting the Mesh Terrain; do not run the
finalizer yet.

## 6. Add the non-destructive detail stack

Use **Tools > Mesh Partition Settings** to open the Mesh Partition Outliner. Put
modifiers in these layers:

- **Base** — imported 4033 heightmap only
- **Erosion** — broad Noise modifiers; keep them low-frequency
- **Hydrology** — Lake/River water modifiers and shoreline corrections
- **LocalDetail** — Remesh before detailed cliff, cave, and shoreline modifiers
- **Paint** — manual channel cleanup and art direction

For the 48 km world, never globally remesh the entire terrain to cinematic
density. Use local Remesh or Spline Remesh modifiers around shorelines, the
airbase, hero valleys, cliffs, riverbanks, and cave entrances. Nanite handles
the resulting local density while distant mountains remain inexpensive.

The imported textures in `/Game/Aether/MeshTerrain/Weightmaps` are source masks
for Texture/Project modifiers and PCG. They are not heightmaps. Use the matching
channel name when projecting each mask.

For each existing Lake or River Water Body, add its Mesh Partition Water modifier,
set **Affected Mesh Partition** to `MeshTerrain_AetherWorld`, and place it in the
`Hydrology` priority. Ocean requires no terrain modifier.

## 7. Build runtime terrain, then switch over

1. Use **Build > Build Mesh Partition**.
2. Wait for Mesh Partition, Nanite, collision, and shader jobs to finish.
3. In the Outliner filter, enable **Show Build Mesh Partition Sections**.
4. Verify the compiled sections are visible and collision works.
5. Run `Content/Python/AuditAetherMeshTerrain_UE58.py` and clear every `MISSING` item.
6. Save All.
7. Run `Content/Python/FinalizeAetherMeshTerrainMigration_UE58.py`.
8. Confirm only after the build has succeeded.
9. Close Unreal and run `BUILD_ME_FIRST.cmd` once more.
10. Open AetherWorld, press Play, then press `R` once.

The finalizer tags the Mesh Partition as `AetherProductionTerrain`, disables every
old Landscape proxy in editor/game, and disables its collision. The C++ runtime
guard then treats Mesh Terrain as the authored ground and keeps the fallback mesh
cleared.

## Roll back without losing work

Stop PIE and run:

`Content/Python/RestoreAetherLandscapeFallback_UE58.py`

This reactivates the production Landscape and moves Mesh Terrain back to preview.
No assets or actors are deleted.

## Expected result

- no overlapping Landscape or rectangular wall artifacts
- no top-down texture stretching on cliffs
- broad, non-repeating grass/forest/rock/scree/snow/sand/wetland transitions
- locally dense Nanite geometry at hero locations
- true caves, overhangs, and vertical formations where modifiers are added
- PCG/foliage masks available as Mesh Partition channels
- independent, simplified collision and World Partition streaming
