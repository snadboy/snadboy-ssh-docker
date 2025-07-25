# SnadBoy SSH Docker Client

A Python library for managing Docker containers over SSH connections with automatic configuration management.

## Installation

```bash
pip install snadboy-ssh-docker
```

## Features

- **Automatic SSH configuration management**
- **Full Docker operations support** (list, inspect, execute, events)
- **Async and sync APIs**
- **YAML-based host configuration** with validation
- **Connection pooling and error handling**
- **CLI tool** (`snadboy-ssh-docker` command)

## Quick Start

### 1. Configuration

Create a `hosts.yml` file:

```yaml
hosts:
  vm-switchboard:
    hostname: vm-switchboard.snadboy.com
    port: 22
    username: snadboy
    
  local-docker:
    hostname: localhost
    port: 22
    username: docker-user

defaults:
  username: snadboy
  port: 22
  key_file: ~/.ssh/id_rsa
  timeout: 30
```

### 2. Basic Usage

```python
from snadboy_ssh_docker import SSHDockerClient

# Initialize from config file
client = SSHDockerClient.from_config("hosts.yml")

# List containers on a host
containers = await client.list_containers("vm-switchboard")

# Inspect a container
info = await client.inspect_container("vm-switchboard", "container_id")

# Monitor events
async for event in client.docker_events("vm-switchboard"):
    print(f"Event: {event}")
```

### 3. Synchronous API

```python
# For non-async code
containers = client.list_containers_sync("vm-switchboard")
info = client.inspect_container_sync("vm-switchboard", "container_id")
```

## CLI Usage

```bash
# List containers
snadboy-ssh-docker list vm-switchboard

# Inspect container
snadboy-ssh-docker inspect vm-switchboard container_id

# Monitor events
snadboy-ssh-docker events vm-switchboard
```

## API Reference

### SSHDockerClient

#### Methods

- `from_config(config_file)` - Create client from YAML config
- `list_containers(host, all_containers=False)` - List containers
- `list_containers_sync(host, all_containers=False)` - Sync version
- `inspect_container(host, container_id)` - Get container details
- `inspect_container_sync(host, container_id)` - Sync version
- `docker_events(host, filters=None)` - Stream Docker events

### Configuration

The `hosts.yml` file supports:

```yaml
hosts:
  alias:
    hostname: string          # Required
    port: int                 # Default: 22
    username: string          # Required
    key_file: string          # Default: ~/.ssh/id_rsa
    timeout: int              # Default: 30
    enabled: bool             # Default: true

defaults:
  username: string
  port: int
  key_file: string
  timeout: int
```

## Development

### Setup

```bash
git clone https://github.com/snadboy/snadboy-ssh-docker.git
cd snadboy-ssh-docker
pip install -e ".[dev]"
```

### Testing

```bash
pytest
```

### Publishing

```bash
# Bump version in pyproject.toml
python -m build
python -m twine upload dist/*
```

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Used By

This library is used by:
- [Docker RevP](https://github.com/snadboy/docker-revp) - Docker Reverse Proxy with Caddy Integration