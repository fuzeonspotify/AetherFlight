"""Stage 15B temporary river-biome probe launcher V3 for UE 5.8.1.

V2 stopped safely because this UE Python build does not expose the global
unreal.get_transient_package helper. The earlier successful Stage 15B graph API
audit used a guarded lookup that returns None when the helper is unavailable;
unreal.new_object then creates the PCGGraph as a transient object with no outer.

V3 patches that exact compatibility point inside the V2 launcher, compiles the
result, and executes it. The persistent graph and full river volume remain
untouched, and no package is saved.
"""

from pathlib import Path
import unreal

SOURCE_PATH = Path(__file__).with_name("RUN_THIS_STAGE15B_START_RIVER_BIOME_PROBE_V2.py")


def replace_exact(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Stage15B probe V3 expected exactly one {label}; found {count}"
        )
    return source.replace(old, new, 1)


def main():
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"Stage 15B probe V2 is missing: {SOURCE_PATH}")

    source = SOURCE_PATH.read_text(encoding="utf-8")
    source = replace_exact(
        source,
        "    transient_package = unreal.get_transient_package()",
        "    transient_package = safe_call(lambda: unreal.get_transient_package())",
        "transient-package construction line",
    )

    # Update V2's visible compatibility marker so the executed path is unambiguous.
    source = replace_exact(
        source,
        'unreal.log_warning("AETHER_STAGE15B_PROBE_COMPATIBILITY=V2")',
        'unreal.log_warning("AETHER_STAGE15B_PROBE_COMPATIBILITY=V3")',
        "compatibility marker",
    )

    compile(source, str(SOURCE_PATH), "exec")

    unreal.log_warning("AETHER_STAGE15B_PROBE_V3_OUTER_FALLBACK=NONE_TRANSIENT")
    unreal.log_warning("AETHER_STAGE15B_PROBE_V3_PATCHED_V2_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
        "__package__": None,
    }
    exec(compile(source, str(SOURCE_PATH), "exec"), namespace, namespace)


main()
