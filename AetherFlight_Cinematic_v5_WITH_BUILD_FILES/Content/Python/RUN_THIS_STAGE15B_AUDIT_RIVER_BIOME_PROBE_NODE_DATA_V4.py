"""Read-only Stage 15B Query/ToPoint node-data audit V4 launcher for UE 5.8.1.

Patches the V2 audit to use one explicit async callback parameter and pass the local
GetNodeDataView tool name while ToolsetName is supplied separately. Uses separate
state/report markers, compile-checks the patched source, then executes it.

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
            f"Stage15B node-data V4 expected exactly one {label}; found {count}"
        )
    return source.replace(old, new, 1)


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
        '    full_name = f"{TOOLSET_NAME}.GetNodeDataView"\n',
        '    full_name = f"{TOOLSET_NAME}.GetNodeDataView"\n    tool_name = "GetNodeDataView"\n',
        "local tool-name declaration",
    )
    source = replace_exact(
        source,
        "            full_name,\n            json.dumps(payload, separators=(\",\", \":\")),\n",
        "            tool_name,\n            json.dumps(payload, separators=(\",\", \":\")),\n",
        "execute_tool local-name argument",
    )
    source = replace_exact(
        source,
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeNodeDataV2.txt"',
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeNodeDataV4.txt"',
        "report path",
    )
    source = replace_exact(
        source,
        'STATE_KEY = "_AETHER_STAGE15B_PROBE_NODE_DATA_AUDIT_V2"',
        'STATE_KEY = "_AETHER_STAGE15B_PROBE_NODE_DATA_AUDIT_V4"',
        "state key",
    )
    source = source.replace(
        "NODE_DATA_AUDIT_V2_RESULT",
        "NODE_DATA_AUDIT_V4_RESULT",
    )
    source = source.replace(
        "AETHER STAGE 15B - TEMPORARY PROBE QUERY/TOPOINT NODE DATA AUDIT V2",
        "AETHER STAGE 15B - TEMPORARY PROBE QUERY/TOPOINT NODE DATA AUDIT V4",
    )
    source = source.replace(
        "AETHER_STAGE15B_PROBE_NODE_DATA_V2_REPORT",
        "AETHER_STAGE15B_PROBE_NODE_DATA_V4_REPORT",
    )

    marker = '            "TOOLSET_ROUTE=ToolsetRegistry.execute_tool",\n'
    replacement = (
        '            "TOOLSET_ROUTE=ToolsetRegistry.execute_tool",\n'
        '            "TOOL_NAME_MODE=LOCAL_NAMES",\n'
        '            "ASYNC_CALLBACK_SIGNATURE=ONE_EXPLICIT_ARGUMENT",\n'
    )
    source = replace_exact(source, marker, replacement, "V4 route marker")

    compile(source, str(SOURCE_PATH) + "::V4_PATCHED", "exec")
    unreal.log_warning("AETHER_STAGE15B_NODE_DATA_V4_TOOL_NAME=GetNodeDataView")
    unreal.log_warning("AETHER_STAGE15B_NODE_DATA_V4_CALLBACK=ONE_ARGUMENT")
    unreal.log_warning("AETHER_STAGE15B_NODE_DATA_V4_PATCHED_SOURCE_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
    }
    exec(compile(source, str(SOURCE_PATH) + "::V4_PATCHED", "exec"), namespace, namespace)


main()
