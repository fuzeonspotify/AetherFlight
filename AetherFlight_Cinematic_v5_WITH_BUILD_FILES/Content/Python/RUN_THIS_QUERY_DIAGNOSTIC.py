"""Single entry point for the current read-only river grounding diagnostic."""

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TARGET = SCRIPT_DIR / "DIAGNOSE_RIVER_GROUNDING_QUERY_V2.py"

if not TARGET.is_file():
    raise RuntimeError(f"Current query diagnostic is missing: {TARGET}")

namespace = {
    "__file__": str(TARGET),
    "__name__": "__main__",
}
source = TARGET.read_text(encoding="utf-8")
exec(compile(source, str(TARGET), "exec"), namespace, namespace)
