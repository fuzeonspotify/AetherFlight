# AetherFlight — Full Mesh Terrain Tutorial Roadmap

Source tutorial: Unreal Sensei, **How to Use Unreal Engine's New Landscape System — Mesh Terrain Tutorial** (`Lhj2LutYNjA`).

This roadmap follows the tutorial as a complete workflow and separates tutorial-native Mesh Terrain work from AetherFlight's custom production systems.

## 1. Project and Mesh Terrain setup — COMPLETE

- UE 5.8 Mesh Partition and Mesh Terrain plugins enabled.
- Open World / World Partition map in use.
- Aether's authoritative Mesh Partition root exists.
- `MPD_AetherWorld` is assigned.
- Legacy Landscape actors were removed.

## 2. Create or import the terrain base — COMPLETE

- Production 16-bit PNG heightmap imported.
- 4032 × 4032 quads.
- 48 km × 48 km world footprint.
- Automatic section generation with a 524,288-triangle cap.
- Save and Unload enabled.
- Compiled Mesh Partition streams and collides in Play.

## 3. Mesh Terrain material and displacement — COMPLETE

- Sensei terrain material integrated.
- Aether-owned material instances created.
- Biome texture parameters tuned.
- Unsafe displacement paths disabled where necessary for renderer stability.
- Weight-channel textures exist for grass, forest floor, rock, sand, scree, snow, and wetland.

## 4. Foliage and environmental assets — COMPLETE CUSTOM EXTENSION

This is outside the tutorial's modifier sequence, but the infrastructure is production-ready:

- DZ Pine, Aspen, Cork Oak, and Coconut/Palm.
- GV Shrub A and Shrub B.
- Nanite Acer trees, Abelia shrubs, Lolium grass, and Ophiopogon ground cover.
- All seven Environment — Rock Collection 04 meshes.
- Persistent HISM streaming, local diversity floor, and runtime audits.

## 5. Local topology control with Remesh/Tessellate — COMPLETE

Actor: `Aether_VideoStage05_LocalRemesh`

- A non-destructive 1.2 km local Remesh zone was installed away from the flight spawn.
- Target edge length was reduced to approximately 6 m locally.
- The rest of the 48 km world remains at the imported base resolution.
- Rock Collection 04 markers identify the test area.
- The compiled whole-world Mesh Partition build was not started.

## 6. Sculpt and paint modifiers — COMPLETE

Actor: `Aether_VideoStage06_SculptPaint`

- A 900 m × 900 m Brush/ProjectMeshLayers modifier was placed inside Stage 05.
- Terrain sculpting was performed.
- Texture painting and material-layer painting were completed.
- Painted channels remain available for terrain material and later biome control.

## 7. Static Mesh and Boolean modifiers — COMPLETE

Actor: `Aether_VideoStage07_BooleanCave`

- A subtractive static-mesh Boolean cave/tunnel was installed.
- The cutter remains inside the verified local Remesh zone.
- Bounds expansion, edge simplification, and shared-edge welding are configured.
- The cave stage was inspected and retained.

## 8. Texture modifiers and adaptive tessellation — COMPLETE

Actor: `Aether_VideoStage08_TexturePatch`

- A local 240 m Texture Patch uses `T_MT_Rock_Weight`.
- Height encoding scale is 18 m with a neutral value of 0.5.
- Adaptive tessellation is requested where exposed by UE 5.8.
- The stage was built, inspected, and committed.

## 9. Regular Spline Modifier — COMPLETE

Actor: `Aether_VideoStage09_SplineChannel`

- A roughly 900 m lowered terrain channel was installed inside Stage 05.
- Five spline control points shape the channel.
- Approximate channel depth is 6 m.
- Full-influence half-width is 14 m with 32 m falloff.
- Position deformation only; weight-channel output is deferred until water/biome integration.
- Priority 40 builds it after the Stage 08 Texture Patch.
- The resulting map and external actor were committed.

## 10. Spline Remesh Modifier — IMPLEMENTATION READY / NEXT INSTALL

Planned actor: `Aether_VideoStage10_SplineRemesh`

Repository support now includes:

- `AUDIT_AETHER_SPLINE_REMESH_API.ps1`
- `Content/Python/AuditAetherSplineRemeshModifierAPI_UE58.py`
- `INSTALL_AETHER_VIDEO_SPLINE_REMESH_STAGE.ps1`
- `Content/Python/InstallAetherVideoSplineRemeshStage_UE58.py`

The installer reuses Stage 09's saved spline and adds local topology only along the channel:

- 60 m spline influence radius.
- 2.5 m target edge length.
- Two remesh iterations.
- Vertex smoothing disabled to preserve the authored channel profile.
- UV resampling enabled.
- Priority 35, so topology is refined before Stage 09 deforms it at priority 40.
- No whole-world compiled Mesh Partition build is started.

## 11. Water-body integration — PREPARED, NOT TERRAIN-INTEGRATED

After Stage 10 is visually verified:

- Add a WaterBodyRiver and corresponding Mesh Terrain RiverModifier.
- Reuse the Stage 09 channel as the first controlled riverbed test.
- Configure wetland or rock weight-channel output only after the banks are stable.
- Keep the river local until preview, collision, and compiled-section behavior are validated.
- Ocean can remain independent because it does not need to terraform the terrain.

## 12. Conversion back to classic Landscape — DEFERRED

The tutorial demonstrates conversion workflows, but Aether should remain Mesh Terrain during production because caves, overhangs, local topology, and Boolean features are core goals. Conversion should only be tested on a duplicate map near the end of development.

## Current checkpoint

**AetherFlight matches the tutorial through the regular Spline Modifier stage. Stage 10 Spline Remesh code is now prepared. Run the Stage 10 launcher, compare the channel with the remesh disabled/enabled in Build To, then commit the resulting map/external-actor assets before beginning water-body integration.**
