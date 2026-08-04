"""Stage 13.3 V2: exact preview-geometry grounding with robust Mesh Partition bounds selection.

This wrapper loads the original Stage 13.3 repair, replaces only its preview
component selector, and then runs the unchanged validated repair pipeline.
"""

from pathlib import Path
import sys

import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

ORIGINAL = SCRIPT_DIR / "RepairAetherVideoRiverEnvironmentPreviewGrounding_UE58.py"
if not ORIGINAL.is_file():
    raise RuntimeError(f"Original preview grounding repair is missing: {ORIGINAL}")

source = ORIGINAL.read_text(encoding="utf-8")
marker = "\ntry:\n    main()"
if marker not in source:
    raise RuntimeError("Original preview grounding entry marker was not found")

ns = {
    "__file__": str(ORIGINAL),
    "__name__": "AetherPreviewGroundingV2Base",
}
exec(compile(source.split(marker, 1)[0], str(ORIGINAL), "exec"), ns, ns)

# The generated Mesh Partition static meshes are not consistent about whether
# their asset bounds are stored in mesh-local, component-world, or partition
# space. Test all safe interpretations and accept the one that intersects the
# river corridor. This avoids double-transforming partition-space mesh bounds.


def _raw_mesh_bounds(mesh):
    try:
        bounds = mesh.get_bounds()
        return (
            float(bounds.origin.x) - float(bounds.box_extent.x),
            float(bounds.origin.x) + float(bounds.box_extent.x),
            float(bounds.origin.y) - float(bounds.box_extent.y),
            float(bounds.origin.y) + float(bounds.box_extent.y),
        )
    except Exception:
        return None


def _translate_bounds(bounds, location):
    if bounds is None or location is None:
        return None
    try:
        return (
            bounds[0] + float(location.x),
            bounds[1] + float(location.x),
            bounds[2] + float(location.y),
            bounds[3] + float(location.y),
        )
    except Exception:
        return None


def _component_location(component):
    for method_name in ("get_world_location", "get_component_location"):
        method = getattr(component, method_name, None)
        if callable(method):
            try:
                return method()
            except Exception:
                pass
    try:
        transform = ns["component_transform"](component)
        if transform is not None:
            return transform.translation
    except Exception:
        pass
    return None


def _owner_location(component):
    try:
        owner = component.get_owner()
    except Exception:
        owner = None
    if owner:
        try:
            return owner.get_actor_location()
        except Exception:
            pass
    return None


def _candidate_bounds(component, mesh):
    raw = _raw_mesh_bounds(mesh)
    candidates = []
    if raw is not None:
        candidates.append(("RAW_PARTITION_SPACE", raw))

    transformed = ns["world_bounds"](component, mesh)
    if transformed is not None:
        candidates.append(("COMPONENT_WORLD_TRANSFORM", transformed))

    component_location = _component_location(component)
    translated_component = _translate_bounds(raw, component_location)
    if translated_component is not None:
        candidates.append(("COMPONENT_LOCATION_TRANSLATION", translated_component))

    owner_location = _owner_location(component)
    translated_owner = _translate_bounds(raw, owner_location)
    if translated_owner is not None:
        candidates.append(("OWNER_LOCATION_TRANSLATION", translated_owner))

    unique = []
    seen = set()
    for mode, bounds in candidates:
        key = tuple(round(float(value), 3) for value in bounds)
        if key in seen:
            continue
        seen.add(key)
        unique.append((mode, bounds))
    return unique


def select_components_v2(world, actors, spline, helpers):
    corridor = ns["corridor_bounds"](spline)
    selected = {}
    scanned = 0
    matched_modes = {}
    section_counts = {}

    sections = helpers["collect_section_actors"](world, actors)
    for section in sections:
        section_name = helpers["actor_label"](section)
        section_counts.setdefault(section_name, 0)
        for component in helpers["get_components"](section):
            mesh = helpers["safe_static_mesh"](component)
            if not mesh:
                continue
            scanned += 1

            match_mode = None
            match_bounds = None
            for mode, bounds in _candidate_bounds(component, mesh):
                if ns["overlaps"](bounds, corridor):
                    match_mode = mode
                    match_bounds = bounds
                    break
            if match_mode is None:
                continue

            transform = ns["component_transform"](component)
            mesh_path = mesh.get_path_name()
            # Prefer the actual preview component over the virtual-texture
            # fallback duplicate while preserving genuinely distinct tiles.
            dedupe_key = (mesh_path, str(transform), tuple(round(v, 2) for v in match_bounds))
            name = component.get_name().lower()
            cls = helpers["class_path"](component).lower()
            rank = 0 if "staticmeshpreviewcomponent" in cls else (1 if "virtualtexturefallback" in name else 2)
            old = selected.get(dedupe_key)
            if old is None or rank < old[0]:
                selected[dedupe_key] = (rank, component, mesh, match_bounds)
                matched_modes[dedupe_key] = match_mode
                section_counts[section_name] += 1

    result = sorted(selected.items(), key=lambda item: (item[1][0], item[1][2].get_path_name()))
    ns["log"](f"Section mesh components scanned={scanned}")
    ns["log"](f"River corridor preview components selected={len(result)}")
    ns["log"](f"River corridor XY bounds={corridor}")
    for section_name, count in sorted(section_counts.items()):
        ns["log"](f"  section candidate matches {section_name}={count}")

    mode_totals = {}
    for key, _ in result:
        mode = matched_modes[key]
        mode_totals[mode] = mode_totals.get(mode, 0) + 1
    for mode, count in sorted(mode_totals.items()):
        ns["log"](f"  bounds interpretation {mode}={count}")

    max_components = 512
    if not result or len(result) > max_components:
        raise RuntimeError(
            f"Invalid preview component count for river corridor after V2 coordinate tests: {len(result)}"
        )

    return [entry for _, entry in result]


ns["select_components"] = select_components_v2
ns["MAX_COMPONENTS"] = 512

try:
    ns["main"]()
except Exception as exc:
    ns["log"]("")
    ns["log"]("PREVIEW_GROUNDING_RESULT=FAIL")
    ns["log"](f"ERROR={type(exc).__name__}: {exc}")
    ns["log"]("SAVED_ENVIRONMENT_ACTOR_WAS_NOT_REPLACED=TRUE")
    ns["log"]("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    ns["report"]()
    unreal.log_error(f"AETHER_PREVIEW_GROUNDING_V2_FAILED={type(exc).__name__}: {exc}")
    raise
