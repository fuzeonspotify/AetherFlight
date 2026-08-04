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

- The spline was repaired into local coordinate space.
- Five control points form a roughly 1.17 km channel.
- The points use a controlled shallow downhill profile.
- Approximate channel depth is 6 m.
- Full-influence half-width is 14 m with 32 m falloff.
- Position deformation only; weight-channel output is deferred until riverbank material integration.
- Priority 40 builds it after the Stage 08 Texture Patch.
- The spline, bounds, and actor transform now move together.

## 10. Spline Remesh Modifier — COMPLETE

Actor: `Aether_VideoStage10_SplineRemesh`

- Reuses the repaired Stage 09 spline through a component reference.
- 60 m spline influence radius.
- 2.5 m target edge length.
- Two remesh iterations.
- Vertex smoothing disabled to preserve the authored channel profile.
- Priority 35 refines topology before Stage 09 deforms it at priority 40.
- The enabled/disabled Wireframe comparison was visually verified.
- No whole-world compiled Mesh Partition build was started.

## 11. Local river water integration — IMPLEMENTATION READY / NEXT INSTALL

Planned actors:

- `Aether_VideoStage11_River`
- `Aether_VideoStage11_WaterZone`

Repository support includes:

- `AUDIT_AETHER_MESH_TERRAIN_RIVER_API.ps1`
- `Content/Python/AuditAetherMeshTerrainRiverAPI_UE58.py`
- `INSTALL_AETHER_VIDEO_RIVER_STAGE.ps1`
- `Content/Python/InstallAetherVideoRiverStage_UE58.py`

The installer is audit-first and will:

- Create a native `WaterBodyRiver`.
- Copy the repaired five-point Stage 09 path into a separate `WaterSplineComponent`.
- Place the water surface approximately 3 m above the Stage 09 channel.
- Request a 20 m total river width, 3 m depth, and a gentle water velocity.
- Create a local 1.6 km `WaterZone` for water-mesh generation.
- Add the concrete Mesh Terrain river modifier exposed by UE 5.8.
- Assign it to the authoritative Mesh Partition at priority 50.
- Save `AetherWorld` without starting the compiled whole-world build.

## 12. Riverbank material and biome integration — NOT STARTED

After Stage 11 is visually verified:

- Write wetland, sand, gravel, or rock weight channels along the banks.
- Exclude dry ground cover from the water corridor.
- Add wet vegetation and riverbank rocks with a controlled local PCG pass.
- Keep the work local until water tiles, collision, and streaming are validated.

## 13. Expanded hydrology — DEFERRED

- Extend the verified local river into a lake, waterfall, or ocean connection.
- Ocean can remain independent because it does not need to terraform the terrain.
- Validate river-to-lake or river-to-ocean transition materials before expanding the system.

## 14. Conversion back to classic Landscape — DEFERRED

The tutorial demonstrates conversion workflows, but Aether should remain Mesh Terrain during production because caves, overhangs, local topology, and Boolean features are core goals. Conversion should only be tested on a duplicate map near the end of development.

## Current checkpoint

**AetherFlight matches the tutorial through the repaired and visually verified Spline Remesh stage. Stage 11 local river support is prepared. Run the Stage 11 launcher, inspect the WaterBodyRiver and WaterZone, Build To through its river modifier, then commit the resulting map/external-actor assets before beginning riverbank weight-channel and environment integration.**
