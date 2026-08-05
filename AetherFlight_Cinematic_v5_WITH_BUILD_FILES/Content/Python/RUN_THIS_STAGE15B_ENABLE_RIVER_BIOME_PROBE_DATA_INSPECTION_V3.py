"""Stage 15B temporary probe inspection V3 launcher for UE 5.8.1.

V2 reached ToolsetRegistry successfully but its delegate callback used *args. Unreal
reflection treated that as zero fixed parameters while ToolCallAsyncResultCompleted
requires exactly one parameter. V3 patches the callback to one explicit parameter,
uses a separate state key/report, compile-checks the patched source, then executes it.

No persistent graph, level package, full river volume, or Mesh Partition data is
modified or saved by this launcher.
"""

from pathlib import Path
import unreal

SOURCE_PATH = Path(__file__).with_name(
    "RUN_THIS_STAGE15B_ENABLE_RIVER_BIOME_PROBE_DATA_INSPECTION_V2.py"
)


def replace_exact(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Stage15B inspection V3 expected exactly one {label}; found {count}"
        )
    return source.replace(old, new, 1)


def replace_all_checked(source, old, new, minimum, label):
    count = source.count(old)
    if count < minimum:
        raise RuntimeError(
            f"Stage15B inspection V3 expected at least {minimum} {label}; found {count}"
        )
    return source.replace(old, new)


def main():
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"Stage 15B inspection V2 source is missing: {SOURCE_PATH}")

    source = SOURCE_PATH.read_text(encoding="utf-8")
    source = replace_exact(
        source,
        "    def completed(*_args):",
        "    def completed(completed_result):",
        "async callback signature",
    )
    source = replace_exact(
        source,
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeInspectionEnableV2.txt"',
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeInspectionEnableV3.txt"',
        "report path",
    )
    source = replace_exact(
        source,
        'STATE_KEY = "_AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V2"',
        'STATE_KEY = "_AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V3"',
        "state key",
    )
    source = replace_all_checked(
        source,
        "PROBE_INSPECTION_ENABLE_V2_RESULT",
        "PROBE_INSPECTION_ENABLE_V3_RESULT",
        2,
        "result markers",
    )
    source = replace_all_checked(
        source,
        "AETHER STAGE 15B - ENABLE TEMPORARY PROBE NODE DATA INSPECTION V2",
        "AETHER STAGE 15B - ENABLE TEMPORARY PROBE NODE DATA INSPECTION V3",
        2,
        "report titles",
    )
    source = replace_exact(
        source,
        "AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V2_REPORT",
        "AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V3_REPORT",
        "report log marker",
    )
    source = source.replace(
        "RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_PROBE_NODE_DATA_V2.py",
        "RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_PROBE_NODE_DATA_V3.py",
    )

    compile(source, str(SOURCE_PATH), "exec")
    unreal.log_warning("AETHER_STAGE15B_INSPECTION_V3_CALLBACK_SIGNATURE=ONE_EXPLICIT_ARGUMENT")
    unreal.log_warning("AETHER_STAGE15B_INSPECTION_V3_PATCHED_SOURCE_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
        "__package__": None,
    }
    exec(compile(source, str(SOURCE_PATH), "exec"), namespace, namespace)


main()
