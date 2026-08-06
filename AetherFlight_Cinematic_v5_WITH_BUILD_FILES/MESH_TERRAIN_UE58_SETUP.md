# Aether Flight — Clean UE 5.8 Mesh Terrain Build

This is the only supported terrain workflow for AetherFlight. It follows the
non-destructive UE 5.8 Mesh Terrain workflow demonstrated in Unreal Sensei's
**How to Use Unreal Engine's New Landscape System — Mesh Terrain Tutorial**.

The old classic Landscape migration is retired. The reset removes every current
Landscape and Mesh Partition actor from `/Game/Maps/AetherWorld`, deletes generated
Mesh Terrain assets, and recreates one clean authoring stack. It preserves the
aircraft, runway, HUD, controls, weather, water actors, source heightmaps,
weightmaps, and reusable terrain textures.

Mesh Terrain is experimental in UE 5.8. Build and save often.

## 1. Run the clean reset

Close Unreal Editor. From the project folder, run:

```powershell
.\RESET_AETHER_TERRAIN_UE58.ps1
```

The script performs these operations:

1. Builds `AetherFlightEditor`.
2. Opens `AetherWorld` through Unreal's Python command-line support.
3. Deletes all classic Landscape actors, Landscape streaming proxies, Mesh
   Partition roots, generated sections, and Mesh Terrain modifiers.
4. Deletes `/Game/Aether/MeshTerrain` and old Landscape-only generated assets.
5. Preserves `/Game/Aether/ProductionTerrain/Textures` for the new material.
6. Recreates the clean material, MPD, three pipeline shells, channels, and masks.
7. Reopens `AetherWorld`.

Successful runs create:

- `Saved/AetherTerrainReset.txt`
- `Saved/AetherMeshTerrainInstall.txt`

## 2. Fill the transformer pipelines

UE 5.8 exposes transformer arrays as `TInstancedStruct`. Unreal Python cannot
reliably author those entries, so this remains a one-time Details-panel step.

### `TP_Preview_AetherWorld`

Add in this order:

1. **Subsection Transformer** — `Sub Section Size = 65536 cm`
2. **Static Mesh Transformer** — enable **Nanite** and **Skirts**
3. **Collision Transformer** — `Error Tolerance = 100 cm`
4. **WP Actor Properties Transformer** — leave Runtime Grid as `None` when no
   named runtime grid is offered; World Partition will choose the map default

### `TP_Compiled_HighEnd_AetherWorld`

Add in this order:

1. **Far Field Transformer** — `Far Field Mesh Edge Length = 10000 cm`
2. **Subsection Transformer** — `Sub Section Size = 65536 cm`
3. **Static Mesh Transformer** — enable **Nanite** and **Skirts**
4. **WP Actor Properties Transformer** — map default grid is acceptable

Use **Derive Screen Size from Error**, `Pixel Error = 8`:

| LOD | Error tolerance | Maximum triangle fraction |
|---|---:|---:|
| 0 | source geometry | `1.00` |
| 1 | `4 cm` | `0.50` |
| 2 | `16 cm` | `0.25` |
| 3 | `64 cm` | `0.10` |

### `TP_Compiled_Common_AetherWorld`

Add in this order:

1. **Subsection Transformer** — `Sub Section Size = 65536 cm`
2. **Collision Transformer** — `Error Tolerance = 100 cm`
3. **WP Actor Properties Transformer** — map default grid is acceptable

Do not add the deprecated Mesh Skirt Transformer. Enable skirts inside the
Static Mesh Transformer.

## 3. Verify `MPD_AetherWorld`

Open `/Game/Aether/MeshTerrain/MPD_AetherWorld` and set:

- Material: `M_MeshTerrain_Aether`
- Channel Texel Size: `400 cm`
- Material Cache Texel Size: `800 cm`
- Channel UV Layout Method: **Plane Project**
- Modifier priorities: `Base`, `Erosion`, `Hydrology`, `LocalDetail`, `Paint`

Channels, in order:

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

Preview section:

- Max Section Complexity: `250000`
- Pipeline: `TP_Preview_AetherWorld`

Compiled variants:

| Variant | Max complexity | Pipeline |
|---|---:|---|
| `HighEnd` | `250000` | `TP_Compiled_HighEnd_AetherWorld` |
| `Common` | `250000` | `TP_Compiled_Common_AetherWorld` |

Under **Platforms > Default > Build Variant Names**, add `HighEnd` and `Common`.

## 4. Import the clean production heightmap

Open `/Game/Maps/AetherWorld`, then switch to **Mesh Terrain** mode.

Choose **Create > Import Heightmap** and select:

```text
SourceAssets/ProductionTerrain/Heightmaps/AetherFlight_4033_16bit.png
```

Do not use or rename `AetherFlight_4033.r16`. The UE 5.8 Mesh Terrain importer
requires the 16-bit PNG in this project.

Use:

| Setting | Value |
|---|---:|
| Resolution when labeled **quads** | `4032 x 4032` |
| Resolution when labeled **samples/vertices** | `4033 x 4033` |
| Size X | `4,800,000 cm` |
| Size Y | `4,800,000 cm` |
| Size Z | `560,000 cm` |
| Sections | explicit `32 x 32` |
| Per-section resolution | `126 x 126` quads / `127 x 127` vertices |
| Save and Unload | enabled |
| Definition | `MPD_AetherWorld` |

The source has 4033 samples and therefore 4032 quads. The 48 km world size is
`48,000 m × 100 = 4,800,000 cm`.

Rename the new root actor:

```text
MeshTerrain_AetherWorld
```

The heightmap encodes sea level at 32768 across a `-2800 m` to `+2800 m` range.
The coastline should meet the ocean near world `Z = 0`. If the importer maps the
minimum height to zero instead of centering the range, set the root actor's
Location Z to `-280000 cm`. Do not change X/Y scale after import.

## 5. Build the non-destructive modifier stack

Open **Tools > Mesh Partition Settings**. This stack follows the video workflow:

### `Base`

- Imported 4033-sample heightmap only
- Never destructively edit or globally remesh the base

### `Erosion`

- Broad Noise or Texture modifiers for mountain breakup and erosion
- Keep these low frequency across the 48 km world

### `Hydrology`

- River and Lake Mesh Partition Water modifiers
- Spline modifiers for riverbeds, shorelines, and drainage cuts
- Ocean needs no terrain deformation modifier

### `LocalDetail`

- Add a local Remesh or Spline Remesh modifier before detailed sculpting
- Use Sculpt/Brush modifiers for airbase grading, hero valleys, cliffs, and
  shoreline corrections
- Use Static Mesh or Boolean modifiers for caves, arches, overhangs, and tunnels
- Never remesh the entire 48 km terrain to cinematic density

### `Paint`

- Paint biome channels for art direction and cleanup
- Project the imported masks from `/Game/Aether/MeshTerrain/Weightmaps`
- Use `FoliageExclusion` around the runway, taxiways, buildings, roads, and caves

`M_MeshTerrain_Aether` provides automatic height/slope biome selection,
world-space triplanar projection for cliffs, and kilometer-scale breakup. The
paint channels are used to refine that automatic result and to drive PCG.

## 6. Build and activate the runtime terrain

1. Choose **Build > Build Mesh Partition**.
2. Wait for Mesh Partition, Nanite, collision, and shader work to finish.
3. In the Outliner, enable **Show Build Mesh Partition Sections**.
4. Verify section seams, collision, coastline, and close-range cliff detail.
5. Run:
   `Content/Python/AuditAetherMeshTerrainClean_UE58.py`
6. Resolve every `MISSING` or `FAIL` entry.
7. Run:
   `Content/Python/ActivateAetherMeshTerrain_UE58.py`
8. Save All.
9. Close Unreal and run `BUILD_ME_FIRST.cmd` once more.
10. Open `AetherWorld` and press Play.

The activation script refuses to continue when a classic Landscape remains or
when more than one Mesh Partition root exists. It tags the single clean root as
`AetherProductionTerrain`, which the runtime director recognizes while keeping
the old procedural fallback cleared.

## 7. Acceptance checks

Before adding vegetation or detailed water work, verify:

- zero classic Landscape actors in `AetherWorld`
- exactly one root named `MeshTerrain_AetherWorld`
- no duplicate/overlapping terrain in PIE
- coastline near `Z = 0`
- generated sections have Nanite enabled
- collision works at the runway and mountain slopes
- no visible cracks between generated sections
- PIE starts after the Mesh Partition build completes
- distant sections stream through World Partition
- triplanar material does not stretch on vertical cliffs

Only after these pass should PCG foliage, rocks, roads, rivers, caves, and airbase
set dressing be added.
