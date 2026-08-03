# Deprecated — Classic Landscape workflow removed

AetherFlight no longer uses the classic Landscape production workflow.

Do not import `AetherFlight_4033.r16` in Landscape Mode and do not run the old
Landscape repair scripts. The supported UE 5.8 terrain workflow is:

`MESH_TERRAIN_UE58_SETUP.md`

Run `RESET_AETHER_TERRAIN_UE58.ps1` first. It removes existing Landscape and Mesh
Terrain actors from `AetherWorld`, then installs the clean Mesh Terrain authoring
assets while preserving the aircraft, runway, HUD, controls, weather, water,
source textures, heightmaps, and weightmaps.
