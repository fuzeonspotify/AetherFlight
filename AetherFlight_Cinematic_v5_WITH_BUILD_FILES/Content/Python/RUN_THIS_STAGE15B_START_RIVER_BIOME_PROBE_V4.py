"""Stage 15B temporary river-biome probe launcher V4 for UE 5.8.1.

V3 stopped before execution because the V2 launcher contains the transient-package
construction line twice: once inside the old source block and once inside the new
clone block. V4 patches only the occurrence inside V2's new_clone block.

The persistent graph and full river volume remain untouched, no actor is created
unless the patched V2 probe reaches its guarded creation stage, and no package is
saved.
"""

from pathlib import Path
import unreal

SOURCE_PATH = Path(__file__).with_name("RUN_THIS_STAGE15B_START_RIVER_BIOME_PROBE_V2.py")
NEW_CLONE_MARKER = '    new_clone = """def _pin_label(pin):'
TRANSIENT_LINE = "    transient_package = unreal.get_transient_package()"
TRANSIENT_REPLACEMENT = "    transient_package = safe_call(lambda: unreal.get_transient_package())"


def replace_exact(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Stage15B probe V4 expected exactly one {label}; found {count}"
        )
    return source.replace(old, new, 1)


def main():
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"Stage 15B probe V2 is missing: {SOURCE_PATH}")

    source = SOURCE_PATH.read_text(encoding="utf-8")

    marker_count = source.count(NEW_CLONE_MARKER)
    if marker_count != 1:
        raise RuntimeError(
            f"Stage15B probe V4 expected one new_clone marker; found {marker_count}"
        )

    prefix, marker, clone_tail = source.partition(NEW_CLONE_MARKER)
    executable_count = clone_tail.count(TRANSIENT_LINE)
    if executable_count != 1:
        raise RuntimeError(
            "Stage15B probe V4 expected one transient-package line inside "
            f"new_clone; found {executable_count}"
        )

    clone_tail = clone_tail.replace(
        TRANSIENT_LINE,
        TRANSIENT_REPLACEMENT,
        1,
    )
    source = prefix + marker + clone_tail

    source = replace_exact(
        source,
        'unreal.log_warning("AETHER_STAGE15B_PROBE_COMPATIBILITY=V2")',
        'unreal.log_warning("AETHER_STAGE15B_PROBE_COMPATIBILITY=V4")',
        "compatibility marker",
    )

    compile(source, str(SOURCE_PATH), "exec")

    unreal.log_warning("AETHER_STAGE15B_PROBE_V4_PATCH_SCOPE=NEW_CLONE_ONLY")
    unreal.log_warning("AETHER_STAGE15B_PROBE_V4_OUTER_FALLBACK=NONE_TRANSIENT")
    unreal.log_warning("AETHER_STAGE15B_PROBE_V4_PATCHED_V2_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
        "__package__": None,
    }
    exec(compile(source, str(SOURCE_PATH), "exec"), namespace, namespace)


main()
