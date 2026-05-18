"""Rule-based file role classification based on file name, path, and extension patterns."""

from typing import Optional

# Patterns are (keyword_in_path, role_label)
# Order matters: first match wins, so more specific patterns go first
ROLE_RULES = [
    # entrypoint patterns
    ("cli.py", "entrypoint"),
    ("main.py", "entrypoint"),
    ("app.py", "entrypoint"),
    ("index.py", "entrypoint"),
    ("server.py", "entrypoint"),
    ("main.go", "entrypoint"),
    ("main.rs", "entrypoint"),
    ("App.tsx", "entrypoint"),
    ("index.tsx", "entrypoint"),
    ("main.ts", "entrypoint"),
    ("index.ts", "entrypoint"),
    ("index.js", "entrypoint"),
    ("server.js", "entrypoint"),
    ("app.js", "entrypoint"),
    # interface layer (before generic matches)
    ("/api/", "interface"),
    ("/routes/", "interface"),
    ("/router", "interface"),
    ("/controllers/", "interface"),
    ("/controller/", "interface"),
    ("/handlers/", "interface"),
    ("/handler", "interface"),
    ("/middleware", "interface"),
    # data layer
    ("/models/", "data"),
    ("/model/", "data"),
    ("/schemas/", "data"),
    ("/schema/", "data"),
    ("/entities/", "data"),
    ("/entity/", "data"),
    ("/types/", "data"),
    ("/types.go", "data"),
    ("/interfaces/", "data"),
    # business logic
    ("/services/", "service"),
    ("/service/", "service"),
    ("/managers/", "service"),
    ("/manager/", "service"),
    ("/core/", "service"),
    ("/lib/", "service"),
    ("/src/", "service"),
    # configuration
    ("/config/", "config"),
    ("/configs/", "config"),
    ("/settings/", "config"),
    ("/constants/", "config"),
    ("/consts/", "config"),
    ("/env/", "config"),
    # tests
    ("/test/", "test"),
    ("/tests/", "test"),
    ("/spec/", "test"),
    ("/specs/", "test"),
    ("/__tests__/", "test"),
    ("/mocks/", "test"),
    ("/mock/", "test"),
    ("/fixtures/", "test"),
    ("/fixture/", "test"),
    # scripts and tools
    ("/scripts/", "script"),
    ("/script/", "script"),
    ("/tools/", "script"),
    ("/tool/", "script"),
    ("/bin/", "script"),
    # documentation
    ("/docs/", "docs"),
    ("/documentation/", "docs"),
    ("/examples/", "docs"),
    ("/example/", "docs"),
    # assets and static
    ("/assets/", "asset"),
    ("/static/", "asset"),
    ("/public/", "asset"),
    ("/templates/", "asset"),
    ("/template/", "asset"),
    ("/styles/", "asset"),
    ("/css/", "asset"),
    ("/components/", "component"),
    ("/component/", "component"),
    ("/ui/", "component"),
    # dot-directory structures
    ("/.github/workflows/", "script"),
    ("/.github/actions/", "script"),
    ("/.github/", "config"),
    ("/.vscode/", "config"),
    ("/.idea/", "config"),
    ("/.claude/commands/", "script"),
    ("/.claude/skills/", "docs"),
    ("/.claude/", "config"),
    # references and guides
    ("/references/", "docs"),
    ("/reference/", "docs"),
    ("/guides/", "docs"),
    ("/guide/", "docs"),
    ("/tutorials/", "docs"),
    ("/tutorial/", "docs"),
]


def classify_file_role(file_path: str, file_name: str) -> str:
    """Classify a file's role based on path and name patterns.

    Returns one of: entrypoint, interface, data, service, config, test,
                    script, docs, asset, component, utility, unknown
    """
    normalized = "/" + file_path.replace("\\", "/") + "/"

    for pattern, role in ROLE_RULES:
        if pattern.startswith("/") and pattern.endswith("/"):
            if pattern in normalized:
                return role
        elif pattern.startswith("/"):
            if pattern in normalized:
                return role
        else:
            if file_name == pattern or normalized.endswith("/" + pattern + "/"):
                return role

    return classify_by_name_heuristic(file_name, normalized)


def classify_by_name_heuristic(file_name: str, normalized_path: str) -> str:
    """Fallback classification based on file naming conventions."""
    name_lower = file_name.lower()

    if name_lower.startswith("test_") or name_lower.endswith("_test.py") or name_lower.endswith(".test"):
        return "test"
    if name_lower.endswith("_spec.py") or name_lower.endswith(".spec"):
        return "test"
    if name_lower.startswith("mock") or name_lower.startswith("fake") or name_lower.startswith("stub"):
        return "test"

    if any(kw in name_lower for kw in ("util", "helper", "common", "misc")):
        return "utility"
    if any(kw in name_lower for kw in ("config", "setting", "env", "constant", "const")):
        return "config"

    if file_name.endswith(".md") or file_name.endswith(".rst") or file_name.endswith(".txt"):
        return "docs"
    if file_name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "NOTICE"):
        return "docs"
    if file_name in ("CHANGELOG.md", "CHANGELOG.txt", "CHANGES.md"):
        return "docs"
    if file_name in ("README.md", "README.txt", "README.rst"):
        return "docs"
    if file_name in ("CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md"):
        return "docs"

    if normalized_path.startswith("."):
        return "config"

    return "utility"
