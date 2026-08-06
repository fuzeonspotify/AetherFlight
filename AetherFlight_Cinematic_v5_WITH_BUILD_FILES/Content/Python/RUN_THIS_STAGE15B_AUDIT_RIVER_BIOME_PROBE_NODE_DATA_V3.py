"""Read-only Stage 15B Query/ToPoint node-data audit V3 launcher for UE 5.8.1.

Patches the V2 ToolCallAsyncResultCompleted callback from *args to one explicit
parameter, matching Unreal's delegate signature. Uses a separate state key/report,
compile-checks the patched source, then executes it.

No graph, actor, package, generation, or Mesh Partition data is modified, saved,
generated, cleaned, or built.
"""

from pathlib import Path
import unreal

SOURCE_PATH = Path(__file__).with_name(
    "RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_PROBE_NODE_DATA_V2.py"
)


def replace_exact(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Stage15B node-data V3 expected exactly one {label}; found {count}"
        )
    return source.replace(old, new, 1)


def replace_all_checked(source, old, new, minimum, label):
    count = source.count(old)
    if count < minimum:
        raise RuntimeError(
            f"Stage15B node-data V3 expected at least {minimum} {label}; found {count}"
        )
    return source.replace(old, new)


def main():
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"Stage 15B node-data V2 source is missing: {SOURCE_PATH}")

    source = SOURCE_PATH.read_text(encoding="utf-8")
    source = replace_exact(
        source,
        "    def completed(*_args):",
        "    def completed(completed_result):",
        "async callback signature",
    )
    source = replace_exact(
        source,
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeNodeDataV2.txt"',
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeNodeDataV3.txt"',
        "report path",
    )
    source = replace_exact(
        source,
        'STATE_KEY = "_AETHER_STAGE15B_PROBE_NODE_DATA_AUDIT_V2"',
        'STATE_KEY = "_AETHER_STAGE15B_PROBE_NODE_DATA_AUDIT_V3"',
        "state key",
    )
    source = replace_all_checked(
        source,
        "NODE_DATA_AUDIT_V2_RESULT",
        "NODE_DATA_AUDIT_V3_RESULT",
        2,
        "result markers",
    )
    source = replace_all_checked(
        source,
        "AETHER STAGE 15B - TEMPORARY PROBE QUERY/TOPOINT NODE DATA AUDIT V2",
        "AETHER STAGE 15B - TEMPORARY PROBE QUERY/TOPOINT NODE DATA AUDIT V3",
        2,
        "report titles",
    )
    source = replace_exact(
        source,
        "AETHER_STAGE15B_PROBE_NODE_DATA_V2_REPORT",
        "AETHER_STAGE15B_PROBE_NODE_DATA_V3_REPORT",
        "report log marker",
    )

    compile(source, str(SOURCE_PATH), "exec")
    unreal.log_warning("AETHER_STAGE15B_NODE_DATA_V3_CALLBACK_SIGNATURE=ONE_EXPLICIT_ARGUMENT")
    unreal.log_warning("AETHER_STAGE15B_NODE_DATA_V3_PATCHED_SOURCE_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
        "__package__": None,
    }
    exec(compile(source, str(SOURCE_PATH), "exec"), namespace, namespace)


main()
