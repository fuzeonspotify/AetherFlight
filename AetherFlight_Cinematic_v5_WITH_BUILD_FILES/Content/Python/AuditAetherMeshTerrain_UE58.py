"""Read-only readiness audit for Aether Flight's UE 5.8 Mesh Terrain."""

import unreal


PACKAGE = "/Game/Aether/MeshTerrain"
ASSETS = (
    "M_MeshTerrain_Aether",
    "MPD_AetherWorld",
    "TP_Preview_AetherWorld",
    "TP_Compiled_HighEnd_AetherWorld",
    "TP_Compiled_Common_AetherWorld",
)


def safe_len_property(obj, name):
    try:
        return len(obj.get_editor_property(name))
    except Exception:
        return None


def is_mesh_partition_root(actor):
    name = actor.get_class().get_name().lower()
    return name == "meshpartition" or (
        "meshpartition" in name and "section" not in name and "modifier" not in name
    )


def main():
    lines = []
    ready = True
    loaded = {}
    for name in ASSETS:
        path = f"{PACKAGE}/{name}.{name}"
        asset = unreal.EditorAssetLibrary.load_asset(path)
        loaded[name] = asset
        if asset is None:
            lines.append(f"MISSING  {name}")
            ready = False
        else:
            lines.append(f"OK       {name}")

    for name in ASSETS[2:]:
        asset = loaded.get(name)
        if asset is None:
            continue
        count = safe_len_property(asset, "transformers")
        if count is None:
            lines.append(f"CHECK    {name}: open and verify its transformer stack")
        elif count == 0:
            lines.append(f"MISSING  {name}: transformer stack is empty")
            ready = False
        else:
            lines.append(f"OK       {name}: {count} transformer entries")

    definition = loaded.get("MPD_AetherWorld")
    if definition is not None:
        priorities = safe_len_property(definition, "modifier_type_priorities")
        variants = safe_len_property(definition, "compiled_section_build_variants")
        lines.append(f"INFO     MPD priority layers: {priorities if priorities is not None else 'check manually'}")
        lines.append(f"INFO     MPD compiled variants: {variants if variants is not None else 'check manually'}")
        if variants == 0:
            ready = False

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()
    roots = [actor for actor in actors if is_mesh_partition_root(actor)]
    compiled = [
        actor for actor in actors
        if "compiledsection" in actor.get_class().get_name().lower()
        or "compiled_section" in actor.get_class().get_name().lower()
    ]
    lines.append(f"INFO     Mesh Partition roots loaded: {len(roots)}")
    lines.append(f"INFO     Compiled sections loaded: {len(compiled)}")
    if not roots:
        lines.append("NEXT     Import AetherFlight_4033.r16 in Mesh Terrain mode")
        ready = False

    authoritative = [
        actor for actor in roots
        if unreal.Name("AetherProductionTerrain") in actor.tags
    ]
    lines.append(f"INFO     Authoritative Mesh Terrain roots: {len(authoritative)}")
    if roots and not authoritative:
        lines.append("NEXT     Build Mesh Partition, verify it, then run the finalizer")

    title = "Aether Mesh Terrain — Ready" if ready else "Aether Mesh Terrain — Setup Needed"
    unreal.EditorDialog.show_message(
        title, "\n".join(lines), unreal.AppMsgType.OK
    )


if __name__ == "__main__":
    main()
