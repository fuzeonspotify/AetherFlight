"""Stage 15B river-biome installer compatibility launcher for UE 5.8.1.

The first guarded installer failed safely because UE exposes the comparison enum as
LESSER_OR_EQUAL (not LESS_OR_EQUAL). UE 5.8.1 also emits handled Python wrapper
ensures when the inherited selector mutator is called directly on derived PCG
selector structs. This launcher patches those two compatibility points in memory
and then executes the original guarded installer. It does not modify the original
script on disk.
"""

from pathlib import Path
import unreal

SOURCE_PATH = Path(__file__).with_name("RUN_THIS_STAGE15B_INSTALL_RIVER_BIOME.py")


def replace_exact(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Stage15B V2 compatibility patch expected exactly one {label} block; found {count}"
        )
    return source.replace(old, new, 1)


def main():
    if not SOURCE_PATH.exists():
        raise RuntimeError(f"Original Stage 15B installer is missing: {SOURCE_PATH}")

    source = SOURCE_PATH.read_text(encoding="utf-8")

    source = replace_exact(
        source,
        '("LESS_OR_EQUAL", "LESS_THAN_OR_EQUAL", "LESS_EQUAL", "LESS"),',
        '(
                "LESSER_OR_EQUAL",
                "LESS_OR_EQUAL",
                "LESS_THAN_OR_EQUAL",
                "LESS_EQUAL",
                "LESSER",
                "LESS",
            ),',
        "less-than comparison enum",
    )

    old_attribute_selector = '''def selector_for_attribute(name):
    selector = unreal.PCGAttributePropertyInputSelector()
    if not selector.set_attribute_name(unreal.Name(name)):
        raise RuntimeError(f"Could not select attribute {name}")
    return selector
'''
    new_attribute_selector = '''def selector_for_attribute(name):
    selector = unreal.PCGAttributePropertyInputSelector()
    import_candidates = (
        f'(Selection=Attribute,AttributeName="{name}")',
        f'(Selection=Attribute,AttributeName={name})',
    )
    for text in import_candidates:
        try:
            if selector.import_text(text):
                return selector
        except Exception:
            pass
    helper = getattr(unreal, "PCGAttributePropertySelectorBlueprintHelpers", None)
    if helper is not None:
        try:
            helper.set_attribute_name(selector, unreal.Name(name), True)
            if str(helper.get_attribute_name(selector)) == str(name):
                return selector
        except Exception:
            pass
    raise RuntimeError(f"Could not select attribute {name} without the UE 5.8 derived-struct wrapper path")
'''
    source = replace_exact(
        source,
        old_attribute_selector,
        new_attribute_selector,
        "attribute selector",
    )

    old_density_selector = '''def selector_for_density(output=False):
    selector_type = unreal.PCGAttributePropertyOutputSelector if output else unreal.PCGAttributePropertyInputSelector
    selector = selector_type()
    density = enum_value(unreal.PCGPointProperties, ("DENSITY",))
    if not selector.set_point_property(density):
        raise RuntimeError("Could not select PCG point Density property")
    return selector
'''
    new_density_selector = '''def selector_for_density(output=False):
    selector_type = unreal.PCGAttributePropertyOutputSelector if output else unreal.PCGAttributePropertyInputSelector
    selector = selector_type()
    import_candidates = (
        '(Selection=PointProperty,PointProperty=Density)',
        '(Selection=PointProperty,PointProperty=DENSITY)',
    )
    for text in import_candidates:
        try:
            if selector.import_text(text):
                return selector
        except Exception:
            pass
    density = enum_value(unreal.PCGPointProperties, ("DENSITY",))
    helper = getattr(unreal, "PCGAttributePropertySelectorBlueprintHelpers", None)
    if helper is not None:
        try:
            helper.set_point_property(selector, density, True)
            if helper.get_point_property(selector) == density:
                return selector
        except Exception:
            pass
    raise RuntimeError("Could not select PCG point Density without the UE 5.8 derived-struct wrapper path")
'''
    source = replace_exact(
        source,
        old_density_selector,
        new_density_selector,
        "density selector",
    )

    unreal.log_warning("AETHER_STAGE15B_INSTALLER_COMPATIBILITY=V2")
    unreal.log_warning("AETHER_STAGE15B_ENUM_FIX=LESSER_OR_EQUAL")
    unreal.log_warning("AETHER_STAGE15B_SELECTOR_WRAPPER_FIX=STRUCT_IMPORT_TEXT")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE_PATH),
        "__package__": None,
    }
    exec(compile(source, str(SOURCE_PATH), "exec"), namespace, namespace)


main()
