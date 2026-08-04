"""UE 5.8 compatibility fixes for the Stage 13 river environment installer.

This module patches the original Stage 13 helpers before the installer imports
them. It addresses API/data issues exposed by real project runs:

* ChannelName and SplineModifierWeightEntry are UStruct values. Logging either
  through UObject.get_name() can make a successful property assignment appear
  to have failed.
* Broad shrub keyword discovery can match editor helper/icon meshes in the
  GlobalFoliageActor folder instead of actual plant geometry.
"""

import unreal

import AetherRiverEnvironmentCommon_UE58 as _base


def _safe_record(lines, text):
    _base.record(lines, text)


def struct_set_property(value_struct, names, value, lines, required=False):
    """Set a UStruct field without invoking UObject-only logging methods."""
    errors = []
    for name in names:
        try:
            value_struct.set_editor_property(name, value)
            stored = value_struct.get_editor_property(name)
            _safe_record(
                lines,
                f"Set {type(value_struct).__name__}.{name}={stored} without UObject logging",
            )
            return name
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    if required:
        raise RuntimeError(f"Could not set any of {names}. Errors={errors}")
    _safe_record(
        lines,
        f"UStruct property not exposed or rejected: {type(value_struct).__name__} candidates={names}",
    )
    return None


def make_channel_name(channel_text, lines):
    """Construct ChannelName without routing the UStruct through UObject logging."""
    channel_class = getattr(unreal, "ChannelName", None)
    if channel_class is None:
        raise RuntimeError("unreal.ChannelName is unavailable")

    name_value = unreal.Name(channel_text)
    errors = []

    # UE 5.8 in this project successfully accepted a default-constructed
    # ChannelName followed by setting its `name` field during Stage 12.
    try:
        candidate = channel_class()
        for property_name in ("name", "channel_name", "value"):
            try:
                candidate.set_editor_property(property_name, name_value)
                stored = candidate.get_editor_property(property_name)
                _safe_record(
                    lines,
                    f"Set ChannelName.{property_name}={stored} without UObject logging",
                )
                _safe_record(lines, f"Constructed ChannelName candidate={candidate}")
                return candidate
            except Exception as exc:
                errors.append(f"default.{property_name}: {exc}")
    except Exception as exc:
        errors.append(f"default constructor: {exc}")

    for kwargs in (
        {"name": name_value},
        {"channel_name": name_value},
        {"value": name_value},
    ):
        try:
            candidate = channel_class(**kwargs)
            _safe_record(lines, f"Constructed ChannelName with kwargs={kwargs}: {candidate}")
            return candidate
        except Exception as exc:
            errors.append(f"constructor {tuple(kwargs)}: {exc}")

    try:
        candidate = channel_class(name_value)
        _safe_record(lines, f"Constructed positional ChannelName={candidate}")
        return candidate
    except Exception as exc:
        errors.append(f"positional constructor: {exc}")

    raise RuntimeError(
        f"Could not construct ChannelName for {channel_text}. Errors={errors}"
    )


def make_weight_entry(channel_text, lines):
    """Build and validate the complete SplineModifierWeightEntry safely."""
    entry_class = getattr(unreal, "SplineModifierWeightEntry", None)
    if entry_class is None:
        raise RuntimeError("unreal.SplineModifierWeightEntry is unavailable")

    entry = entry_class()
    _safe_record(lines, f"Created weight entry={entry}")

    channel_prop = struct_set_property(
        entry,
        ("weight_channel_name", "channel_name", "channel"),
        make_channel_name(channel_text, lines),
        lines,
        required=True,
    )
    value_prop = struct_set_property(
        entry,
        ("value", "weight", "weight_value", "channel_value", "target_value"),
        1.0,
        lines,
        required=True,
    )

    blend = _base.resolve_enum_member(
        "SplineWeightBlendMode",
        ("ALPHA_BLEND", "ALPHABLEND", "ALPHA", "MAX"),
        lines,
    )
    if blend is None:
        raise RuntimeError("SplineWeightBlendMode AlphaBlend could not be resolved")

    blend_prop = struct_set_property(
        entry,
        ("blend_mode", "weight_blend_mode"),
        blend,
        lines,
        required=True,
    )

    stored_channel = entry.get_editor_property(channel_prop)
    stored_value = float(entry.get_editor_property(value_prop))
    stored_blend = entry.get_editor_property(blend_prop)
    _safe_record(lines, f"Validated weight entry channel={stored_channel}")
    _safe_record(lines, f"Validated weight entry value={stored_value}")
    _safe_record(lines, f"Validated weight entry blend={stored_blend}")

    if abs(stored_value - 1.0) > 0.001:
        raise RuntimeError(f"Weight entry value validation failed: {stored_value}")

    return entry, channel_prop, value_prop, blend_prop, blend


def discover_static_meshes(asset_paths, tokens, limit):
    """Discover production geometry while excluding editor helper/icon meshes."""
    results = []
    static_mesh_class = getattr(unreal, "StaticMesh", None)
    if static_mesh_class is None:
        return results

    token_set = {str(token).lower() for token in tokens}
    shrub_search = bool(token_set.intersection({"abelia", "shrub", "bush"}))
    ground_search = any(
        token in token_set
        for token in ("ophiopogon", "lolium", "groundcover", "ground_cover", "fern")
    )

    universal_reject = (
        "/material",
        "/texture",
        "/mi_",
        "/m_",
        "/t_",
        "/globalfoliageactor/",
        "sm_icon_",
        "/icons/",
        "/editor/",
        "_test.",
    )
    shrub_reject = (
        "_branches.",
        "_branch.",
        "_sock.",
        "_arrow.",
    )

    for path in asset_paths:
        lower = str(path).lower().replace("-", "_")
        if not any(token in lower for token in token_set):
            continue
        if any(skip in lower for skip in universal_reject):
            continue

        if shrub_search:
            # Prefer actual shrub geometry folders or named Abelia assets.
            if "/meshes/shrubs/" not in lower and "abelia" not in lower:
                continue
            if any(skip in lower for skip in shrub_reject):
                continue

        if ground_search and not any(
            token in lower
            for token in ("ophiopogon", "lolium", "groundcover", "ground_cover", "fern")
        ):
            continue

        try:
            asset = unreal.EditorAssetLibrary.load_asset(path)
        except Exception:
            asset = None
        if isinstance(asset, static_mesh_class):
            results.append((path, asset))
            if len(results) >= limit:
                break

    return results


# Patch the original module's globals. Functions already defined in that module,
# including configure_exclusion_modifier(), resolve these names at call time.
_base.make_channel_name = make_channel_name
_base.make_weight_entry = make_weight_entry
_base.discover_static_meshes = discover_static_meshes

# Re-export the original public API after patching it.
from AetherRiverEnvironmentCommon_UE58 import *  # noqa: F401,F403,E402
