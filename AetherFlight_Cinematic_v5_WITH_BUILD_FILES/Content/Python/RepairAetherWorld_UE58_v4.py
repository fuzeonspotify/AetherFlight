"""Repair Aether Flight's Landscape visuals and Open World template conflicts.

UE 5.8 repair v4:
- corrects LandscapeLayerCoords scales for the 11.90476 m vertex spacing;
- fills unpainted weightmap regions with the Grass PBR layer instead of black;
- preserves and uses imported Grass/Rock/Scree/Snow weightmaps;
- applies the material to the largest authored Landscape;
- hides smaller duplicate Landscape actors in game without deleting them; and
- disables the Open World template atmosphere actors that compete with the
  runtime Aether environment.
"""

import unreal


PACKAGE = "/Game/Aether/ProductionTerrain"
TEXTURE_PACKAGE = f"{PACKAGE}/Textures"
MATERIAL_NAME = "M_Landscape_Production"
LAYERS = ("Grass", "Rock", "Scree", "Snow")

# Landscape2 was imported at 1190.476190 cm per vertex. The old world-space
# graph divided centimeters by these tile sizes. LandscapeLayerCoords instead
# starts in vertex coordinates, so use vertex spacing / desired tile size.
XY_VERTEX_SPACING_CM = 1190.476190
DETAIL_TILE_SIZE_CM = 420.0
MACRO_TILE_SIZE_CM = 185000.0
DETAIL_MAPPING_SCALE = XY_VERTEX_SPACING_CM / DETAIL_TILE_SIZE_CM
MACRO_MAPPING_SCALE = XY_VERTEX_SPACING_CM / MACRO_TILE_SIZE_CM

TEMPLATE_ENVIRONMENT_LABELS = {
    "DirectionalLight",
    "SkyLight",
    "SkyAtmosphere",
    "ExponentialHeightFog",
    "VolumetricCloud",
    "PostProcessVolume",
}


def log(message: str) -> None:
    unreal.log(f"[Aether UE5.8 World Repair v4] {message}")


def expression(material, expression_class, x: int, y: int):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, expression_class, x, y
    )
    if node is None:
        raise RuntimeError(f"Could not create material node {expression_class}")
    return node


def connect(source, source_output: str, target, target_input: str, description: str) -> None:
    if not unreal.MaterialEditingLibrary.connect_material_expressions(
        source, source_output, target, target_input
    ):
        raise RuntimeError(f"Could not connect {description}")


def load_texture(name: str) -> unreal.Texture2D:
    path = f"{TEXTURE_PACKAGE}/{name}.{name}"
    texture = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError(
            f"Missing {path}. Run InstallProductionLandscape.py once to import textures."
        )
    return texture


def get_material() -> unreal.Material:
    path = f"{PACKAGE}/{MATERIAL_NAME}.{MATERIAL_NAME}"
    material = unreal.EditorAssetLibrary.load_asset(path)
    if not isinstance(material, unreal.Material):
        unreal.EditorAssetLibrary.make_directory(PACKAGE)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            MATERIAL_NAME,
            PACKAGE,
            unreal.Material,
            unreal.MaterialFactoryNew(),
        )
    if not isinstance(material, unreal.Material):
        raise RuntimeError(f"Could not create or load {path}")

    unreal.MaterialEditingLibrary.delete_all_material_expressions(material)
    material.set_editor_property("two_sided", False)
    material.set_editor_property("tangent_space_normal", True)
    return material


def landscape_uv(material, scale: float, x: int, y: int):
    coords = expression(material, unreal.MaterialExpressionLandscapeLayerCoords, x, y)
    coords.set_editor_property("mapping_scale", scale)
    return coords


def texture_sample(material, texture, parameter_name: str, uv, x: int, y: int,
                   normal=False, scalar=False):
    sample = expression(material, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    sample.set_editor_property("parameter_name", parameter_name)
    sample.set_editor_property("texture", texture)
    if normal:
        sample.set_editor_property(
            "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
        )
    elif scalar:
        sample.set_editor_property(
            "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
        )
    else:
        sample.set_editor_property(
            "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
        )
    connect(uv, "", sample, "UVs", f"UVs for {parameter_name}")
    return sample


def weighted_sum(material, sources, x: int, y: int):
    """Return sum(source * painted layer weight) through fixed UE5.8 pins."""
    previous = None
    for index, (layer_name, source, output_name) in enumerate(sources):
        node = expression(
            material,
            unreal.MaterialExpressionLandscapeLayerWeight,
            x + index * 230,
            y,
        )
        node.set_editor_property("parameter_name", layer_name)
        node.set_editor_property("preview_weight", 1.0 if index == 0 else 0.0)
        if previous is not None:
            connect(previous, "", node, "Base", f"Base for {layer_name}")
        connect(source, output_name, node, "Layer", f"Layer for {layer_name}")
        previous = node
    return previous


def missing_weight(material, x: int, y: int):
    """Return 1 minus the normalized sum of all painted layer weights."""
    one = expression(material, unreal.MaterialExpressionConstant, x, y - 180)
    one.set_editor_property("r", 1.0)
    sources = [(layer_name, one, "") for layer_name in LAYERS]
    total = weighted_sum(material, sources, x + 180, y)

    # UE 5.8 does not consistently expose the unary Saturate/OneMinus input
    # name to Python. Weight-Blended Layer data is normalized already, so a
    # fixed-pin Subtract node provides the same missing-weight value safely.
    missing = expression(material, unreal.MaterialExpressionSubtract, x + 1160, y)
    connect(one, "", missing, "A", "one to missing-weight Subtract")
    connect(total, "", missing, "B", "total Landscape weight to Subtract")
    return missing


def add_unpainted_fallback(material, painted, fallback_source, fallback_output: str,
                           unpainted_weight, x: int, y: int):
    fallback = expression(material, unreal.MaterialExpressionMultiply, x, y)
    connect(fallback_source, fallback_output, fallback, "A", "fallback texture")
    connect(unpainted_weight, "", fallback, "B", "unpainted Landscape weight")

    result = expression(material, unreal.MaterialExpressionAdd, x + 230, y)
    connect(painted, "", result, "A", "painted Landscape layers")
    connect(fallback, "", result, "B", "Grass fallback")
    return result


def build_material() -> unreal.Material:
    material = get_material()
    detail_uv = landscape_uv(material, DETAIL_MAPPING_SCALE, -2100, -900)
    macro_uv = landscape_uv(material, MACRO_MAPPING_SCALE, -2100, 900)

    base_samples = {}
    normal_samples = {}
    roughness_samples = {}
    for index, layer_name in enumerate(LAYERS):
        y = -1260 + index * 290
        base_samples[layer_name] = texture_sample(
            material,
            load_texture(f"T_{layer_name}_BaseColor"),
            f"{layer_name}_BaseColor",
            detail_uv,
            -1420,
            y,
        )
        normal_samples[layer_name] = texture_sample(
            material,
            load_texture(f"T_{layer_name}_Normal"),
            f"{layer_name}_Normal",
            detail_uv,
            -1140,
            y,
            normal=True,
        )
        roughness_samples[layer_name] = texture_sample(
            material,
            load_texture(f"T_{layer_name}_Roughness"),
            f"{layer_name}_Roughness",
            detail_uv,
            -860,
            y,
            scalar=True,
        )

    base_sources = [
        (layer_name, base_samples[layer_name], "RGB") for layer_name in LAYERS
    ]
    normal_sources = [
        (layer_name, normal_samples[layer_name], "RGB") for layer_name in LAYERS
    ]
    roughness_sources = [
        (layer_name, roughness_samples[layer_name], "R") for layer_name in LAYERS
    ]

    base_painted = weighted_sum(material, base_sources, -480, -500)
    normal_painted = weighted_sum(material, normal_sources, -480, 80)
    roughness_painted = weighted_sum(material, roughness_sources, -480, 660)
    unpainted = missing_weight(material, -700, 1260)

    base_complete = add_unpainted_fallback(
        material,
        base_painted,
        base_samples["Grass"],
        "RGB",
        unpainted,
        620,
        -500,
    )
    normal_complete = add_unpainted_fallback(
        material,
        normal_painted,
        normal_samples["Grass"],
        "RGB",
        unpainted,
        620,
        80,
    )
    roughness_complete = add_unpainted_fallback(
        material,
        roughness_painted,
        roughness_samples["Grass"],
        "R",
        unpainted,
        620,
        660,
    )

    macro = texture_sample(
        material,
        load_texture("T_MacroVariation"),
        "MacroVariation",
        macro_uv,
        620,
        -900,
        scalar=True,
    )
    tint = expression(material, unreal.MaterialExpressionMultiply, 1100, -500)
    connect(base_complete, "", tint, "A", "complete base color")
    connect(macro, "R", tint, "B", "macro color variation")

    unreal.MaterialEditingLibrary.connect_material_property(
        tint, "", unreal.MaterialProperty.MP_BASE_COLOR
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        normal_complete, "", unreal.MaterialProperty.MP_NORMAL
    )
    unreal.MaterialEditingLibrary.connect_material_property(
        roughness_complete, "", unreal.MaterialProperty.MP_ROUGHNESS
    )

    specular = expression(material, unreal.MaterialExpressionConstant, 1100, 440)
    specular.set_editor_property("r", 0.24)
    unreal.MaterialEditingLibrary.connect_material_property(
        specular, "", unreal.MaterialProperty.MP_SPECULAR
    )
    ao = expression(material, unreal.MaterialExpressionConstant, 1100, 560)
    ao.set_editor_property("r", 1.0)
    unreal.MaterialEditingLibrary.connect_material_property(
        ao, "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION
    )

    unreal.MaterialEditingLibrary.layout_material_expressions(material)
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False)
    log(
        f"Rebuilt {material.get_path_name()} with corrected UV scale and Grass fallback"
    )
    return material


def configure_landscapes(material):
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    root_landscapes = [
        actor
        for actor in actor_subsystem.get_all_level_actors()
        if actor.get_class().get_name() == "Landscape"
    ]
    if not root_landscapes:
        raise RuntimeError("No root Landscape actor was found in the current level.")

    production = max(
        root_landscapes,
        key=lambda actor: abs(
            actor.get_actor_scale3d().x * actor.get_actor_scale3d().y
        ),
    )
    production.modify()
    production.set_editor_property("landscape_material", material)
    production.set_actor_hidden_in_game(False)
    production.set_actor_enable_collision(True)

    hidden_labels = []
    for landscape in root_landscapes:
        if landscape == production:
            continue
        landscape.modify()
        landscape.set_actor_hidden_in_game(True)
        landscape.set_actor_enable_collision(False)
        hidden_labels.append(landscape.get_actor_label())
        log(f"Hidden duplicate Landscape during play: {landscape.get_actor_label()}")

    return production.get_actor_label(), hidden_labels


def disable_template_environment():
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    disabled_labels = []
    for actor in actor_subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if label not in TEMPLATE_ENVIRONMENT_LABELS:
            continue

        actor.modify()
        try:
            actor.set_actor_hidden_in_game(True)
        except Exception:
            pass
        try:
            actor.set_editor_property("enabled", False)
        except Exception:
            pass
        try:
            components = actor.get_components_by_class(unreal.SceneComponent)
        except Exception:
            components = []
        for component in components:
            try:
                component.set_visibility(False, True)
            except Exception:
                try:
                    component.set_editor_property("visible", False)
                except Exception:
                    pass
        disabled_labels.append(label)
        log(f"Disabled duplicate template environment actor: {label}")
    return disabled_labels


def save_level() -> None:
    try:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    except Exception as error:
        log(f"Level auto-save was skipped: {error}")


def main() -> None:
    material = build_material()
    production_label, hidden_landscapes = configure_landscapes(material)
    disabled_environment = disable_template_environment()
    save_level()

    hidden_text = ", ".join(hidden_landscapes) if hidden_landscapes else "none"
    disabled_text = ", ".join(disabled_environment) if disabled_environment else "none"
    unreal.EditorDialog.show_message(
        "Aether UE5.8 World Repair v4",
        "The world visual repair completed successfully.\n\n"
        f"Production Landscape: {production_label}\n"
        f"Hidden duplicate Landscapes: {hidden_text}\n"
        f"Disabled template environment actors: {disabled_text}\n\n"
        "Wait for shaders, Save All, press Play, then press R once to reset the aircraft.",
        unreal.AppMsgType.OK,
    )


if __name__ == "__main__":
    main()
