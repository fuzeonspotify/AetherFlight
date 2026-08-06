# Aether Flight — Fluid Ocean and Aerodynamic Vapor Upgrade

This revision replaces the colored wing ribbons with layered aerodynamic condensation and upgrades the generated ocean with Gerstner-style orbital motion.

## Install

Close Unreal Editor completely, then run:

```powershell
cd C:\Projects\AetherFlight
git pull origin agent/high-quality-biome-scatter
cd .\AetherFlight_Cinematic_v5_WITH_BUILD_FILES
.\BUILD_ME_FIRST.cmd
```

Open the project, stop Play/PIE, and run both scripts from **Tools > Execute Python Script** in this order:

```text
Content/Python/InstallWingCondensationMaterial_UE58.py
Content/Python/InstallExtremeOceanMaterial_UE58.py
```

Wait for shader compilation to reach zero, then select **File > Save All** and press Play.

## What changed

### Aerodynamic condensation

- Neutral white vapor; vertex RGB is no longer sent to the visible color output.
- Five softly faded planes form each volumetric-looking wingtip vortex.
- The vortex core expands and rolls into a subtle helix behind each wingtip.
- Five noisy pressure-cloud layers form above the wing during high positive lift.
- Volumetric directional translucency receives scene and sun lighting.
- Depth fading removes hard intersections with the airframe.
- Density responds to positive G-load, airspeed, angle of attack, Mach, and weather humidity.
- The effect remains short-lived liquid-water condensation rather than persistent engine smoke.

Test above 185 knots with a hard positive-G turn. Broken Clouds and Storm Front produce the most visible vapor. Golden Clear intentionally produces less.

### Ocean

- Seven directional wave bands, from long swell to capillary ripples.
- Gerstner-style horizontal orbital motion makes crests sharpen and water roll instead of only moving vertically.
- Wave-slope detection creates whitecaps on genuinely steep, breaking sections.
- Weather drives sea height, roughness, choppiness, and foam independently.
- Single Layer Water continues to provide physical scattering, absorption, Fresnel reflection, and refraction.

Press **T** while flying to compare calm, broken, storm, and blue-hour sea states.

## Expected Output Log

```text
[Aether Vapor Material v2] Installed neutral, lit, soft-edged aerodynamic vapor material
[Aether Water] Extreme Single Layer Water ocean material installed successfully
[Aether Vapor] Aerodynamic wing condensation is active (G-load, airspeed, AoA and humidity driven).
[Aether Water] Dynamic Single Layer Water ocean is active.
```
