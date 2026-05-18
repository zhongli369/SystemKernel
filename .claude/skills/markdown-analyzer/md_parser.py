#!/usr/bin/env python3
"""
md_parser.py — Markdown structure parser for markdown-analyzer skill.

Parses a markdown file and outputs a JSON skeleton:
  frontmatter, headings, links, code_blocks, todos,
  references, section_tree

Usage:
    python md_parser.py <path-to-markdown-file>
    python md_parser.py <path-to-markdown-file> --json > output.json
"""

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Heading:
    depth: int
    text: str
    line: int


@dataclass
class Link:
    text: str
    url: str
    line: int
    heading_context: str = ""


@dataclass
class CodeBlock:
    language: str
    line_count: int
    start_line: int
    heading_context: str = ""


@dataclass
class TodoItem:
    text: str
    checked: bool
    line: int
    heading_context: str = ""


@dataclass
class SectionNode:
    heading: str
    depth: int
    line: int
    children: List["SectionNode"] = field(default_factory=list)
    todo_count: int = 0
    link_count: int = 0
    code_block_count: int = 0


@dataclass
class MarkdownSkeleton:
    file_path: str
    frontmatter: Dict[str, str] = field(default_factory=dict)
    headings: List[Heading] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)
    todos: List[TodoItem] = field(default_factory=list)
    references: Dict[str, str] = field(default_factory=dict)
    section_tree: List[SectionNode] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)


def _current_heading_context(headings: List[Heading], line: int) -> str:
    """Find the deepest heading that precedes the given line."""
    context = ""
    for h in headings:
        if h.line < line:
            context = h.text
    return context


def parse_markdown(file_path: str) -> MarkdownSkeleton:
    """Parse a markdown file and extract its structural skeleton."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    result = MarkdownSkeleton(file_path=str(path.resolve()))

    # ── Frontmatter ──────────────────────────────────────────────────────
    fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    fm_end_line = 0
    if fm_match:
        fm_end_line = fm_match.group(0).count("\n")
        for line in fm_match.group(1).split("\n"):
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                result.frontmatter[key.strip()] = value.strip().strip("\"'")

    # ── Code blocks (fenced) — collect first so headings skip them ───────
    code_line_set: set = set()
    in_block = False
    block_lang = ""
    block_start = 0
    block_lines: List[str] = []
    for i, line in enumerate(lines, start=1):
        fm = re.match(r"^```(\w*)", line)
        if fm and not in_block:
            in_block = True
            block_lang = fm.group(1) or ""
            block_start = i
            block_lines = []
            code_line_set.add(i)
        elif re.match(r"^```\s*$", line) and in_block:
            in_block = False
            code_line_set.add(i)
            context = _current_heading_context(result.headings, block_start)
            result.code_blocks.append(CodeBlock(
                language=block_lang,
                line_count=len(block_lines),
                start_line=block_start,
                heading_context=context,
            ))
        elif in_block:
            block_lines.append(line)
            code_line_set.add(i)

    # ── Headings (skip code block lines) ─────────────────────────────────
    for i, line in enumerate(lines, start=1):
        if i in code_line_set:
            continue
        m = re.match(r"^(#{1,6})\s+(.+?)(?:\s+#+\s*)?$", line)
        if m:
            result.headings.append(Heading(
                depth=len(m.group(1)),
                text=m.group(2).strip(),
                line=i,
            ))

    # ── Links (inline [text](url)) ───────────────────────────────────────
    for i, line in enumerate(lines, start=1):
        if i in code_line_set:
            continue
        for m in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", line):
            text_part = m.group(1)
            url = m.group(2)
            context = _current_heading_context(result.headings, i)
            result.links.append(Link(
                text=text_part,
                url=url,
                line=i,
                heading_context=context,
            ))

    # ── TODOs (- [ ] and - [x]) — skip code blocks ───────────────────────
    for i, line in enumerate(lines, start=1):
        if i in code_line_set:
            continue
        m = re.match(r"^\s*[-*+]\s+\[(x|\s)\]\s+(.+)", line, re.IGNORECASE)
        if m:
            context = _current_heading_context(result.headings, i)
            result.todos.append(TodoItem(
                text=m.group(2).strip(),
                checked=m.group(1).lower() == "x",
                line=i,
                heading_context=context,
            ))

    # ── Reference-style links ([label]: url) — skip code blocks ──────────
    for i, line in enumerate(lines, start=1):
        if i in code_line_set:
            continue
        m = re.match(r"^\s*\[([^\]]+)\]:\s*(\S+)", line)
        if m:
            result.references[m.group(1)] = m.group(2)

    # ── Section tree ─────────────────────────────────────────────────────
    stack: List[SectionNode] = []
    for h in result.headings:
        node = SectionNode(heading=h.text, depth=h.depth, line=h.line)
        # Assign TODOs, links, code blocks under this heading (until next same-depth heading)
        next_h = None
        for nh in result.headings:
            if nh.line > h.line and nh.depth <= h.depth:
                next_h = nh
                break

        for todo in result.todos:
            if todo.line > h.line and (next_h is None or todo.line < next_h.line):
                node.todo_count += 1
        for link in result.links:
            if link.line > h.line and (next_h is None or link.line < next_h.line):
                node.link_count += 1
        for cb in result.code_blocks:
            if cb.start_line > h.line and (next_h is None or cb.start_line < next_h.line):
                node.code_block_count += 1

        # Build tree
        while stack and stack[-1].depth >= h.depth:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            result.section_tree.append(node)
        stack.append(node)

    # ── Stats ────────────────────────────────────────────────────────────
    internal_links = sum(1 for l in result.links if not l.url.startswith("http"))
    external_links = sum(1 for l in result.links if l.url.startswith("http"))
    result.stats = {
        "total_lines": len(lines),
        "heading_count": len(result.headings),
        "link_count": len(result.links),
        "internal_links": internal_links,
        "external_links": external_links,
        "code_block_count": len(result.code_blocks),
        "code_languages": len(set(cb.language for cb in result.code_blocks)),
        "todo_total": len(result.todos),
        "todo_done": sum(1 for t in result.todos if t.checked),
        "todo_pending": sum(1 for t in result.todos if not t.checked),
        "reference_count": len(result.references),
    }

    return result


def to_dict(skeleton: MarkdownSkeleton) -> dict:
    """Convert skeleton to a JSON-safe dict."""
    d = asdict(skeleton)
    return d


def main():
    if len(sys.argv) < 2:
        print("Usage: python md_parser.py <path-to-markdown-file> [--json]", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    skeleton = parse_markdown(file_path)
    data = to_dict(skeleton)
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
