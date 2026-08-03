# Aether Flight cinematic graphics setup

The graphics overhaul is active in code immediately after rebuilding. One editor-side install step creates the PBR materials because Unreal binary `.uasset` files cannot be authored outside Unreal Editor.

## Required one-time step

1. Close Unreal Editor and run `Build_AetherFlight.bat`.
2. Open the project and wait for shader compilation to finish.
3. Choose **Tools → Execute Python Script**.
4. Run `Content\Python\InstallCinematicMaterials.py`.
5. Press **Play**. If Play was already running, stop and restart it.

The material installer is safe to run again. Existing terrain and runway materials are preserved, while the generated ocean material is rebuilt so a previously broken version is repaired in place.

The script creates these assets:

- `/Game/Aether/Materials/M_Terrain_Cinematic`
- `/Game/Aether/Materials/M_Ocean_Cinematic`
- `/Game/Aether/Materials/M_Runway_Cinematic`
- `/Game/Aether/Materials/M_RunwayMarkings_Cinematic`

## Unreal quality setting

Use **Settings → Engine Scalability Settings → Epic** while playing. Use **Cinematic** only for screenshots or Movie Render Queue; its cloud, fog, shadow, Lumen, and reflection sample budgets are intentionally expensive.

At 1440p, Epic is intended for a modern upper-midrange GPU. If frame rate is poor, reduce **Effects** first (volumetric clouds/fog), then **Shadows**. Do not lower textures first; the included aircraft uses 4K maps and loses surface definition quickly.

## Optional free environment assets

The world now has deterministic high-density HISM scatter hooks. Import one Nanite-capable conifer and one rock/cliff mesh, then place/rename them exactly as follows:

| Type | Required Unreal asset path |
|---|---|
| Tree | `/Game/Aether/Environment/Foliage/SM_Conifer` |
| Rock | `/Game/Aether/Environment/Rocks/SM_CliffRock` |

On the next Play, the generator distributes up to 6,500 trees and 1,800 rocks by altitude, slope, moisture, and runway exclusion. Missing assets are simply skipped—there are no placeholder blocks.

For best results, choose photogrammetry or high-quality scanned assets with base color, normal, and packed roughness/AO maps. Enable Nanite on the rock. For the tree, use a mesh with sensible LODs and masked leaf materials; Nanite foliage works only when its source geometry and material are suitable.

## What changed

- 64 independently generated terrain tiles, roughly 524,000 triangles total, with continuous sampled normals.
- Slope-, altitude-, and noise-aware sand, grass, alpine, exposed-rock, cliff, and snow coloration.
- PBR roughness/specular materials for terrain, ocean, runway, and markings.
- Higher-quality volumetric cloud tracing, cloud shadows, aerial perspective, fog, Lumen, virtual shadow maps, and reflections.
- Restrained exposure, bloom, flare, contrast, saturation, and physically focused cinematic depth of field.
- Epic and Cinematic scalability profiles, with a clean 100% screen-percentage baseline.

## Honest remaining gap

The project now has a cinematic rendering foundation, but procedural vertex color alone cannot equal a scanned real location. The biggest remaining leap will come from free licensed surface assets: landscape material layers (rock/soil/grass/snow), a production water material, vegetation, cliff meshes, and one hand-dressed hero airbase/fjord. The hooks above make the first vegetation/rock pass automatic once those assets are present.
