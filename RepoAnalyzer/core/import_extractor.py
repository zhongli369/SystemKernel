"""Extract import/require statements from Python, JavaScript, and TypeScript files."""

import re
from typing import List, Tuple

# --- Python patterns ---

# import xxx, import xxx as yyy
RE_PY_IMPORT = re.compile(
    r"^\s*import\s+(\S+)", re.MULTILINE
)

# from xxx import yyy, from xxx.yyy import zzz
RE_PY_FROM_IMPORT = re.compile(
    r"^\s*from\s+(\S+)\s+import\s+", re.MULTILINE
)


def extract_python_imports(file_content: str) -> List[str]:
    """Extract raw module names from Python import statements.

    Returns a list of top-level module paths, e.g. ['os', 'json', 'core.model']
    """
    modules: List[str] = []

    for m in RE_PY_FROM_IMPORT.finditer(file_content):
        module = m.group(1)
        if not module.startswith("."):
            modules.append(module)

    for m in RE_PY_IMPORT.finditer(file_content):
        module = m.group(1)
        if not module.startswith("."):
            modules.append(module)

    return modules


# --- JavaScript / TypeScript patterns ---

# import xxx from 'yyy'
# import { xxx } from 'yyy'
# import * as xxx from 'yyy'
# import 'yyy'
RE_JS_IMPORT = re.compile(
    r"""import\s+(?:(?:\{[^}]*\}|[^'"\n;]+)\s+from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)

# const xxx = require('yyy')
# let xxx = require('yyy')
# var xxx = require('yyy')
RE_JS_REQUIRE = re.compile(
    r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE,
)

# import('yyy') dynamic imports
RE_JS_DYNAMIC = re.compile(
    r"""\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE,
)


def extract_js_ts_imports(file_content: str) -> List[str]:
    """Extract raw module paths from JS/TS import and require statements.

    Returns a list of module paths, e.g. ['./utils', 'react', '../core/module']
    """
    modules: List[str] = []

    for m in RE_JS_IMPORT.finditer(file_content):
        modules.append(m.group(1))

    for m in RE_JS_REQUIRE.finditer(file_content):
        modules.append(m.group(1))

    for m in RE_JS_DYNAMIC.finditer(file_content):
        modules.append(m.group(1))

    return modules


# --- unified API ---

def extract_imports(language: str, file_content: str) -> List[str]:
    """Extract import targets from source code based on language.

    Returns a list of module paths (strings).
    For external packages, returns the package name as-is.
    For local imports, returns relative paths (e.g. './utils', '../core/model').
    """
    if not file_content:
        return []

    if language == "python":
        return extract_python_imports(file_content)
    elif language in ("javascript", "typescript"):
        return extract_js_ts_imports(file_content)
    else:
        return []
