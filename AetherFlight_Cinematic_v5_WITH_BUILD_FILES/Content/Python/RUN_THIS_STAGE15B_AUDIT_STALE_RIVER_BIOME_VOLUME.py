"""Read-only audit for the stale Stage 15B river-biome PCG volume.

Finds the exact actor labelled Aether_Stage15B_RiverBiomeVolume and records its
external package and candidate .uasset path so only that package can be
quarantined with Unreal closed. This script does not modify, save, destroy,
generate, or build anything.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BStaleRiverBiomeVolumeAudit.txt"
VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"


def safe_call(fn, fallback=None):
    try:
        return fn()
    except Exception:
        return fallback


def object_path(obj):
    if obj is None:
        return "NONE"
    for fn in (
        lambda: obj.get_path_name(),
        lambda: obj.get_full_name(),
        lambda: str(obj),
    ):
        value = safe_call(fn)
        if value:
            return str(value)
    return "UNKNOWN"


def package_name(package):
    if package is None:
        return "NONE"
    for fn in (
        lambda: package.get_name(),
        lambda: package.get_path_name(),
        lambda: str(package),
    ):
        value = safe_call(fn)
        if value:
            return str(value)
    return "UNKNOWN"


def candidate_filename(long_package_name):
    if not long_package_name.startswith("/Game/"):
        return "NONE", False
    relative = long_package_name[len("/Game/"):] + ".uasset"
    path = Path(unreal.Paths.project_content_dir()) / Path(relative)
    return str(path.resolve()), path.exists()


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running the stale volume audit.")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - STALE RIVER BIOME VOLUME AUDIT",
        "=" * 100,
        "READ_ONLY=TRUE",
        "NO_ACTORS_MODIFIED=TRUE",
        "NO_ACTORS_DESTROYED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    ]

    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = []
    for actor in subsystem.get_all_level_actors():
        if safe_call(lambda actor=actor: actor.get_actor_label(), "") == VOLUME_LABEL:
            matches.append(actor)

    lines.append(f"MATCHING_ACTORS={len(matches)}")
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one actor labelled {VOLUME_LABEL}; found {len(matches)}"
        )

    actor = matches[0]
    lines.append(f"ACTOR_LABEL={VOLUME_LABEL}")
    lines.append(f"ACTOR_CLASS={object_path(safe_call(lambda: actor.get_class()))}")
    lines.append(f"ACTOR_OBJECT_PATH={object_path(actor)}")
    lines.append(f"ACTOR_LOCATION={safe_call(lambda: actor.get_actor_location(), 'UNAVAILABLE')}")
    lines.append(f"ACTOR_SCALE={safe_call(lambda: actor.get_actor_scale3d(), 'UNAVAILABLE')}")
    bounds = safe_call(lambda: actor.get_actor_bounds(False))
    lines.append(f"ACTOR_BOUNDS={bounds}")
    lines.append(
        f"IS_SPATIALLY_LOADED={safe_call(lambda: actor.get_editor_property('is_spatially_loaded'), 'UNEXPOSED')}"
    )

    external_package = safe_call(lambda: actor.get_external_package())
    outermost_package = safe_call(lambda: actor.get_outermost())
    actor_package = safe_call(lambda: actor.get_package())

    external_name = package_name(external_package)
    outermost_name = package_name(outermost_package)
    actor_package_name = package_name(actor_package)

    lines.append(f"EXTERNAL_PACKAGE_OBJECT={object_path(external_package)}")
    lines.append(f"EXTERNAL_PACKAGE_NAME={external_name}")
    lines.append(f"OUTERMOST_PACKAGE_NAME={outermost_name}")
    lines.append(f"ACTOR_PACKAGE_NAME={actor_package_name}")

    candidates = []
    for label, name in (
        ("EXTERNAL", external_name),
        ("OUTERMOST", outermost_name),
        ("ACTOR_PACKAGE", actor_package_name),
    ):
        filename, exists = candidate_filename(name)
        lines.append(f"{label}_PACKAGE_FILE={filename}")
        lines.append(f"{label}_PACKAGE_FILE_EXISTS={exists}")
        if exists:
            candidates.append(filename)

    components = actor.get_components_by_class(unreal.PCGComponent)
    lines.append(f"PCG_COMPONENT_COUNT={len(components)}")
    if len(components) == 1:
        component = components[0]
        graph = safe_call(lambda: component.get_graph())
        if graph is None:
            graph = safe_call(lambda: component.get_editor_property("graph"))
        lines.append(f"PCG_COMPONENT={object_path(component)}")
        lines.append(f"PCG_GRAPH={object_path(graph)}")
        lines.append(
            f"PCG_GENERATION_TRIGGER={safe_call(lambda: component.get_editor_property('generation_trigger'), 'UNEXPOSED')}"
        )
        lines.append(
            f"PCG_PARTITIONED={safe_call(lambda: component.get_editor_property('is_component_partitioned'), 'UNEXPOSED')}"
        )
        lines.append(f"PCG_ACTIVE={safe_call(lambda: component.is_active(), 'UNAVAILABLE')}")
        lines.append(f"PCG_SEED={safe_call(lambda: component.get_editor_property('seed'), 'UNEXPOSED')}")

    unique_candidates = sorted(set(candidates), key=str.lower)
    lines.append(f"EXISTING_PACKAGE_FILE_CANDIDATES={len(unique_candidates)}")
    for index, filename in enumerate(unique_candidates, 1):
        path = Path(filename)
        stat = path.stat()
        lines.append(f"PACKAGE_FILE_{index}={filename}")
        lines.append(f"PACKAGE_FILE_{index}_SIZE={stat.st_size}")
        lines.append(f"PACKAGE_FILE_{index}_MTIME_NS={stat.st_mtime_ns}")

    if len(unique_candidates) != 1:
        raise RuntimeError(
            f"Could not resolve exactly one existing external actor package file; found {len(unique_candidates)}"
        )

    lines.extend((
        "AUDIT_RESULT=PASS",
        f"EXACT_STALE_VOLUME_FILE={unique_candidates[0]}",
        "NEXT=Close Unreal without saving, quarantine EXACT_STALE_VOLUME_FILE, restore only AetherWorld.umap if tracked-modified, then rerun V4.",
    ))

    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_STALE_VOLUME_AUDIT_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    failure = "\n".join((
        "AETHER STAGE 15B - STALE RIVER BIOME VOLUME AUDIT",
        "=" * 100,
        "AUDIT_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "NO_ACTORS_MODIFIED=TRUE",
        "NO_ACTORS_DESTROYED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    )) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(failure, encoding="utf-8")
    unreal.log_error(failure)
    raise
