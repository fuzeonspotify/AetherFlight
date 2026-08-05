"""Stage 15B river-biome installer compatibility launcher V4 for UE 5.8.1.

V4 keeps the guarded original installer but patches four verified compatibility issues:
1. UE exposes LESSER_OR_EQUAL instead of LESS_OR_EQUAL.
2. PCG selector helpers are used directly to avoid derived-struct wrapper ensures.
3. PCGVolume's non-unit default actor scale is preserved and bounds are calibrated.
4. Lightweight shrub L1 meshes replace multi-million-triangle full shrub meshes.

On failure, the unsaved graph is not force-deleted while native graph nodes still
reference it. Close the editor without saving to release it safely.
"""

from pathlib import Path
import unreal

SOURCE_PATH = Path(__file__).with_name("RUN_THIS_STAGE15B_INSTALL_RIVER_BIOME.py")


def replace_exact(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Stage15B V4 compatibility patch expected exactly one {label} block; found {count}"
        )
    return source.replace(old, new, 1)


def main():
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"Original Stage 15B installer is missing: {SOURCE_PATH}")

    source = SOURCE_PATH.read_text(encoding="utf-8")

    old_enum = '("LESS_OR_EQUAL", "LESS_THAN_OR_EQUAL", "LESS_EQUAL", "LESS"),'
    new_enum = """(
                "LESSER_OR_EQUAL",
                "LESS_OR_EQUAL",
                "LESS_THAN_OR_EQUAL",
                "LESS_EQUAL",
                "LESSER",
                "LESS",
            ),"""
    source = replace_exact(source, old_enum, new_enum, "less-than comparison enum")

    old_attribute_selector = """def selector_for_attribute(name):
    selector = unreal.PCGAttributePropertyInputSelector()
    if not selector.set_attribute_name(unreal.Name(name)):
        raise RuntimeError(f"Could not select attribute {name}")
    return selector
"""
    new_attribute_selector = """def selector_for_attribute(name):
    selector = unreal.PCGAttributePropertyInputSelector()
    helper = getattr(unreal, "PCGAttributePropertySelectorBlueprintHelpers", None)
    if helper is None:
        raise RuntimeError("PCG selector Blueprint helpers are unavailable")
    try:
        helper.set_attribute_name(selector, unreal.Name(name), True)
        return selector
    except Exception as exc:
        raise RuntimeError(f"Could not select attribute {name}: {exc}")
"""
    source = replace_exact(
        source, old_attribute_selector, new_attribute_selector, "attribute selector"
    )

    old_density_selector = """def selector_for_density(output=False):
    selector_type = unreal.PCGAttributePropertyOutputSelector if output else unreal.PCGAttributePropertyInputSelector
    selector = selector_type()
    density = enum_value(unreal.PCGPointProperties, ("DENSITY",))
    if not selector.set_point_property(density):
        raise RuntimeError("Could not select PCG point Density property")
    return selector
"""
    new_density_selector = """def selector_for_density(output=False):
    selector_type = unreal.PCGAttributePropertyOutputSelector if output else unreal.PCGAttributePropertyInputSelector
    selector = selector_type()
    density = enum_value(unreal.PCGPointProperties, ("DENSITY",))
    helper = getattr(unreal, "PCGAttributePropertySelectorBlueprintHelpers", None)
    if helper is None:
        raise RuntimeError("PCG selector Blueprint helpers are unavailable")
    try:
        helper.set_point_property(selector, density, True)
        return selector
    except Exception as exc:
        raise RuntimeError(f"Could not select PCG point Density property: {exc}")
"""
    source = replace_exact(
        source, old_density_selector, new_density_selector, "density selector"
    )

    shrub_replacements = {
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_A/GV_Vol7_Shrub_A_full_type1.GV_Vol7_Shrub_A_full_type1":
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_A/GV_Vol7_Shrub_A_type1_L1.GV_Vol7_Shrub_A_type1_L1",
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_B/GV_Vol7_Shrub_B_full_type1.GV_Vol7_Shrub_B_full_type1":
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_B/GV_Vol7_Shrub_B_type1_L1.GV_Vol7_Shrub_B_type1_L1",
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_C/GV_Vol7_Shrub_C_full_type1.GV_Vol7_Shrub_C_full_type1":
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_C/GV_Vol7_Shrub_C_type1_L1.GV_Vol7_Shrub_C_type1_L1",
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_D/GV_Vol7_Shrub_D_full_type1.GV_Vol7_Shrub_D_full_type1":
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_D/GV_Vol7_Shrub_D_type1_L1.GV_Vol7_Shrub_D_type1_L1",
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_E/GV_Vol7_Shrub_E_full_type1_A.GV_Vol7_Shrub_E_full_type1_A":
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_E/GV_Vol7_Shrub_E_type1_A_L1.GV_Vol7_Shrub_E_type1_A_L1",
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_F/GV_Vol7_Shrub_F_full_type1_B.GV_Vol7_Shrub_F_full_type1_B":
        "/Game/GV_FreeShrubsPack/Meshes/Shrubs/Wind/Shrub_F/GV_Vol7_Shrub_F_type1_B_L1.GV_Vol7_Shrub_F_type1_B_L1",
    }
    for old_path, new_path in shrub_replacements.items():
        source = replace_exact(source, old_path, new_path, f"shrub mesh {old_path}")

    old_volume_scale = """    _, initial_extent = actor_bounds(actor)
    values = (float(initial_extent.x), float(initial_extent.y), float(initial_extent.z))
    if min(values) <= 0.01:
        raise RuntimeError(f"PCGVolume default bounds are invalid: {initial_extent}")
    scale = unreal.Vector(
        float(desired_extent.x) / values[0],
        float(desired_extent.y) / values[1],
        float(desired_extent.z) / values[2],
    )
    actor.set_actor_scale3d(scale)
    actor.set_actor_location(center, False, False)
"""
    new_volume_scale = """    _, initial_extent = actor_bounds(actor)
    initial_scale = actor.get_actor_scale3d()
    values = (float(initial_extent.x), float(initial_extent.y), float(initial_extent.z))
    scale_values = (float(initial_scale.x), float(initial_scale.y), float(initial_scale.z))
    if min(values) <= 0.01 or min(scale_values) <= 0.000001:
        raise RuntimeError(
            f"PCGVolume default bounds/scale are invalid: extent={initial_extent} scale={initial_scale}"
        )
    scale = unreal.Vector(
        scale_values[0] * float(desired_extent.x) / values[0],
        scale_values[1] * float(desired_extent.y) / values[1],
        scale_values[2] * float(desired_extent.z) / values[2],
    )
    actor.set_actor_scale3d(scale)
    actor.set_actor_location(center, False, False)
    lines.append(f"VOLUME_INITIAL_EXTENT={initial_extent}")
    lines.append(f"VOLUME_INITIAL_SCALE={initial_scale}")
"""
    source = replace_exact(
        source, old_volume_scale, new_volume_scale, "PCGVolume initial scale calibration"
    )

    old_bounds_validation = """    bounds_origin, bounds_extent = actor_bounds(actor)
    tolerance = 100.0
    if (
        float(bounds_extent.x) + tolerance < float(desired_extent.x)
        or float(bounds_extent.y) + tolerance < float(desired_extent.y)
        or float(bounds_extent.z) + tolerance < float(desired_extent.z)
    ):
        raise RuntimeError(
            f"PCGVolume bounds did not reach requested extent. actual={bounds_extent} requested={desired_extent}"
        )

    lines.append(f"VOLUME_CENTER={center}")
"""
    new_bounds_validation = """    tolerance = 100.0
    bounds_origin, bounds_extent = actor_bounds(actor)
    for calibration_index in range(3):
        short_x = float(bounds_extent.x) + tolerance < float(desired_extent.x)
        short_y = float(bounds_extent.y) + tolerance < float(desired_extent.y)
        short_z = float(bounds_extent.z) + tolerance < float(desired_extent.z)
        if not (short_x or short_y or short_z):
            break
        current_scale = actor.get_actor_scale3d()
        current_values = (
            max(float(bounds_extent.x), 0.01),
            max(float(bounds_extent.y), 0.01),
            max(float(bounds_extent.z), 0.01),
        )
        corrected_scale = unreal.Vector(
            float(current_scale.x) * float(desired_extent.x) / current_values[0],
            float(current_scale.y) * float(desired_extent.y) / current_values[1],
            float(current_scale.z) * float(desired_extent.z) / current_values[2],
        )
        if max(
            abs(float(corrected_scale.x)),
            abs(float(corrected_scale.y)),
            abs(float(corrected_scale.z)),
        ) > 1000000.0:
            raise RuntimeError(f"PCGVolume calibrated scale is unreasonable: {corrected_scale}")
        actor.set_actor_scale3d(corrected_scale)
        actor.set_actor_location(center, False, False)
        bounds_origin, bounds_extent = actor_bounds(actor)
        lines.append(
            f"VOLUME_CALIBRATION_{calibration_index + 1}=scale:{corrected_scale} extent:{bounds_extent}"
        )

    if (
        float(bounds_extent.x) + tolerance < float(desired_extent.x)
        or float(bounds_extent.y) + tolerance < float(desired_extent.y)
        or float(bounds_extent.z) + tolerance < float(desired_extent.z)
    ):
        raise RuntimeError(
            f"PCGVolume bounds did not reach requested extent after calibration. "
            f"actual={bounds_extent} requested={desired_extent}"
        )
    scale = actor.get_actor_scale3d()

    lines.append(f"VOLUME_CENTER={center}")
"""
    source = replace_exact(
        source, old_bounds_validation, new_bounds_validation, "PCGVolume bounds validation"
    )

    old_failure_cleanup = """        if graph_created:
            try:
                unreal.EditorAssetLibrary.delete_asset(GRAPH_OBJECT_PATH)
            except Exception:
                pass
        raise
"""
    new_failure_cleanup = """        if graph_created:
            unreal.log_warning(
                "AETHER_STAGE15B_UNSAVED_GRAPH_LEFT_IN_MEMORY=TRUE; "
                "close Unreal without saving before retrying"
            )
        raise
"""
    source = replace_exact(
        source, old_failure_cleanup, new_failure_cleanup, "failure graph cleanup"
    )

    compile(source, str(SOURCE_PATH), "exec")

    unreal.log_warning("AETHER_STAGE15B_INSTALLER_COMPATIBILITY=V4")
    unreal.log_warning("AETHER_STAGE15B_ENUM_FIX=LESSER_OR_EQUAL")
    unreal.log_warning("AETHER_STAGE15B_SELECTOR_FIX=BLUEPRINT_HELPERS")
    unreal.log_warning("AETHER_STAGE15B_VOLUME_SCALE_FIX=PRESERVE_DEFAULT_AND_CALIBRATE")
    unreal.log_warning("AETHER_STAGE15B_SHRUB_POLICY=LOD1_ONLY")
    unreal.log_warning("AETHER_STAGE15B_FAILURE_POLICY=NO_FORCE_DELETE")
    unreal.log_warning("AETHER_STAGE15B_PATCHED_SOURCE_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
        "__package__": None,
    }
    exec(compile(source, str(SOURCE_PATH), "exec"), namespace, namespace)


main()
