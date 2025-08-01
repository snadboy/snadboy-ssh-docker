# SnadBoy SSH Docker Client

A Python library for managing Docker containers over SSH connections with automatic configuration management.

## Installation

```bash
pip install snadboy-ssh-docker
```

## Features

- **Automatic SSH configuration management**
- **Full Docker operations support** (list, inspect, execute, events)
- **Docker Compose deployment analysis** - Compare compose files with running containers
- **Flexible container filtering** by labels and names
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

### 3. Docker Compose Analysis

Analyze the deployment state of docker-compose.yml files:

```python
# Read compose file
with open("docker-compose.yml", "r") as f:
    compose_content = f.read()

# Analyze deployment state
result = await client.analyze_compose_deployment(
    host="vm-switchboard",
    compose_content=compose_content,
    compose_dir="/path/to/compose/directory"  # Required - determines project name
)

# Check service states
for service_name, service_info in result["services"].items():
    state = service_info["state"]  # running, stopped, mixed, not_deployed
    containers = service_info["containers"]
    print(f"Service {service_name}: {state} ({len(containers)} containers)")

# Check available actions for UI buttons
actions = result["actions_available"]
print(f"Can run 'up': {actions['up']}")
print(f"Can run 'down': {actions['down']}")
print(f"Can run 'restart': {actions['restart']}")
```

### 4. Container Filtering

#### Using Filter Shortcuts (Recommended)

```python
# Filter containers using uppercase shortcuts - much cleaner!
containers = await client.list_containers(
    host="vm-switchboard",
    filters={"SERVICE": "web", "STATUS": "running"}
)

# Mix shortcuts with regular filters
containers = await client.list_containers(
    host="vm-switchboard", 
    filters={"PROJECT": "myapp", "NAME": "frontend"}
)

# Available shortcuts:
# Docker Compose: SERVICE, PROJECT, COMPOSE_FILE
# Common Docker: STATUS, IMAGE, NETWORK, VOLUME  
# Names: NAME, ID
```

#### Using Raw Docker Filters

```python
# Traditional Docker filter syntax still supported
containers = await client.list_containers(
    host="vm-switchboard",
    filters={"label": "com.docker.compose.service=web"}
)

# Filter by name pattern
containers = await client.list_containers(
    host="vm-switchboard", 
    filters={"name": "myapp"}
)
```

### 5. Synchronous API

```python
# For non-async code
containers = client.list_containers_sync("vm-switchboard")
info = client.inspect_container_sync("vm-switchboard", "container_id")
```

## Use Cases

### Docker Compose File Editor/UI

Perfect for building UIs that edit docker-compose.yml files and need to show deployment status:

```python
async def update_ui_buttons(compose_content, host, compose_dir):
    """Update UI buttons based on current deployment state."""
    
    result = await client.analyze_compose_deployment(
        host=host,
        compose_content=compose_content,
        compose_dir=compose_dir  # Directory where compose file is located
    )
    
    # Enable/disable action buttons
    actions = result["actions_available"]
    ui.up_button.enabled = actions["up"]
    ui.down_button.enabled = actions["down"] 
    ui.restart_button.enabled = actions["restart"]
    ui.start_button.enabled = actions["start"]
    ui.stop_button.enabled = actions["stop"]
    
    # Show service status indicators
    for service_name, service_info in result["services"].items():
        status_indicator = ui.get_service_indicator(service_name)
        
        if service_info["state"] == "running":
            status_indicator.set_color("green")
            status_indicator.set_tooltip(f"{len(service_info['containers'])} containers running")
        elif service_info["state"] == "stopped":
            status_indicator.set_color("red")
            status_indicator.set_tooltip("Containers stopped")
        elif service_info["state"] == "mixed":
            status_indicator.set_color("yellow") 
            status_indicator.set_tooltip("Some containers running, some stopped")
        else:  # not_deployed
            status_indicator.set_color("gray")
            status_indicator.set_tooltip("Not deployed")

# Call whenever compose file is modified or on page load
await update_ui_buttons(editor.get_content(), selected_host, compose_directory)
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

**Core Docker Operations:**
- `from_config(config_file)` - Create client from YAML config
- `list_containers(host, all_containers=False, filters=None)` - List containers with optional filtering (supports shortcuts!)
- `list_containers_sync(host, all_containers=False, filters=None)` - Sync version
- `inspect_container(host, container_id)` - Get container details
- `inspect_container_sync(host, container_id)` - Sync version
- `execute(command, host, timeout=None)` - Execute arbitrary Docker command
- `docker_events(host, filters=None)` - Stream Docker events

**Docker Compose Analysis:**
- `analyze_compose_deployment(host, compose_content, compose_dir)` - Analyze compose deployment state

### Filter Shortcuts Reference

| Shortcut | Expands To | Description |
|----------|------------|-------------|
| `SERVICE` | `label: "com.docker.compose.service=value"` | Docker Compose service name |
| `PROJECT` | `label: "com.docker.compose.project=value"` | Docker Compose project name |
| `COMPOSE_FILE` | `label: "com.docker.compose.config-file=value"` | Docker Compose config file |
| `STATUS` | `status: "value"` | Container status (running, exited, etc.) |
| `IMAGE` | `ancestor: "value"` | Container image |
| `NETWORK` | `network: "value"` | Docker network |
| `VOLUME` | `volume: "value"` | Docker volume |
| `NAME` | `name: "value"` | Container name pattern |
| `ID` | `id: "value"` | Container ID |

**Usage Examples:**
```python
# Before (verbose)
filters = {"label": "com.docker.compose.service=web", "status": "running"}

# After (with shortcuts)
filters = {"SERVICE": "web", "STATUS": "running"}
```

**Important Notes:**
- Shortcuts must be UPPERCASE to be expanded
- Shortcuts that expand to the same key will overwrite each other
- Mix shortcuts with regular filters, but avoid conflicts (e.g., don't use both `SERVICE` and `label` keys)
- Lowercase and mixed-case keys are treated as regular Docker filters

#### analyze_compose_deployment() Response

```python
{
    "services": {
        "service_name": {
            "defined": True,
            "config": {...},           # Service configuration from compose file
            "containers": [...],       # List of matching containers (max 1)
            "state": "running"         # running|stopped|not_deployed
        }
    },
    "project_name": "myproject",              # Project name derived from compose_dir
    "actions_available": {
        "up": True,        # Always available (docker-compose up is idempotent)
        "down": True,      # Some services running
        "restart": True,   # Some services running  
        "start": False,    # All already running or not deployed
        "stop": True       # Some services running
    }
}
```

**Important Notes about analyze_compose_deployment():**
- **Requires `compose_dir`**: Used to determine the project name from directory basename
- **Uses Docker's default naming**: Looks for containers named `{project}_{service}_1`
- **Single instance only**: Only finds the first instance (`_1`) of each service
- **Supports `container_name`**: If specified in compose file, uses that exact name
- **No scaling support**: Scaled services (`_2`, `_3`, etc.) are not detected
- **No `-p` flag support**: Only works with default project names
- **`up` is always available**: Since `docker-compose up` is idempotent and safe to run repeatedly

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
# Run all tests
pytest

# Run only unit tests  
pytest tests/unit/

# Run with coverage
pytest --cov=src/snadboy_ssh_docker --cov-report=html
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