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

- Production heightmap imported at 4032 × 4032 quads.
- 48 km × 48 km world footprint.
- Automatic section generation with a 524,288-triangle cap.
- Save and Unload enabled.
- Compiled Mesh Partition streams and collides in Play.

## 3. Mesh Terrain material and displacement — COMPLETE

- Sensei terrain material integrated through Aether-owned material instances.
- Biome texture parameters tuned.
- Unsafe displacement paths disabled where necessary for renderer stability.
- Weight channels exist for grass, forest floor, rock, sand, scree, snow, wetland, water, forest, and foliage exclusion.

## 4. Foliage and environmental assets — COMPLETE CUSTOM EXTENSION

- DZ Pine, Aspen, Cork Oak, and Coconut/Palm.
- GV Shrub A and Shrub B.
- Nanite Acer trees, Abelia shrubs, Lolium grass, and Ophiopogon ground cover.
- All seven Environment — Rock Collection 04 meshes.
- Persistent HISM streaming, local diversity floor, and runtime audits.

## 5. Local topology control with Remesh/Tessellate — COMPLETE

Actor: `Aether_VideoStage05_LocalRemesh`

- Non-destructive 1.2 km local Remesh zone.
- Approximately 6 m local target edge length.
- The rest of the 48 km world remains at imported base resolution.
- No whole-world compiled Mesh Partition build was started.

## 6. Sculpt and paint modifiers — COMPLETE

Actor: `Aether_VideoStage06_SculptPaint`

- 900 m × 900 m Brush/ProjectMeshLayers workspace.
- Terrain sculpting, texture painting, and material-layer painting completed.

## 7. Static Mesh and Boolean modifiers — COMPLETE

Actor: `Aether_VideoStage07_BooleanCave`

- Subtractive static-mesh cave/tunnel installed inside the verified Remesh zone.
- Bounds expansion, edge simplification, and shared-edge welding configured.

## 8. Texture modifiers and adaptive tessellation — COMPLETE

Actor: `Aether_VideoStage08_TexturePatch`

- Local 240 m Texture Patch using `T_MT_Rock_Weight`.
- Height encoding scale of 18 m with neutral value 0.5.
- Stage built, inspected, and committed.

## 9. Regular Spline Modifier — COMPLETE

Actor: `Aether_VideoStage09_SplineChannel`

- Five repaired local-space control points form a roughly 1.17 km channel.
- Controlled shallow downhill profile.
- Approximate channel depth 6 m.
- Full-influence half-width 14 m with 32 m falloff.
- Position deformation only at priority 40.

## 10. Spline Remesh Modifier — COMPLETE

Actor: `Aether_VideoStage10_SplineRemesh`

- Reuses the repaired Stage 09 spline through a component reference.
- 60 m influence radius, 2.5 m target edge length, and two remesh iterations.
- Vertex smoothing disabled.
- Priority 35 refines topology before Stage 09 deformation.
- Enabled/disabled wireframe comparison visually verified.

## 11. Local river water integration — COMPLETE

Actors:

- `Aether_VideoStage11_River`
- `Aether_VideoStage11_WaterZone`

Completed configuration:

- Native `WaterBodyRiver` follows a separate copy of the repaired five-point Stage 09 path.
- Visible water mesh confirmed after an editor-side spline refresh.
- Water surface approximately 3 m above the Stage 09 channel centerline.
- Requested total width approximately 20 m through spline-point scaling.
- UE 5.8 preserved its 1.5 m engine-default depth metadata because the default struct is `EditDefaultsOnly`.
- Local Water Zone extent 1.6 km.
- Native `RiverModifier` assigned at priority 50.
- Map and external actors committed in `b3a46e7bd24cd7fd947faf23ac890faa141fc9ff`.

## 12. Riverbank wetland weight integration — COMPLETE

Actor: `Aether_VideoStage12_RiverbankWetland`

- Separate five-point spline copied from Stage 09.
- Writes only the `Wetland` channel with Alpha Blend and value 1.0.
- `write_mode = 2`, so terrain positions cannot be changed.
- 14 m full influence and 32 m falloff.
- Priority 55.
- Map and external actor committed in `5b121fbf40ea04c7b5a55241d52171dd5f360131`.

## 13. River environment integration — IMPLEMENTATION READY / NEXT INSTALL

Planned actors:

- `Aether_VideoStage13_RiverExclusion`
- `Aether_VideoStage13_RiverEnvironment`

Repository support includes:

- `AUDIT_AETHER_RIVER_ENVIRONMENT_API.ps1`
- `Content/Python/AuditAetherRiverEnvironmentAPI_UE58.py`
- `INSTALL_AETHER_VIDEO_RIVER_ENVIRONMENT_STAGE.ps1`
- `Content/Python/AetherRiverEnvironmentCommon_UE58.py`
- `Content/Python/AetherRiverEnvironmentPlacement_UE58.py`
- `Content/Python/InstallAetherVideoRiverEnvironmentStage_UE58.py`

The audit-first installer will:

- Verify all saved Stage 09–12 dependencies.
- Verify `MPD_AetherWorld` contains `FoliageExclusion`.
- Clone the repaired five-point Stage 09 spline into a separate Stage 13 exclusion actor.
- Write only `FoliageExclusion` with `write_mode = 2` at priority 56.
- Use a 14 m full-exclusion corridor and 24 m falloff.
- Discover installed riverbank rock, shrub, and ground-cover static meshes.
- Create a deterministic local HISM environment actor along both banks.
- Keep generated instances outside the full water-exclusion corridor.
- Use terrain traces when available and a controlled channel-height fallback when unattended Mesh Terrain traces are unavailable.
- Keep environment collision disabled until Stage 14 runtime validation.
- Save `AetherWorld` without starting a compiled whole-world build.

## 14. Water polish and runtime validation — NOT STARTED

- Tune flow speed and river appearance.
- Add foam around rocks or sharper banks where useful.
- Validate collision and interaction.
- Confirm Water Zone, river, exclusion, and environment actors remain visible during World Partition streaming.
- Run local compiled-section validation only after the editor preview is stable.

## 15. Expanded hydrology — DEFERRED

- Extend the verified river into a lake, waterfall, or ocean connection.
- Validate transition materials before expansion.

## 16. Conversion back to classic Landscape — DEFERRED

Aether remains Mesh Terrain during production because caves, overhangs, local topology, and Boolean features are core goals. Conversion should only be tested on a duplicate map near the end of development.

## Current checkpoint

**AetherFlight is complete through the committed Stage 12 wetland bank modifier. Stage 13 river environment support is prepared. Run `INSTALL_AETHER_VIDEO_RIVER_ENVIRONMENT_STAGE.ps1`, inspect the priority-56 exclusion modifier and deterministic HISM riverbank actor, then commit the resulting map and external actors before beginning Stage 14 runtime validation.**
