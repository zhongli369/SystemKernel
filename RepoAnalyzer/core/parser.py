import os
from typing import Dict, List

from core.model import FileEntry, FolderEntry, RepoStats, RepoStructure
from core.scanner import scan_directory, collect_folder_hierarchy


LANGUAGE_MAP: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".ps1": "powershell",
    ".bat": "batch",
    ".cmd": "batch",
    ".json": "json",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "config",
    ".conf": "config",
    ".md": "markdown",
    ".rst": "restructuredtext",
    ".txt": "text",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".html": "html",
    ".htm": "html",
    ".svg": "svg",
    ".sql": "sql",
    ".graphql": "graphql",
    ".proto": "protobuf",
    ".dockerfile": "dockerfile",
    ".makefile": "makefile",
    ".cmake": "cmake",
    ".lock": "lockfile",
    ".gitignore": "gitconfig",
    ".gitattributes": "gitconfig",
}


def detect_language(ext: str, filename: str) -> str:
    """Detect language from file extension. Falls back to filename for special cases."""
    if ext in LANGUAGE_MAP:
        return LANGUAGE_MAP[ext]

    name_lower = filename.lower()
    if name_lower == "dockerfile":
        return "dockerfile"
    if name_lower == "makefile":
        return "makefile"
    if name_lower == "license":
        return "text"
    if name_lower == "changelog":
        return "text"

    return "unknown"


def parse_repo(root_path: str) -> RepoStructure:
    """Parse a repository directory into a structured RepoStructure model."""
    root_path = os.path.abspath(root_path)
    repo_name = os.path.basename(root_path)

    raw_files = scan_directory(root_path)
    raw_folders = collect_folder_hierarchy(root_path)

    files: List[FileEntry] = []
    for rel_path in sorted(raw_files):
        full_path = os.path.join(root_path, rel_path)
        try:
            size = os.path.getsize(full_path)
        except OSError:
            size = 0

        _, filename = os.path.split(rel_path)
        name, ext = os.path.splitext(filename)
        language = detect_language(ext.lower(), filename)

        files.append(FileEntry(
            path=rel_path.replace("\\", "/"),
            name=filename,
            ext=ext.lower(),
            size=size,
            language=language,
        ))

    folders: List[FolderEntry] = []
    for rel_path in sorted(raw_folders):
        normalized = rel_path.replace("\\", "/")
        depth = normalized.count("/") + 1
        folders.append(FolderEntry(path=normalized, depth=depth))

    lang_dist: Dict[str, int] = {}
    for f in files:
        lang = f.language
        lang_dist[lang] = lang_dist.get(lang, 0) + 1

    stats = RepoStats(
        total_files=len(files),
        total_folders=len(folders),
        language_distribution=dict(sorted(lang_dist.items())),
    )

    return RepoStructure(
        repo_name=repo_name,
        root_path=root_path,
        files=files,
        folders=folders,
        stats=stats,
    )
