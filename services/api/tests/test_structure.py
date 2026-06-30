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


# External SDKs that must stay confined to the repo/ layer. boto3/botocore is
# the storage SDK; deoldify/torch/fastai/cv2/imageio_ffmpeg are the colorization
# model stack. Same containment invariant: service/runtime never import them.
CONTAINED_SDK_PREFIXES = (
    "boto3",
    "botocore",
    "deoldify",
    "torch",
    "torchvision",
    "fastai",
    "cv2",
    "imageio_ffmpeg",
)


def _is_contained_sdk(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in CONTAINED_SDK_PREFIXES
    )


def test_boto3_only_in_repo():
    """Verify boto3 + the DeOldify model stack are only imported in app/repo/."""
    violations = []
    for layer in LAYER_ORDER:
        if layer == "repo":
            continue
        layer_dir = APP_ROOT / layer
        if not layer_dir.exists():
            continue
        for pyfile in _get_python_files(layer_dir):
            for imp in _get_imports(pyfile):
                if _is_contained_sdk(imp):
                    rel = pyfile.relative_to(APP_ROOT.parent)
                    violations.append(
                        f"{rel}: external SDK '{imp}' imported outside repo/"
                    )
    assert violations == [], "SDK boundary violations:\n" + "\n".join(violations)


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
