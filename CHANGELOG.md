# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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