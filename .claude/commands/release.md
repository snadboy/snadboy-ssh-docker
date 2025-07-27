---
description: Complete release process - update version, commit, push to GitHub, and publish to PyPI
allowed-tools: Bash(*), Read(*), Edit(*), TodoWrite(*)
---

# Complete Release Process

Execute the full release workflow for the snadboy-ssh-docker library:

1. **Update Version**: Bump version in pyproject.toml to $ARGUMENTS (if provided, otherwise prompt for version)
2. **Run Tests**: Ensure all tests pass before releasing
3. **Update Documentation**: Verify README is up to date
4. **Commit & Push**: Create commit and push to GitHub
5. **Build Package**: Create distribution files
6. **Publish to PyPI**: Upload to PyPI using stored credentials

## Version to Release
$ARGUMENTS

## Instructions
- If no version argument provided, determine the next version automatically
- Follow semantic versioning (patch/minor/major)
- Include all recent changes in the commit message
- Verify the release appears on both GitHub and PyPI
- Provide final URLs for verification

## Safety Checks
- Confirm all tests pass before proceeding
- Verify git working directory is clean (except for version bump)
- Check that PyPI credentials are available
- Confirm user wants to proceed with the release

This command automates the entire release pipeline from version bump to PyPI publication.