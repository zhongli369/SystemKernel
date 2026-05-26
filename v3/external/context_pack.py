"""
External Context Pack Adapter — Safe wrapper for external codebase packing tools.

Wraps Repomix (npx repomix) as an external process. The adapter constructs
commands deterministically but never executes them without explicit opt-in.

Key invariants:
- plan() never executes external commands
- generate() refuses unless allow_execute=True
- truth_source is always False
- repo root is blocked by default
- oversize targets are blocked

This is NOT a kernel module. It lives under v3/external/ and is an optional
developer tool, not part of the kernel execution pipeline.
"""

from __future__ import annotations

import hashlib
import os
import shlex
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ContextPackConfig:
    """Immutable configuration for a context pack operation."""

    target_path: str = ""
    output_path: str = ""
    style: str = "markdown"
    max_bytes: int = 10_000_000
    max_tokens: int = 200_000
    include_patterns: Tuple[str, ...] = ()
    exclude_patterns: Tuple[str, ...] = ()
    dry_run: bool = True
    tool: str = "repomix"
    allow_repo_root: bool = False

    def __post_init__(self):
        if self.style not in ("markdown", "xml", "json", "plain"):
            raise ValueError(f"Unsupported style: {self.style}. Use markdown, xml, json, or plain.")


# ═══════════════════════════════════════════════════════════════════════
# Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ContextPackResult:
    """Result of a context pack operation. truth_source is ALWAYS False."""

    status: str = "planned"  # planned | generated | blocked | failed
    command: str = ""
    target_path: str = ""
    output_path: str = ""
    size_bytes: int = 0
    line_count: int = 0
    token_estimate: int = 0
    included_files: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    pack_hash: str = ""
    truth_source: bool = False  # ALWAYS False — never a truth source


# ═══════════════════════════════════════════════════════════════════════
# Path resolution
# ═══════════════════════════════════════════════════════════════════════

def _resolve_root() -> str:
    """Resolve the SystemKernel root directory."""
    external_dir = os.path.dirname(os.path.abspath(__file__))
    v3_dir = os.path.dirname(external_dir)
    return os.path.dirname(v3_dir)


def _resolve_absolute(target: str) -> str:
    """Resolve a target path to absolute, relative to SystemKernel root."""
    if os.path.isabs(target):
        return os.path.normpath(target)
    root = _resolve_root()
    return os.path.normpath(os.path.join(root, target))


def _is_repo_root(target: str) -> bool:
    """Check if target is the SystemKernel repository root or v3 root."""
    root = _resolve_root()
    v3_root = os.path.join(root, "v3")
    abs_target = _resolve_absolute(target)
    normalized_root = os.path.normpath(root)
    normalized_v3 = os.path.normpath(v3_root)
    return abs_target == normalized_root or abs_target == normalized_v3


# ═══════════════════════════════════════════════════════════════════════
# Command construction
# ═══════════════════════════════════════════════════════════════════════

def _build_repomix_command(target: str, output: str, style: str = "markdown") -> str:
    """Construct a deterministic npx repomix command.

    Uses npx repomix@latest to avoid installing globally.
    Output is always deterministic for the same inputs.
    """
    # Use cross-platform path
    target_norm = target.replace("\\", "/")
    output_norm = output.replace("\\", "/")
    return f'npx repomix@latest {shlex.quote(target_norm)} --output {shlex.quote(output_norm)} --style {shlex.quote(style)}'


# ═══════════════════════════════════════════════════════════════════════
# Size estimation
# ═══════════════════════════════════════════════════════════════════════

def _estimate_output_bytes(target_abs: str) -> int:
    """Estimate output size by summing source file sizes in target directory.

    Only counts text files (Python, Markdown, JSON, YAML, TOML, etc.).
    Adds 15% overhead for markdown formatting and headers.
    """
    if not os.path.isdir(target_abs):
        if os.path.isfile(target_abs):
            return os.path.getsize(target_abs)
        return 0

    text_extensions = {
        ".py", ".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
        ".txt", ".rst", ".js", ".ts", ".jsx", ".tsx", ".css", ".html",
        ".xml", ".sh", ".bash", ".zsh", ".ps1",
    }

    total = 0
    for dirpath, dirnames, filenames in os.walk(target_abs):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in text_extensions or fname in (
                "Dockerfile", "Makefile", "LICENSE", "README",
            ):
                fpath = os.path.join(dirpath, fname)
                try:
                    total += os.path.getsize(fpath)
                except OSError:
                    pass

    # Add ~15% for markdown formatting overhead
    return int(total * 1.15)


def _list_files(target_abs: str) -> Tuple[str, ...]:
    """List files in target directory (relative paths). Returns sorted tuple."""
    if not os.path.isdir(target_abs):
        if os.path.isfile(target_abs):
            return (os.path.basename(target_abs),)
        return ()

    files = []
    for dirpath, dirnames, filenames in os.walk(target_abs):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        for fname in filenames:
            if fname.endswith(".pyc"):
                continue
            fpath = os.path.join(dirpath, fname)
            files.append(os.path.relpath(fpath, target_abs).replace("\\", "/"))

    return tuple(sorted(files))


# ═══════════════════════════════════════════════════════════════════════
# Adapter
# ═══════════════════════════════════════════════════════════════════════

class ContextPackAdapter:
    """Safe external wrapper for codebase context pack tools.

    plan() never executes. generate() requires allow_execute=True.
    inspect_output() is read-only. verify_pack() checks invariants.
    """

    @staticmethod
    def plan(config: ContextPackConfig) -> ContextPackResult:
        """Plan a context pack command. NEVER executes an external process.

        Returns a result with status='planned' or status='blocked'.
        The command string is constructed deterministically.
        """
        warnings = []
        target_abs = _resolve_absolute(config.target_path)
        output_abs = _resolve_absolute(config.output_path)

        # Safety: block repo root
        if not config.allow_repo_root and _is_repo_root(config.target_path):
            return ContextPackResult(
                status="blocked",
                command="",
                target_path=config.target_path,
                output_path=config.output_path,
                warnings=(
                    "REPO_ROOT_BLOCKED: target is the repository root. "
                    "Use allow_repo_root=True or specify a subdirectory.",
                ),
            )

        # Safety: check target exists
        if not os.path.exists(target_abs):
            return ContextPackResult(
                status="blocked",
                command="",
                target_path=config.target_path,
                output_path=config.output_path,
                warnings=(f"TARGET_NOT_FOUND: {config.target_path} does not exist.",),
            )

        # Estimate size
        estimated = _estimate_output_bytes(target_abs)
        if estimated > config.max_bytes:
            return ContextPackResult(
                status="blocked",
                command="",
                target_path=config.target_path,
                output_path=config.output_path,
                warnings=(
                    f"OVERSIZE: estimated {estimated:,} bytes exceeds max {config.max_bytes:,}. "
                    "Use a smaller target or increase max_bytes.",
                ),
            )

        # Count files
        included_files = _list_files(target_abs)

        # Estimate tokens (rough: 1 token ≈ 4 chars for code)
        rough_tokens = estimated // 4
        if rough_tokens > config.max_tokens:
            warnings.append(
                f"Token estimate ({rough_tokens:,}) exceeds max ({config.max_tokens:,}). "
                "Consider a smaller target or --compress."
            )

        # Build command deterministically
        command = _build_repomix_command(
            config.target_path, config.output_path, config.style
        )

        return ContextPackResult(
            status="planned",
            command=command,
            target_path=config.target_path,
            output_path=config.output_path,
            size_bytes=estimated,
            line_count=0,
            token_estimate=rough_tokens,
            included_files=included_files,
            warnings=tuple(warnings),
            pack_hash="",
            truth_source=False,
        )

    @staticmethod
    def generate(config: ContextPackConfig, allow_execute: bool = False) -> ContextPackResult:
        """Generate a context pack by executing the planned command.

        REFUSES to execute unless allow_execute=True is explicitly passed.
        This is a deliberate safety gate — automated systems must opt in.
        """
        if not allow_execute:
            return ContextPackResult(
                status="blocked",
                command="",
                target_path=config.target_path,
                output_path=config.output_path,
                warnings=(
                    "EXECUTE_NOT_ALLOWED: set allow_execute=True to run the command.",
                ),
            )

        # Plan first to validate
        plan_result = ContextPackAdapter.plan(config)
        if plan_result.status != "planned":
            return plan_result

        # Execute the command
        import subprocess
        import tempfile

        target_abs = _resolve_absolute(config.target_path)
        try:
            result = subprocess.run(
                plan_result.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=_resolve_root(),
            )

            if result.returncode != 0:
                return ContextPackResult(
                    status="failed",
                    command=plan_result.command,
                    target_path=config.target_path,
                    output_path=config.output_path,
                    warnings=(f"COMMAND_FAILED (exit {result.returncode}): {result.stderr[:500]}",),
                )

            # Inspect the output
            output_abs = _resolve_absolute(config.output_path)
            return ContextPackAdapter.inspect_output(output_abs, command=plan_result.command)

        except FileNotFoundError:
            return ContextPackResult(
                status="failed",
                command=plan_result.command,
                target_path=config.target_path,
                output_path=config.output_path,
                warnings=("NODE_NOT_FOUND: npx requires Node.js to be installed.",),
            )
        except subprocess.TimeoutExpired:
            return ContextPackResult(
                status="failed",
                command=plan_result.command,
                target_path=config.target_path,
                output_path=config.output_path,
                warnings=("TIMEOUT: command exceeded 300s limit.",),
            )

    @staticmethod
    def inspect_output(path: str, command: str = "") -> ContextPackResult:
        """Inspect an existing context pack output file. Read-only.

        Returns size, line count, hash, and extracted metadata.
        Never modifies the file.
        """
        output_abs = _resolve_absolute(path)

        if not os.path.exists(output_abs):
            return ContextPackResult(
                status="blocked",
                command=command,
                output_path=path,
                warnings=(f"OUTPUT_NOT_FOUND: {path} does not exist.",),
            )

        if not os.path.isfile(output_abs):
            return ContextPackResult(
                status="blocked",
                command=command,
                output_path=path,
                warnings=(f"NOT_A_FILE: {path} is not a regular file.",),
            )

        try:
            size_bytes = os.path.getsize(output_abs)
        except OSError:
            return ContextPackResult(
                status="failed",
                command=command,
                output_path=path,
                warnings=("Cannot read file size.",),
            )

        # Read and analyze
        try:
            with open(output_abs, encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            return ContextPackResult(
                status="failed",
                command=command,
                output_path=path,
                size_bytes=size_bytes,
                warnings=(f"Cannot read file: {e}",),
            )

        lines = content.split("\n")
        line_count = len(lines)

        # Compute SHA-256 hash
        pack_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        # Extract file headers (## File: pattern)
        included_files = []
        for line in lines:
            if line.startswith("## File: "):
                fname = line[len("## File: "):].strip()
                included_files.append(fname)

        # Rough token estimate
        token_estimate = len(content) // 4

        return ContextPackResult(
            status="generated",
            command=command,
            output_path=path,
            size_bytes=size_bytes,
            line_count=line_count,
            token_estimate=token_estimate,
            included_files=tuple(included_files),
            pack_hash=pack_hash,
            truth_source=False,
        )

    @staticmethod
    def verify_pack(result: ContextPackResult) -> bool:
        """Verify a context pack result meets invariants.

        Returns True if the pack passes all checks:
        - truth_source must be False
        - status must not be 'failed'
        - if generated, must have a non-empty pack_hash
        """
        if result.truth_source:
            return False
        if result.status == "failed":
            return False
        if result.status == "blocked":
            return len(result.warnings) > 0  # blocked must have a reason
        if result.status == "generated":
            if not result.pack_hash:
                return False
            if result.size_bytes == 0:
                return False
        return True
