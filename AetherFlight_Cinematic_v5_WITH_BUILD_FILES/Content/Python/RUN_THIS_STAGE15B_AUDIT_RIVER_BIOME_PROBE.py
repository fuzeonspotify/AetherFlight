"""Read-only audit for the temporary Stage 15B river-biome generation probe.

Run after RUN_THIS_STAGE15B_START_RIVER_BIOME_PROBE.py and after Unreal has had
time to finish PCG generation. The audit reports generation state, instance
component counts, total instances, and per-mesh instance counts. It modifies and
saves nothing.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeAudit.txt"
PROBE_LABEL = "Aether_Stage15B_RiverBiomeProbe_UNSAVED"
SOURCE_VOLUME_LABEL = "Aether_Stage15B_RiverBiomeVolume"
EXPECTED_TRANSIENT_GRAPH_TOKEN = "AetherStage15B_RiverBiomeProbeGraph"
MAX_SAFE_TOTAL_INSTANCES = 2500


def safe_call(fn, fallback=None):
    try:
        return fn()
    except Exception:
        return fallback


def object_path(obj):
    if obj is None:
        return "NONE"
    for fn in (lambda: obj.get_path_name(), lambda: obj.get_full_name(), lambda: str(obj)):
        value = safe_call(fn)
        if value:
            return str(value)
    return "UNKNOWN"


def actors_with_label(label):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return [
        actor for actor in subsystem.get_all_level_actors()
        if safe_call(lambda actor=actor: actor.get_actor_label(), "") == label
    ]


def get_single_actor(label):
    matches = actors_with_label(label)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one actor labelled {label}; found {len(matches)}")
    return matches[0]


def get_component(actor):
    components = actor.get_components_by_class(unreal.PCGComponent)
    if len(components) != 1:
        raise RuntimeError(f"Expected exactly one PCG component on {PROBE_LABEL}; found {len(components)}")
    return components[0]


def component_mesh_path(component):
    mesh = safe_call(lambda: component.get_editor_property("static_mesh"))
    if mesh is None:
        mesh = safe_call(lambda: component.get_static_mesh())
    return object_path(mesh)


def instance_count(component):
    for fn in (
        lambda: component.get_instance_count(),
        lambda: component.get_editor_property("instance_count"),
    ):
        value = safe_call(fn)
        if value is not None:
            try:
                return int(value)
            except Exception:
                pass
    return 0


def collect_instance_components(actor):
    combined = []
    seen = set()
    for cls in (
        unreal.HierarchicalInstancedStaticMeshComponent,
        unreal.InstancedStaticMeshComponent,
    ):
        for component in actor.get_components_by_class(cls):
            path = object_path(component)
            if path not in seen:
                seen.add(path)
                combined.append(component)
    return combined


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_RIVER_BIOME_PROBE_AUDIT_REPORT={REPORT_PATH}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before auditing the river-biome probe")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - TEMPORARY RIVER BIOME PROBE AUDIT",
        "=" * 100,
        "READ_ONLY=TRUE",
        "NO_ASSETS_MODIFIED=TRUE",
        "NO_ACTORS_MODIFIED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    ]

    probe = get_single_actor(PROBE_LABEL)
    component = get_component(probe)
    graph = safe_call(lambda: component.get_graph())
    if graph is None:
        graph = safe_call(lambda: component.get_editor_property("graph"))
    graph_path = object_path(graph)

    source_volume = get_single_actor(SOURCE_VOLUME_LABEL)
    source_instances = collect_instance_components(source_volume)
    source_total = sum(instance_count(item) for item in source_instances)

    is_generating = safe_call(lambda: component.is_generating(), False)
    is_generated = safe_call(lambda: component.get_editor_property("generated"), "UNEXPOSED")
    is_active = safe_call(lambda: component.is_active(), "UNEXPOSED")
    is_partitioned = safe_call(lambda: component.get_editor_property("is_component_partitioned"), "UNEXPOSED")
    trigger = safe_call(lambda: component.get_editor_property("generation_trigger"), "UNEXPOSED")
    bounds = safe_call(lambda: probe.get_actor_bounds(False), "UNAVAILABLE")

    lines.append(f"PROBE_ACTOR={object_path(probe)}")
    lines.append(f"PROBE_GRAPH={graph_path}")
    lines.append(f"PROBE_GRAPH_IS_TRANSIENT={graph_path.startswith('/Engine/Transient.')}")
    lines.append(f"PROBE_GRAPH_NAME_MATCH={EXPECTED_TRANSIENT_GRAPH_TOKEN in graph_path}")
    lines.append(f"PROBE_IS_GENERATING={is_generating}")
    lines.append(f"PROBE_GENERATED={is_generated}")
    lines.append(f"PROBE_ACTIVE={is_active}")
    lines.append(f"PROBE_PARTITIONED={is_partitioned}")
    lines.append(f"PROBE_GENERATION_TRIGGER={trigger}")
    lines.append(f"PROBE_LOCATION={safe_call(lambda: probe.get_actor_location(), 'UNAVAILABLE')}")
    lines.append(f"PROBE_SCALE={safe_call(lambda: probe.get_actor_scale3d(), 'UNAVAILABLE')}")
    lines.append(f"PROBE_BOUNDS={bounds}")
    lines.append(f"FULL_VOLUME_INSTANCE_COMPONENT_COUNT={len(source_instances)}")
    lines.append(f"FULL_VOLUME_INSTANCE_COUNT={source_total}")

    probe_components = collect_instance_components(probe)
    total_instances = 0
    per_mesh = {}
    for component_index, item in enumerate(probe_components, 1):
        count = instance_count(item)
        mesh_path = component_mesh_path(item)
        total_instances += count
        per_mesh[mesh_path] = per_mesh.get(mesh_path, 0) + count
        lines.append(f"INSTANCE_COMPONENT_{component_index}={object_path(item)}")
        lines.append(f"INSTANCE_COMPONENT_{component_index}_MESH={mesh_path}")
        lines.append(f"INSTANCE_COMPONENT_{component_index}_COUNT={count}")

    lines.append(f"PROBE_INSTANCE_COMPONENT_COUNT={len(probe_components)}")
    lines.append(f"PROBE_TOTAL_INSTANCE_COUNT={total_instances}")
    lines.append(f"PROBE_UNIQUE_MESH_COUNT={len(per_mesh)}")
    for index, mesh_path in enumerate(sorted(per_mesh, key=str.lower), 1):
        lines.append(f"PROBE_MESH_{index}={mesh_path}")
        lines.append(f"PROBE_MESH_{index}_INSTANCE_COUNT={per_mesh[mesh_path]}")

    failures = []
    if not graph_path.startswith("/Engine/Transient."):
        failures.append("Probe graph is not transient")
    if EXPECTED_TRANSIENT_GRAPH_TOKEN not in graph_path:
        failures.append("Unexpected transient graph name")
    if is_partitioned is not False:
        failures.append(f"Probe is partitioned: {is_partitioned}")
    if source_total != 0 or source_instances:
        failures.append("Full river volume unexpectedly contains generated instances")
    if total_instances > MAX_SAFE_TOTAL_INSTANCES:
        failures.append(
            f"Probe exceeded safe instance ceiling: {total_instances} > {MAX_SAFE_TOTAL_INSTANCES}"
        )

    lines.append(f"AUDIT_FAILURE_COUNT={len(failures)}")
    for index, failure in enumerate(failures, 1):
        lines.append(f"AUDIT_FAILURE_{index}={failure}")

    if is_generating:
        lines.extend((
            "PROBE_AUDIT_RESULT=PENDING",
            "NEXT=Wait for PCG generation to finish, then run this audit again.",
            "DO_NOT_SAVE_LEVEL=TRUE",
        ))
    elif failures:
        lines.extend((
            "PROBE_AUDIT_RESULT=FAIL",
            "NEXT=Do not save. Close Unreal without saving and provide this report.",
        ))
    else:
        lines.extend((
            "PROBE_AUDIT_RESULT=PASS",
            "NEXT=Visually inspect the probe around PROBE_LOCATION, then provide this report before any persistent generation.",
            "DO_NOT_SAVE_LEVEL=TRUE",
        ))

    write_report(lines)


try:
    main()
except Exception as exc:
    failure = [
        "AETHER STAGE 15B - TEMPORARY RIVER BIOME PROBE AUDIT",
        "=" * 100,
        "PROBE_AUDIT_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "NO_ASSETS_MODIFIED=TRUE",
        "NO_ACTORS_MODIFIED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    ]
    write_report(failure)
    unreal.log_error("\n".join(failure))
    raise
