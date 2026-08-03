# Fab asset shortlist for Aether Flight

These are acquisition links, not redistributed files. Add assets through your
own Epic/Fab account so the correct license stays attached to the project.

## Verified free on 2026-08-02

| Use | Asset | Notes |
|---|---|---|
| Ocean shader | [Water Materials](https://www.fab.com/listings/063155ea-d9d2-4f29-b09f-33270b0bc861) | 12 water materials plus variations for oceans, rivers, waterfalls, and pools. |
| Cliff surface | [Quixel Megascans Rock Cliff](https://www.fab.com/listings/22762313-071f-4017-a721-b29c5a2f1a87) | High-resolution scanned base color, roughness, normal, displacement, AO, and supporting maps. |

Confirm the current price and license before acquisition; marketplace details
can change after this package is built.

## High-quality candidates to compare

| Use | Asset | Why it fits |
|---|---|---|
| Conifer forest | [Realistic Norwegian Pine Trees](https://www.fab.com/listings/0a55c7fa-16e1-44ce-ad22-9f3533ad721f) | Nanite/Lumen UE5 pine environment aimed at high-end RTX hardware. |
| Conifer forest | [UCreate - Conifer Forest](https://www.fab.com/listings/d9d249e1-6550-4e74-bfde-6bafa87b0226) | Large realistic biome set with trees, plants, rocks, debris, and procedural foliage support. |
| Nordic hero rock | [Nordic Beach Rock Formation](https://www.fab.com/listings/d15cbbca-1b5a-49e8-a011-92abeb18147a) | Scanned 4.26 x 8.38 x 3.08 m formation suitable for Nanite shoreline dressing. |
| Large cliff | [Massive Nordic Coastal Cliff](https://www.fab.com/listings/08fc1d81-3d5b-463c-9110-bb95dfa6c53f) | Large scanned coastal cliff for masking weak Landscape silhouettes at hero locations. |

## Integration contract

The game already searches for these assets at runtime:

| Asset role | Final Unreal path |
|---|---|
| One representative conifer mesh | `/Game/Aether/Environment/Foliage/SM_Conifer` |
| One representative rock mesh | `/Game/Aether/Environment/Rocks/SM_CliffRock` |

Duplicate or move the chosen mesh to the final path above. Do not rename the
original marketplace asset in place if other demo maps depend on it. When the
path exists, the game automatically scatters the mesh using the new Landscape's
collision, elevation, slope, moisture, exposure, and runway-exclusion rules.

For a hero-quality pass, use the automatic scatter only for mid/far coverage.
Hand-place the largest cliff pieces along the runway approach, fjords, and
shoreline silhouettes, then create HLODs for those authored clusters.
