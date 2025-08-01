# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2025-07-27

### Added
- **Filter Shortcuts**: New uppercase key shortcuts for common Docker filters
  - `SERVICE`, `PROJECT`, `STATUS`, `IMAGE`, `NETWORK`, `VOLUME`, `NAME`, `ID`
  - Simplifies filtering syntax (e.g., `{"SERVICE": "web"}` instead of `{"label": "com.docker.compose.service=web"}`)
  - Available in `list_containers()` and `docker_events()` methods

### Changed
- **analyze_compose_deployment() redesign**: Now requires `compose_dir` parameter instead of optional `project_name`
  - More predictable behavior aligned with Docker Compose conventions
  - Project name derived from directory basename automatically
  - Simplified to support only single instance containers (`_1`)
- **analyze_compose_deployment() fix**: `up` action is now always available, reflecting Docker Compose's idempotent behavior

### Fixed
- Version inconsistency between pyproject.toml and package version
- Multiple type checking errors and linting issues
- Code formatting applied with black and isort

### Improved
- Documentation updated with filter shortcuts examples and reference table
- Test coverage for new features
- Type annotations and mypy compliance

## [0.1.1] - 2025-07-25

### Fixed
- Removed invalid `asyncio-subprocess` dependency that doesn't exist
- Fixed PyPI installation issues

### Changed
- Updated dependencies to only include required packages: paramiko, pyyaml, pydantic

## [0.1.0] - 2025-07-25

### Added
- Initial release of snadboy-ssh-docker library
- SSH Docker Client with automatic configuration management
- Full Docker operations support (list, inspect, execute, events)
- Async and sync APIs
- YAML-based host configuration with validation
- Connection pooling and error handling
- CLI tool (`snadboy-ssh-docker` command)
- Support for Python 3.8-3.12

### Features
- **SSHDockerClient**: Main client class for managing Docker over SSH
- **Configuration management**: YAML-based hosts configuration
- **Async operations**: Full async support for Docker operations
- **Sync operations**: Synchronous versions for non-async codebases
- **Event streaming**: Real-time Docker events monitoring
- **Connection pooling**: Efficient SSH connection management
- **Error handling**: Comprehensive exception handling with custom exceptions
- **CLI interface**: Command-line tool for common operations

### Documentation
- Complete API documentation
- Configuration examples
- Usage examples for both async and sync APIs
- CLI usage documentation