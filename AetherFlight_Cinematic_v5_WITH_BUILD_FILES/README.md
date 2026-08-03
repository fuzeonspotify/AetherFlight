# Aether Flight — Unreal Engine 5.8 vertical slice

Aether Flight is a source-complete cinematic flight prototype for Windows. It includes a production 4033 x 4033, 16-bit Landscape source for a 48 km eroded mountain archipelago, starts the aircraft airborne near a hidden runway, and provides a force-based flight model, volumetric atmosphere, dynamic weather, telemetry HUD, and four camera styles.

The C++ targets explicitly use Unreal Engine 5.8's `BuildSettingsVersion.V7`. Do not convert this project backward to an earlier engine version.

This is the first playable foundation for the larger game—not a claim that a full ultra-realistic commercial flight game is already finished. The systems are intentionally data-driven so the next passes can add mission content, production vegetation/water, cockpit interaction, audio, VFX, damage, AI, and replay cinematics without replacing the foundation.

## First launch on Windows 11

1. Install **Unreal Engine 5.8** through Epic Games Launcher.
2. Install **Visual Studio 2022** with “Desktop development with C++”, “Game development with C++”, and a current Windows SDK.
3. Extract this project to a short local path such as `C:\Projects\AetherFlight`.
4. Double-click `Build_AetherFlight.bat` first. When it reports **BUILD SUCCEEDED**, open `Launch_AetherFlight.bat` (or `AetherFlight.uproject`).
5. In Unreal Editor, choose **Tools → Execute Python Script**, then select `Content\Python\ImportStealthDrone.py`. This one-time operation creates `/Game/Aircraft/StealthDrone/SM_StealthDrone` from the included GLB.
6. Use **Tools → Execute Python Script** again and run `Content\Python\InstallCinematicMaterials.py`. This creates the PBR environment materials.
7. Follow `PRODUCTION_LANDSCAPE_SETUP.md` to install and import the high-resolution Landscape. This is a one-time editor import and does not delete the fallback world.
8. Press **Play**.

Both Python setup scripts are safe to run again. Re-running the aircraft script applies compatibility/shading repairs to the existing mesh; re-running the graphics script rebuilds the generated ocean material while preserving the other installed materials.

If Windows does not associate `.uproject` files with Unreal, right-click `AetherFlight.uproject`, choose **Show more options → Generate Visual Studio project files**, build the `AetherFlightEditor` target in Visual Studio, then reopen the project.

If the one-click build reports **BUILD FAILED**, upload `Build_AetherFlight.log`. The final lines shown by Unreal's popup are generic; this log contains the first actionable compiler or toolchain error.

## Controls

| Input | Action |
|---|---|
| W / S | Increase / decrease throttle |
| A / D or mouse | Roll |
| Up / Down or mouse | Pitch |
| Q / E | Yaw |
| Right mouse | Hold for free look |
| C | Cockpit / chase / wing camera |
| V | Cinematic orbit camera |
| T | Cycle golden, broken-cloud, storm, and blue-hour weather |
| R | Reset to the air start |

An Xbox-style controller is mapped for pitch, roll, yaw, throttle, and camera cycling.

## What is implemented

- 8,500 kg physics aircraft with thrust, altitude-dependent air density, lift, parasite and induced drag, sideslip, stalls, control authority, angular damping, G load, and weather turbulence.
- Cockpit, spring-lag chase, wing, and autonomous cinematic orbit cameras with speed-reactive FOV and motion blur.
- Production 4033 x 4033 eroded Landscape source covering 48 km at roughly 11.9 m vertex spacing; 16-bit PNG and R16 heightmaps; grass, rock, scree, and snow masks; a flattened airbase; and a 2.2 km runway. The old 64-tile runtime terrain remains only as a safe fallback.
- Movable atmospheric sun, real-time skylight, Sky Atmosphere, volumetric fog, Unreal's volumetric-cloud material, Lumen, virtual shadow maps, Nanite project support, and four smoothly blended weather/light presets.
- Generated tileable PBR grass, granite, scree, snow, and macro-variation textures; a four-layer Landscape material installer; high-quality Epic/Cinematic render profiles; restrained filmic grading; and physically focused depth of field on the orbit camera.
- Landscape-aware deterministic scatter hooks for up to 6,500 licensed trees and 1,800 Nanite rocks. Exact asset paths and the Fab/Quixel workflow are documented in `PRODUCTION_LANDSCAPE_SETUP.md`.
- Unreal Water and PCG plugins enabled. Authored Water Body Ocean/Lake actors automatically replace the fallback ocean without code changes.
- A compact HUD with knots, feet, throttle, Mach, G load, camera state, and controls.
- Supplied aircraft preserved as one Unreal-ready GLB: 27,250 triangles, 11 material definitions, six embedded 4K maps, 6.67 m source length and a deliberate 2x in-game scale.

## Performance presets

The project targets a modern DX12/Shader Model 6 PC. If the editor is slow while shaders compile, wait for compilation to finish before judging frame rate. Start with Epic scalability; reduce Effects first if clouds/fog are expensive. Reserve Cinematic scalability for screenshots and Movie Render Queue. See `CINEMATIC_GRAPHICS_SETUP.md` for the exact setup and free-asset hooks.

## Important limitations of this milestone

- The supplied aircraft is a static model. Control surfaces, landing gear, internal cockpit controls, and damage sections are not separately rigged yet.
- The production heightmap and materials are generated source assets, not scanned real-world geography. Fab/Quixel meshes and water materials must be acquired through your own Epic account so their licenses remain attached correctly; they are not redistributed in this archive.
- Flight coefficients are plausible and tunable, but they are not wind-tunnel data for a real aircraft.
- Unreal Engine is not available in the build environment used to assemble this package, so the source was structurally validated but could not be compiled or visually rendered here. The first local Unreal build is the definitive API/shader validation pass.

## Asset license

The aircraft is CC BY 4.0. Keep `ATTRIBUTION.md` and `SourceAssets/StealthDrone/license.txt` with any public build or credits page. Commercial use is allowed with attribution. All model-specific credit belongs to radekstepan.

## Recommended next milestone

Build one five-minute mission: cold open in storm clouds, terrain-following ingress, target reveal, escape through a fjord, and a scripted sunset flyaway. That single mission will expose the exact needs for cockpit work, AI, audio, VFX, damage, objective logic, and a replay/Sequencer bridge before the project grows wider.
