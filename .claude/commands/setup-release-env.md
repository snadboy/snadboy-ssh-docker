---
description: Set up the release environment with all necessary tools
allowed-tools: Bash(*), Read(*)
---

# Setup Release Environment

Prepare the development environment for releasing:

## Install/Update Release Tools
- Install/update `build` package for building distributions
- Install/update `twine` package for PyPI uploads
- Verify `pytest` and testing tools are available

## Verify Credentials
- Check if PyPI API token is configured
- Test PyPI connection (without uploading)
- Verify git configuration for commits

## Environment Check
- Activate virtual environment if needed
- Check Python version compatibility
- Verify all dependencies are installed

## Git Setup
- Ensure git user.name and user.email are set
- Check remote repository configuration
- Verify push permissions to GitHub

Run this once to set up your environment, then use `/release-check` before each release.