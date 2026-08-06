# AetherFlight Procedural Biomes

This adds a data-driven biome population system without replacing the working
AetherWorld Landscape, flight code, weather, or terrain material.

## Fast setup

1. Build the C++ project with `BUILD_ME_FIRST.cmd` or `Build_AetherFlight.bat`.
2. Open Unreal Editor and load `/Game/Maps/AetherWorld`.
3. Run:

   `Content/Python/InstallProceduralBiomes.py`

   In Unreal, use **Tools > Execute Python Script** and select that file.
4. The script creates or reuses an actor named **Aether Procedural Biomes**,
   discovers suitable Static Mesh assets, fills four biome profiles, builds the
   instances, and saves the open level.

When no vegetation or rock meshes exist in `/Game`, the actor is still
installed. Add Fab/Megascans assets and run the installer again.

## Included biome profiles

- **Meadow** — low, warm, relatively flat ground; intended for grass, shrubs,
  flowers, and ground cover.
- **EvergreenForest** — moist low-to-mid elevations; intended for tree variants.
- **RockyHighlands** — exposed mid/high terrain; intended for rocks and cliffs.
- **AlpineSnow** — cold high elevations; intended for sparse rock variants.

The profile order is not the priority. Matching profiles are scored by their
environmental fit and the editable `Priority` value.

## Main controls

Select **Aether Procedural Biomes** in the World Outliner.

- `Seed` changes the deterministic layout.
- `Sample Count` controls the maximum generation work. Start near 32,000.
- `Density` is per-biome spawn probability.
- `Patchiness` controls clustering from the biome patch noise.
- Elevation is in meters.
- Moisture and temperature range from 0 to 1.
- `Min Ground Normal Z` controls steepness: 1 is flat; lower values allow
  steeper slopes.
- Each mesh entry has weight, scale range, surface alignment, yaw, and Z offset.
- `Build Biomes`, `Clear Biomes`, and `Reset Default Biomes` are buttons in the
  actor Details panel.

## Performance behavior

The system creates one Hierarchical Instanced Static Mesh component per unique
mesh, so thousands of instances share draw calls. Collision is disabled on
generated biome instances by default. Start/end cull distances are editable.

Generation uses one landscape trace per sample. It is intended to run in the
editor or once at startup, not every frame.

## Compatibility with the existing world director

The old `ProceduralForest` and `ProceduralRocks` HISM components are cleared and
hidden after BeginPlay when `Disable Legacy Forest And Rocks` is enabled. The
rest of `AProceduralWorldDirector`—terrain fallback, ocean fallback, runway,
weather, atmosphere, spawn placement, and turbulence—continues unchanged.

## Material integration

The population masks are generated independently from the Landscape material.
Your production Landscape already has Grass, Rock, Scree, and Snow layers. The
biome actor uses the same visual ideas—height, moisture, temperature, and
slope—but does not rewrite or damage painted layer data.
