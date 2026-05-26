This file is a merged representation of a sample codebase, combined into a single document by Repomix.

# File Summary

## Purpose
This file contains a packed representation of sample repository contents.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files

## Usage Guidelines
- This file should be treated as read-only.
- When processing this file, use the file path to distinguish between different files.
- Be aware that this file may contain sensitive information.

## Notes
- Some files may have been excluded based on .gitignore rules.
- Binary files are not included.

# Directory Structure
```
sample.py
utils.py
```

# Files

## File: sample.py
```python
"""Sample module for testing."""
def hello():
    return "Hello, World!"

class Sample:
    def __init__(self):
        self.value = 42

    def get_value(self):
        return self.value
```

## File: utils.py
```python
"""Utility functions for testing."""
def add(a: int, b: int) -> int:
    return a + b

def multiply(a: int, b: int) -> int:
    return a * b

class Helper:
    @staticmethod
    def greet(name: str) -> str:
        return f"Hi, {name}!"
```
