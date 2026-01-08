---
description: Auto-fix lint issues and format code
---

# Fix Code Style

Auto-fix lint issues and format all code.

## Execute

```bash
make lint-fix && make format
```

This runs:
1. `ruff check --fix src tests` - Auto-fix lint issues
2. `ruff format src tests` - Format code

## What Gets Fixed

### Auto-fixable by ruff:
- Import sorting (isort)
- Unused imports removal
- Simple code style issues
- Pyupgrade transformations (Python 3.11+ syntax)
- Some security issues

### Formatted by ruff format:
- Consistent indentation
- Line length (100 chars max)
- Quote style
- Trailing commas
- Blank lines

## What Won't Be Auto-Fixed

- Type errors (need manual fixes)
- Complex logic issues
- Security issues requiring code changes
- Test failures

## After Fixing

Run the full CI to verify:
```bash
make ci
```
