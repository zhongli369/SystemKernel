"""Resolve import module paths to real file paths."""

import os
from typing import Dict, List, Optional, Set, Tuple

# Extensions to try when resolving a bare module path
SEARCH_EXTENSIONS = (
    ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs",
    ".java", ".go", ".rs", ".rb", ".php",
)


def build_file_index(file_paths: List[str]) -> Dict[str, str]:
    """Build an index mapping basenames and extensionless names to full paths.

    Returns a dict where keys are:
      - full relative path (e.g. 'core/model.py')
      - path without extension (e.g. 'core/model')
      - bare filename (e.g. 'model.py', 'model')
    """
    idx: Dict[str, str] = {}
    for fpath in file_paths:
        normalized = fpath.replace("\\", "/")
        idx[normalized] = normalized

        if "." in normalized:
            noext, _ = os.path.splitext(normalized)
            idx[noext] = normalized
        else:
            idx[normalized] = normalized

        basename = os.path.basename(fpath)
        idx[basename] = normalized

        name_noext, _ = os.path.splitext(basename)
        idx[name_noext] = normalized

    return idx


def _normalize_dots(import_path: str) -> str:
    """Convert dot-separated Python module paths to directory separators.

    'core.model' → 'core/model'
    """
    return import_path.replace(".", "/")


def resolve_import(
    import_path: str,
    from_file: str,
    file_index: Dict[str, str],
    language: str,
) -> Optional[Tuple[str, float]]:
    """Resolve an import path to a real file path.

    Args:
        import_path: The raw import string (e.g. './utils', 'core.model', 'react')
        from_file: The file containing the import (e.g. 'core/parser.py')
        file_index: Built file index
        language: Source language

    Returns:
        (resolved_path, confidence) or None if unresolvable
    """
    import_clean = import_path.strip()

    # External package — doesn't start with dot or slash
    if not import_clean.startswith(".") and "/" not in import_clean:
        if language == "python":
            clean = _normalize_dots(import_clean)
        else:
            clean = import_clean
    else:
        clean = import_clean

    # Relative import: resolve against from_file's directory
    if clean.startswith("."):
        from_dir = os.path.dirname(from_file.replace("\\", "/"))
        resolved = os.path.normpath(os.path.join(from_dir, clean)).replace("\\", "/")
        return _find_with_extensions(resolved, file_index)

    # Absolute-looking import: try as direct path lookup
    result = _find_with_extensions(clean, file_index)
    if result:
        return result

    # Try basename lookup (last-ditch)
    basename = os.path.basename(clean)
    for ext in SEARCH_EXTENSIONS:
        candidate = basename + ext
        if candidate in file_index:
            return (file_index[candidate], 0.7)
    if basename in file_index:
        return (file_index[basename], 0.7)

    return None


def _find_with_extensions(
    resolved_path: str,
    file_index: Dict[str, str],
) -> Optional[Tuple[str, float]]:
    """Try to find a resolved path in the file index, trying extensions.

    Returns (path, confidence) or None.
    """
    # Direct match
    if resolved_path in file_index:
        return (file_index[resolved_path], 1.0)

    # Try adding extensions
    for ext in SEARCH_EXTENSIONS:
        candidate = resolved_path + ext
        if candidate in file_index:
            return (file_index[candidate], 1.0)

    # Try index file in directory
    for ext in (".py", ".js", ".ts", ".tsx"):
        candidate = resolved_path + "/__init__" + ext
        if candidate in file_index:
            return (file_index[candidate], 0.8)
        candidate = resolved_path + "/index" + ext
        if candidate in file_index:
            return (file_index[candidate], 0.8)

    # Partial match: filename match for last component
    basename = os.path.basename(resolved_path)
    for ext in SEARCH_EXTENSIONS:
        candidate = basename + ext
        if candidate in file_index:
            return (file_index[candidate], 0.7)
    if basename in file_index:
        return (file_index[basename], 0.7)

    return None
