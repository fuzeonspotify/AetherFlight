"""Destructively replace AetherWorld's old Landscape setup with the procedural world + biomes.

Run from Tools > Execute Python Script while /Game/Maps/AetherWorld is open.
For World Partition maps, load the full terrain region first so every streaming
Landscape proxy is available for deletion.
"""

from __future__ import annotations

from pathlib import Path
import runpy

import unreal


TITLE = "Aether Fresh Procedural World"
WORLD_LABEL = "Aether Fresh Procedural World"
BIOME_INSTALLER = Path(unreal.Paths.project_content_dir()) / "Python" / "InstallProceduralBiomes.py"

LANDSCAPE_CLASS_NAMES = (
    "LandscapeProxy",
    "LandscapeStreamingProxy",
    "Landscape",
    "LandscapeSplineActor",
    "LandscapeSplineMeshesActor",
    "LandscapeGizmoActor",
    "LandscapeMeshProxyActor",
    "LandscapePlaceholder",
)

DIRECTOR_CLASS_NAMES = (
    "ProceduralWorldDirector",
    "ProceduralBiomeDirector",
)


def log(message: str) -> None:
    unreal.log(f"[Aether Fresh World] {message}")


def available_actor_types(class_names: tuple[str, ...]) -> tuple[type, ...]:
    classes = []
    for class_name in class_names:
        actor_type = getattr(unreal, class_name, None)
        if isinstance(actor_type, type):
            classes.append(actor_type)
    return tuple(classes)


def destroy_old_terrain_and_directors(
    actor_subsystem: unreal.EditorActorSubsystem,
) -> tuple[int, int]:
    landscape_types = available_actor_types(LANDSCAPE_CLASS_NAMES)
    director_types = available_actor_types(DIRECTOR_CLASS_NAMES)

    landscapes = []
    directors = []
    for actor in actor_subsystem.get_all_level_actors():
        if landscape_types and isinstance(actor, landscape_types):
            landscapes.append(actor)
        elif director_types and isinstance(actor, director_types):
            directors.append(actor)

    actors_to_destroy = [*landscapes, *directors]
    if actors_to_destroy and not actor_subsystem.destroy_actors(actors_to_destroy):
        raise RuntimeError("Unreal could not delete one or more old terrain actors.")

    log(f"Deleted {len(landscapes)} Landscape-related actor(s).")
    log(f"Deleted {len(directors)} old world/biome director actor(s).")
    return len(landscapes), len(directors)


def spawn_fresh_world(
    actor_subsystem: unreal.EditorActorSubsystem,
):
    world_type = getattr(unreal, "ProceduralWorldDirector", None)
    if world_type is None:
        raise RuntimeError(
            "ProceduralWorldDirector is unavailable. Build the C++ project and reopen Unreal."
        )

    world_actor = actor_subsystem.spawn_actor_from_class(
        world_type,
        unreal.Vector(0.0, 0.0, 0.0),
        unreal.Rotator(0.0, 0.0, 0.0),
    )
    if world_actor is None:
        raise RuntimeError("Unreal could not spawn the fresh procedural world actor.")

    world_actor.set_actor_label(WORLD_LABEL)
    world_actor.set_editor_property("is_spatially_loaded", False)
    world_actor.set_editor_property("world_seed", 1847)
    world_actor.set_editor_property("terrain_tiles_per_axis", 8)
    world_actor.set_editor_property("terrain_tile_resolution", 129)
    world_actor.set_editor_property("terrain_size_kilometers", 48.0)

    # The dedicated biome actor replaces the old hardcoded tree/rock pass.
    world_actor.set_editor_property("forest_instance_budget", 0)
    world_actor.set_editor_property("rock_instance_budget", 0)
    world_actor.ensure_world_generated()
    return world_actor


def verify_no_loaded_landscapes(
    actor_subsystem: unreal.EditorActorSubsystem,
) -> None:
    landscape_types = available_actor_types(LANDSCAPE_CLASS_NAMES)
    if not landscape_types:
        return

    remaining = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if isinstance(actor, landscape_types)
    ]
    if remaining:
        labels = ", ".join(actor.get_actor_label() for actor in remaining[:8])
        raise RuntimeError(
            "Landscape actors remain after reset: "
            f"{labels}. Load all World Partition cells and run the reset again."
        )


def install_biomes() -> None:
    if not BIOME_INSTALLER.is_file():
        raise RuntimeError(f"Missing biome installer: {BIOME_INSTALLER}")

    runpy.run_path(str(BIOME_INSTALLER), run_name="__main__")


def main() -> None:
    answer = unreal.EditorDialog.show_message(
        TITLE,
        "This permanently removes every loaded Landscape, Landscape Streaming Proxy, "
        "old procedural world director, and old biome director from the open level.\n\n"
        "It then creates one new 48 km procedural terrain and rebuilds the procedural "
        "biomes on top of it.\n\n"
        "Continue?",
        unreal.AppMsgType.YES_NO,
    )
    if answer != unreal.AppReturnType.YES:
        log("Reset cancelled.")
        return

    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_subsystem.is_in_play_in_editor():
        raise RuntimeError("Stop Play In Editor before running the fresh-world reset.")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor_subsystem.clear_actor_selection_set()

    deleted_landscapes, deleted_directors = destroy_old_terrain_and_directors(
        actor_subsystem
    )
    verify_no_loaded_landscapes(actor_subsystem)
    spawn_fresh_world(actor_subsystem)
    install_biomes()

    log(
        "Fresh world complete: "
        f"{deleted_landscapes} Landscape actor(s) and "
        f"{deleted_directors} old director actor(s) removed."
    )


if __name__ == "__main__":
    main()
