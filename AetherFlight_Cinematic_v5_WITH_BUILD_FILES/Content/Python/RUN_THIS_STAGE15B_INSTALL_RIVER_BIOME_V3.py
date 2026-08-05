"""Stage 15B river-biome installer compatibility launcher V3 for UE 5.8.1.

V2 never executed because its multiline enum replacement was written as a
single-quoted Python literal. This launcher applies the same guarded
compatibility changes using syntactically valid triple-quoted replacement
blocks, then executes the original installer in memory.

No source file is modified on disk. The original installer's rollback and
no-generation protections remain active.
"""

from pathlib import Path
import unreal

SOURCE_PATH = Path(__file__).with_name("RUN_THIS_STAGE15B_INSTALL_RIVER_BIOME.py")


def replace_exact(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Stage15B V3 compatibility patch expected exactly one {label} block; found {count}"
        )
    return source.replace(old, new, 1)


def main():
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"Original Stage 15B installer is missing: {SOURCE_PATH}")

    source = SOURCE_PATH.read_text(encoding="utf-8")

    old_enum = '("LESS_OR_EQUAL", "LESS_THAN_OR_EQUAL", "LESS_EQUAL", "LESS"),'
    new_enum = """(
                "LESSER_OR_EQUAL",
                "LESS_OR_EQUAL",
                "LESS_THAN_OR_EQUAL",
                "LESS_EQUAL",
                "LESSER",
                "LESS",
            ),"""
    source = replace_exact(
        source,
        old_enum,
        new_enum,
        "less-than comparison enum",
    )

    old_attribute_selector = """def selector_for_attribute(name):
    selector = unreal.PCGAttributePropertyInputSelector()
    if not selector.set_attribute_name(unreal.Name(name)):
        raise RuntimeError(f"Could not select attribute {name}")
    return selector
"""
    new_attribute_selector = """def selector_for_attribute(name):
    selector = unreal.PCGAttributePropertyInputSelector()
    import_candidates = (
        f'(Selection=Attribute,AttributeName="{name}")',
        f'(Selection=Attribute,AttributeName={name})',
    )
    for text in import_candidates:
        try:
            result = selector.import_text(text)
            if result is not False:
                return selector
        except Exception:
            pass
    helper = getattr(unreal, "PCGAttributePropertySelectorBlueprintHelpers", None)
    if helper is not None:
        try:
            helper.set_attribute_name(selector, unreal.Name(name), True)
            return selector
        except Exception:
            pass
    raise RuntimeError(
        f"Could not select attribute {name} without the UE 5.8 derived-struct wrapper path"
    )
"""
    source = replace_exact(
        source,
        old_attribute_selector,
        new_attribute_selector,
        "attribute selector",
    )

    old_density_selector = """def selector_for_density(output=False):
    selector_type = unreal.PCGAttributePropertyOutputSelector if output else unreal.PCGAttributePropertyInputSelector
    selector = selector_type()
    density = enum_value(unreal.PCGPointProperties, ("DENSITY",))
    if not selector.set_point_property(density):
        raise RuntimeError("Could not select PCG point Density property")
    return selector
"""
    new_density_selector = """def selector_for_density(output=False):
    selector_type = unreal.PCGAttributePropertyOutputSelector if output else unreal.PCGAttributePropertyInputSelector
    selector = selector_type()
    import_candidates = (
        '(Selection=PointProperty,PointProperty=Density)',
        '(Selection=PointProperty,PointProperty=DENSITY)',
    )
    for text in import_candidates:
        try:
            result = selector.import_text(text)
            if result is not False:
                return selector
        except Exception:
            pass
    density = enum_value(unreal.PCGPointProperties, ("DENSITY",))
    helper = getattr(unreal, "PCGAttributePropertySelectorBlueprintHelpers", None)
    if helper is not None:
        try:
            helper.set_point_property(selector, density, True)
            return selector
        except Exception:
            pass
    raise RuntimeError(
        "Could not select PCG point Density without the UE 5.8 derived-struct wrapper path"
    )
"""
    source = replace_exact(
        source,
        old_density_selector,
        new_density_selector,
        "density selector",
    )

    compile(source, str(SOURCE_PATH), "exec")

    unreal.log_warning("AETHER_STAGE15B_INSTALLER_COMPATIBILITY=V3")
    unreal.log_warning("AETHER_STAGE15B_ENUM_FIX=LESSER_OR_EQUAL")
    unreal.log_warning("AETHER_STAGE15B_SELECTOR_WRAPPER_FIX=STRUCT_IMPORT_TEXT")
    unreal.log_warning("AETHER_STAGE15B_PATCHED_SOURCE_COMPILE=PASS")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
        "__package__": None,
    }
    exec(compile(source, str(SOURCE_PATH), "exec"), namespace, namespace)


main()
