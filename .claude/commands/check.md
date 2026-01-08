---
description: Run full CI pipeline locally (lint, format, typecheck, test)
---

# Run CI Pipeline

Run the complete CI pipeline locally to verify code quality before pushing.

## Execute

```bash
make ci
```

This runs:
1. **Lint check**: `ruff check src tests`
2. **Format check**: `ruff format --check src tests`
3. **Type check**: `pyright src`
4. **Tests**: `pytest -v`

## If Checks Fail

### Lint errors
```bash
make lint-fix  # Auto-fix what's possible
```

### Format errors
```bash
make format  # Auto-format code
```

### Type errors
Review the pyright output and fix type annotations. Common issues:
- Missing return type annotations
- Incompatible types in assignments
- Missing `TYPE_CHECKING` imports

### Test failures
```bash
pytest tests/test_specific.py -v  # Run specific test
pytest tests/ -x  # Stop on first failure
```

## Quick Fixes

If you want to auto-fix everything possible:
```bash
make lint-fix && make format
```

Then re-run `make ci` to verify.
