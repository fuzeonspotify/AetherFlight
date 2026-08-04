# AetherFlight — Full Mesh Terrain Tutorial Roadmap

Source tutorial: Unreal Sensei, **How to Use Unreal Engine's New Landscape System — Mesh Terrain Tutorial** (`Lhj2LutYNjA`).

This roadmap follows the tutorial as a complete workflow rather than starting from the shared timestamp. It also separates tutorial-native Mesh Terrain work from AetherFlight's custom production systems.

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

This is not the tutorial's modifier workflow, but it is now production-ready infrastructure:

- DZ Pine, Aspen, Cork Oak, and Coconut/Palm.
- GV Shrub A and Shrub B.
- Nanite Acer trees, Abelia shrubs, Lolium grass, and Ophiopogon ground cover.
- All seven Environment — Rock Collection 04 meshes.
- Persistent HISM streaming, local diversity floor, and runtime audits.

## 5. Local topology control with Remesh/Tessellate — NEXT

The tutorial's next missing foundation is local resolution control. Aether currently relies on the imported base resolution everywhere.

Planned first feature:

- Create a small non-destructive local Remesh modifier zone away from the flight spawn.
- Increase topology only around a dedicated terrain-feature test site.
- Keep the rest of the 48 km world at its current base resolution.
- Validate editor preview build time before any compiled Mesh Partition rebuild.

## 6. Sculpt and paint modifiers — NOT STARTED

After local topology is validated:

- Add a Sculpt modifier over the local test site.
- Test height sculpting without altering the imported base terrain.
- Paint existing Aether weight channels inside the modifier.
- Use the painted channels later for material and foliage control.

## 7. Static Mesh and Boolean modifiers — NOT STARTED

After Remesh/Sculpt validation:

- Use a simple Boolean tool mesh to create a controlled cave or sinkhole.
- Use Rock Collection 04 around the opening for a natural entrance and overhang.
- Test `Trim`, operator-bound expansion, collision, preview build, and compiled build.
- Keep the feature in a small isolated section until stable.

## 8. Texture modifiers and adaptive tessellation — NOT STARTED

- Reuse Aether height/weight textures for local erosion or displacement patches.
- Test adaptive tessellation only in a limited region.
- Avoid applying a high-frequency texture modifier to the complete 48 km terrain.

## 9. Spline and spline-remesh modifiers — NOT STARTED

- Create one terrain channel or valley path.
- Add local spline remeshing before deformation.
- Use weight-channel output for wetland, rock, or ground-cover transitions.
- Later connect this to water or route systems only after the terrain spline is stable.

## 10. Water-body integration — PREPARED, NOT TERRAIN-INTEGRATED

- Hydrology and ocean support files exist.
- Mesh Terrain Lake/River modifiers are not yet installed on the production terrain.
- Ocean can remain independent because it does not need to terraform the terrain.

## 11. Conversion back to classic Landscape — DEFERRED

The tutorial demonstrates conversion workflows, but Aether should remain Mesh Terrain during production because caves, overhangs, local topology, and Boolean features are core goals. Conversion should only be tested on a duplicate map near the end of development.

## Current checkpoint

**Tutorial foundation complete through terrain creation, partitioning, and material setup. Custom foliage and rocks are complete. The next genuine tutorial-native feature is a small local Remesh/Tessellate modifier zone, followed by Sculpt/Paint and then a Boolean cave feature.**
