# Fresh `Heightmap_Out` landscape setup (UE 5.8)

This is the replacement landscape workflow for the clean project baseline at
commit `0cf2520`. It uses the supplied YouTube heightmap rather than the removed
4033 production landscape.

## What is included

- The untouched supplied file: `SourceAssets/VideoLandscape/Heightmaps/Heightmap_Out_Original_2048.png`
- A landscape-safe, centered 16-bit version: `Heightmap_Out_2017_16bit.png`
- Four normalized weightmaps: Grass, Rock, Scree, and Snow
- A UE 5.8 Python installer that rebuilds the tested multiscale PBR landscape material for 400 cm vertex spacing
- A finalizer that assigns the material and applies safe Landscape settings
- `VideoLandscape_Metadata.json`, including source checksum, conversion details, topology, and mask validation

The original is 2048x2048 RGBA with identical RGB channels. The processed file
is center-cropped—not resampled—to 2017x2017, converted to 16-bit grayscale, and
centered around Unreal Landscape's neutral height value. No interpolated height
detail is invented.

## 1. Pull and open the project

Close Unreal before pulling. From `C:\Projects\AetherFlight`:

```powershell
git switch agent/procedural-biomes
git pull --ff-only origin agent/procedural-biomes
```

Extract the supplied `AetherFlight_Fresh_Video_Landscape_Patch.zip` into
`C:\Projects\AetherFlight` and allow it to merge with the existing project
folder. It contains the processed heightmap and weightmaps; it does not delete
or replace unrelated project files.

Open `AetherFlight_Cinematic_v5_WITH_BUILD_FILES/AetherFlight.uproject`.

## 2. Build the material assets

In Unreal, use **Tools > Execute Python Script** and run:

`Content/Python/InstallFreshVideoLandscape.py`

Wait for the imported textures and shaders to finish. The script rebuilds and retunes:

`/Game/Aether/ProductionTerrain/M_Landscape_Production`

It also attempts to create these Weight-Blended Layer Info assets:

- `LI_Grass`
- `LI_Rock`
- `LI_Scree`
- `LI_Snow`

If this UE build does not expose the Layer Info factory to Python, create the
same four **Weight-Blended Layer** assets manually in Landscape Paint mode.

## 3. Import the supplied heightmap

Open `/Game/Maps/AetherWorld`, then enter **Landscape Mode > Manage > New**.
Choose **Import from File** and select:

`SourceAssets/VideoLandscape/Heightmaps/Heightmap_Out_2017_16bit.png`

Use these exact values:

| Setting | Value |
|---|---:|
| Section Size | 63 x 63 quads |
| Sections Per Component | 2 x 2 |
| Number of Components | 16 x 16 |
| Overall Resolution | 2017 x 2017 |
| Location | 0, 0, 0 |
| Scale X | 400 |
| Scale Y | 400 |
| Scale Z | 400 |
| Material | `M_Landscape_Production` |
| Enable Edit Layers | On |

This produces an approximately 8.064 km square landscape with approximately
602 m of total vertical relief. Do not select the untouched 2048 RGBA source
for the actual Landscape import.

## 4. Import the generated biome weights

Open **Landscape Mode > Paint**. For every layer, make sure its matching
Weight-Blended Layer Info is assigned. Right-click each layer, choose **Import
from File**, and select:

| Landscape layer | File |
|---|---|
| Grass | `SourceAssets/VideoLandscape/Weightmaps/Heightmap_Out_Grass_2017.png` |
| Rock | `SourceAssets/VideoLandscape/Weightmaps/Heightmap_Out_Rock_2017.png` |
| Scree | `SourceAssets/VideoLandscape/Weightmaps/Heightmap_Out_Scree_2017.png` |
| Snow | `SourceAssets/VideoLandscape/Weightmaps/Heightmap_Out_Snow_2017.png` |

The four weightmaps are normalized so every pixel sums to exactly 255. This
prevents unpainted black regions and unstable weight-blended results.

## 5. Finalize and validate

Use **Tools > Execute Python Script** and run:

`Content/Python/FinalizeFreshVideoLandscape.py`

Then:

1. Use **Landscape > Build Nanite Only** (the label can vary slightly).
2. Wait for shader compilation and Nanite building to finish.
3. Choose **Save All**.
4. Press Play in `AetherWorld` and verify the aircraft, runway, lighting,
   volumetric clouds, ocean, and terrain collision.

The project already points both its editor startup and game default map to
`/Game/Maps/AetherWorld`.

## 6. Save the generated Unreal assets

Close Unreal after Save All, then commit the generated `.uasset`, `.umap`, and
source PNG changes through Git LFS:

```powershell
git add -A
git commit -m "Build fresh Heightmap_Out landscape"
git pull --rebase origin agent/procedural-biomes
git push origin agent/procedural-biomes
```

## Recovery

The clean no-landscape state remains available at commit `0cf2520`. Never
reset or force-push while Unreal is open. If an import is wrong, close without
saving the map, reopen `AetherWorld`, and repeat the import using the exact
2017 settings above.
