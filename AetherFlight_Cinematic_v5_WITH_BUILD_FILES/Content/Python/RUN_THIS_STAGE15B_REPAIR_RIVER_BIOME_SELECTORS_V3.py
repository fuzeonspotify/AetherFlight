"""Stage 15B selector repair V3 launcher for UE 5.8.1.

V2 successfully assigned and read back all derived selector structs, but nested PCG
settings edits did not automatically dirty the outer graph package. V3 patches V2
in memory to:
- call modify() on the graph and the 16 affected settings before persistent edits;
- call post_edit_change() on affected settings and the graph after verified edits;
- attempt graph.mark_package_dirty() and package.set_dirty_flag(True);
- force-save only PCG_Aether_RiverBiome even if this UE build still reports the
  package as clean.

The level, PCG volume, generated state, and Mesh Partition data remain untouched.
"""

from pathlib import Path
import unreal

SOURCE_PATH = Path(__file__).with_name(
    "RUN_THIS_STAGE15B_REPAIR_RIVER_BIOME_SELECTORS_V2.py"
)


def replace_exact(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Stage15B selector repair V3 expected exactly one {label}; found {count}"
        )
    return source.replace(old, new, 1)


def replace_count(source, old, new, expected_count, label):
    count = source.count(old)
    if count != expected_count:
        raise RuntimeError(
            f"Stage15B selector repair V3 expected {expected_count} {label}; found {count}"
        )
    return source.replace(old, new)


def main():
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"Stage 15B selector repair V2 is missing: {SOURCE_PATH}")

    source = SOURCE_PATH.read_text(encoding="utf-8")

    source = replace_exact(
        source,
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeSelectorRepairV2.txt"',
        'REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeSelectorRepairV3.txt"',
        "report path",
    )

    source = replace_count(
        source,
        "AETHER STAGE 15B - RIVER BIOME SELECTOR REPAIR V2",
        "AETHER STAGE 15B - RIVER BIOME SELECTOR REPAIR V3",
        2,
        "repair title markers",
    )
    source = replace_count(
        source,
        "SELECTOR_REPAIR_V2_RESULT",
        "SELECTOR_REPAIR_V3_RESULT",
        2,
        "result markers",
    )

    old_setup = '''    filters = settings_by_class["PCGAttributeFilteringSettings"]
    noises = settings_by_class["PCGAttributeNoiseSettings"]
    repaired = 0
'''
    new_setup = '''    filters = settings_by_class["PCGAttributeFilteringSettings"]
    noises = settings_by_class["PCGAttributeNoiseSettings"]
    repaired = 0

    # Nested settings struct edits do not reliably propagate package dirtiness in
    # this UE Python build. Establish proper editor transactions before editing.
    graph_modify_result = safe_call(lambda: graph.modify(), False)
    settings_modify_true = 0
    settings_modify_attempts = 0
    for affected_settings in list(filters) + list(noises):
        settings_modify_attempts += 1
        result = safe_call(
            lambda affected_settings=affected_settings: affected_settings.modify(),
            False,
        )
        if bool(result):
            settings_modify_true += 1
    lines.append(f"GRAPH_MODIFY_RESULT={graph_modify_result}")
    lines.append(f"SETTINGS_MODIFY_ATTEMPTS={settings_modify_attempts}")
    lines.append(f"SETTINGS_MODIFY_TRUE={settings_modify_true}")
'''
    source = replace_exact(source, old_setup, new_setup, "persistent edit setup block")

    old_dirty_block = '''    dirty_after_edit = package_dirty(graph)
    lines.append(f"GRAPH_DIRTY_AFTER_EDIT={dirty_after_edit}")
    if not dirty_after_edit:
        raise RuntimeError("Graph did not become dirty after selector repair")

    saved = unreal.EditorAssetLibrary.save_asset(GRAPH_OBJECT_PATH, only_if_is_dirty=False)
'''
    new_dirty_block = '''    # Notify the editor after all 20 selector readbacks have passed.
    settings_post_edit_calls = 0
    for affected_settings in list(filters) + list(noises):
        method = getattr(affected_settings, "post_edit_change", None)
        if callable(method):
            try:
                method()
                settings_post_edit_calls += 1
            except Exception:
                pass
    graph_post_edit_called = False
    graph_post_edit = getattr(graph, "post_edit_change", None)
    if callable(graph_post_edit):
        try:
            graph_post_edit()
            graph_post_edit_called = True
        except Exception:
            pass
    lines.append(f"SETTINGS_POST_EDIT_CHANGE_CALLS={settings_post_edit_calls}")
    lines.append(f"GRAPH_POST_EDIT_CHANGE_CALLED={graph_post_edit_called}")

    dirty_after_edit = package_dirty(graph)
    lines.append(f"GRAPH_DIRTY_AFTER_EDIT={dirty_after_edit}")

    dirty_mark_routes = []
    if not dirty_after_edit:
        mark_graph = getattr(graph, "mark_package_dirty", None)
        if callable(mark_graph):
            try:
                result = mark_graph()
                dirty_mark_routes.append(f"graph.mark_package_dirty:{result}")
            except Exception as exc:
                dirty_mark_routes.append(
                    f"graph.mark_package_dirty:{type(exc).__name__}:{exc}"
                )

    package = safe_call(lambda: graph.get_outermost())
    if not package_dirty(graph) and package is not None:
        set_dirty = getattr(package, "set_dirty_flag", None)
        if callable(set_dirty):
            try:
                result = set_dirty(True)
                dirty_mark_routes.append(f"package.set_dirty_flag:{result}")
            except Exception as exc:
                dirty_mark_routes.append(
                    f"package.set_dirty_flag:{type(exc).__name__}:{exc}"
                )

    dirty_after_mark = package_dirty(graph)
    lines.append(
        "GRAPH_DIRTY_MARK_ROUTES="
        + (" | ".join(dirty_mark_routes) if dirty_mark_routes else "NONE_AVAILABLE")
    )
    lines.append(f"GRAPH_DIRTY_AFTER_EXPLICIT_MARK={dirty_after_mark}")
    lines.append("GRAPH_SAVE_MODE=FORCED_ONLY_IF_IS_DIRTY_FALSE")

    # Readbacks already proved the exact 20 in-memory values. Force-saving this one
    # graph is the authoritative persistence operation even if package dirtiness is
    # not surfaced correctly by this experimental PCG Python path.
    saved = unreal.EditorAssetLibrary.save_asset(GRAPH_OBJECT_PATH, only_if_is_dirty=False)
'''
    source = replace_exact(source, old_dirty_block, new_dirty_block, "dirty/save block")

    source = replace_exact(
        source,
        '        "SELECTOR_REPAIR_V3_RESULT=PASS",',
        '        "SELECTOR_REPAIR_V3_RESULT=PASS",\n        "PERSISTENCE_REQUIRES_FRESH_RELOAD_AUDIT=TRUE",',
        "V3 pass marker",
    )

    compile(source, str(SOURCE_PATH), "exec")

    unreal.log_warning("AETHER_STAGE15B_SELECTOR_REPAIR_COMPATIBILITY=V3")
    unreal.log_warning("AETHER_STAGE15B_SELECTOR_REPAIR_V3_NESTED_DIRTY_FIX=ENABLED")
    unreal.log_warning("AETHER_STAGE15B_SELECTOR_REPAIR_V3_FORCE_SINGLE_ASSET_SAVE=ENABLED")
    unreal.log_warning("AETHER_STAGE15B_SELECTOR_REPAIR_V3_PATCHED_V2_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
        "__package__": None,
    }
    exec(compile(source, str(SOURCE_PATH), "exec"), namespace, namespace)


main()
