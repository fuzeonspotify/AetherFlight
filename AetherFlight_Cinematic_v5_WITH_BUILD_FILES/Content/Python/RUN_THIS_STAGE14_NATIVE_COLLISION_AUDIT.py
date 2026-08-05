"""Run the read-only native Stage 14 river collision registration audit during PIE."""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage14NativeCollisionAudit.txt"


def log(text=""):
    unreal.log_warning(str(text))


def main():
    cls = getattr(unreal, "AetherMeshPartitionDiagnostics", None)
    if cls is None:
        raise RuntimeError(
            "AetherMeshPartitionDiagnostics is unavailable. Close Unreal, rebuild the AetherFlightEditor target, then reopen the project."
        )

    method = getattr(cls, "audit_pie_mesh_partition_collision", None)
    if not callable(method):
        raise RuntimeError("Native collision audit function is not exposed to Python")

    report = str(method())
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report.rstrip() + "\n", encoding="utf-8")
    for line in report.splitlines():
        log(line)
    log(f"AETHER_STAGE14_NATIVE_COLLISION_AUDIT_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    failure = "\n".join(
        (
            "AETHER STAGE 14I - NATIVE RIVER COLLISION REGISTRATION AUDIT",
            "=" * 100,
            "NATIVE_AUDIT_RESULT=FAIL",
            f"ERROR={type(exc).__name__}: {exc}",
            "NO_COLLISION_SETTINGS_CHANGED=TRUE",
            "NO_COMPONENT_REBUILD_CALLED=TRUE",
            "NO_PACKAGES_SAVED=TRUE",
            "NO_PIE_START_OR_STOP_COMMAND_CALLED=TRUE",
            "NO_MESH_PARTITION_BUILD_WAS_STARTED=TRUE",
        )
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(failure + "\n", encoding="utf-8")
    unreal.log_error(failure)
    raise
