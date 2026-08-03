#!/usr/bin/env python3
"""Generate the production Aether Flight landscape source assets.

The output is intentionally source-controlled/importable data rather than a
runtime procedural mesh.  A 4033-square, 16-bit heightmap is a valid Unreal
Landscape resolution and gives roughly 11.9 metre vertex spacing over 48 km.
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


def build_heightfield() -> np.ndarray:
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
    elevation = (
        -310.0
        + land * 380.0
        + mountain_envelope * ridge * (1_760.0 + 670.0 * detail)
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

    elevation = gaussian_filter(elevation, 0.55, mode="nearest")
    return np.clip(elevation, -420.0, MAX_ABSOLUTE_HEIGHT_METERS).astype(np.float32)


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


def build_weightmaps(height_m: np.ndarray) -> dict[str, np.ndarray]:
    meters_per_pixel = WORLD_SIZE_METERS / (height_m.shape[0] - 1)
    gy, gx = np.gradient(height_m, meters_per_pixel)
    slope = np.arctan(np.hypot(gx, gy))

    above_water = smoothstep(-3.0, 18.0, height_m)
    gentle = 1.0 - smoothstep(np.deg2rad(20.0), np.deg2rad(42.0), slope)
    cliff = smoothstep(np.deg2rad(27.0), np.deg2rad(50.0), slope)
    alpine = smoothstep(850.0, 1_550.0, height_m)
    snowline = smoothstep(1_560.0, 2_100.0, height_m)

    grass = above_water * gentle * (1.0 - smoothstep(920.0, 1_620.0, height_m))
    snow = above_water * snowline * (1.0 - cliff * 0.82)
    rock = above_water * np.maximum(cliff, alpine * 0.55) * (1.0 - snow * 0.55)
    scree = np.maximum(0.12, above_water * (0.28 + alpine * 0.48 + cliff * 0.25))
    scree += (1.0 - above_water) * 0.85

    weights = np.stack([grass, rock, scree, snow], axis=0).astype(np.float32)
    weights = gaussian_filter(weights, sigma=(0.0, 1.2, 1.2), mode="nearest")
    weights /= np.maximum(weights.sum(axis=0, keepdims=True), 1e-6)
    return {
        "Grass": weights[0],
        "Rock": weights[1],
        "Scree": weights[2],
        "Snow": weights[3],
    }


def save_weightmaps(weightmaps: dict[str, np.ndarray]) -> None:
    for name, weights in weightmaps.items():
        image = np.clip(np.rint(weights * 255.0), 0, 255).astype(np.uint8)
        save_png(image, WEIGHT_DIR / f"AetherFlight_{name}_4033.png")


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


def save_preview(height_m: np.ndarray, weights: dict[str, np.ndarray]) -> None:
    preview_size = 1600
    factor = preview_size / height_m.shape[0]
    h = zoom(height_m, factor, order=1, mode="nearest")[:preview_size, :preview_size]
    resized_weights = {
        key: zoom(value, factor, order=1, mode="nearest")[:preview_size, :preview_size]
        for key, value in weights.items()
    }
    palettes = {
        "Grass": np.array([0.115, 0.205, 0.075]),
        "Rock": np.array([0.275, 0.265, 0.235]),
        "Scree": np.array([0.30, 0.265, 0.20]),
        "Snow": np.array([0.84, 0.88, 0.90]),
    }
    color = sum(resized_weights[name][..., None] * palettes[name] for name in palettes)
    water = h <= 0.0
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
    for directory in (HEIGHT_DIR, WEIGHT_DIR, TEXTURE_DIR, PREVIEW_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    print("Generating eroded terrain at working resolution...")
    working_height = build_heightfield()
    print("Resampling to Unreal Landscape resolution 4033 x 4033...")
    height = resize_field(working_height, OUTPUT_RESOLUTION, order=3)
    save_heightmap(height)
    print("Computing landscape biome masks...")
    weights = build_weightmaps(height)
    save_weightmaps(weights)

    print("Generating tileable production surface textures...")
    save_surface_texture_set("Grass", (0.19, 0.255, 0.105), 101, (0.72, 0.94), 0.58, 7.0)
    save_surface_texture_set("Rock", (0.32, 0.305, 0.275), 202, (0.66, 0.90), 0.64, 10.0)
    save_surface_texture_set("Scree", (0.34, 0.285, 0.20), 303, (0.76, 0.97), 0.62, 8.0)
    save_surface_texture_set("Snow", (0.83, 0.87, 0.88), 404, (0.48, 0.82), 0.35, 5.0)
    save_macro_variation()
    save_preview(height, weights)

    metadata = {
        "seed": SEED,
        "resolution": OUTPUT_RESOLUTION,
        "world_size_meters": WORLD_SIZE_METERS,
        "xy_scale_centimeters": WORLD_SIZE_METERS * 100.0 / (OUTPUT_RESOLUTION - 1),
        "z_scale_centimeters": MAX_ABSOLUTE_HEIGHT_METERS * 100.0 / 256.0,
        "height_encoding": "32768 is sea level; positive range reaches +2800 m",
        "airbase_world_meters": [AIRBASE_X_METERS, AIRBASE_Y_METERS, AIRBASE_HEIGHT_METERS],
        "landscape_layers": ["Grass", "Rock", "Scree", "Snow"],
    }
    (OUTPUT / "AetherFlight_Landscape_Metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
