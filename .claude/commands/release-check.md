---
description: Check if the project is ready for release
allowed-tools: Bash(*), Read(*), Grep(*)
---

# Release Readiness Check

Verify that the project is ready for a new release by checking:

## Code Quality
- [ ] All tests pass (`pytest`)
- [ ] No linting errors
- [ ] No type checking errors
- [ ] Code coverage is acceptable

## Git Status
- [ ] Working directory is clean (or only has intended changes)
- [ ] All changes are committed except version bump
- [ ] Current branch is `main`
- [ ] Local is up to date with remote

## Documentation
- [ ] README is up to date
- [ ] API documentation reflects current functionality
- [ ] CHANGELOG updated (if exists)
- [ ] Version number is consistent

## Build System
- [ ] pyproject.toml is valid
- [ ] Build dependencies are available
- [ ] Can build without errors

## PyPI Readiness  
- [ ] PyPI credentials are configured
- [ ] Package builds successfully
- [ ] No conflicting versions

Run this before using `/release` or `/patch-release` to catch issues early!