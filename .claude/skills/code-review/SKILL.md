---
name: code-review
description: Review code changes for correctness, security, performance, and maintainability. Use when the user asks for a code review, PR review, or wants feedback on their code.
---

# Code Review

Perform thorough, structured code reviews on diffs, branches, or individual files.

## Trigger

- "review this code"
- "code review"
- "review my PR"
- "check this for bugs"
- "audit this code"

## Review Dimensions

### 1. Correctness
- Logic errors, off-by-one, edge cases
- Null/undefined handling, type errors
- Race conditions, async ordering issues
- Incorrect assumptions about input data

### 2. Security
- Injection vectors (SQL, command, XSS)
- Missing authorization/authentication checks
- Sensitive data exposure (logging, error messages)
- Unsafe deserialization

### 3. Performance
- N+1 queries, unnecessary allocations
- Blocking operations on hot paths
- Missing caching opportunities
- Inefficient data structures for the use case

### 4. Maintainability
- Clear naming, single responsibility
- Appropriate abstraction level (don't over-abstract)
- Error handling clarity
- Test coverage and test quality

### 5. Conventions
- Follows project CLAUDE.md and style guides
- Consistent patterns with surrounding code
- Commit hygiene

## Workflow

1. Read the changed files in full
2. Understand the change context (git log, related files)
3. Check each dimension above
4. Categorize findings:
   - **Critical**: merge-blocking — security holes, data loss, wrong behavior
   - **Major**: should fix — perf issues, unclear logic, missing tests
   - **Minor**: nice to have — style nits, naming suggestions
   - **Question**: need clarification from author
5. Present findings sorted by severity
6. For each finding, include:
   - File path and line reference
   - What the issue is
   - Why it matters
   - Suggested fix (if clear)

## Output Format

```
## Code Review: [branch/diff name]

### Critical
- **file:line** — Description. Suggestion: ...

### Major
- **file:line** — Description. Suggestion: ...

### Minor
- **file:line** — Description.

### Questions
- file:line — Question to clarify with author.
```

## Guidelines

- Be constructive, not judgmental
- Review the code, not the author
- Distinguish fact (bug) from opinion (style preference)
- If the codebase follows a different convention than what you'd prefer, respect the existing convention
- Don't flag issues in generated code or vendored dependencies unless they cause real problems
- Limit review to what changed — don't suggest unrelated refactors
