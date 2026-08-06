# Aether Terrain V2 — UE 5.8 Mesh Terrain

Aether Terrain V2 applies the useful parts of the Sensei Terrain workflow without assigning the Sensei master material directly to `MPD_AetherWorld`.

## What V2 changes

- Creates `/Game/Aether/MeshTerrain/M_MeshTerrain_Aether_V2`.
- Preserves `/Game/Aether/MeshTerrain/M_MeshTerrain_Aether` as the rollback material.
- Keeps terrain geometry unchanged.
- Uses triplanar projection for Grass, ForestFloor, Rock, Scree, and Snow.
- Uses planar projection for Sand and Wetland because those biomes are expected on flatter ground.
- Adds near and far macro variation to reduce repetition from flight altitude.
- Repairs the MPD channel order when UE exposes the channel map to Python:
  1. Grass
  2. ForestFloor
  3. Rock
  4. Scree
  5. Snow
  6. Sand
  7. Wetland
  8. Water
  9. Forest
  10. FoliageExclusion
- Reads the first seven weight channels in the material when the UE 5.8 Mesh Partition material expressions are exposed.
- Leaves automatic slope/height biome blending active when weight channels contain no painted data.
- Uses no displacement, tessellation, or World Position Offset.

## Apply

Close Unreal Editor, pull the branch, build the C++ project, and then run:

```powershell
Set-Location "C:\Projects\AetherFlight"
Set-ExecutionPolicy -Scope Process Bypass
.\APPLY_AETHER_TERRAIN_V2.ps1
```

Wait for the `Aether Terrain V2 Installed` dialog.

Then:

1. Open `/Game/Maps/AetherWorld`.
2. Save All.
3. Close and reopen `AetherWorld`.
4. Test Play mode.
5. Confirm the aircraft starts near 20,000 feet and waits briefly for the initial streaming area.
6. Confirm terrain geometry is unchanged and nearby sections load before flight begins.

Do not immediately rebuild Mesh Partition. Rebuild it once only when streamed sections continue using the previous material after reopening the map.

## Roll back

Run this from Unreal's Output Log while Play mode is stopped:

```text
py import unreal; p=unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()+"Python/RestoreAetherMeshTerrainMaterial_UE58.py"); f=open(p,"r",encoding="utf-8"); code=f.read(); f.close(); exec(compile(code,p,"exec"))
```

This restores `M_MeshTerrain_Aether` to `MPD_AetherWorld`.

## Expected result

- Same mountain silhouettes and collision.
- Cleaner cliff projection.
- More distinct grass, rock, scree, forest-floor, and snow regions.
- Less obvious repetition at 20,000 feet.
- Future paint and modifier work can override automatic biomes through Mesh Partition weight channels.
- No giant displacement walls or missing terrain caused by the Sensei master material.
