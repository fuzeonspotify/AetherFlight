"""Create spline Water Body rivers and lakes from the generated hydrology plan.

The terrain generator already cuts the beds, so these Water Bodies do not
modify Landscape height. They use Unreal's Water mesh/physics pipeline and can
be regenerated safely; only actors tagged AetherGeneratedHydrology are replaced.
"""

import json
import math
from pathlib import Path

import unreal


LOG = "[Aether Hydrology v1]"
TAG = unreal.Name("AetherGeneratedHydrology")
PLAN = (
    Path(unreal.Paths.project_dir())
    / "SourceAssets" / "ProductionTerrain" / "Hydrology"
    / "AetherFlight_Hydrology.json"
)


def log(message):
    unreal.log(f"{LOG} {message}")


def optional_property(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:
        return False


def water_spline(actor):
    for method_name in ("get_water_spline", "get_spline_component"):
        method = getattr(actor, method_name, None)
        if callable(method):
            try:
                result = method()
                if result:
                    return result
            except Exception:
                pass
    component_class = getattr(unreal, "WaterSplineComponent", None)
    if component_class:
        try:
            return actor.get_component_by_class(component_class)
        except Exception:
            pass
    return actor.get_component_by_class(unreal.SplineComponent)


def configure_water(actor):
    actor.tags = list(actor.tags) + ([TAG] if TAG not in actor.tags else [])
    actor.set_folder_path("Aether/GeneratedHydrology")
    component_class = getattr(unreal, "WaterBodyComponent", None)
    component = actor.get_component_by_class(component_class) if component_class else None
    target = component or actor
    # Beds are already present in the .r16. Reapplying a Water brush here would
    # double-carve the landscape and recreate vertical cuts.
    optional_property(target, "affects_landscape", False)
    optional_property(actor, "affects_landscape", False)
    optional_property(target, "generate_collisions", True)
    # Keep the Water plugin's river/lake transition materials. The separate
    # Aether Single Layer Water material is intentionally reserved for ocean
    # swells; applying it here would put multi-metre Gerstner waves in lakes.


def replace_old_generated_actors(actor_subsystem):
    removed = 0
    for actor in list(actor_subsystem.get_all_level_actors()):
        if TAG in actor.tags:
            actor_subsystem.destroy_actor(actor)
            removed += 1
    return removed


def add_local_points(spline, points, closed):
    spline.clear_spline_points(False)
    for point in points:
        spline.add_spline_point(
            unreal.Vector(float(point[0]), float(point[1]), float(point[2])),
            unreal.SplineCoordinateSpace.LOCAL,
            False,
        )
    spline.set_closed_loop(closed, True)


def create_lake(actor_subsystem, definition):
    lake_class = getattr(unreal, "WaterBodyLake", None)
    if lake_class is None:
        raise RuntimeError("WaterBodyLake is unavailable; confirm the Water plugin is enabled.")
    cx, cy = definition["center_m"]
    rx, ry = definition["radius_m"]
    z = float(definition["surface_z_m"])
    actor = actor_subsystem.spawn_actor_from_class(
        lake_class, unreal.Vector(cx * 100.0, cy * 100.0, z * 100.0)
    )
    actor.set_actor_label(f"Aether_{definition['name']}")
    configure_water(actor)
    spline = water_spline(actor)
    if not spline:
        raise RuntimeError(f"No Water spline was found for {definition['name']}")
    points = []
    for index in range(20):
        angle = index * math.tau / 20.0
        # Mild harmonics prevent a perfect procedural oval shoreline.
        wobble = 1.0 + 0.07 * math.sin(angle * 3.0 + 0.8) + 0.035 * math.sin(angle * 7.0)
        points.append((math.cos(angle) * rx * 100.0 * wobble,
                       math.sin(angle) * ry * 100.0 * wobble, 0.0))
    add_local_points(spline, points, True)
    return actor


def create_river(actor_subsystem, definition):
    river_class = getattr(unreal, "WaterBodyRiver", None)
    if river_class is None:
        raise RuntimeError("WaterBodyRiver is unavailable; confirm the Water plugin is enabled.")
    source = definition["points"][0]
    actor = actor_subsystem.spawn_actor_from_class(
        river_class, unreal.Vector(source[0] * 100.0, source[1] * 100.0, source[2] * 100.0)
    )
    actor.set_actor_label(f"Aether_{definition['name']}")
    configure_water(actor)
    spline = water_spline(actor)
    if not spline:
        raise RuntimeError(f"No Water spline was found for {definition['name']}")
    local_points = [
        ((point[0] - source[0]) * 100.0,
         (point[1] - source[1]) * 100.0,
         (point[2] - source[2]) * 100.0)
        for point in definition["points"]
    ]
    add_local_points(spline, local_points, False)
    width_scale = max(float(definition["width_m"]) * 100.0 / 2048.0, 0.5)
    for index in range(len(local_points)):
        try:
            spline.set_scale_at_spline_point(
                index, unreal.Vector(width_scale, 1.0, 1.0), False
            )
        except Exception:
            break
    spline.update_spline()
    return actor


def ensure_water_zone(actor_subsystem):
    zone_class = getattr(unreal, "WaterZone", None)
    if zone_class is None:
        return None
    for actor in actor_subsystem.get_all_level_actors():
        if isinstance(actor, zone_class):
            return actor
    zone = actor_subsystem.spawn_actor_from_class(zone_class, unreal.Vector(0.0, 0.0, 0.0))
    zone.set_actor_label("Aether_WaterZone")
    optional_property(zone, "zone_extent", unreal.Vector2D(5200000.0, 5200000.0))
    zone.set_folder_path("Aether/GeneratedHydrology")
    return zone


def main():
    if not PLAN.is_file():
        raise RuntimeError(
            f"Missing {PLAN}. Run GENERATE_PRODUCTION_WORLD.cmd before this installer."
        )
    data = json.loads(PLAN.read_text(encoding="utf-8"))
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    removed = replace_old_generated_actors(actor_subsystem)
    ensure_water_zone(actor_subsystem)
    lakes = [create_lake(actor_subsystem, item) for item in data.get("lakes", [])]
    rivers = [create_river(actor_subsystem, item) for item in data.get("rivers", [])]
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    message = (
        f"Created {len(lakes)} lakes and {len(rivers)} rivers.\n"
        f"Replaced {removed} previously generated hydrology actors.\n\n"
        "The existing Aether ocean remains the sea-level ocean. River/lake beds come from the v2 heightmap."
    )
    log(message.replace("\n", " | "))
    unreal.EditorDialog.show_message("Aether Hydrology v1", message, unreal.AppMsgType.OK)


if __name__ == "__main__":
    main()
