"""Entry point detector — identifies project entry point files."""

from typing import List, Optional

# Canonical list of entry point file names
ENTRYPOINT_NAMES = {
    "cli.py",
    "main.py",
    "app.py",
    "index.py",
    "server.py",
    "run.py",
    "wsgi.py",
    "asgi.py",
    "manage.py",
    "setup.py",
    "main.go",
    "main.rs",
    "App.tsx",
    "index.tsx",
    "index.ts",
    "main.ts",
    "index.js",
    "server.js",
    "app.js",
    "main.js",
    "Program.cs",
    "Main.java",
    "Application.java",
}


def is_entrypoint(file_name: str) -> bool:
    """Check if a file is a recognized entry point by name."""
    return file_name in ENTRYPOINT_NAMES


def detect_entrypoints(file_entries) -> List[dict]:
    """Detect all entry point files and return them sorted by importance.

    Each file_entry must have .name and .path fields.
    Returns list of dicts with path and name for inspection.
    """
    entries = [
        {"path": f.path, "name": f.name}
        for f in file_entries
        if is_entrypoint(f.name)
    ]
    return entries


def identify_primary_entrypoint(entrypoints: List[dict]) -> Optional[str]:
    """Select the primary entry point from a list of candidates.

    Priority: cli.py > main.py > app.py > server.py > index.py > first found
    """
    if not entrypoints:
        return None

    priority_order = [
        "cli.py", "main.py", "app.py", "server.py",
        "run.py", "index.py", "wsgi.py", "asgi.py", "manage.py",
        "main.go", "main.rs", "main.ts", "main.js",
        "index.ts", "index.js", "index.tsx", "App.tsx",
    ]

    for preferred in priority_order:
        for ep in entrypoints:
            if ep["name"] == preferred:
                return ep["path"]

    return entrypoints[0]["path"]
