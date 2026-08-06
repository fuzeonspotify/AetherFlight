"""Offset-aware fallback grounding for the Stage 13 river environment.

The first Stage 13 install proved that unattended Mesh Terrain traces return no
hits in this project. The original fallback placed every instance at a fixed
+650 cm relative to the channel spline, which visibly floated inner-bank plants
and rocks. This module preserves the deterministic layout while approximating
the authored Stage 09 channel cross-section:

* inner bank starts just above the +300 cm water surface;
* elevation rises smoothly across the 32 m Stage 09 falloff;
* outer-bank placement approaches the original terrain height;
* rocks are embedded slightly rather than balanced exactly on their bounds.
"""

import random
import unreal

import AetherRiverEnvironmentPlacement_UE58 as _base
from AetherRiverEnvironmentCommon_UE58 import (
    EXCLUSION_PLATEAU_CM,
    add_component_to_actor,
    record,
)

RANDOM_SEED = 130013
STATION_SPACING_CM = 2600.0
EDGE_MARGIN_CM = 2200.0

# Stage 09 authored channel profile.
CHANNEL_PLATEAU_CM = 1400.0
CHANNEL_FALLOFF_CM = 3200.0
INNER_BANK_LIFT_CM = 340.0
OUTER_BANK_LIFT_CM = 600.0


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _smoothstep(value):
    value = _clamp(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def fallback_bank_lift_cm(offset_cm):
    t = (float(offset_cm) - CHANNEL_PLATEAU_CM) / CHANNEL_FALLOFF_CM
    alpha = _smoothstep(t)
    return INNER_BANK_LIFT_CM + (OUTER_BANK_LIFT_CM - INNER_BANK_LIFT_CM) * alpha


def grounded_base_offset(mesh, scale_value, category):
    base_offset = float(_base.mesh_base_offset(mesh, scale_value))
    try:
        bounds = mesh.get_bounds()
        scaled_height = float(bounds.box_extent.z) * 2.0 * float(scale_value)
    except Exception:
        scaled_height = 0.0

    if category == "rock":
        # Natural rocks should penetrate the bank slightly. Cap the embed so a
        # very large source mesh cannot disappear into the terrain.
        embed = min(90.0, max(18.0, scaled_height * 0.12))
        return max(0.0, base_offset - embed)
    if category == "ground":
        return max(0.0, base_offset - min(12.0, scaled_height * 0.025))
    return max(0.0, base_offset - min(8.0, scaled_height * 0.015))


def place_environment_instances(world, source_spline, environment_actor, mesh_sets, ignored_actors, lines):
    rng = random.Random(RANDOM_SEED)
    hism_class = getattr(unreal, "HierarchicalInstancedStaticMeshComponent", None)
    if not hism_class:
        raise RuntimeError("unreal.HierarchicalInstancedStaticMeshComponent is unavailable")

    components = {}
    counts = {}
    for category, entries in mesh_sets.items():
        for path, mesh in entries:
            component = add_component_to_actor(environment_actor, hism_class, lines)
            _base.configure_hism(component, mesh, category, lines)
            components[(category, path)] = component
            counts[(category, path)] = 0

    length = float(source_spline.get_spline_length())
    world_space = unreal.SplineCoordinateSpace.WORLD
    station_count = max(1, int((length - 2.0 * EDGE_MARGIN_CM) / STATION_SPACING_CM) + 1)
    trace_hits = 0
    fallbacks = 0
    closest_offset = float("inf")
    fallback_lifts = []

    def place(category, station_distance, side, offset_min, offset_max, scale_min, scale_max):
        nonlocal trace_hits, fallbacks, closest_offset
        entries = mesh_sets[category]
        if not entries:
            return

        sampled_distance = max(
            EDGE_MARGIN_CM,
            min(length - EDGE_MARGIN_CM, station_distance + rng.uniform(-650.0, 650.0)),
        )
        center = source_spline.get_location_at_distance_along_spline(sampled_distance, world_space)
        right = source_spline.get_right_vector_at_distance_along_spline(sampled_distance, world_space)
        offset = rng.uniform(offset_min, offset_max)
        closest_offset = min(closest_offset, offset)

        fallback_lift = fallback_bank_lift_cm(offset)
        fallback_lifts.append(fallback_lift)
        candidate = unreal.Vector(
            float(center.x) + float(right.x) * float(side) * offset,
            float(center.y) + float(right.y) * float(side) * offset,
            float(center.z) + fallback_lift,
        )

        ground, normal = _base.trace_ground(world, candidate, ignored_actors, lines)
        if normal is not None:
            trace_hits += 1
        else:
            fallbacks += 1

        path, mesh = entries[rng.randrange(len(entries))]
        component = components[(category, path)]
        scale_value = rng.uniform(scale_min, scale_max)
        location = unreal.Vector(
            float(ground.x),
            float(ground.y),
            float(ground.z) + grounded_base_offset(mesh, scale_value, category),
        )

        if category == "rock":
            rotation = unreal.Rotator(
                rng.uniform(-9.0, 9.0),
                rng.uniform(0.0, 360.0),
                rng.uniform(-9.0, 9.0),
            )
        else:
            rotation = unreal.Rotator(0.0, rng.uniform(0.0, 360.0), 0.0)

        _base.add_instance(
            component,
            _base.make_transform(
                location,
                rotation,
                unreal.Vector(scale_value, scale_value, scale_value),
            ),
        )
        counts[(category, path)] += 1

    for station_index in range(station_count):
        distance = min(
            EDGE_MARGIN_CM + station_index * STATION_SPACING_CM,
            length - EDGE_MARGIN_CM,
        )
        for side in (-1.0, 1.0):
            place("ground", distance, side, 1650.0, 3000.0, 0.72, 1.24)
            if station_index % 2 == 0:
                place("shrub", distance, side, 2100.0, 3900.0, 0.78, 1.22)
            if station_index % 3 == 0:
                place("rock", distance, side, 1500.0, 3600.0, 0.68, 1.35)
            if station_index % 4 == 1:
                place("ground", distance, side, 2000.0, 4200.0, 0.65, 1.12)

    total = sum(counts.values())
    if total <= 0:
        raise RuntimeError("No river environment instances were created")
    if closest_offset < EXCLUSION_PLATEAU_CM:
        raise RuntimeError(
            f"An environment instance was requested inside the full exclusion corridor: {closest_offset} cm"
        )

    minimum_lift = min(fallback_lifts) if fallback_lifts else 0.0
    maximum_lift = max(fallback_lifts) if fallback_lifts else 0.0
    record(lines, f"River station count={station_count}")
    record(lines, f"Ground trace placements={trace_hits}")
    record(lines, f"Offset-aware spline-height fallbacks={fallbacks}")
    record(lines, f"Fallback lift range cm={minimum_lift}..{maximum_lift}")
    record(lines, f"Closest requested environment offset cm={closest_offset}")
    record(lines, f"Total HISM instances={total}")
    for (category, path), count in sorted(counts.items()):
        record(lines, f"  {category.upper()} count={count} | {path}")

    for component in components.values():
        try:
            component.modify()
        except Exception:
            pass
    try:
        environment_actor.modify()
    except Exception:
        pass

    return total, counts, trace_hits, fallbacks, closest_offset
