"""Tag generator — produces lightweight semantic tags for each file."""

from typing import Dict, List, Set

# Domain heuristic keywords → tag mapping
DOMAIN_KEYWORDS: Dict[str, Set[str]] = {
    "auth": {"auth", "login", "logout", "session", "token", "oauth", "jwt", "permission", "rbac"},
    "db": {"db", "database", "migrate", "migration", "seed", "seed", "repository", "dao", "orm"},
    "api": {"api", "rest", "graphql", "endpoint", "request", "response", "http", "route", "router"},
    "ui": {"ui", "component", "view", "template", "render", "dom", "html", "css", "style", "widget"},
    "cli": {"cli", "command", "argparse", "click", "cobra", "flag", "console", "terminal"},
    "data": {"schema", "model", "entity", "dto", "serializer", "deserialize", "marshal", "unmarshal"},
    "config": {"config", "setting", "env", "environment", "constant", "option", "profile"},
    "test": {"test", "spec", "mock", "stub", "fake", "assert", "expect", "junit"},
    "io": {"file", "io", "stream", "reader", "writer", "buffer", "socket", "network", "pipe"},
    "error": {"error", "exception", "panic", "recover", "retry", "fallback", "circuit"},
    "log": {"log", "logger", "logging", "trace", "debug", "monitor", "metrics", "telemetry"},
    "build": {"build", "compile", "bundle", "webpack", "rollup", "vite", "esbuild", "gradle", "maven"},
    "ci": {"ci", "cd", "jenkins", "github", "gitlab", "action", "pipeline", "workflow", "deploy", "docker"},
}


def generate_tags(
    language: str,
    role: str,
    is_entrypoint: bool,
    path: str,
    name: str,
) -> List[str]:
    tags: List[str] = []

    if language and language != "unknown":
        tags.append(language)

    if role and role != "unknown":
        tags.append(role)

    if is_entrypoint:
        tags.append("entrypoint")

    normalized_path = path.replace("\\", "/").lower()
    name_lower = name.lower()

    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in normalized_path or kw in name_lower for kw in keywords):
            tags.append(domain)

    if not any(t in {"auth", "db", "api", "ui", "cli"} for t in tags):
        if "core" in normalized_path:
            tags.append("core")

    seen: Set[str] = set()
    unique = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return unique
