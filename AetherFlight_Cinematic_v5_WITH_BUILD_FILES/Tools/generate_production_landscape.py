#!/usr/bin/env python3
"""Generate Aether Flight's production terrain, biomes, and hydrology.

The 4033-square heightfield is an Unreal-native Landscape resolution. Geometry
is generated at 1009, hydrologically carved, then linearly upsampled to avoid
the cubic ringing that can create needles and proxy-edge walls. Rivers and
lakes are authored into the heightfield and exported as a water-body plan.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates, zoom


SEED = 1847
WORK_RESOLUTION = 1009
OUTPUT_RESOLUTION = 4033
WORLD_SIZE_METERS = 48_000.0
MAX_ABSOLUTE_HEIGHT_METERS = 2_800.0
AIRBASE_X_METERS = -6_500.0
AIRBASE_Y_METERS = -9_000.0
AIRBASE_HEIGHT_METERS = 115.0

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SourceAssets" / "ProductionTerrain"
HEIGHT_DIR = OUTPUT / "Heightmaps"
WEIGHT_DIR = OUTPUT / "Weightmaps"
TEXTURE_DIR = OUTPUT / "Textures"
PREVIEW_DIR = OUTPUT / "Previews"
HYDROLOGY_DIR = OUTPUT / "Hydrology"

LANDSCAPE_LAYERS = (
    "Grass", "ForestFloor", "Rock", "Scree", "Snow", "Sand", "Wetland"
)

# Normalized world coordinates. River point order is source to mouth.
RIVER_DEFINITIONS = (
    {
        "name": "River_Aster",
        "width_m": 155.0,
        "points": ((-0.34, 0.46), (-0.25, 0.39), (-0.31, 0.27),
                   (-0.17, 0.18), (-0.22, 0.05), (-0.04, -0.02),
                   (-0.10, -0.16), (0.12, -0.21), (0.20, -0.34),
                   (0.38, -0.31), (0.52, -0.44), (0.70, -0.39),
                   (0.83, -0.49), (0.96, -0.46)),
    },
    {
        "name": "River_Kestrel",
        "width_m": 118.0,
        "points": ((0.30, 0.51), (0.41, 0.45), (0.36, 0.34),
                   (0.50, 0.29), (0.44, 0.20), (0.61, 0.16),
                   (0.56, 0.08), (0.72, 0.05), (0.80, 0.10), (0.96, 0.01)),
    },
    {
        "name": "River_Vesper",
        "width_m": 105.0,
        "points": ((-0.03, 0.57), (-0.11, 0.51), (-0.08, 0.42),
                   (-0.24, 0.38), (-0.20, 0.27), (-0.40, 0.22),
                   (-0.36, 0.12), (-0.55, 0.08), (-0.59, -0.03),
                   (-0.76, 0.01), (-0.91, -0.10)),
    },
)

LAKE_DEFINITIONS = (
    {"name": "Lake_Aster", "center": (-0.33, 0.43), "radius": (0.095, 0.063)},
    {"name": "Lake_Meridian", "center": (0.29, 0.48), "radius": (0.070, 0.050)},
    {"name": "Lake_Vesper", "center": (-0.03, 0.55), "radius": (0.062, 0.046)},
    {"name": "Lake_Echo", "center": (0.12, -0.10), "radius": (0.052, 0.038)},
)


def normalized(field: np.ndarray) -> np.ndarray:
    low = np.percentile(field, 0.4)
    high = np.percentile(field, 99.6)
    return np.clip((field - low) / max(high - low, 1e-6), 0.0, 1.0).astype(np.float32)


def multiscale_noise(rng: np.random.Generator, size: int, scales: list[tuple[float, float]], mode="reflect"):
    result = np.zeros((size, size), dtype=np.float32)
    total = 0.0
    for sigma, weight in scales:
        source = rng.standard_normal((size, size), dtype=np.float32)
        layer = normalized(gaussian_filter(source, sigma=sigma, mode=mode))
        result += layer * weight
        total += weight
    return normalized(result / total)


def smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    value = np.clip((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def save_png(array: np.ndarray, path: Path) -> None:
    """Write and verify a PNG before replacing the previous generated file."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    Image.fromarray(array).save(temporary, format="PNG", compress_level=6)
    with Image.open(temporary) as verification:
        verification.verify()
    temporary.replace(path)


def sample_field(field: np.ndarray, normalized_points) -> np.ndarray:
    """Sample a square field at normalized [-1, 1] XY coordinates."""
    points = np.asarray(normalized_points, dtype=np.float32)
    px = (points[:, 0] * 0.5 + 0.5) * (field.shape[1] - 1)
    py = (points[:, 1] * 0.5 + 0.5) * (field.shape[0] - 1)
    return map_coordinates(field, (py, px), order=1, mode="nearest")


def smooth_polyline(points, passes: int = 3) -> np.ndarray:
    """Chaikin subdivision: smooth water corridors without spline dependencies."""
    result = np.asarray(points, dtype=np.float32)
    for _ in range(passes):
        smoothed = [result[0]]
        for start, end in zip(result[:-1], result[1:]):
            smoothed.append(start * 0.75 + end * 0.25)
            smoothed.append(start * 0.25 + end * 0.75)
        smoothed.append(result[-1])
        result = np.asarray(smoothed, dtype=np.float32)
    return result


def monotonic_river_heights(field: np.ndarray, points) -> np.ndarray:
    """Create a downhill spline profile that cannot run uphill between points."""
    sampled = sample_field(gaussian_filter(field, 6.0, mode="nearest"), points) - 12.0
    sampled[0] = max(sampled[0], 260.0)
    for index in range(1, len(sampled)):
        remaining = len(sampled) - 1 - index
        floor = 4.0 + remaining * 3.0
        sampled[index] = np.clip(sampled[index], floor, sampled[index - 1] - 0.45)
    sampled[-1] = 1.5
    return sampled.astype(np.float32)


def carve_hydrology(elevation: np.ndarray, xx: np.ndarray, yy: np.ndarray):
    """Carve connected basins and drainage corridors; return masks and water plan."""
    world_x = xx * WORLD_SIZE_METERS * 0.5
    world_y = yy * WORLD_SIZE_METERS * 0.5
    river_mask = np.zeros_like(elevation, dtype=np.float32)
    lake_mask = np.zeros_like(elevation, dtype=np.float32)
    moisture = np.zeros_like(elevation, dtype=np.float32)
    plan = {"sea_level_m": 0.0, "rivers": [], "lakes": []}

    for definition in LAKE_DEFINITIONS:
        cx, cy = definition["center"]
        rx, ry = definition["radius"]
        radial = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
        shore = 1.0 - smoothstep(0.76, 1.26, radial)
        water = 1.0 - smoothstep(0.72, 0.98, radial)
        center_height = float(sample_field(elevation, ((cx, cy),))[0])
        surface = float(np.clip(center_height - 48.0, 42.0, 760.0))
        bottom = surface - 26.0 - 34.0 * np.clip(1.0 - radial, 0.0, 1.0)
        # Lower only; this preserves surrounding mountain silhouettes and
        # creates a broad natural shoreline rather than a circular crater rim.
        shoreline_target = surface + 15.0 + np.clip(radial - 0.82, 0.0, 1.0) * 55.0
        elevation = np.minimum(elevation, elevation * (1.0 - shore) + shoreline_target * shore)
        elevation = np.minimum(elevation, elevation * (1.0 - water) + bottom * water)
        lake_mask = np.maximum(lake_mask, water)
        moisture = np.maximum(moisture, 1.0 - smoothstep(0.9, 2.8, radial))
        plan["lakes"].append({
            "name": definition["name"],
            "center_m": [cx * WORLD_SIZE_METERS * 0.5, cy * WORLD_SIZE_METERS * 0.5],
            "radius_m": [rx * WORLD_SIZE_METERS * 0.5, ry * WORLD_SIZE_METERS * 0.5],
            "surface_z_m": surface,
        })

    for definition in RIVER_DEFINITIONS:
        points = smooth_polyline(definition["points"], passes=3)
        heights = monotonic_river_heights(elevation, points)
        width = float(definition["width_m"])
        nearest_distance = np.full_like(elevation, np.inf, dtype=np.float32)
        nearest_surface = np.zeros_like(elevation, dtype=np.float32)

        for index in range(len(points) - 1):
            p0 = points[index] * (WORLD_SIZE_METERS * 0.5)
            p1 = points[index + 1] * (WORLD_SIZE_METERS * 0.5)
            vx, vy = p1 - p0
            length_squared = max(float(vx * vx + vy * vy), 1.0)
            t = np.clip(((world_x - p0[0]) * vx + (world_y - p0[1]) * vy) / length_squared, 0.0, 1.0)
            closest_x = p0[0] + t * vx
            closest_y = p0[1] + t * vy
            distance = np.hypot(world_x - closest_x, world_y - closest_y)
            closer = distance < nearest_distance
            nearest_distance = np.where(closer, distance, nearest_distance)
            segment_surface = heights[index] * (1.0 - t) + heights[index + 1] * t
            nearest_surface = np.where(closer, segment_surface, nearest_surface)

        channel = 1.0 - smoothstep(width * 0.50, width * 1.35, nearest_distance)
        floodplain = 1.0 - smoothstep(width * 1.20, width * 5.2, nearest_distance)
        channel_bottom = nearest_surface - (8.0 + width * 0.055)
        bank_target = nearest_surface + 5.0 + nearest_distance * 0.018
        elevation = np.minimum(
            elevation,
            elevation * (1.0 - floodplain * 0.52) + bank_target * (floodplain * 0.52),
        )
        elevation = np.minimum(
            elevation,
            elevation * (1.0 - channel) + channel_bottom * channel,
        )
        river_mask = np.maximum(river_mask, channel)
        moisture = np.maximum(
            moisture, 1.0 - smoothstep(width * 1.4, width * 9.0, nearest_distance)
        )
        plan["rivers"].append({
            "name": definition["name"],
            "width_m": width,
            "points": [
                [float(point[0] * WORLD_SIZE_METERS * 0.5),
                 float(point[1] * WORLD_SIZE_METERS * 0.5), float(z)]
                for point, z in zip(points, heights)
            ],
        })

    # Hydrology is softened only across banks; channels remain readable from
    # flight altitude without producing razor-thin geometry.
    elevation = gaussian_filter(elevation, 0.62, mode="nearest")
    return elevation.astype(np.float32), {
        "river_mask": np.clip(river_mask, 0.0, 1.0),
        "lake_mask": np.clip(lake_mask, 0.0, 1.0),
        "moisture": np.clip(moisture, 0.0, 1.0),
        "plan": plan,
    }


def build_heightfield():
    rng = np.random.default_rng(SEED)
    size = WORK_RESOLUTION
    axis = np.linspace(-1.0, 1.0, size, dtype=np.float32)
    xx, yy = np.meshgrid(axis, axis)

    warp_x = multiscale_noise(rng, size, [(165, 1.0), (74, 0.55), (31, 0.2)]) - 0.5
    warp_y = multiscale_noise(rng, size, [(142, 1.0), (63, 0.5), (27, 0.2)]) - 0.5
    warped_x = xx + warp_x * 0.22
    warped_y = yy + warp_y * 0.18

    continental = multiscale_noise(
        rng, size, [(235, 1.0), (118, 0.78), (58, 0.5), (27, 0.24), (12, 0.1)]
    )
    radial = 1.0 - np.sqrt((warped_x / 1.02) ** 2 + (warped_y / 0.93) ** 2)
    island_field = radial * 0.75 + (continental - 0.5) * 0.82
    land = smoothstep(-0.055, 0.12, island_field)

    ridge_source = multiscale_noise(
        rng, size, [(110, 0.35), (55, 0.65), (26, 0.9), (12, 0.65), (5, 0.25)]
    )
    ridge = 1.0 - np.abs(ridge_source * 2.0 - 1.0)
    ridge = np.power(np.clip(ridge, 0.0, 1.0), 2.15)
    ridge = gaussian_filter(ridge, 1.15, mode="reflect")

    valley_source = multiscale_noise(rng, size, [(92, 1.0), (41, 0.7), (18, 0.25)])
    valleys = np.power(1.0 - np.abs(valley_source * 2.0 - 1.0), 4.0)
    detail = multiscale_noise(rng, size, [(30, 0.72), (14, 0.52), (6, 0.28), (2.5, 0.12)])

    mountain_envelope = smoothstep(0.12, 0.86, land)
    # Two broad tectonic belts keep the world from reading as uniformly noisy
    # hills. Their overlap makes long ridgelines and distinct flyable valleys.
    belt_a = np.exp(-((warped_y - warped_x * 0.34 - 0.08) / 0.33) ** 2)
    belt_b = np.exp(-((warped_y + warped_x * 0.52 + 0.16) / 0.42) ** 2)
    tectonic = np.clip(0.34 + belt_a * 0.54 + belt_b * 0.38, 0.0, 1.18)
    elevation = (
        -310.0
        + land * 380.0
        + mountain_envelope * tectonic * ridge * (1_660.0 + 720.0 * detail)
        + mountain_envelope * (detail - 0.46) * 420.0
        - mountain_envelope * valleys * 360.0
    )

    # A restrained thermal erosion pass rounds impossible needle peaks while
    # keeping long ridges and drainage-shaped valleys readable from the air.
    for _ in range(22):
        smoothed = gaussian_filter(elevation, 1.05, mode="nearest")
        gy, gx = np.gradient(elevation)
        steep = smoothstep(19.0, 55.0, np.hypot(gx, gy)) * mountain_envelope
        elevation = elevation * (1.0 - steep * 0.075) + smoothed * (steep * 0.075)

    broad_drainage = gaussian_filter(valleys, 5.0, mode="reflect")
    elevation -= broad_drainage * mountain_envelope * 110.0

    # Preserve an irregular continental shelf and a gently submerged seabed.
    shelf = smoothstep(-0.17, 0.02, island_field)
    seabed = -340.0 + continental * 145.0
    elevation = np.where(land < 0.025, seabed, elevation)
    elevation = seabed * (1.0 - shelf) + elevation * shelf

    # Cut a broad, softly blended airfield bench into the source heightmap so
    # the existing runway actor and flight-spawn coordinates remain valid.
    x_m = xx * WORLD_SIZE_METERS * 0.5
    y_m = yy * WORLD_SIZE_METERS * 0.5
    runway_distance = np.sqrt(
        ((x_m - AIRBASE_X_METERS) / 2_050.0) ** 2
        + ((y_m - AIRBASE_Y_METERS) / 430.0) ** 2
    )
    runway_blend = 1.0 - smoothstep(0.68, 1.18, runway_distance)
    elevation = elevation * (1.0 - runway_blend) + AIRBASE_HEIGHT_METERS * runway_blend

    elevation, hydrology = carve_hydrology(elevation, xx, yy)

    # A guaranteed submerged border hides the finite Landscape edge under the
    # ocean horizon and prevents imported boundary values from becoming walls.
    border_distance = np.minimum(1.0 - np.abs(xx), 1.0 - np.abs(yy))
    border_blend = 1.0 - smoothstep(0.025, 0.105, border_distance)
    border_seabed = -360.0 + continental * 35.0
    elevation = elevation * (1.0 - border_blend) + border_seabed * border_blend

    elevation = gaussian_filter(elevation, 0.55, mode="nearest")
    return (
        np.clip(elevation, -420.0, MAX_ABSOLUTE_HEIGHT_METERS).astype(np.float32),
        hydrology,
    )


def resize_field(field: np.ndarray, resolution: int, order: int = 3) -> np.ndarray:
    factor = (resolution - 1) / (field.shape[0] - 1)
    result = zoom(field, factor, order=order, mode="nearest", prefilter=order > 1)
    return result[:resolution, :resolution].astype(np.float32)


def save_heightmap(height_m: np.ndarray) -> None:
    encoded = 32768.0 + height_m * (32767.0 / MAX_ABSOLUTE_HEIGHT_METERS)
    encoded = np.clip(np.rint(encoded), 0, 65535).astype(np.uint16)
    save_png(encoded, HEIGHT_DIR / "AetherFlight_4033_16bit.png")
    raw_path = HEIGHT_DIR / "AetherFlight_4033.r16"
    temporary = raw_path.with_suffix(raw_path.suffix + ".tmp")
    encoded.astype("<u2").tofile(temporary)
    temporary.replace(raw_path)


def build_weightmaps(height_m: np.ndarray, hydrology) -> dict[str, np.ndarray]:
    meters_per_pixel = WORLD_SIZE_METERS / (height_m.shape[0] - 1)
    gy, gx = np.gradient(height_m, meters_per_pixel)
    slope = np.arctan(np.hypot(gx, gy))

    above_water = smoothstep(-3.0, 18.0, height_m)
    gentle = 1.0 - smoothstep(np.deg2rad(20.0), np.deg2rad(42.0), slope)
    cliff = smoothstep(np.deg2rad(27.0), np.deg2rad(50.0), slope)
    alpine = smoothstep(850.0, 1_550.0, height_m)
    snowline = smoothstep(1_560.0, 2_100.0, height_m)

    river = hydrology["river_mask"]
    lake = hydrology["lake_mask"]
    moisture = hydrology["moisture"]
    shoreline = (1.0 - smoothstep(8.0, 62.0, np.abs(height_m))) * gentle
    wet_basin = np.maximum(river, lake) * gentle

    grass = above_water * gentle * (1.0 - smoothstep(920.0, 1_620.0, height_m))
    forest_floor = grass * moisture * (1.0 - smoothstep(980.0, 1_440.0, height_m))
    grass *= 1.0 - forest_floor * 0.68
    snow = above_water * snowline * (1.0 - cliff * 0.82)
    rock = above_water * np.maximum(cliff, alpine * 0.55) * (1.0 - snow * 0.55)
    scree = np.maximum(0.12, above_water * (0.28 + alpine * 0.48 + cliff * 0.25))
    scree += (1.0 - above_water) * 0.85
    sand = shoreline * (1.0 - cliff) + (1.0 - above_water) * smoothstep(-55.0, -3.0, height_m)
    wetland = above_water * wet_basin * (1.0 - cliff) * (1.0 - snow)

    weights = np.stack(
        [grass, forest_floor, rock, scree, snow, sand, wetland], axis=0
    ).astype(np.float32)
    # A wider normalized transition removes the painted rings and hard texture
    # borders visible in the previous map while retaining cliff definition.
    weights = gaussian_filter(weights, sigma=(0.0, 2.35, 2.35), mode="nearest")
    weights /= np.maximum(weights.sum(axis=0, keepdims=True), 1e-6)
    return {name: weights[index] for index, name in enumerate(LANDSCAPE_LAYERS)}


def save_weightmaps(weightmaps: dict[str, np.ndarray]) -> None:
    for name, weights in weightmaps.items():
        image = np.clip(np.rint(weights * 255.0), 0, 255).astype(np.uint8)
        save_png(image, WEIGHT_DIR / f"AetherFlight_{name}_4033.png")


def save_hydrology(hydrology) -> None:
    for key, filename in (
        ("river_mask", "AetherFlight_RiverMask_4033.png"),
        ("lake_mask", "AetherFlight_LakeMask_4033.png"),
        ("moisture", "AetherFlight_Moisture_4033.png"),
    ):
        image = np.clip(np.rint(hydrology[key] * 255.0), 0, 255).astype(np.uint8)
        save_png(image, HYDROLOGY_DIR / filename)
    (HYDROLOGY_DIR / "AetherFlight_Hydrology.json").write_text(
        json.dumps(hydrology["plan"], indent=2) + "\n", encoding="utf-8"
    )


def tileable_noise(rng: np.random.Generator, size: int, scales: list[tuple[float, float]]):
    value = np.zeros((size, size), dtype=np.float32)
    total = 0.0
    for sigma, weight in scales:
        source = rng.standard_normal((size, size), dtype=np.float32)
        layer = normalized(gaussian_filter(source, sigma=sigma, mode="wrap"))
        value += layer * weight
        total += weight
    return normalized(value / total)


def normal_map(height: np.ndarray, strength: float) -> np.ndarray:
    gy, gx = np.gradient(height)
    nx = -gx * strength
    ny = gy * strength
    nz = np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack([nx / length, ny / length, nz / length], axis=-1)
    return np.clip(np.rint((normal * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)


def save_surface_texture_set(name: str, base_rgb: tuple[float, float, float], seed_offset: int,
                             roughness_range: tuple[float, float], contrast: float, normal_strength: float):
    rng = np.random.default_rng(SEED + seed_offset)
    size = 1024
    macro = tileable_noise(rng, size, [(96, 1.0), (43, 0.7), (18, 0.35)])
    micro = tileable_noise(rng, size, [(15, 0.6), (6, 0.85), (2.2, 0.52)])
    grain = tileable_noise(rng, size, [(2.4, 0.4), (0.75, 0.9)])
    height = normalized(macro * 0.43 + micro * 0.48 + grain * 0.09)
    modulation = np.clip(0.70 + (height - 0.5) * contrast + macro * 0.34, 0.38, 1.35)
    color = np.clip(np.asarray(base_rgb)[None, None, :] * modulation[..., None], 0.0, 1.0)

    if name == "Rock":
        strata = (np.sin((np.indices((size, size))[0] + macro * 110.0) * 0.062) * 0.5 + 0.5)
        color *= (0.83 + strata[..., None] * 0.18)
        height = normalized(height * 0.72 + strata * 0.28)
    elif name == "Grass":
        flecks = smoothstep(0.68, 0.87, grain)
        color[..., 1] += flecks * 0.035
        color[..., 0] -= flecks * 0.012
    elif name == "ForestFloor":
        leaf_litter = smoothstep(0.58, 0.82, macro) * (0.55 + grain * 0.45)
        color[..., 0] += leaf_litter * 0.038
        color[..., 1] -= leaf_litter * 0.018
        height = normalized(height * 0.62 + leaf_litter * 0.38)
    elif name == "Sand":
        ripples = np.sin((np.indices((size, size))[0] * 0.032) + macro * 8.0) * 0.5 + 0.5
        color *= 0.91 + ripples[..., None] * 0.10
        height = normalized(height * 0.38 + ripples * 0.62)
    elif name == "Wetland":
        dark_pools = smoothstep(0.64, 0.88, macro)
        color *= 0.78 + (1.0 - dark_pools[..., None]) * 0.28
        height = normalized(height * 0.72 + dark_pools * 0.28)
    elif name == "Snow":
        wind = gaussian_filter(rng.standard_normal((size, size), dtype=np.float32), (2.0, 24.0), mode="wrap")
        wind = normalized(wind)
        color *= (0.92 + wind[..., None] * 0.11)
        height = normalized(height * 0.55 + wind * 0.45)

    roughness = roughness_range[0] + (1.0 - micro) * (roughness_range[1] - roughness_range[0])
    save_png(
        np.rint(color * 255.0).astype(np.uint8), TEXTURE_DIR / f"T_{name}_BaseColor.png"
    )
    save_png(normal_map(height, normal_strength), TEXTURE_DIR / f"T_{name}_Normal.png")
    save_png(
        np.rint(np.clip(roughness, 0.0, 1.0) * 255.0).astype(np.uint8),
        TEXTURE_DIR / f"T_{name}_Roughness.png",
    )


def save_macro_variation() -> None:
    rng = np.random.default_rng(SEED + 909)
    macro = tileable_noise(rng, 1024, [(155, 1.0), (72, 0.7), (31, 0.32), (12, 0.1)])
    macro = np.clip(0.72 + macro * 0.40, 0.0, 1.0)
    save_png(np.rint(macro * 255.0).astype(np.uint8), TEXTURE_DIR / "T_MacroVariation.png")


def save_preview(height_m: np.ndarray, weights: dict[str, np.ndarray], hydrology) -> None:
    preview_size = 1600
    factor = preview_size / height_m.shape[0]
    h = zoom(height_m, factor, order=1, mode="nearest")[:preview_size, :preview_size]
    resized_weights = {
        key: zoom(value, factor, order=1, mode="nearest")[:preview_size, :preview_size]
        for key, value in weights.items()
    }
    palettes = {
        "Grass": np.array([0.115, 0.205, 0.075]),
        "ForestFloor": np.array([0.095, 0.135, 0.055]),
        "Rock": np.array([0.275, 0.265, 0.235]),
        "Scree": np.array([0.30, 0.265, 0.20]),
        "Snow": np.array([0.84, 0.88, 0.90]),
        "Sand": np.array([0.44, 0.38, 0.25]),
        "Wetland": np.array([0.07, 0.13, 0.08]),
    }
    color = sum(resized_weights[name][..., None] * palettes[name] for name in palettes)
    hydro_water = np.maximum(hydrology["river_mask"], hydrology["lake_mask"])
    hydro_water = zoom(hydro_water, factor, order=1, mode="nearest")[:preview_size, :preview_size]
    water = (h <= 0.0) | (hydro_water > 0.28)
    water_depth = np.clip(-h / 360.0, 0.0, 1.0)
    water_color = np.stack(
        [0.018 + water_depth * 0.002, 0.135 - water_depth * 0.075, 0.19 - water_depth * 0.095], axis=-1
    )
    color = np.where(water[..., None], water_color, color)

    gy, gx = np.gradient(h)
    light = np.array([-0.45, -0.52, 0.73])
    nx, ny, nz = -gx * 0.022, -gy * 0.022, np.ones_like(h)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    shade = np.clip((nx * light[0] + ny * light[1] + nz * light[2]) / length, 0.12, 1.0)
    color = np.clip(color * (0.48 + shade[..., None] * 0.78), 0.0, 1.0)
    save_png(
        np.rint(color * 255.0).astype(np.uint8),
        PREVIEW_DIR / "AetherFlight_ProductionTerrain_Preview.png",
    )


def main() -> None:
    for directory in (HEIGHT_DIR, WEIGHT_DIR, TEXTURE_DIR, PREVIEW_DIR, HYDROLOGY_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    print("Generating tectonic terrain and carved hydrology at working resolution...")
    working_height, working_hydrology = build_heightfield()
    print("Resampling to Unreal Landscape resolution 4033 x 4033...")
    # Linear interpolation is intentional: cubic overshoot was capable of
    # creating out-of-range needles near sharp channels and tile boundaries.
    height = resize_field(working_height, OUTPUT_RESOLUTION, order=1)
    hydrology = {
        key: resize_field(value, OUTPUT_RESOLUTION, order=1)
        for key, value in working_hydrology.items() if key != "plan"
    }
    hydrology["plan"] = working_hydrology["plan"]
    save_heightmap(height)
    print("Computing landscape biome masks...")
    weights = build_weightmaps(height, hydrology)
    save_weightmaps(weights)
    save_hydrology(hydrology)

    print("Generating tileable production surface textures...")
    save_surface_texture_set("Grass", (0.19, 0.255, 0.105), 101, (0.72, 0.94), 0.58, 7.0)
    save_surface_texture_set("ForestFloor", (0.135, 0.16, 0.075), 151, (0.78, 0.96), 0.62, 8.0)
    save_surface_texture_set("Rock", (0.32, 0.305, 0.275), 202, (0.66, 0.90), 0.64, 10.0)
    save_surface_texture_set("Scree", (0.34, 0.285, 0.20), 303, (0.76, 0.97), 0.62, 8.0)
    save_surface_texture_set("Snow", (0.83, 0.87, 0.88), 404, (0.48, 0.82), 0.35, 5.0)
    save_surface_texture_set("Sand", (0.43, 0.37, 0.245), 454, (0.67, 0.88), 0.42, 4.0)
    save_surface_texture_set("Wetland", (0.105, 0.145, 0.072), 505, (0.60, 0.90), 0.58, 6.0)
    save_macro_variation()
    save_preview(height, weights, hydrology)

    metadata = {
        "seed": SEED,
        "resolution": OUTPUT_RESOLUTION,
        "world_size_meters": WORLD_SIZE_METERS,
        "xy_scale_centimeters": WORLD_SIZE_METERS * 100.0 / (OUTPUT_RESOLUTION - 1),
        "z_scale_centimeters": MAX_ABSOLUTE_HEIGHT_METERS * 100.0 / 256.0,
        "height_encoding": "32768 is sea level; positive range reaches +2800 m",
        "airbase_world_meters": [AIRBASE_X_METERS, AIRBASE_Y_METERS, AIRBASE_HEIGHT_METERS],
        "landscape_layers": list(LANDSCAPE_LAYERS),
        "hydrology_plan": "Hydrology/AetherFlight_Hydrology.json",
        "import_guard": "Use 4033x4033, XY 1190.476190, Z 1093.75; do not pad or clip",
    }
    (OUTPUT / "AetherFlight_Landscape_Metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
