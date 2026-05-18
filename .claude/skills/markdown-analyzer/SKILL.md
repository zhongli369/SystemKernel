---
name: markdown-analyzer
description: Parse markdown files, extract structural elements (headings, links, code blocks, TODOs), analyze via RepoAnalyzer dependency pipeline, and record actionable items into TaskSystem. Trigger when user wants to analyze a markdown document, extract TODOs from docs, or turn documentation into tracked tasks.
tags:
  - markdown
  - analysis
  - task-extraction
  - structure
---

# Markdown Analyzer Workflow

Parse a markdown file to extract its structural skeleton, analyze relationships via RepoAnalyzer, and record findings as tracked tasks in TaskSystem.

## Stage 1: Markdown Structure Parsing

Run the helper script to extract the structural skeleton of the target markdown file:

```bash
python F:/Claude/SkillsManagementSystem/packages/base/skills/markdown-analyzer/md_parser.py <path-to-markdown-file>
```

This outputs a JSON structure containing:
- `frontmatter` — YAML frontmatter key/value pairs
- `headings` — heading hierarchy with depth, text, and line numbers
- `links` — all markdown links (text, url, source heading context)
- `code_blocks` — fenced code blocks with language and line count
- `todos` — `- [ ]` and `- [x]` checklist items with surrounding context
- `references` — `[label]: url` reference-style links
- `section_tree` — nested section outline

## Stage 2: RepoAnalyzer Structural Analysis

Feed the parsed structure into RepoAnalyzer for semantic analysis:

```bash
python F:/Claude/RepoAnalyzer/cli.py insights <path-to-markdown-file>
```

If the markdown file is inside a larger repo, analyze the full repo and cross-reference:

```bash
python F:/Claude/RepoAnalyzer/cli.py plan <repo-root>
```

Interpret the output:
- Sections with high fan-in (many references) → likely core documentation nodes
- Sections referencing external repos/files → cross-cutting concerns
- Isolated sections → candidate for expansion or removal

## Stage 3: TaskSystem Recording

For each actionable TODO discovered in Stage 1, create a task in TaskSystem:

```bash
python F:/Claude/TaskSystem/cli.py new "<todo-text>"
```

Apply metadata based on Stage 2 analysis:
- Tag with the heading context: `python F:/Claude/TaskSystem/cli.py tag <TASK-ID> <section-name>`
- Set priority by heading depth: H1-H2 → P0, H3-H4 → P1, H5+ → P2
- Log analysis context: `python F:/Claude/TaskSystem/cli.py log <TASK-ID> "Source: <markdown-file>#L<line>"`

For structural issues found by RepoAnalyzer (broken links, orphan sections), create review tasks:

```bash
python F:/Claude/TaskSystem/cli.py new "Review broken link: <url> in <section>"
python F:/Claude/TaskSystem/cli.py new "Orphan section: <section> — consider linking or removing"
```

## Stage 4: Summary Report

After all tasks are created, display a summary:

```
[INFO] Markdown Analysis Complete
  File:     <path>
  Headings: <N>
  Links:    <N> (internal: <n>, external: <n>)
  TODOs:    <N> (done: <n>, pending: <n>)
  Code:     <N> blocks across <M> languages

[TASK] Tasks created: <N>
[ANALYZER] RepoAnalyzer output: .../output/...
```

Use `python F:/Claude/TaskSystem/cli.py query --tag markdown` to list all tasks from this analysis.
