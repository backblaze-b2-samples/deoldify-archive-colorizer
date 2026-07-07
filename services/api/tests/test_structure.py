"""Structural tests that enforce layering rules and code quality invariants."""

import ast
from pathlib import Path

APP_ROOT = Path(__file__).parent.parent / "app"

# Layer ordering: lower layers must not import from higher layers
LAYER_ORDER = ["types", "config", "repo", "service", "runtime"]

# Map of layer -> set of layers it must NOT import from
FORBIDDEN_IMPORTS: dict[str, set[str]] = {}
for i, layer in enumerate(LAYER_ORDER):
    # Each layer cannot import from layers above it
    FORBIDDEN_IMPORTS[layer] = set(LAYER_ORDER[i + 1 :])


def _get_python_files(directory: Path) -> list[Path]:
    """Get all .py files in a directory recursively."""
    return list(directory.rglob("*.py"))


def _get_imports(filepath: Path) -> list[str]:
    """Extract all import module names from a Python file."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _layer_of_import(module: str) -> str | None:
    """Return the layer name if the import is from app.<layer>, else None."""
    if not module.startswith("app."):
        return None
    parts = module.split(".")
    if len(parts) >= 2:
        return parts[1]
    return None


def test_no_backward_imports():
    """Verify no layer imports from a higher layer."""
    violations = []
    for layer in LAYER_ORDER:
        layer_dir = APP_ROOT / layer
        if not layer_dir.exists():
            continue
        for pyfile in _get_python_files(layer_dir):
            for imp in _get_imports(pyfile):
                imported_layer = _layer_of_import(imp)
                if imported_layer and imported_layer in FORBIDDEN_IMPORTS[layer]:
                    rel = pyfile.relative_to(APP_ROOT.parent)
                    violations.append(
                        f"{rel}: {layer}/ imports from {imported_layer}/ ({imp})"
                    )
    assert violations == [], "Backward import violations:\n" + "\n".join(violations)


# boto3/botocore is the storage SDK — confined to the repo/ layer (b2_client).
STORAGE_SDK_PREFIXES = ("boto3", "botocore")

# The DeOldify model stack (fastai-v1 / torch-1.11 / deoldify) is irreconcilable
# with this API's modern env, so it runs in the infra/deoldify/ container. The
# architectural invariant is therefore stronger than mere layer containment:
# these must NOT be imported ANYWHERE in this API, including repo/. The adapter
# in repo/deoldify_repo.py talks to the container over HTTP (httpx) only.
# cv2 is intentionally NOT banned — the light restore pass may use it (though it
# currently uses only Pillow).
MODEL_STACK_PREFIXES = (
    "deoldify",
    "torch",
    "torchvision",
    "fastai",
    "imageio_ffmpeg",
)


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".") for prefix in prefixes
    )


def test_boto3_only_in_repo():
    """Verify boto3/botocore are only imported in app/repo/ (storage SDK)."""
    violations = []
    for layer in LAYER_ORDER:
        if layer == "repo":
            continue
        layer_dir = APP_ROOT / layer
        if not layer_dir.exists():
            continue
        for pyfile in _get_python_files(layer_dir):
            for imp in _get_imports(pyfile):
                if _matches_prefix(imp, STORAGE_SDK_PREFIXES):
                    rel = pyfile.relative_to(APP_ROOT.parent)
                    violations.append(
                        f"{rel}: storage SDK '{imp}' imported outside repo/"
                    )
    assert violations == [], "SDK boundary violations:\n" + "\n".join(violations)


def test_deoldify_stack_not_imported_anywhere():
    """The DeOldify model stack must live only in the container, never in this API.

    Enforces the two-container split: torch/fastai/deoldify are imported nowhere
    under app/ (not even repo/). The repo adapter is an HTTP client to the
    infra/deoldify/ colorization service instead.
    """
    violations = []
    for pyfile in _get_python_files(APP_ROOT):
        for imp in _get_imports(pyfile):
            if _matches_prefix(imp, MODEL_STACK_PREFIXES):
                rel = pyfile.relative_to(APP_ROOT.parent)
                violations.append(
                    f"{rel}: model-stack import '{imp}' — must live only in "
                    "infra/deoldify/"
                )
    assert violations == [], "Model-stack boundary violations:\n" + "\n".join(
        violations
    )


def test_file_size_limits():
    """Verify no Python file exceeds 300 lines."""
    violations = []
    for pyfile in _get_python_files(APP_ROOT):
        line_count = len(pyfile.read_text().splitlines())
        if line_count > 300:
            rel = pyfile.relative_to(APP_ROOT.parent)
            violations.append(f"{rel}: {line_count} lines (max 300)")
    assert violations == [], "File size violations:\n" + "\n".join(violations)


def test_all_layers_exist():
    """Verify all expected layer directories exist."""
    for layer in LAYER_ORDER:
        layer_dir = APP_ROOT / layer
        assert layer_dir.exists(), f"Missing layer directory: app/{layer}/"
        init_file = layer_dir / "__init__.py"
        assert init_file.exists(), f"Missing __init__.py in app/{layer}/"
