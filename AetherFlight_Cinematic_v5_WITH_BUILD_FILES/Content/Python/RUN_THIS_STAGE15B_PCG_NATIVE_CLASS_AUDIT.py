"""Read-only native class-path audit for UE 5.8 PCG Mesh Partition interop.

The Stage 15B biome preflight confirmed that the asset library and Mesh Terrain
weight channels are ready, but Query/ToPoint node settings are not exported as
normal ``unreal`` Python attributes. This audit enumerates Unreal UClass objects
instead, records their native /Script paths and checks whether Python can still
instantiate them through reflection.

No graph, actor, component, package, instance, or Mesh Partition build is created.
"""

from pathlib import Path
import unreal

REPORT_PATH = Path(unreal.Paths.project_saved_dir()) / "AetherStage15BPCGNativeClassAudit.txt"

TOKENS = (
    "pcgmeshpartitioninterop",
    "meshpartitionpcg",
    "meshpartitionquery",
    "meshpartitiontopoint",
    "megamesh",
)

CANDIDATE_CLASS_PATHS = (
    "/Script/PCGMeshPartitionInterop.PCGMeshPartitionQuerySettings",
    "/Script/PCGMeshPartitionInterop.PCGMeshPartitionToPointSettings",
    "/Script/PCGMeshPartitionInterop.PCGMeshPartitionWriteSettings",
    "/Script/PCGMeshPartitionInterop.PCGMeshPartitionPatchInstanceSpawnerSettings",
    "/Script/PCGMeshPartitionInterop.PCGMeshProjectionInstanceSpawnerSettings",
    "/Script/PCGMeshPartitionInteropEditor.PCGMeshPartitionQuerySettings",
    "/Script/PCGMeshPartitionInteropEditor.PCGMeshPartitionToPointSettings",
    "/Script/PCGMeshPartitionInteropEditor.PCGMeshPartitionWriteSettings",
    "/Script/PCGMeshPartitionInteropEditor.PCGAdapterComponent",
    "/Script/PCGMeshPartitionInterop.PCGDataComponent",
)


def safe_text(callable_value, fallback=""):
    try:
        value = callable_value()
        return str(value) if value is not None else fallback
    except Exception:
        return fallback


def class_chain(cls):
    names = []
    current = cls
    for _ in range(12):
        if current is None:
            break
        names.append(safe_text(lambda current=current: current.get_name(), "Unknown"))
        current = safe_super(current)
    return " <- ".join(names)


def safe_super(cls):
    for getter in (
        lambda: cls.get_super_class(),
        lambda: cls.get_editor_property("super_struct"),
    ):
        try:
            result = getter()
            if result is not None:
                return result
        except Exception:
            pass
    return None


def python_type_name(cls):
    try:
        py_type = unreal.get_type_from_class(cls)
        if py_type is None:
            return "NONE"
        return getattr(py_type, "__name__", str(py_type))
    except Exception as exc:
        return f"UNAVAILABLE:{type(exc).__name__}:{exc}"


def class_rows():
    rows = []
    failures = []
    try:
        iterator = unreal.ClassIterator()
    except Exception as exc:
        return [], [f"CLASS_ITERATOR_FAILED={type(exc).__name__}:{exc}"]

    for cls in iterator:
        path = safe_text(lambda cls=cls: cls.get_path_name())
        name = safe_text(lambda cls=cls: cls.get_name())
        text = f"{path} {name}".lower()
        if not any(token in text for token in TOKENS):
            continue

        py_type = python_type_name(cls)
        cdo_status = "NOT_TESTED"
        cdo_dir = []
        try:
            cdo = unreal.get_default_object(unreal.get_type_from_class(cls))
            cdo_status = "OK" if cdo is not None else "NONE"
            if cdo is not None:
                cdo_dir = sorted(
                    name for name in dir(cdo)
                    if any(token in name.lower() for token in (
                        "channel", "layer", "priority", "query", "point",
                        "mesh", "partition", "inclusive", "density", "actor"
                    ))
                )
        except Exception as exc:
            cdo_status = f"UNAVAILABLE:{type(exc).__name__}:{exc}"

        rows.append(
            " | ".join((
                f"CLASS={path}",
                f"PYTHON_TYPE={py_type}",
                f"CDO={cdo_status}",
                f"CHAIN={class_chain(cls)}",
                f"RELEVANT_MEMBERS={','.join(cdo_dir[:80]) if cdo_dir else 'NONE'}",
            ))
        )
    return sorted(set(rows), key=str.lower), failures


def candidate_rows():
    rows = []
    for path in CANDIDATE_CLASS_PATHS:
        loaded = None
        error = ""
        try:
            loaded = unreal.load_class(None, path)
        except Exception as exc:
            error = f"{type(exc).__name__}:{exc}"
        if loaded is None:
            rows.append(f"CANDIDATE={path} | LOAD=NONE | ERROR={error or 'NONE'}")
            continue
        rows.append(
            " | ".join((
                f"CANDIDATE={path}",
                "LOAD=OK",
                f"RESOLVED={safe_text(lambda loaded=loaded: loaded.get_path_name())}",
                f"PYTHON_TYPE={python_type_name(loaded)}",
                f"CHAIN={class_chain(loaded)}",
            ))
        )
    return rows


def object_rows():
    rows = []
    try:
        iterator = unreal.ObjectIterator()
    except Exception as exc:
        return [f"OBJECT_ITERATOR_FAILED={type(exc).__name__}:{exc}"]

    for obj in iterator:
        path = safe_text(lambda obj=obj: obj.get_path_name())
        cls_path = safe_text(lambda obj=obj: obj.get_class().get_path_name())
        text = f"{path} {cls_path}".lower()
        if not any(token in text for token in TOKENS):
            continue
        rows.append(f"OBJECT={path} | CLASS={cls_path}")
        if len(rows) >= 300:
            rows.append("OBJECT_LIST_TRUNCATED=TRUE")
            break
    return sorted(set(rows), key=str.lower)


def main():
    try:
        if unreal.EditorLevelLibrary.is_playing():
            raise RuntimeError("Stop PIE before running the Stage 15B native class audit.")
    except AttributeError:
        pass

    classes, failures = class_rows()
    candidates = candidate_rows()
    objects = object_rows()

    query_like = [row for row in classes if "query" in row.lower()]
    point_like = [row for row in classes if "point" in row.lower()]
    writable = [row for row in classes if "PYTHON_TYPE=NONE" not in row and "UNAVAILABLE" not in row]

    lines = [
        "AETHER STAGE 15B - PCG MESH TERRAIN NATIVE CLASS AUDIT",
        "=" * 100,
        "READ_ONLY=TRUE",
        "NO_GRAPHS_CREATED=TRUE",
        "NO_ACTORS_CREATED=TRUE",
        "NO_COMPONENTS_CREATED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
        f"MATCHING_NATIVE_CLASSES={len(classes)}",
        f"QUERY_LIKE_CLASSES={len(query_like)}",
        f"POINT_LIKE_CLASSES={len(point_like)}",
        f"PYTHON_RESOLVABLE_CLASSES={len(writable)}",
    ]
    lines.extend(failures)

    lines.extend(("", "NATIVE_CLASSES", "-" * 100))
    lines.extend(classes or ["NONE"])
    lines.extend(("", "KNOWN_CLASS_PATH_PROBES", "-" * 100))
    lines.extend(candidates)
    lines.extend(("", "LOADED_INTEROP_OBJECTS", "-" * 100))
    lines.extend(objects or ["NONE"])

    query_ready = bool(query_like)
    point_ready = bool(point_like)
    lines.extend((
        "",
        "SUMMARY",
        "-" * 100,
        f"NATIVE_QUERY_CLASS_FOUND={query_ready}",
        f"NATIVE_TO_POINT_CLASS_FOUND={point_ready}",
        "AUDIT_RESULT=PASS",
        "NEXT=Use the resolved native class paths to author PCG_Aether_RiverBiome, or use the smallest documented manual-node fallback only if those settings classes are intentionally editor-private.",
    ))

    report = "\n".join(lines).rstrip() + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    for line in lines:
        unreal.log_warning(line)
    unreal.log_warning(f"AETHER_STAGE15B_PCG_NATIVE_CLASS_REPORT={REPORT_PATH}")


try:
    main()
except Exception as exc:
    failure = "\n".join((
        "AETHER STAGE 15B - PCG MESH TERRAIN NATIVE CLASS AUDIT",
        "=" * 100,
        "AUDIT_RESULT=FAIL",
        f"ERROR={type(exc).__name__}: {exc}",
        "NO_GRAPHS_CREATED=TRUE",
        "NO_ACTORS_CREATED=TRUE",
        "NO_COMPONENTS_CREATED=TRUE",
        "NO_PACKAGES_SAVED=TRUE",
        "NO_PCG_GENERATION_STARTED=TRUE",
        "NO_MESH_PARTITION_BUILD_STARTED=TRUE",
    )) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(failure, encoding="utf-8")
    unreal.log_error(failure)
    raise
