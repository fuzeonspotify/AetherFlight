import unreal

EXPECTED_COMPONENTS = {
    "CinematicPineTrees": "DZ Pine",
    "CinematicAspenTrees": "DZ Aspen",
    "CinematicOakTrees": "DZ Cork Oak",
    "CinematicCoastalTrees": "DZ Coconut/Palm",
    "CinematicShrubPrimary": "GV Shrub A",
    "CinematicShrubSecondary": "GV Shrub B",
    "CinematicGroundPlants": "Nanite Abelia",
    "CinematicRocks": "Rock",
}


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_game_world()
    if not world:
        unreal.log_error(
            "AETHER_VARIANT_AUDIT_ERROR=No PIE game world. Press Play first, wait for environment generation, then run this script."
        )
        return

    actors = list(unreal.ActorIterator(world))
    environment_actors = [
        actor
        for actor in actors
        if "AetherVerifiedEnvironmentActor" in actor.get_class().get_name()
        or "AetherVerifiedEnvironmentActor" in actor.get_name()
    ]

    if not environment_actors:
        unreal.log_error(
            "AETHER_VARIANT_AUDIT_ERROR=No AetherVerifiedEnvironmentActor exists in PIE. Launch with BUILD_AND_RUN_AETHER_MAP_WIDE_ENVIRONMENT.ps1."
        )
        return

    actor = environment_actors[0]
    components = actor.get_components_by_class(
        unreal.HierarchicalInstancedStaticMeshComponent
    )
    by_name = {component.get_name(): component for component in components}

    unreal.log_warning("AETHER_RUNTIME_VARIANT_AUDIT")
    unreal.log_warning("=" * 88)
    unreal.log_warning(f"World={world.get_name()} Actor={actor.get_name()}")

    loaded_pass = True
    spawned_pass = True
    total_instances = 0

    for component_name, label in EXPECTED_COMPONENTS.items():
        component = by_name.get(component_name)
        if not component:
            loaded_pass = False
            spawned_pass = False
            unreal.log_error(
                f"MISSING_COMPONENT | {label} | expected_component={component_name}"
            )
            continue

        mesh = component.get_editor_property("static_mesh")
        count = int(component.get_instance_count())
        total_instances += count
        mesh_path = mesh.get_path_name() if mesh else "None"
        loaded = mesh is not None
        spawned = count > 0
        loaded_pass = loaded_pass and loaded
        spawned_pass = spawned_pass and spawned

        unreal.log_warning(
            f"{label:18s} | loaded={'YES' if loaded else 'NO ':3s} | "
            f"instances={count:4d} | component={component_name} | mesh={mesh_path}"
        )

    unreal.log_warning("-" * 88)
    unreal.log_warning(
        f"AETHER_VARIANTS_LOADED={'PASS' if loaded_pass else 'FAIL'}"
    )
    unreal.log_warning(
        f"AETHER_VARIANTS_SPAWNED_IN_CURRENT_RING={'PASS' if spawned_pass else 'PARTIAL'}"
    )
    unreal.log_warning(f"AETHER_VARIANT_TOTAL_INSTANCES={total_instances}")
    unreal.log_warning(
        "A PARTIAL spawn result does not mean an asset is missing. The normal biome rules can "
        "produce zero instances of a species in the current local ring because selection depends "
        "on elevation, slope, moisture, and coastal conditions."
    )


main()
