"""Repair duplicate/stale Landscape state before installing Aether World v2.

This pass never deletes a Landscape. It chooses one authoritative production
root, disables collision and game visibility on every legacy root/proxy, keeps
the active World Partition proxies in one LOD group, and applies the production
material. It also clears the retired ProceduralWorldDirector terrain and its
fallback foliage so nothing can render underneath the authored Landscape.
"""

import unreal


LOG = "[Aether Production World Repair v7]"
MATERIAL_PATH = "/Game/Aether/ProductionTerrain/M_Landscape_Production.M_Landscape_Production"
EXPECTED_XY_SCALE = 1190.476190
EXPECTED_Z_SCALE = 1093.75
ACTIVE_TAG = unreal.Name("AetherProductionLandscape")
LEGACY_TAG = unreal.Name("AetherLegacyLandscape")


def log(message):
    unreal.log(f"{LOG} {message}")


def optional_property(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:
        return False


def actor_bounds_area(actor):
    try:
        _origin, extent = actor.get_actor_bounds(False)
        return max(float(extent.x) * float(extent.y) * 4.0, 1.0)
    except Exception:
        scale = actor.get_actor_scale3d()
        return max(abs(float(scale.x) * float(scale.y)), 1.0)


def actor_guid(actor):
    try:
        return str(actor.get_editor_property("landscape_guid"))
    except Exception:
        return ""


def root_for(proxy):
    try:
        return proxy.get_landscape_actor()
    except Exception:
        return proxy if proxy.get_class().get_name() == "Landscape" else None


def production_score(actor):
    label = actor.get_actor_label().lower()
    score = 0.0
    if "production" in label:
        score += 1.0e22
    if "4033" in label:
        score += 5.0e21
    if "landscape2" in label:
        score += 1.0e20
    scale = actor.get_actor_scale3d()
    xy_error = abs(abs(scale.x) - EXPECTED_XY_SCALE) / EXPECTED_XY_SCALE
    z_error = abs(abs(scale.z) - EXPECTED_Z_SCALE) / EXPECTED_Z_SCALE
    if xy_error < 0.025:
        score += 2.0e21
    if z_error < 0.08:
        score += 1.0e21
    return score + actor_bounds_area(actor)


def mark_active(actor, material):
    actor.set_actor_hidden_in_game(False)
    actor.set_actor_enable_collision(True)
    try:
        actor.set_is_temporarily_hidden_in_editor(False)
    except Exception:
        pass
    tags = [tag for tag in actor.tags if tag != LEGACY_TAG]
    if ACTIVE_TAG not in tags:
        tags.append(ACTIVE_TAG)
    actor.tags = tags
    actor.set_editor_property("landscape_material", material)
    optional_property(actor, "lod_group_key", 1847)
    optional_property(actor, "nanite_skirt_enabled", True)
    optional_property(actor, "nanite_skirt_depth", 2.0)
    optional_property(actor, "lod0_screen_size", 0.62)
    optional_property(actor, "lod0_distribution_setting", 1.65)
    optional_property(actor, "lod_distribution_setting", 2.6)
    optional_property(actor, "is_editor_only_actor", False)
    actor.modify()


def mark_legacy(actor):
    actor.set_actor_enable_collision(False)
    actor.set_actor_hidden_in_game(True)
    try:
        actor.set_is_temporarily_hidden_in_editor(True)
    except Exception:
        pass
    tags = [tag for tag in actor.tags if tag != ACTIVE_TAG]
    if LEGACY_TAG not in tags:
        tags.append(LEGACY_TAG)
    actor.tags = tags
    # Reversible and non-destructive: the actor remains in the editor/map, but
    # cannot reappear when a World Partition cell streams into PIE or a build.
    optional_property(actor, "is_editor_only_actor", True)
    actor.modify()


def disable_runtime_placeholders(actors):
    disabled = []
    for actor in actors:
        actor_name = actor.get_name().lower()
        actor_label = actor.get_actor_label().lower()
        class_name = actor.get_class().get_name().lower()
        is_world_director = (
            "proceduralworlddirector" in actor_name
            or "proceduralworlddirector" in actor_label
            or "proceduralworlddirector" in class_name
        )
        if not is_world_director:
            continue

        try:
            procedural_components = actor.get_components_by_class(
                unreal.ProceduralMeshComponent
            )
        except Exception:
            procedural_components = []
        for component in procedural_components:
            component_name = component.get_name().lower()
            if "proceduralterrain" not in component_name:
                continue
            try:
                component.clear_all_mesh_sections()
            except Exception:
                pass
            try:
                component.set_visibility(False, True)
            except Exception:
                pass
            optional_property(component, "hidden_in_game", True)
            try:
                component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            except Exception:
                optional_property(component, "collision_enabled", unreal.CollisionEnabled.NO_COLLISION)
            component.modify()
            disabled.append(f"{actor.get_actor_label()}.{component.get_name()}")

        # These are the old single-species fallback clusters. The production
        # biome scatter actor owns foliage and rock instances now.
        try:
            instanced_components = actor.get_components_by_class(
                unreal.HierarchicalInstancedStaticMeshComponent
            )
        except Exception:
            instanced_components = []
        for component in instanced_components:
            component_name = component.get_name().lower()
            if component_name not in ("proceduralforest", "proceduralrocks"):
                continue
            try:
                component.clear_instances()
            except Exception:
                pass
            try:
                component.set_visibility(False, True)
            except Exception:
                pass
            optional_property(component, "hidden_in_game", True)
            component.modify()
            disabled.append(f"{actor.get_actor_label()}.{component.get_name()}")
    return disabled


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before repairing the production world.")
    except AttributeError:
        pass

    material = unreal.EditorAssetLibrary.load_asset(MATERIAL_PATH)
    if not isinstance(material, unreal.MaterialInterface):
        raise RuntimeError(
            "Production material is missing. Run InstallProductionLandscape.py first."
        )

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    placeholders = disable_runtime_placeholders(actors)
    proxies = [actor for actor in actors if isinstance(actor, unreal.LandscapeProxy)]
    roots = [actor for actor in proxies if actor.get_class().get_name() == "Landscape"]
    if not roots:
        raise RuntimeError("No root Landscape exists in the current level.")

    production = max(roots, key=production_score)
    production_guid = actor_guid(production)
    active = []
    legacy = []
    for proxy in proxies:
        same_root = root_for(proxy) == production
        same_guid = bool(production_guid) and actor_guid(proxy) == production_guid
        if proxy == production or same_root or same_guid:
            active.append(proxy)
            mark_active(proxy, material)
        else:
            legacy.append(proxy)
            mark_legacy(proxy)

    scale = production.get_actor_scale3d()
    warnings = []
    if abs(abs(scale.x) - EXPECTED_XY_SCALE) / EXPECTED_XY_SCALE > 0.025:
        warnings.append(
            f"XY scale is {scale.x:.3f}; expected {EXPECTED_XY_SCALE:.6f}. Reimport, do not rescale."
        )
    if abs(abs(scale.z) - EXPECTED_Z_SCALE) / EXPECTED_Z_SCALE > 0.08:
        warnings.append(
            f"Z scale is {scale.z:.3f}; expected {EXPECTED_Z_SCALE:.2f}."
        )
    try:
        if production.get_editor_property("enable_nanite"):
            warnings.append(
                "Nanite is enabled. Select the production Landscape and use Build > Build Landscape after every heightmap import."
            )
    except Exception:
        pass

    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    try:
        actor_subsystem.set_selected_level_actors([production])
    except Exception:
        pass

    warning_text = "\n".join(warnings) if warnings else "No scale or Nanite warnings."
    legacy_labels = ", ".join(sorted({actor.get_actor_label() for actor in legacy})) or "none"
    message = (
        f"Authoritative Landscape: {production.get_actor_label()}\n"
        f"Active Landscape proxies: {len(active)}\n"
        f"Legacy proxies disabled (not deleted): {len(legacy)}\n"
        f"Legacy labels: {legacy_labels}\n\n{warning_text}\n\n"
        f"Runtime placeholder components cleared: {len(placeholders)}\n\n"
        "The legacy roots are now editor-only, so their late-streamed World Partition proxies cannot overlap PIE. "
        "Rebuild the C++ module before testing so the runtime guard is active."
    )
    log(message.replace("\n", " | "))
    unreal.EditorDialog.show_message(
        "Aether Production World Repair v7", message, unreal.AppMsgType.OK
    )


if __name__ == "__main__":
    main()
