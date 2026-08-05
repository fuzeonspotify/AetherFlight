"""Read-only semantic audit for the saved Stage 15B river-biome PCG graph.

The first bounded generation probe completed but produced zero instances. Before
loosening density or changing the persistent graph, this audit verifies the saved
attribute selectors, comparison operators, thresholds, deterministic density-noise
settings, and density gates for all four branches.

No graph, actor, component, package, generated output, or Mesh Partition data is
modified, saved, generated, cleaned, or built.
"""

from pathlib import Path
import math
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BRiverBiomeFilterSemantics.txt"
GRAPH_OBJECT_PATH = "/Game/Aether/PCG/Biomes/PCG_Aether_RiverBiome.PCG_Aether_RiverBiome"

FILTER_SPECS = (
    # branch, role, attribute, operator token, threshold
    ("Trees", "Include", "Wetland", "GREATER_OR_EQUAL", 0.12),
    ("Trees", "Water", "Water", "LESSER_OR_EQUAL", 0.05),
    ("Trees", "Exclusion", "FoliageExclusion", "LESSER_OR_EQUAL", 0.05),
    ("Shrubs", "Include", "Wetland", "GREATER_OR_EQUAL", 0.08),
    ("Shrubs", "Water", "Water", "LESSER_OR_EQUAL", 0.05),
    ("Shrubs", "Exclusion", "FoliageExclusion", "LESSER_OR_EQUAL", 0.05),
    ("GroundCover", "Include", "Grass", "GREATER_OR_EQUAL", 0.08),
    ("GroundCover", "Water", "Water", "LESSER_OR_EQUAL", 0.05),
    ("GroundCover", "Exclusion", "FoliageExclusion", "LESSER_OR_EQUAL", 0.05),
    ("Rocks", "Include", "Rock", "GREATER_OR_EQUAL", 0.10),
    ("Rocks", "Water", "Water", "LESSER_OR_EQUAL", 0.05),
    ("Rocks", "Exclusion", "FoliageExclusion", "LESSER_OR_EQUAL", 0.05),
)

DENSITY_SPECS = (
    ("Trees", 0.996),
    ("Shrubs", 0.985),
    ("GroundCover", 0.960),
    ("Rocks", 0.995),
)

NOISE_SPECS = (
    ("Trees", 150101),
    ("Shrubs", 150201),
    ("GroundCover", 150301),
    ("Rocks", 150401),
)


def safe_call(fn, fallback=None):
    try:
        return fn()
    except Exception:
        return fallback


def object_path(obj):
    if obj is None:
        return "NONE"
    for fn in (
        lambda: obj.get_path_name(),
        lambda: obj.get_full_name(),
        lambda: str(obj),
    ):
        value = safe_call(fn)
        if value:
            return str(value)
    return "UNKNOWN"


def class_name(obj):
    cls = safe_call(lambda: obj.get_class())
    if cls is not None:
        name = safe_call(lambda: cls.get_name())
        if name:
            return str(name)
    return type(obj).__name__ if obj is not None else "NONE"


def get_property(obj, names, fallback=None):
    if obj is None:
        return fallback
    for name in names:
        try:
            return obj.get_editor_property(name)
        except Exception:
            pass
        try:
            return getattr(obj, name)
        except Exception:
            pass
    return fallback


def export_value(value):
    if value is None:
        return "NONE"
    for method_name in ("export_text", "to_tuple", "get_path_name", "get_full_name"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                text = str(method())
                if text:
                    return text[:4000]
            except Exception:
                pass
    return repr(value)[:4000]


def graph_nodes(graph):
    for getter in (
        lambda: graph.get_nodes(),
        lambda: graph.get_editor_property("nodes"),
        lambda: graph.nodes,
    ):
        value = safe_call(getter)
        if value is not None:
            return [item for item in list(value) if item is not None]
    raise RuntimeError("Could not enumerate saved PCG graph nodes")


def node_settings(node):
    for getter in (
        lambda: node.get_settings(),
        lambda: node.get_editor_property("settings"),
        lambda: node.settings,
    ):
        value = safe_call(getter)
        if value is not None:
            return value
    return None


def selector_text(selector):
    parts = [export_value(selector)]
    helper = getattr(unreal, "PCGAttributePropertySelectorBlueprintHelpers", None)
    if helper is not None:
        for method_name in ("get_attribute_name", "get_name"):
            method = getattr(helper, method_name, None)
            if callable(method):
                value = safe_call(lambda method=method: method(selector))
                if value is not None:
                    parts.append(str(value))
    for property_name in (
        "attribute_name",
        "name",
        "selection",
        "point_property",
        "extra_names",
    ):
        value = get_property(selector, (property_name,), None)
        if value is not None:
            parts.append(f"{property_name}={export_value(value)}")
    return " | ".join(parts)


def constant_float(constant):
    for name in ("float_value", "double_value"):
        value = get_property(constant, (name,), None)
        if value is not None:
            try:
                return float(value)
            except Exception:
                pass
    text = export_value(constant)
    lowered = text.lower()
    for token in ("float_value=", "double_value="):
        index = lowered.find(token)
        if index >= 0:
            tail = text[index + len(token):]
            number = []
            for char in tail:
                if char in "+-.0123456789eE":
                    number.append(char)
                else:
                    break
            try:
                return float("".join(number))
            except Exception:
                pass
    return None


def package_dirty(obj):
    package = safe_call(lambda: obj.get_outermost())
    return safe_call(lambda: package.is_dirty(), False)


def close_enough(actual, expected, tolerance=0.0005):
    return actual is not None and math.isfinite(actual) and abs(actual - expected) <= tolerance


def write_report(lines):
    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_FILTER_SEMANTICS_REPORT={REPORT_PATH}")


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running the Stage 15B filter semantics audit")
    except AttributeError:
        pass

    lines = [
        "AETHER STAGE 15B - RIVER BIOME FILTER SEMANTICS AUDIT",
        "=" * 100,
        "READ_ONLY=TRUE",
        "NO_ASSETS_MODIFIED=TRUE",
        "NO_ACTORS_MODIFIED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    ]
    failures = []

    graph = unreal.EditorAssetLibrary.load_asset(GRAPH_OBJECT_PATH)
    if graph is None:
        raise RuntimeError(f"Saved graph could not be loaded: {GRAPH_OBJECT_PATH}")

    dirty_before = package_dirty(graph)
    lines.append(f"GRAPH={object_path(graph)}")
    lines.append(f"GRAPH_DIRTY_BEFORE={dirty_before}")

    nodes = graph_nodes(graph)
    settings_by_class = {}
    for node in nodes:
        settings = node_settings(node)
        settings_by_class.setdefault(class_name(settings), []).append(settings)

    filters = settings_by_class.get("PCGAttributeFilteringSettings", [])
    noises = settings_by_class.get("PCGAttributeNoiseSettings", [])
    densities = settings_by_class.get("PCGDensityFilterSettings", [])

    lines.append(f"ATTRIBUTE_FILTER_COUNT={len(filters)}")
    lines.append(f"DENSITY_NOISE_COUNT={len(noises)}")
    lines.append(f"DENSITY_FILTER_COUNT={len(densities)}")

    if len(filters) != len(FILTER_SPECS):
        failures.append(f"attribute filter count {len(filters)} != {len(FILTER_SPECS)}")
    if len(noises) != len(NOISE_SPECS):
        failures.append(f"noise count {len(noises)} != {len(NOISE_SPECS)}")
    if len(densities) != len(DENSITY_SPECS):
        failures.append(f"density filter count {len(densities)} != {len(DENSITY_SPECS)}")

    lines.extend(("", "ATTRIBUTE_FILTERS", "-" * 100))
    for index, spec in enumerate(FILTER_SPECS):
        branch, role, expected_attribute, expected_operator, expected_threshold = spec
        if index >= len(filters):
            lines.append(f"FILTER_{index + 1:02d}=MISSING expected:{branch}/{role}")
            continue

        settings = filters[index]
        selector = get_property(settings, ("target_attribute",), None)
        selector_export = selector_text(selector)
        operator = get_property(settings, ("operator",), "UNEXPOSED")
        constant = get_property(settings, ("attribute_types",), None)
        threshold = constant_float(constant)
        use_constant = get_property(settings, ("use_constant_threshold",), "UNEXPOSED")
        warn_missing = get_property(settings, ("warn_on_data_missing_attribute",), "UNEXPOSED")

        lines.append(f"FILTER_{index + 1:02d}_EXPECTED={branch}/{role}")
        lines.append(f"FILTER_{index + 1:02d}_SELECTOR={selector_export}")
        lines.append(f"FILTER_{index + 1:02d}_OPERATOR={operator}")
        lines.append(f"FILTER_{index + 1:02d}_THRESHOLD={threshold if threshold is not None else 'UNRESOLVED'}")
        lines.append(f"FILTER_{index + 1:02d}_CONSTANT_EXPORT={export_value(constant)}")
        lines.append(f"FILTER_{index + 1:02d}_USE_CONSTANT={use_constant}")
        lines.append(f"FILTER_{index + 1:02d}_WARN_MISSING={warn_missing}")

        if expected_attribute.lower() not in selector_export.lower():
            failures.append(
                f"{branch}/{role} selector does not contain {expected_attribute}: {selector_export}"
            )
        if expected_operator not in str(operator):
            failures.append(
                f"{branch}/{role} operator {operator} does not contain {expected_operator}"
            )
        if not close_enough(threshold, expected_threshold):
            failures.append(
                f"{branch}/{role} threshold {threshold} != {expected_threshold}"
            )
        if use_constant is not True:
            failures.append(f"{branch}/{role} use_constant_threshold is {use_constant}")

    lines.extend(("", "DENSITY_NOISE", "-" * 100))
    for index, spec in enumerate(NOISE_SPECS):
        branch, expected_seed = spec
        if index >= len(noises):
            lines.append(f"NOISE_{index + 1:02d}=MISSING expected:{branch}")
            continue
        settings = noises[index]
        input_source = selector_text(get_property(settings, ("input_source",), None))
        output_target = selector_text(get_property(settings, ("output_target",), None))
        mode = get_property(settings, ("mode",), "UNEXPOSED")
        noise_min = get_property(settings, ("noise_min",), None)
        noise_max = get_property(settings, ("noise_max",), None)
        seed = get_property(settings, ("seed",), None)
        clamp_result = get_property(settings, ("clamp_result",), "UNEXPOSED")

        lines.append(f"NOISE_{index + 1:02d}_EXPECTED={branch}")
        lines.append(f"NOISE_{index + 1:02d}_INPUT={input_source}")
        lines.append(f"NOISE_{index + 1:02d}_OUTPUT={output_target}")
        lines.append(f"NOISE_{index + 1:02d}_MODE={mode}")
        lines.append(f"NOISE_{index + 1:02d}_MIN={noise_min}")
        lines.append(f"NOISE_{index + 1:02d}_MAX={noise_max}")
        lines.append(f"NOISE_{index + 1:02d}_SEED={seed}")
        lines.append(f"NOISE_{index + 1:02d}_CLAMP={clamp_result}")

        if "density" not in input_source.lower():
            failures.append(f"{branch} noise input is not Density: {input_source}")
        if "density" not in output_target.lower():
            failures.append(f"{branch} noise output is not Density: {output_target}")
        if "SET" not in str(mode):
            failures.append(f"{branch} noise mode is not SET: {mode}")
        if not close_enough(float(noise_min) if noise_min is not None else None, 0.0):
            failures.append(f"{branch} noise min {noise_min} != 0")
        if not close_enough(float(noise_max) if noise_max is not None else None, 1.0):
            failures.append(f"{branch} noise max {noise_max} != 1")
        if seed is None or int(seed) != expected_seed:
            failures.append(f"{branch} noise seed {seed} != {expected_seed}")

    lines.extend(("", "DENSITY_FILTERS", "-" * 100))
    for index, spec in enumerate(DENSITY_SPECS):
        branch, expected_lower = spec
        if index >= len(densities):
            lines.append(f"DENSITY_{index + 1:02d}=MISSING expected:{branch}")
            continue
        settings = densities[index]
        lower = get_property(settings, ("lower_bound",), None)
        upper = get_property(settings, ("upper_bound",), None)
        invert = get_property(settings, ("invert_filter",), "UNEXPOSED")
        normalize = get_property(settings, ("normalize_output_density",), "UNEXPOSED")
        keep_zero = get_property(settings, ("keep_zero_density_points",), "UNEXPOSED")

        lines.append(f"DENSITY_{index + 1:02d}_EXPECTED={branch}")
        lines.append(f"DENSITY_{index + 1:02d}_LOWER={lower}")
        lines.append(f"DENSITY_{index + 1:02d}_UPPER={upper}")
        lines.append(f"DENSITY_{index + 1:02d}_INVERT={invert}")
        lines.append(f"DENSITY_{index + 1:02d}_NORMALIZE={normalize}")
        lines.append(f"DENSITY_{index + 1:02d}_KEEP_ZERO={keep_zero}")

        actual_lower = float(lower) if lower is not None else None
        actual_upper = float(upper) if upper is not None else None
        if not close_enough(actual_lower, expected_lower):
            failures.append(f"{branch} density lower {lower} != {expected_lower}")
        if not close_enough(actual_upper, 1.0):
            failures.append(f"{branch} density upper {upper} != 1")
        if invert is True:
            failures.append(f"{branch} density invert_filter is True")

    dirty_after = package_dirty(graph)
    lines.extend((
        "",
        "SUMMARY",
        "-" * 100,
        f"GRAPH_DIRTY_AFTER={dirty_after}",
        f"SEMANTIC_FAILURE_COUNT={len(failures)}",
    ))
    for index, failure in enumerate(failures, 1):
        lines.append(f"FAILURE_{index:02d}={failure}")

    result = "PASS" if not failures and dirty_after == dirty_before else "FAIL"
    if dirty_after != dirty_before:
        lines.append("FAILURE_DIRTY_STATE=Graph dirty state changed during read-only audit")
        result = "FAIL"
    lines.extend((
        f"FILTER_SEMANTICS_RESULT={result}",
        "NEXT=Use the semantic result to choose either a query-only marker probe or a narrowly corrected graph repair; do not generate the persistent volume.",
    ))
    write_report(lines)

    if result != "PASS":
        raise RuntimeError(f"Stage 15B filter semantics audit failed with {len(failures)} semantic failures")


try:
    main()
except Exception as exc:
    if not REPORT_PATH.exists():
        failure = "\n".join((
            "AETHER STAGE 15B - RIVER BIOME FILTER SEMANTICS AUDIT",
            "=" * 100,
            "FILTER_SEMANTICS_RESULT=FAIL",
            f"ERROR={type(exc).__name__}: {exc}",
            "NO_ASSETS_MODIFIED=TRUE",
            "NO_ACTORS_MODIFIED=TRUE",
            "NO_PACKAGES_SAVED=TRUE",
            "NO_PCG_GENERATION_STARTED=TRUE",
            "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
        )) + "\n"
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(failure, encoding="utf-8")
        unreal.log_error(failure)
    raise
