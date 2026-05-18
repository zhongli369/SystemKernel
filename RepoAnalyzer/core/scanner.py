import os
from typing import List, Set


IGNORE_DIRS: Set[str] = {"venv", "node_modules", ".git", "__pycache__"}


def scan_directory(root_path: str) -> List[str]:
    """Recursively scan a directory and return a flat list of relative file paths.

    Ignores directories: venv, node_modules, .git, __pycache__
    """
    root_path = os.path.abspath(root_path)
    file_paths: List[str] = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root_path)
            file_paths.append(rel_path)

    return file_paths


def collect_folder_hierarchy(root_path: str) -> List[str]:
    """Collect all folder paths (relative) in the repo, respecting ignore rules."""
    root_path = os.path.abspath(root_path)
    folder_paths: List[str] = []

    for dirpath, dirnames, _ in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        if dirpath != root_path:
            rel_path = os.path.relpath(dirpath, root_path)
            folder_paths.append(rel_path)

    return folder_paths
