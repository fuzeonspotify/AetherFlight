"""Read-only Stage 14 PIE runtime validation with Mesh Partition readiness gating.

Loads the original Stage 14B validator, checks whether transient CompiledSection
static meshes/components are still compiling, and reports WAITING instead of
running terrain traces against incomplete physics data. It never starts/stops
PIE, changes collision, saves packages, or invokes a Mesh Partition build.
"""

from pathlib import Path
import unreal

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_SCRIPT = SCRIPT_DIR / "AuditAetherStage14PIERuntime_UE58.py"

if not BASE_SCRIPT.is_file():
    raise RuntimeError(f"Base Stage 14 PIE validator is missing: {BASE_SCRIPT}")

source = BASE_SCRIPT.read_text(encoding="utf-8")
marker = "\ntry:\n    main()"
if marker not in source:
    raise RuntimeError("Base Stage 14 PIE validator entry marker was not found")

ns = {"__file__": str(BASE_SCRIPT), "__name__": "AetherStage14PIEBase"}
exec(compile(source.split(marker, 1)[0], str(BASE_SCRIPT), "exec"), ns, ns)


def safe_static_mesh(component):
    method = getattr(component, "get_static_mesh", None)
    if callable(method):
        try:
            mesh = method()
            if mesh:
                return mesh
        except Exception:
            pass
    for name in ("static_mesh", "mesh"):
        try:
            mesh = component.get_editor_property(name)
            if mesh:
                return mesh
        except Exception:
            pass
    return None


def is_compiling(obj):
    method = getattr(obj, "is_compiling", None)
    if not callable(method):
        return False
    try:
        return bool(method())
    except Exception:
        return False


def compiled_section_readiness(sections):
    component_total = 0
    static_mesh_component_total = 0
    compiling_components = []
    compiling_meshes = {}

    for section in sections:
        for component in ns["get_components"](section):
            component_total += 1
            cls = ns["class_path"](component)
            mesh = safe_static_mesh(component)
            static_like = mesh is not None or "STATICMESH" in cls.upper() or "FARFIELDMESH" in cls.upper()
            if not static_like:
                continue
            static_mesh_component_total += 1
            if is_compiling(component):
                compiling_components.append(f"{section.get_name()}.{component.get_name()}")
            if mesh and is_compiling(mesh):
                try:
                    key = mesh.get_path_name()
                except Exception:
                    key = str(mesh)
                compiling_meshes[key] = mesh

    return {
        "component_total": component_total,
        "static_mesh_component_total": static_mesh_component_total,
        "compiling_components": compiling_components,
        "compiling_meshes": sorted(compiling_meshes),
    }


def write_waiting_report(world, sections, readiness):
    ns["LINES"].clear()
    ns["log"]("AETHER STAGE 14B V2 - PIE RUNTIME COLLISION VALIDATION")
    ns["log"]("=" * 96)
    ns["log"]("Read-only readiness gate: no builder, collision mutation, package save, or PIE start/stop command is issued.")
    ns["log"](f"PIE_WORLD={world.get_path_name()}")
    ns["log"](f"PIE_COMPILED_SECTIONS={len(sections)}")
    ns["log"](f"PIE_COMPILED_SECTION_COMPONENTS={readiness['component_total']}")
    ns["log"](f"PIE_STATIC_MESH_COMPONENTS={readiness['static_mesh_component_total']}")
    ns["log"](f"PIE_COMPILING_STATIC_MESH_COMPONENTS={len(readiness['compiling_components'])}")
    ns["log"](f"PIE_COMPILING_STATIC_MESH_ASSETS={len(readiness['compiling_meshes'])}")
    for value in readiness["compiling_components"][:20]:
        ns["log"](f"  COMPILING_COMPONENT={value}")
    for value in readiness["compiling_meshes"][:20]:
        ns["log"](f"  COMPILING_MESH={value}")
    ns["log"]("")
    ns["log"]("PIE_MESH_PARTITION_READY=False")
    ns["log"]("TERRAIN_TRACES_SKIPPED_UNTIL_COMPILATION_FINISHES=TRUE")
    ns["log"]("PIE_RUNTIME_VALIDATION_RESULT=WAITING")
    ns["log"]("RERUN_THE_SAME_VALIDATOR_AFTER_PLAY_BECOMES_RESPONSIVE=TRUE")
    ns["log"]("NO_BUILD_METHOD_CALLED=TRUE")
    ns["log"]("NO_COLLISION_SETTINGS_CHANGED=TRUE")
    ns["log"]("NO_PACKAGES_SAVED=TRUE")
    ns["log"]("NO_PIE_START_OR_STOP_COMMAND_CALLED=TRUE")
    ns["log"]("NO_WHOLE_WORLD_MESH_PARTITION_BUILD_WAS_STARTED=TRUE")
    ns["write_report"]()
    unreal.log_warning(f"AETHER_STAGE14_PIE_RUNTIME_REPORT={ns['REPORT_PATH']}")


def main():
    world = ns["get_pie_world"]()
    if not world:
        ns["main"]()
        return

    sections = ns["collect_compiled_sections"](world)
    readiness = compiled_section_readiness(sections)
    pending = len(readiness["compiling_components"]) + len(readiness["compiling_meshes"])
    if pending > 0:
        write_waiting_report(world, sections, readiness)
        return

    unreal.log_warning("PIE_MESH_PARTITION_READY=True")
    ns["main"]()


try:
    main()
except Exception:
    raise
