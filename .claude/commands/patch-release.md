---
description: Quick patch release - auto-increment patch version and publish
allowed-tools: Bash(*), Read(*), Edit(*), TodoWrite(*)
---

# Quick Patch Release

Automatically increment the patch version and complete the full release process:

1. **Auto-increment patch version** (e.g., 0.2.1 → 0.2.2)
2. **Run all tests** to ensure everything works
3. **Commit changes** with auto-generated message
4. **Push to GitHub**
5. **Build and publish to PyPI**

This is perfect for bug fixes and small improvements that don't change the API.

## What gets released
- All current uncommitted changes
- Automatic patch version bump
- Standard commit message format

## Safety checks
- Verify tests pass
- Confirm working directory state
- Check PyPI credentials

Use this for quick iterations and hotfixes!