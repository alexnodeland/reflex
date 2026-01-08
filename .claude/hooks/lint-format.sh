#!/bin/bash
# Claude Code Stop hook: Run linting and formatting after each turn

set -e

# Auto-fix lint issues
ruff check --fix src tests 2>/dev/null || true

# Format code
ruff format src tests 2>/dev/null || true

exit 0
