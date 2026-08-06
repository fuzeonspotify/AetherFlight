"""Stage 14A V3: use QueryAndPhysics for the four grounded rock HISM components."""

from pathlib import Path
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
V2 = SCRIPT_DIR / "InstallAetherStage14RockCollision_UE58_v2.py"
if not V2.is_file():
    raise RuntimeError(f"Stage 14 collision V2 is missing: {V2}")

source = V2.read_text(encoding="utf-8")
marker = "\ntry:\n    main_v2()"
if marker not in source:
    raise RuntimeError("Stage 14 collision V2 entry marker was not found")

wrapper = {"__file__": str(V2), "__name__": "AetherStage14RockCollisionV3Base"}
exec(compile(source.split(marker, 1)[0], str(V2), "exec"), wrapper, wrapper)
base = wrapper["ns"]


def apply_collision_v3(grouped):
    enum = getattr(unreal, "CollisionEnabled", None)
    if not enum:
        raise RuntimeError("unreal.CollisionEnabled is unavailable")
    query_and_physics = getattr(enum, "QUERY_AND_PHYSICS", None)
    no_collision = getattr(enum, "NO_COLLISION", None)
    if query_and_physics is None or no_collision is None:
        raise RuntimeError("Required QueryAndPhysics/NoCollision enum members are unavailable")

    for component in grouped["rock"]:
        base["set_profile"](component, unreal.Name("BlockAll"))
        base["set_collision"](component, query_and_physics)
        base["set_overlap"](component, False)
        base["refresh_collision"](component)
        base["log"](
            f"ENABLED_ROCK_COLLISION={component.get_name()} mesh={base['mesh_path'](component)} "
            f"collision={base['collision_enabled'](component)} profile={base['collision_profile'](component)}"
        )

    for name in ("shrub", "ground"):
        for component in grouped[name]:
            base["set_collision"](component, no_collision)
            base["set_overlap"](component, False)
            base["refresh_collision"](component)
            base["log"](
                f"DISABLED_{name.upper()}_COLLISION={component.get_name()} "
                f"mesh={base['mesh_path'](component)} collision={base['collision_enabled'](component)}"
            )


base["apply_collision"] = apply_collision_v3
original_log = base["log"]


def log_v3(text=""):
    if str(text) == "ROCK_COLLISION_MODE=QUERY_ONLY":
        text = "ROCK_COLLISION_MODE=QUERY_AND_PHYSICS"
    original_log(text)


base["log"] = log_v3

try:
    base["log"]("STAGE14_ROCK_PHYSICS_COLLISION_V3=TRUE")
    wrapper["main_v2"]()
except Exception as exc:
    base["log"]("")
    base["log"]("ROCK_COLLISION_INSTALL_RESULT=FAIL")
    base["log"](f"ERROR={type(exc).__name__}: {exc}")
    base["log"]("COLLISION_CHANGES_WERE_NOT_SAVED=TRUE")
    base["log"]("TERRAIN_COLLISION_UNCHANGED=TRUE")
    base["log"]("NO_COMPILED_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    base["write_report"]()
    unreal.log_error(f"AETHER_STAGE14_ROCK_COLLISION_V3_FAILED={type(exc).__name__}: {exc}")
    raise
