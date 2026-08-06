# AetherFlight high-quality environment setup

This pass adds a deterministic runtime ecosystem to the 48 km production
Landscape. It creates clustered forests, mixed species, understory plants,
ground cover, boulders, and steep-slope rock outcrops while keeping the runway
clear. All placement uses Hierarchical Instanced Static Mesh components, has no
gameplay collision, and uses distance culling appropriate for an aerial game.

The system starts automatically in Play/Standalone. If an
`AetherBiomeScatterActor` is placed manually, the automatic subsystem reuses it
instead, allowing its budgets to be tuned in the Details panel.

## Why meshes are not committed

Fab/Marketplace assets generally cannot be redistributed in a public source
repository. Install free or owned packs through Fab inside Unreal Editor, then
duplicate selected meshes into the stable Aether paths below. Their original
materials and textures remain attached.

Two free starting packs verified when this document was written:

- [DZ Sample Trees](https://www.fab.com/listings/7c95ac5f-246e-42fb-9d2a-4807db87f69d)
  contains five high-resolution Nanite trees, including pine and aspen.
- [Environment - Rock Collection 04 (Free)](https://www.fab.com/listings/a51e61ac-98fa-4c54-ab23-fc533687afb7)
  contains seven 4K rock meshes.

Confirm that each listing is still free and review its current license before
adding it to the project.

## Required Content Browser paths

Create these folders:

- `/Game/Aether/Environment/Foliage`
- `/Game/Aether/Environment/Rocks`

Duplicate and rename your chosen meshes to these paths:

| Role | Preferred asset name | Required? |
|---|---|---|
| Main pine/spruce | `SM_Conifer_A` | Yes, unless broadleaf is present |
| Second conifer silhouette | `SM_Conifer_B` | Recommended |
| Aspen/oak/broadleaf | `SM_Broadleaf_A` | Recommended |
| Bush or young tree | `SM_Shrub_A` | Recommended |
| Fern/grass clump | `SM_GroundCover_A` | Recommended |
| Medium boulder | `SM_Boulder_A` | Yes |
| Large/cliff boulder | `SM_Boulder_B` | Recommended |

Legacy names `SM_Conifer` and `SM_CliffRock` remain supported.

## Verify and test

1. Close Unreal and run `BUILD_ME_FIRST.cmd` so the new C++ files compile.
2. Open `AetherWorld`.
3. Use **Tools > Execute Python Script** and run
   `Content/Python/AuditEnvironmentAssets_UE58.py`.
4. Keep collision enabled for **queries** on the production Landscape. The
   ecosystem uses vertical visibility traces to place assets on its surface.
   Foliage and rock instances themselves remain non-colliding.
5. Press Play and press `R` once to reset the aircraft.

Successful Output contains a line similar to:

`[Aether] Production ecosystem built: 12000 trees, 7000 understory plants, 4200 rocks.`

Exact counts vary with the landscape, mesh availability, and biome rules.

## Quality guidance

- Enable Nanite on rocks and on foliage meshes explicitly designed for Nanite.
- Keep masked leaf materials two-sided and preserve their wind/material setup.
- Use at least two tree silhouettes; scale and yaw variation cannot fully hide
  repetition when every tree has the same crown.
- Avoid enabling collision on every tree. Add separate simple collision only to
  a small hand-authored airport or mission area if gameplay needs it.
- The ground-cover cull distance is intentionally short, while full trees and
  large rocks remain visible much farther away.
