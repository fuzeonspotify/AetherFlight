import math
from pathlib import Path
import random
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoLocalRemeshInstall.txt"

# This is intentionally outside the normal flight spawn area. The local feature
# covers roughly 1.2 km and does not request a whole-world Mesh Partition build.
TEST_CENTER_X = -720000.0
TEST_CENTER_Y = -760000.0
TRACE_TOP_Z = 900000.0
TRACE_BOTTOM_Z = -300000.0

ROCK_ASSETS = [
    "/Game/Rock_Collection_04/Meshes/Rock_01/StaticMeshes/SM_Rock_01",
    "/Game/Rock_Collection_04/Meshes/Rock_02/StaticMeshes/SM_Rock_02",
    "/Game/Rock_Collection_04/Meshes/Rock_03/StaticMeshes/SM_Rock_03",
    "/Game/Rock_Collection_04/Meshes/Rock_04/StaticMeshes/SM_Rock_04",
    "/Game/Rock_Collection_04/Meshes/Rock_05/StaticMeshes/SM_Rock_05",
    "/Game/Rock_Collection_04/Meshes/Rock_06/StaticMeshes/SM_Rock_06",
    "/Game/Rock_Collection_04/Meshes/Rock_07/StaticMeshes/SM_Rock_07",
]

ACTOR_LABEL = "Aether_VideoStage05_LocalRemesh"
ROCK_LABEL_PREFIX = "Aether_VideoStage05_RockMarker_"
TAG = "AetherVideoLocalRemeshStage"


def record(lines, text):
    lines.append(str(text))
    unreal.log_warning(str(text))


def load_world():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def all_actors():
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return subsystem, list(subsystem.get_all_level_actors())


def actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def clear_previous_install(editor_actor_subsystem, actors, lines):
    removed = 0
    for actor in actors:
        label = actor_label(actor)
        tags = []
        try:
            tags = [str(tag) for tag in actor.get_editor_property("tags")]
        except Exception:
            pass
        if label == ACTOR_LABEL or label.startswith(ROCK_LABEL_PREFIX) or TAG in tags:
            editor_actor_subsystem.destroy_actor(actor)
            removed += 1
    record(lines, f"Previous stage actors removed={removed}")


def find_mesh_partition(actors):
    preferred = []
    fallback = []
    for actor in actors:
        combined = f"{actor.get_name()} {actor.get_class().get_path_name()}"
        if "MeshPartition" not in combined and "MeshTerrain" not in combined:
            continue
        fallback.append(actor)
        tags = []
        try:
            tags = [str(tag) for tag in actor.get_editor_property("tags")]
        except Exception:
            pass
        if actor.get_name() == "MeshTerrain_AetherWorld" or "AetherProductionTerrain" in tags:
            preferred.append(actor)
    if len(preferred) == 1:
        return preferred[0]
    return fallback[0] if len(fallback) == 1 else None


def terrain_hit(world, x, y):
    start = unreal.Vector(x, y, TRACE_TOP_Z)
    end = unreal.Vector(x, y, TRACE_BOTTOM_Z)
    try:
        hit = unreal.SystemLibrary.line_trace_single(
            world,
            start,
            end,
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        if hit:
            for prop in ("impact_point", "location"):
                try:
                    point = hit.get_editor_property(prop)
                    if point:
                        return point
                except Exception:
                    pass
    except Exception as exc:
        unreal.log_warning(f"Visibility terrain trace failed at {x:.0f},{y:.0f}: {exc}")

    try:
        hit = unreal.SystemLibrary.line_trace_single_by_profile(
            world,
            start,
            end,
            "BlockAll",
            False,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        if hit:
            for prop in ("impact_point", "location"):
                try:
                    point = hit.get_editor_property(prop)
                    if point:
                        return point
                except Exception:
                    pass
    except Exception as exc:
        unreal.log_warning(f"Profile terrain trace failed at {x:.0f},{y:.0f}: {exc}")
    return None


def add_component_to_actor(actor, component_class, lines):
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = list(subsystem.k2_gather_subobject_data_for_instance(actor))
    if not handles:
        raise RuntimeError("SubobjectDataSubsystem returned no actor root handle")

    params = unreal.AddNewSubobjectParams()
    params.set_editor_property("parent_handle", handles[0])
    params.set_editor_property("new_class", component_class)
    new_handle, fail_reason = subsystem.add_new_subobject(params)
    if not new_handle or not new_handle.is_valid():
        raise RuntimeError(f"Could not add {component_class}: {fail_reason}")

    data = subsystem.k2_find_subobject_data_from_handle(new_handle)
    component = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(data)
    if not component:
        raise RuntimeError(f"Added {component_class}, but could not resolve the new component object")

    record(lines, f"Added component={component.get_class().get_path_name()}")
    return component


def try_set_property(obj, names, value, lines):
    for name in names:
        try:
            obj.set_editor_property(name, value)
            record(lines, f"Set {obj.get_name()}.{name}={value}")
            return True
        except Exception:
            continue
    record(lines, f"Property not exposed: {obj.get_name()} candidates={names}")
    return False


def configure_remesh(component, mesh_partition, center, lines):
    try:
        component.set_world_location(center, False, False)
    except Exception:
        try_set_property(component, ("relative_location",), center, lines)

    try_set_property(
        component,
        ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor"),
        mesh_partition,
        lines,
    )

    # 1.2 km square with a deep Z range so it covers the terrain regardless of
    # local elevation. Base edge length is roughly 11.9 m; 6 m locally provides
    # about twice the linear resolution without an extreme triangle increase.
    try_set_property(
        component,
        ("unscaled_coverage", "coverage"),
        unreal.Vector(120000.0, 120000.0, 700000.0),
        lines,
    )

    for method_name, args in (
        ("set_target_edge_length", (600.0,)),
        ("set_use_target_edge_length", (True,)),
        ("set_remesh_iterations", (2,)),
        ("set_vertex_smoothing", (False,)),
        ("set_resample_uvs", (True,)),
    ):
        method = getattr(component, method_name, None)
        if method:
            try:
                method(*args)
                record(lines, f"Called {component.get_name()}.{method_name}{args}")
            except Exception as exc:
                record(lines, f"Could not call {method_name}: {exc}")

    try_set_property(component, ("priority",), 5.0, lines)
    try_set_property(component, ("is_disabled", "disabled"), False, lines)

    try:
        component.modify()
    except Exception:
        pass


def spawn_rock_markers(editor_actor_subsystem, world, center, lines):
    rng = random.Random(5805)
    spawned = 0
    for index, asset_path in enumerate(ROCK_ASSETS, start=1):
        mesh = unreal.EditorAssetLibrary.load_asset(asset_path)
        if not mesh:
            record(lines, f"Rock marker {index} skipped; missing={asset_path}")
            continue

        angle = (index - 1) * (2.0 * math.pi / len(ROCK_ASSETS))
        radius = 43000.0 + (index % 2) * 9000.0
        x = center.x + math.cos(angle) * radius
        y = center.y + math.sin(angle) * radius
        hit = terrain_hit(world, x, y)
        if not hit:
            record(lines, f"Rock marker {index} skipped; no terrain hit at {x:.0f},{y:.0f}")
            continue

        actor = editor_actor_subsystem.spawn_actor_from_class(
            unreal.StaticMeshActor,
            hit,
            unreal.Rotator(
                rng.uniform(-7.0, 7.0),
                rng.uniform(-180.0, 180.0),
                rng.uniform(-7.0, 7.0),
            ),
            False,
        )
        actor.set_actor_label(f"{ROCK_LABEL_PREFIX}{index:02d}", True)
        actor.set_editor_property("tags", [unreal.Name(TAG)])

        component = actor.get_editor_property("static_mesh_component")
        component.set_static_mesh(mesh)
        try:
            component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        except Exception:
            pass
        scale = rng.uniform(2.0, 5.2)
        actor.set_actor_scale3d(
            unreal.Vector(
                scale * rng.uniform(0.78, 1.25),
                scale * rng.uniform(0.78, 1.25),
                scale * rng.uniform(0.82, 1.18),
            )
        )
        spawned += 1
        record(lines, f"Rock marker {index}={asset_path} at {hit}")
    return spawned


def save_map(lines):
    saved = False
    try:
        saved = bool(unreal.EditorLevelLibrary.save_current_level())
    except Exception as exc:
        record(lines, f"save_current_level warning={exc}")
    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(False, True)
        saved = True
    except Exception as exc:
        record(lines, f"save_dirty_packages warning={exc}")
    return saved


def main():
    lines = []
    record(lines, "AETHER VIDEO STAGE 05 — LOCAL REMESH INSTALL")
    record(lines, "=" * 96)

    world = load_world()
    editor_actor_subsystem, actors = all_actors()
    clear_previous_install(editor_actor_subsystem, actors, lines)

    _, actors = all_actors()
    mesh_partition = find_mesh_partition(actors)
    if not mesh_partition:
        raise RuntimeError("Expected exactly one authoritative Mesh Partition actor, but none could be resolved")
    record(lines, f"Affected Mesh Partition={mesh_partition.get_name()} | {mesh_partition.get_class().get_path_name()}")

    remesh_class = getattr(unreal, "RemeshModifier", None)
    modifier_actor_class = getattr(unreal, "ModifierActor", unreal.Actor)
    if not remesh_class:
        exposed = [name for name in dir(unreal) if "remesh" in name.lower()]
        raise RuntimeError(f"unreal.RemeshModifier is unavailable. Exposed remesh names={exposed}")

    center_hit = terrain_hit(world, TEST_CENTER_X, TEST_CENTER_Y)
    center_z = center_hit.z if center_hit else 0.0
    center = unreal.Vector(TEST_CENTER_X, TEST_CENTER_Y, center_z)
    record(lines, f"Local stage center={center} terrain_trace={'PASS' if center_hit else 'FALLBACK_Z0'}")

    modifier_actor = editor_actor_subsystem.spawn_actor_from_class(
        modifier_actor_class,
        center,
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    modifier_actor.set_actor_label(ACTOR_LABEL, True)
    modifier_actor.set_editor_property("tags", [unreal.Name(TAG)])

    remesh_component = add_component_to_actor(modifier_actor, remesh_class, lines)
    configure_remesh(remesh_component, mesh_partition, center, lines)

    rocks_spawned = spawn_rock_markers(
        editor_actor_subsystem,
        world,
        center,
        lines,
    )
    record(lines, f"Rock Collection 04 stage markers spawned={rocks_spawned}/7")

    saved = save_map(lines)
    record(lines, f"Map save={'PASS' if saved else 'CHECK'}")
    record(lines, "")
    record(lines, "INSTALL_RESULT=PASS")
    record(lines, "NEXT_EDITOR_CHECK=Open AetherWorld, select Aether_VideoStage05_LocalRemesh, and inspect Mesh Partition Outliner.")
    record(lines, "NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_LOCAL_REMESH_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"INSTALL_RESULT=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
