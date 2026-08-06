import random
import unreal

from AetherRiverEnvironmentCommon_UE58 import (
    EXCLUSION_PLATEAU_CM,
    add_component_to_actor,
    record,
    try_call_variants,
    try_set_property,
)

RANDOM_SEED = 130013
BANK_FALLBACK_LIFT_CM = 650.0
TRACE_HALF_HEIGHT_CM = 25000.0
STATION_SPACING_CM = 2600.0
EDGE_MARGIN_CM = 2200.0


def configure_hism(component, mesh, category, lines):
    setter = getattr(component, "set_static_mesh", None)
    if callable(setter):
        setter(mesh)
        record(lines, f"Set {component.get_name()} static mesh={mesh.get_path_name()}")
    else:
        try_set_property(component, ("static_mesh",), mesh, lines, required=True)
    try:
        component.clear_instances()
    except Exception:
        pass

    try_set_property(component, ("mobility",), unreal.ComponentMobility.STATIC, lines)
    try_set_property(component, ("cast_shadow",), category != "ground", lines)
    try_set_property(component, ("cast_dynamic_shadow",), category != "ground", lines)
    try_set_property(component, ("affect_distance_field_lighting",), category == "rock", lines)
    try_set_property(component, ("receives_decals",), True, lines)
    try_set_property(component, ("component_tags",), [unreal.Name(f"AetherRiver_{category}")], lines)

    collision_enum = getattr(unreal, "CollisionEnabled", None)
    if collision_enum:
        no_collision = getattr(collision_enum, "NO_COLLISION", None)
        if no_collision is not None:
            try_call_variants(component, ("set_collision_enabled",), ((no_collision,),), lines)

    start, end = {
        "ground": (4000, 45000),
        "shrub": (10000, 90000),
        "rock": (0, 180000),
    }[category]
    try_call_variants(component, ("set_cull_distances",), ((start, end),), lines)


def extract_hit(result):
    if result is None:
        return None
    if isinstance(result, tuple):
        if result and isinstance(result[0], bool) and not result[0]:
            return None
        for item in reversed(result):
            if item is None or isinstance(item, bool):
                continue
            if hasattr(item, "impact_point") or hasattr(item, "get_editor_property"):
                return item
        return None
    return result


def hit_property(hit, names):
    for name in names:
        try:
            value = getattr(hit, name)
            if value is not None:
                return value
        except Exception:
            pass
        try:
            value = hit.get_editor_property(name)
            if value is not None:
                return value
        except Exception:
            pass
    return None


def trace_ground(world, candidate, ignored_actors, lines):
    start = unreal.Vector(candidate.x, candidate.y, candidate.z + TRACE_HALF_HEIGHT_CM)
    end = unreal.Vector(candidate.x, candidate.y, candidate.z - TRACE_HALF_HEIGHT_CM)
    attempts = []
    try:
        attempts.append(
            unreal.SystemLibrary.line_trace_single(
                world,
                start,
                end,
                unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                False,
                ignored_actors,
                unreal.DrawDebugTrace.NONE,
                True,
            )
        )
    except Exception as exc:
        record(lines, f"Visibility trace warning={exc}")
    try:
        attempts.append(
            unreal.SystemLibrary.line_trace_single_by_profile(
                world,
                start,
                end,
                "BlockAll",
                False,
                ignored_actors,
                unreal.DrawDebugTrace.NONE,
                True,
            )
        )
    except Exception:
        pass

    for result in attempts:
        hit = extract_hit(result)
        if not hit:
            continue
        point = hit_property(hit, ("impact_point", "location"))
        if point:
            return point, hit_property(hit, ("impact_normal", "normal"))
    return candidate, None


def make_transform(location, rotation, scale):
    try:
        return unreal.Transform(location=location, rotation=rotation, scale=scale)
    except Exception:
        try:
            return unreal.Transform(location, rotation, scale)
        except Exception as exc:
            raise RuntimeError(f"Could not construct Transform: {exc}")


def add_instance(component, transform):
    method = getattr(component, "add_instance_world_space", None)
    if callable(method):
        return method(transform)
    method = getattr(component, "add_instance", None)
    if callable(method):
        try:
            return method(transform, True)
        except TypeError:
            return method(transform)
    raise RuntimeError(f"{component.get_name()} exposes no HISM add-instance method")


def mesh_base_offset(mesh, scale_value):
    try:
        bounds = mesh.get_bounds()
        minimum_z = float(bounds.origin.z) - float(bounds.box_extent.z)
        return max(0.0, -minimum_z * scale_value)
    except Exception:
        return 0.0


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
            configure_hism(component, mesh, category, lines)
            components[(category, path)] = component
            counts[(category, path)] = 0

    length = float(source_spline.get_spline_length())
    world_space = unreal.SplineCoordinateSpace.WORLD
    station_count = max(1, int((length - 2.0 * EDGE_MARGIN_CM) / STATION_SPACING_CM) + 1)
    trace_hits = 0
    fallbacks = 0
    closest_offset = float("inf")

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
        candidate = unreal.Vector(
            float(center.x) + float(right.x) * float(side) * offset,
            float(center.y) + float(right.y) * float(side) * offset,
            float(center.z) + BANK_FALLBACK_LIFT_CM,
        )
        ground, normal = trace_ground(world, candidate, ignored_actors, lines)
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
            float(ground.z) + mesh_base_offset(mesh, scale_value),
        )
        if category == "rock":
            rotation = unreal.Rotator(
                rng.uniform(-9.0, 9.0),
                rng.uniform(0.0, 360.0),
                rng.uniform(-9.0, 9.0),
            )
        else:
            rotation = unreal.Rotator(0.0, rng.uniform(0.0, 360.0), 0.0)
        add_instance(
            component,
            make_transform(
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

    record(lines, f"River station count={station_count}")
    record(lines, f"Ground trace placements={trace_hits}")
    record(lines, f"Controlled spline-height fallbacks={fallbacks}")
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
