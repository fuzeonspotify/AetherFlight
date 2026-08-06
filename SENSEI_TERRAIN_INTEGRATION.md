# AetherFlight Sensei Terrain Integration

This integration uses the UE 5.8 Sensei Terrain master material as an optional
high-quality visual layer while preserving AetherFlight's existing Mesh Terrain
root, `MPD_AetherWorld`, transformer pipelines, channels, and original
`M_MeshTerrain_Aether` rollback material.

## Why the binary assets are not committed

The AetherFlight repository is public. Unreal Sensei distributes these assets
for use in your own projects, but its published terms do not grant permission
to republish the downloadable source assets in a public repository. The
third-party `.uasset` files therefore remain local and are installed from the
ZIP you downloaded directly from Unreal Sensei.

## One-command local installation

Close Unreal Editor, open PowerShell in the repository root, and run:

```powershell
.\INSTALL_SENSEI_TERRAIN_ASSETS.ps1
```

The installer automatically finds the newest `*SenseiTerrain*.zip` in:

- `SourceAssets\ThirdParty`
- your Windows Downloads folder
- the repository root

You can also pass the ZIP path directly:

```powershell
.\INSTALL_SENSEI_TERRAIN_ASSETS.ps1 "C:\path\to\SenseiTerrainEA.zip"
```

The script copies only:

- `M_SenseiTerrain`
- the 14 material functions it depends on
- the 4 Sensei utility textures

It deliberately skips the supplied project config, example maps, example
external actors, `MPD_SenseiTerrain`, preview pipeline, and patches. It then
launches UE 5.8 with `IntegrateSenseiTerrain_Aether_UE58.py`.

## Aether material mapping

The generated `MI_AetherTerrain_Sensei` instance maps Aether textures as:

- A: Grass
- B: Rock
- C: Scree
- D: Forest floor
- E: Snow

The integration enables the Sensei material layers, slope auto-blending,
triplanar projection, color variation, and normal variation. Sand, wetland,
water, forest, and foliage-exclusion channels remain in `MPD_AetherWorld` for
later Aether-specific material and PCG work.

## Final editor step

After the integration dialog appears:

1. Open `/Game/Maps/AetherWorld`.
2. Use **Build > Build Mesh Partition**.
3. Save the current level, then **Save All**.
4. Test in Play mode.

## Rollback

Run this from Unreal's Output Log:

```text
py exec(open(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir() + "Python/RestoreAetherMeshTerrainMaterial_UE58.py")).read())
```

Then rebuild Mesh Partition sections.
