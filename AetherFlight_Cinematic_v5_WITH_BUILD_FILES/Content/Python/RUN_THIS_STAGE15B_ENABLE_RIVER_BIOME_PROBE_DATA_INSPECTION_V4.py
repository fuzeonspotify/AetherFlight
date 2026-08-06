"""Stage 15B temporary probe inspection V4 launcher for UE 5.8.1.

V3 proved ToolsetRegistry and the one-argument completion delegate work, but passed
fully-qualified schema names as ToolName while ToolsetName was already supplied.
This build expects local names such as GetNodeDataView and ExecuteGraphInstance.

V4 patches V2 in memory to use one explicit callback argument, pass local tool
names, reject Unknown tool as an inspection-arm response, use separate state/report
markers, compile-check the patched source, and execute it.

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
            f"Stage15B inspection V4 expected exactly one {label}; found {count}"
        )
    return source.replace(old, new, 1)


def replace_count(source, old, new, expected, label):
    count = source.count(old)
    if count != expected:
        raise RuntimeError(
            f"Stage15B inspection V4 expected {expected} {label}; found {count}"
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
        '    full_name = f"{TOOLSET_NAME}.{local_name}"\n',
        '    full_name = f"{TOOLSET_NAME}.{local_name}"\n    tool_name = local_name\n',
        "local tool-name declaration",
    )
    source = replace_exact(
        source,
        "            full_name,\n            json.dumps(payload, separators=(\",\", \":\")),\n",
        "            tool_name,\n            json.dumps(payload, separators=(\",\", \":\")),\n",
        "execute_tool local-name argument",
    )

    old_accept = '        accepted = not error or any(token in error.lower() for token in ("inspection", "execute", "data"))\n'
    new_accept = '''        lowered_error = error.lower()
        accepted = (
            not error
            or "no inspection data" in lowered_error
            or "re-execute" in lowered_error
            or "reexecute" in lowered_error
            or ("inspection" in lowered_error and "data" in lowered_error)
        )
'''
    source = replace_count(
        source,
        old_accept,
        new_accept,
        2,
        "inspection-arm acceptance blocks",
    )

    source = replace_exact(
        source,
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeInspectionEnableV2.txt"',
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeProbeInspectionEnableV4.txt"',
        "report path",
    )
    source = replace_exact(
        source,
        'STATE_KEY = "_AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V2"',
        'STATE_KEY = "_AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V4"',
        "state key",
    )
    source = source.replace(
        "PROBE_INSPECTION_ENABLE_V2_RESULT",
        "PROBE_INSPECTION_ENABLE_V4_RESULT",
    )
    source = source.replace(
        "AETHER STAGE 15B - ENABLE TEMPORARY PROBE NODE DATA INSPECTION V2",
        "AETHER STAGE 15B - ENABLE TEMPORARY PROBE NODE DATA INSPECTION V4",
    )
    source = source.replace(
        "AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V2_REPORT",
        "AETHER_STAGE15B_PROBE_INSPECTION_ENABLE_V4_REPORT",
    )
    source = source.replace(
        "RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_PROBE_NODE_DATA_V2.py",
        "RUN_THIS_STAGE15B_AUDIT_RIVER_BIOME_PROBE_NODE_DATA_V4.py",
    )

    marker = '            "TOOLSET_ROUTE=ToolsetRegistry.execute_tool",\n'
    replacement = (
        '            "TOOLSET_ROUTE=ToolsetRegistry.execute_tool",\n'
        '            "TOOL_NAME_MODE=LOCAL_NAMES",\n'
        '            "ASYNC_CALLBACK_SIGNATURE=ONE_EXPLICIT_ARGUMENT",\n'
        '            "UNKNOWN_TOOL_ACCEPTED_AS_ARM_RESPONSE=FALSE",\n'
    )
    source = replace_exact(source, marker, replacement, "V4 route marker")

    compile(source, str(SOURCE_PATH) + "::V4_PATCHED", "exec")
    unreal.log_warning("AETHER_STAGE15B_INSPECTION_V4_TOOL_NAMES=LOCAL")
    unreal.log_warning("AETHER_STAGE15B_INSPECTION_V4_CALLBACK=ONE_ARGUMENT")
    unreal.log_warning("AETHER_STAGE15B_INSPECTION_V4_UNKNOWN_TOOL_GUARD=ENABLED")
    unreal.log_warning("AETHER_STAGE15B_INSPECTION_V4_PATCHED_SOURCE_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
    }
    exec(compile(source, str(SOURCE_PATH) + "::V4_PATCHED", "exec"), namespace, namespace)


main()
