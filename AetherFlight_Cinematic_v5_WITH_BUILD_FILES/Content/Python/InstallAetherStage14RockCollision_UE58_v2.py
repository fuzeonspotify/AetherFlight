"""Stage 14A V2: stable numeric transform validation and list-based rollback."""

from pathlib import Path
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR / "InstallAetherStage14RockCollision_UE58.py"
if not BASE.is_file():
    raise RuntimeError(f"Base Stage 14 collision installer is missing: {BASE}")

source = BASE.read_text(encoding="utf-8")
marker = "\ntry:\n    main()"
if marker not in source:
    raise RuntimeError("Base Stage 14 collision installer entry marker was not found")

ns = {"__file__": str(BASE), "__name__": "AetherStage14RockCollisionBase"}
exec(compile(source.split(marker, 1)[0], str(BASE), "exec"), ns, ns)


def _xyz(value):
    if value is None:
        return None
    result = []
    for name in ("x", "y", "z"):
        try:
            result.append(round(float(getattr(value, name)), 6))
        except Exception:
            result.append(round(float(value.get_editor_property(name)), 6))
    return tuple(result)


def _rotation(value):
    if value is None:
        return None
    quaternion = []
    for name in ("x", "y", "z", "w"):
        try:
            quaternion.append(round(float(getattr(value, name)), 7))
        except Exception:
            try:
                quaternion.append(round(float(value.get_editor_property(name)), 7))
            except Exception:
                quaternion = []
                break
    if quaternion:
        return tuple(quaternion)
    rotator = []
    for name in ("pitch", "yaw", "roll"):
        try:
            rotator.append(round(float(getattr(value, name)), 6))
        except Exception:
            rotator.append(round(float(value.get_editor_property(name)), 6))
    return tuple(rotator)


def transform_signature_v2(component):
    result = []
    for index in range(ns["instance_count"](component)):
        transform = ns["instance_transform"](component, index)
        if transform is None:
            raise RuntimeError(
                f"Could not read instance transform {index} from {component.get_name()}"
            )
        location = ns["safe_property"](transform, "translation")
        rotation = ns["safe_property"](transform, "rotation")
        scale = ns["safe_property"](transform, "scale3d")
        result.append((_xyz(location), _rotation(rotation), _xyz(scale)))
    return tuple(result)


ns["transform_signature"] = transform_signature_v2


def main_v2():
    ns["log"]("AETHER STAGE 14A V2 - STRICT RIVER ROCK COLLISION")
    ns["log"]("=" * 96)
    ns["log"](
        "Only the 30 Stage 13 river rocks receive query collision. Shrubs and ground cover remain non-colliding."
    )
    ns["log"]("Numeric instance transforms are compared before and after collision setup.")
    ns["log"]("Mesh Terrain collision is not modified and no Mesh Partition build is started.")

    world = ns["load_world"]()
    actors = ns["all_editor_actors"]()
    environment = ns["find_environment"](actors)
    ns["log"](f"WORLD={world.get_path_name() if world else None}")
    ns["log"](
        f"ENVIRONMENT_ACTOR={ns['actor_label'](environment) if environment else None}"
    )
    if not world or not environment:
        raise RuntimeError("AetherWorld or the Stage 13 river environment actor is missing")

    components, grouped = ns["collect_and_validate"](environment)
    before_layout = {
        ns["mesh_path"](component): transform_signature_v2(component)
        for component in components
    }
    states = [(component, ns["snapshot"](component)) for component in components]

    try:
        ns["apply_collision"](grouped)
        simple_pass, complex_pass = ns["validate_collision"](grouped)
        after_layout = {
            ns["mesh_path"](component): transform_signature_v2(component)
            for component in components
        }
        if before_layout != after_layout:
            raise RuntimeError("One or more Stage 13 instance transforms changed during collision setup")
        if not ns["save_world"]():
            raise RuntimeError("Map save did not report success")

        ns["log"]("MAP_SAVE=PASS")
        ns["log"]("")
        ns["log"]("ROCK_COLLISION_INSTALL_RESULT=PASS")
        ns["log"]("ROCK_HISM_COMPONENTS=4")
        ns["log"]("ROCK_INSTANCES=30")
        ns["log"](f"ROCK_SIMPLE_TRACE_COMPONENTS_PASS={simple_pass}")
        ns["log"](f"ROCK_COMPLEX_TRACE_COMPONENTS_PASS={complex_pass}")
        ns["log"]("ROCK_COLLISION_MODE=QUERY_ONLY")
        ns["log"]("ROCK_COLLISION_PROFILE=BlockAll")
        ns["log"]("NON_ROCK_COLLISION_DISABLED=TRUE")
        ns["log"]("INSTANCE_TRANSFORMS_PRESERVED=TRUE")
        ns["log"]("TERRAIN_COLLISION_UNCHANGED=TRUE")
        ns["log"]("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    except Exception:
        ns["log"]("ROLLBACK_STARTED=TRUE")
        for component, state in states:
            ns["restore"](component, state)
        ns["log"]("ROLLBACK_FINISHED=TRUE")
        raise

    ns["write_report"]()
    unreal.log_warning(f"AETHER_STAGE14_ROCK_COLLISION_REPORT={ns['REPORT_PATH']}")


try:
    main_v2()
except Exception as exc:
    ns["log"]("")
    ns["log"]("ROCK_COLLISION_INSTALL_RESULT=FAIL")
    ns["log"](f"ERROR={type(exc).__name__}: {exc}")
    ns["log"]("COLLISION_CHANGES_WERE_NOT_SAVED=TRUE")
    ns["log"]("TERRAIN_COLLISION_UNCHANGED=TRUE")
    ns["log"]("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    ns["write_report"]()
    unreal.log_error(f"AETHER_STAGE14_ROCK_COLLISION_V2_FAILED={type(exc).__name__}: {exc}")
    raise
