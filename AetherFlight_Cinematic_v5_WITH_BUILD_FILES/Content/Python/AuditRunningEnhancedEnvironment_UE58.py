import unreal


def find_actor(world, class_name_fragment):
    for actor in unreal.ActorIterator(world):
        if class_name_fragment in actor.get_class().get_name():
            return actor
    return None


def component_map(actor):
    components = actor.get_components_by_class(
        unreal.HierarchicalInstancedStaticMeshComponent
    )
    return {component.get_name(): component for component in components}


def describe(component, label):
    if not component:
        unreal.log_error(f"MISSING_COMPONENT | {label}")
        return False, False, 0

    mesh = component.get_editor_property("static_mesh")
    count = int(component.get_instance_count())
    mesh_path = mesh.get_path_name() if mesh else "None"
    loaded = mesh is not None
    spawned = count > 0
    unreal.log_warning(
        f"{label:24s} | loaded={'YES' if loaded else 'NO ':3s} | "
        f"instances={count:5d} | component={component.get_name()} | mesh={mesh_path}"
    )
    return loaded, spawned, count


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_game_world()
    if not world:
        unreal.log_error(
            "AETHER_ENHANCED_AUDIT_ERROR=No PIE game world. Press Play first, wait 20 seconds, then run this script."
        )
        return

    actor = find_actor(world, "AetherEnhancedEnvironmentActor")
    if not actor:
        unreal.log_error(
            "AETHER_ENHANCED_AUDIT_ERROR=No AetherEnhancedEnvironmentActor. Launch with BUILD_AND_RUN_AETHER_MAP_WIDE_ENVIRONMENT.ps1."
        )
        return

    components = component_map(actor)
    expected = [
        ("NaniteSampleTreeA", "Nanite Acer Tree A"),
        ("NaniteSampleTreeB", "Nanite Acer Tree B"),
        ("NaniteAbeliaShrubs", "Nanite Abelia Shrubs"),
        ("NaniteLoliumGrass", "Nanite Lolium Grass"),
        ("NaniteOphiopogonGroundCover", "Nanite Ophiopogon"),
    ]

    unreal.log_warning("AETHER_ENHANCED_ENVIRONMENT_AUDIT")
    unreal.log_warning("=" * 112)
    unreal.log_warning(f"World={world.get_name()} Actor={actor.get_name()}")

    loaded_pass = True
    spawned_pass = True
    total_instances = 0

    for component_name, label in expected:
        loaded, spawned, count = describe(components.get(component_name), label)
        loaded_pass = loaded_pass and loaded
        spawned_pass = spawned_pass and spawned
        total_instances += count

    unreal.log_warning("-" * 112)
    rock_loaded = 0
    rock_spawned = 0
    rock_total = 0
    for index in range(1, 8):
        name = f"RockCollection04Variant{index:02d}"
        loaded, spawned, count = describe(
            components.get(name),
            f"Rock Collection 04 #{index}",
        )
        rock_loaded += int(loaded)
        rock_spawned += int(spawned)
        rock_total += count
        loaded_pass = loaded_pass and loaded
        spawned_pass = spawned_pass and spawned

    total_instances += rock_total
    unreal.log_warning("-" * 112)
    unreal.log_warning(
        f"AETHER_NANITE_PLANTS_LOADED={'PASS' if loaded_pass else 'FAIL'}"
    )
    unreal.log_warning(
        f"AETHER_ALL_7_ROCKS_LOADED={'PASS' if rock_loaded == 7 else 'FAIL'} ({rock_loaded}/7)"
    )
    unreal.log_warning(
        f"AETHER_ALL_7_ROCKS_SPAWNED={'PASS' if rock_spawned == 7 else 'PARTIAL'} ({rock_spawned}/7)"
    )
    unreal.log_warning(
        f"AETHER_ENHANCED_VARIANTS_SPAWNED={'PASS' if spawned_pass else 'PARTIAL'}"
    )
    unreal.log_warning(f"AETHER_ENHANCED_TOTAL_INSTANCES={total_instances}")
    unreal.log_warning(
        "Expected after the local ring finishes: both Acer trees > 0, Abelia/Lolium/Ophiopogon > 0, and every rock variant > 0."
    )


main()
