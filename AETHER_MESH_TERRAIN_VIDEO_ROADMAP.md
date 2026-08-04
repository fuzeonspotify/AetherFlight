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
- `MPD_AetherWorld` defines `Grass`, `ForestFloor`, `Rock`, `Scree`, `Snow`, `Sand`, `Wetland`, `Water`, `Forest`, and `FoliageExclusion` channels.

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
- Position deformation only; weight-channel output was deferred to Stage 12.
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

## 11. Local river water integration — COMPLETE

Actors:

- `Aether_VideoStage11_River`
- `Aether_VideoStage11_WaterZone`

Completed configuration:

- Native `WaterBodyRiver` follows a separate copy of the repaired five-point Stage 09 path.
- Visible water mesh was confirmed after one editor-side spline refresh.
- Water surface sits approximately 3 m above the Stage 09 channel centerline.
- Requested width is approximately 20 m total through spline-point scaling.
- UE 5.8 preserved its 1.5 m engine-default depth metadata because the default struct is `EditDefaultsOnly`.
- Local Water Zone extent is 1.6 km.
- Native `RiverModifier` is assigned to the authoritative Mesh Partition at priority 50.
- Map and external actors were committed in `b3a46e7bd24cd7fd947faf23ac890faa141fc9ff`.
- No whole-world compiled Mesh Partition build was started.

## 12. Riverbank wetland weight integration — IMPLEMENTATION READY / NEXT INSTALL

Planned actor:

- `Aether_VideoStage12_RiverbankWetland`

Repository support includes:

- `AUDIT_AETHER_RIVERBANK_WEIGHT_API.ps1`
- `Content/Python/AuditAetherRiverbankWeightAPI_UE58.py`
- `INSTALL_AETHER_VIDEO_RIVERBANK_STAGE.ps1`
- `Content/Python/InstallAetherVideoRiverbankStage_UE58.py`

The audit-first installer will:

- Verify all saved Stage 09–11 dependencies.
- Verify `MPD_AetherWorld` contains the channel named `Wetland`.
- Verify UE 5.8 exposes `SplineModifierWeightEntry` and the required channel/blend fields.
- Clone the repaired five-point Stage 09 spline into a separate Stage 12 actor.
- Set `write_mode = 2`, which is **Weights only**; terrain positions cannot be changed by Stage 12.
- Write one `Wetland` channel entry using Alpha Blend and a target weight of 1.0 where exposed.
- Use a 14 m full-influence half-width and 32 m outer falloff.
- Assign the modifier to the authoritative Mesh Partition at priority 55.
- Save `AetherWorld` without starting the compiled whole-world build.

## 13. River environment integration — NOT STARTED

After Stage 12 is visually verified:

- Exclude grass and dry ground cover near the water corridor.
- Add wet vegetation outside the water surface.
- Add controlled riverbank rocks.
- Prevent foliage from spawning inside the river.
- Keep the pass local until collision and World Partition streaming are validated.

## 14. Water polish and runtime validation — NOT STARTED

- Tune flow speed and river appearance.
- Add foam around rocks or sharper banks where useful.
- Validate collision and interaction.
- Confirm the Water Zone and river remain visible during World Partition streaming.
- Run a local compiled-section validation only after the editor preview is stable.

## 15. Expanded hydrology — DEFERRED

- Extend the verified local river into a lake, waterfall, or ocean connection.
- Ocean can remain independent because it does not need to terraform the terrain.
- Validate river-to-lake or river-to-ocean transition materials before expansion.

## 16. Conversion back to classic Landscape — DEFERRED

The tutorial demonstrates conversion workflows, but Aether should remain Mesh Terrain during production because caves, overhangs, local topology, and Boolean features are core goals. Conversion should only be tested on a duplicate map near the end of development.

## Current checkpoint

**AetherFlight matches the tutorial through a visually verified local WaterBodyRiver. Stage 12 riverbank wetland support is prepared. Run `INSTALL_AETHER_VIDEO_RIVERBANK_STAGE.ps1`, inspect `Aether_VideoStage12_RiverbankWetland`, Build To through priority 55, and compare it disabled/enabled before committing the resulting map and external actor.**
