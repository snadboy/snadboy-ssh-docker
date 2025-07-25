# SnadBoy SSH Docker Client

A Python library for managing Docker containers over SSH connections with automatic configuration management.

## Package Information

- **Package Name**: `snadboy-ssh-docker`
- **Module Name**: `snadboy_ssh_docker`
- **Version**: Ready for PyPI publication

## Migration Status

This library has been renamed from `ssh_docker_client` to `snadboy_ssh_docker` and is ready for publication to PyPI as `snadboy-ssh-docker`.

## Library Features

- Automatic SSH configuration management
- Full Docker operations support (list, inspect, execute, events)
- Async and sync APIs
- YAML-based host configuration with validation
- Connection pooling and error handling
- CLI tool (`ssh-docker-client` command)

## Integration

The `docker_monitor.py` file uses this library to replace the previous embedded SSH Docker logic, providing:

- Cleaner, more maintainable code
- Better error handling
- Reusable SSH connection management
- Type-safe operations