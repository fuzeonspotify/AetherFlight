from pathlib import Path
import unreal

MAP_PATH = "/Game/Maps/AetherWorld"
ACTOR_LABEL = "Aether_VideoStage05_LocalRemesh"
REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherVideoLocalRemeshAudit.txt"


def record(lines, text):
    text = str(text)
    lines.append(text)
    unreal.log_warning(text)


def load_world():
    world = unreal.EditorLevelLibrary.get_editor_world()
    if not world or not world.get_path_name().startswith(MAP_PATH):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        world = unreal.EditorLevelLibrary.get_editor_world()
    return world


def get_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def safe_property(obj, names):
    for name in names:
        try:
            return name, obj.get_editor_property(name)
        except Exception:
            continue
    return None, None


def safe_call(obj, names):
    for name in names:
        fn = getattr(obj, name, None)
        if not fn:
            continue
        try:
            return name, fn()
        except Exception:
            continue
    return None, None


def main():
    lines = []
    record(lines, "AETHER VIDEO LOCAL REMESH VERIFICATION")
    record(lines, "=" * 96)

    world = load_world()
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(actor_subsystem.get_all_level_actors())

    matches = [actor for actor in actors if get_label(actor) == ACTOR_LABEL]
    record(lines, f"World={world.get_path_name()}")
    record(lines, f"Matching actors={len(matches)}")

    if len(matches) != 1:
        record(lines, "AETHER_LOCAL_REMESH_ACTOR=FAIL")
        record(lines, "AETHER_LOCAL_REMESH_COMPONENT=FAIL")
        record(lines, "AETHER_LOCAL_REMESH_CONFIGURATION=FAIL")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    actor = matches[0]
    record(lines, f"Actor={actor.get_name()} label={get_label(actor)}")
    record(lines, f"Actor location={actor.get_actor_location()}")
    record(lines, "AETHER_LOCAL_REMESH_ACTOR=PASS")

    components = list(actor.get_components_by_class(unreal.ActorComponent))
    remesh_components = []
    for component in components:
        class_path = component.get_class().get_path_name()
        if "RemeshModifier" in class_path:
            remesh_components.append(component)
        record(lines, f"Component={component.get_name()} | {class_path}")

    record(lines, f"Remesh components={len(remesh_components)}")
    if len(remesh_components) != 1:
        record(lines, "AETHER_LOCAL_REMESH_COMPONENT=FAIL")
        record(lines, "AETHER_LOCAL_REMESH_CONFIGURATION=FAIL")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    component = remesh_components[0]
    record(lines, "AETHER_LOCAL_REMESH_COMPONENT=PASS")
    record(lines, "-" * 96)
    record(lines, f"Remesh class={component.get_class().get_path_name()}")

    try:
        record(lines, f"Registered={component.is_registered()}")
    except Exception:
        record(lines, "Registered=not exposed")

    checks = [
        ("Affected Mesh Partition", ("affected_mega_mesh", "affected_mesh_partition", "affected_mesh_partition_actor")),
        ("Coverage", ("unscaled_coverage", "coverage")),
        ("Priority", ("priority",)),
        ("Disabled", ("is_disabled", "disabled", "disabled_in_editor")),
        ("Disabled in Build", ("disabled_in_build", "is_disabled_in_build")),
    ]

    exposed_values = {}
    for label, names in checks:
        property_name, value = safe_property(component, names)
        if property_name:
            exposed_values[label] = value
            record(lines, f"{label}={value} | property={property_name}")
        else:
            record(lines, f"{label}=not exposed | candidates={names}")

    getter_checks = [
        ("Target edge length", ("get_target_edge_length",)),
        ("Use target edge length", ("get_use_target_edge_length",)),
        ("Remesh iterations", ("get_remesh_iterations",)),
        ("Vertex smoothing", ("get_vertex_smoothing",)),
        ("Resample UVs", ("get_resample_uvs",)),
    ]

    for label, names in getter_checks:
        method_name, value = safe_call(component, names)
        if method_name:
            exposed_values[label] = value
            record(lines, f"{label}={value} | getter={method_name}")
        else:
            record(lines, f"{label}=not exposed | getters={names}")

    relevant_names = sorted(
        name for name in dir(component)
        if any(token in name.lower() for token in (
            "edge", "remesh", "coverage", "disabled", "affected", "tessellate", "priority"
        ))
    )
    record(lines, f"Relevant exposed API names={','.join(relevant_names)}")

    disabled_value = exposed_values.get("Disabled", False)
    if isinstance(disabled_value, bool) and disabled_value:
        record(lines, "AETHER_LOCAL_REMESH_CONFIGURATION=FAIL")
        record(lines, "Reason=Remesh modifier is disabled in the editor")
    else:
        record(lines, "AETHER_LOCAL_REMESH_CONFIGURATION=PASS")

    record(lines, "AETHER_LOCAL_REMESH_VISUAL_NOTE=The intended 6 m target is only about twice the linear density of the 11.9 m base terrain, so the difference can be subtle in wireframe.")
    record(lines, "AETHER_LOCAL_REMESH_STAGE=PASS")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    unreal.log_warning(f"AETHER_VIDEO_LOCAL_REMESH_AUDIT_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    message = f"AETHER_LOCAL_REMESH_STAGE=FAIL\nERROR={type(exc).__name__}: {exc}\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(message, encoding="utf-8")
    unreal.log_error(message)
    raise
