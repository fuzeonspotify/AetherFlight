# Aether Flight — Extreme Water Setup (Unreal 5.8)

This upgrade rebuilds the generated fallback ocean as physically based **Single Layer Water**. It adds a five-band animated wave spectrum, world-space wave normals, Fresnel color, physical absorption and scattering, refraction, wave-crest foam, and weather-controlled sea state.

## Install

1. Close Unreal Editor completely.
2. Pull and compile the branch:

   ```powershell
   cd C:\Projects\AetherFlight
   git pull origin agent/high-quality-biome-scatter
   cd .\AetherFlight_Cinematic_v5_WITH_BUILD_FILES
   .\BUILD_ME_FIRST.cmd
   ```

3. Open `AetherFlight.uproject` and the `AetherWorld` map.
4. Make sure Play/PIE is stopped.
5. Choose **Tools > Execute Python Script**.
6. Run:

   ```text
   Content/Python/InstallExtremeOceanMaterial_UE58.py
   ```

7. Wait until shader compilation reaches zero, then choose **File > Save All**.
8. Press Play. Press **T** while flying to cycle the weather and compare the sea states.

The Output Log should contain:

```text
[Aether Water] Extreme Single Layer Water ocean material installed successfully
[Aether Water] Dynamic Single Layer Water ocean is active.
```

## What changes with weather

| Weather | Surface | Roughness | Foam |
|---|---|---:|---:|
| Golden Clear | Long, gentle swell | 0.045 | Very light |
| Broken Clouds | Active ocean | 0.075 | Moderate crests |
| Storm Front | Large, rough swell | 0.150 | Strong whitecaps |
| Blue Hour | Calm-to-moderate swell | 0.060 | Light crests |

The transitions are interpolated rather than snapping. The material parameters are named `SeaState`, `OceanRoughness`, and `FoamAmount` if you want to tune them later.

## Safety and compatibility

- The first run copies the previous material to `/Game/Aether/Materials/Backups/M_Ocean_Cinematic_PreExtreme` before rebuilding it.
- `InstallCinematicMaterials.py` now preserves this ocean graph instead of overwriting it.
- If the map contains a tagged `AetherWater`, `WaterBodyOcean`, or `WaterBodyLake` actor, Aether intentionally keeps that authored Water System surface and disables the generated fallback ocean. The installer affects the generated fallback ocean material.
- The fallback water has no collision, so it cannot interfere with aircraft or landscape collision.
- The analytical wave graph uses no texture assets, so it remains deterministic and has no missing-texture dependencies.

## If the ocean is still flat or gray

1. Confirm the installer success line appears in Output Log.
2. Wait for all shaders to finish before testing.
3. In the Content Browser, open `/Game/Aether/Materials/M_Ocean_Cinematic` and confirm its shading model is **Single Layer Water**.
4. Search the World Outliner for `WaterBody`. If one exists, the authored Water System owns the visible water, not Aether's generated fallback ocean.
5. Stop Play, save the material and map, and start Play again.
