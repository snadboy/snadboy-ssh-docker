# snadboy-ssh-docker

A Python library for managing Docker containers across multiple remote hosts using Tailscale SSH.

## Installation

```bash
pip install snadboy-ssh-docker
```

## Features

- **Tailscale SSH support** - Zero-config authentication via Tailscale
- **Full Docker operations support** (list, inspect, execute, events)
- **Docker Compose deployment analysis** - Compare compose files with running containers
- **Flexible container filtering** by labels and names
- **Async and sync APIs** for different use cases
- **Type-safe configuration** with Pydantic models
- **Connection pooling** for efficient resource usage

## Prerequisites

### Tailscale Setup
1. Install Tailscale on all hosts: https://tailscale.com/download
2. Enable SSH in Tailscale: `tailscale up --ssh`
3. Ensure all hosts are on the same Tailnet
4. No SSH keys or config files needed!

## Quick Start

### 1. Configuration File

Create a `hosts.yml` file:

```yaml
hosts:
  # Production server
  prod:
    hostname: prod.tail-scale.ts.net
    username: docker-admin
    description: "Production Docker host"

  # Staging server with custom settings
  staging:
    hostname: staging.tail-scale.ts.net
    username: deploy
    port: 2222          # Custom SSH port
    description: "Staging environment"

defaults:
  username: deploy
  port: 22
  enabled: true
```

### 2. Basic Usage

```python
from snadboy_ssh_docker import SSHDockerClient

# Initialize client
client = SSHDockerClient.from_config("hosts.yml")
client.setup_ssh()

# List containers on a specific host
containers = client.list_containers("prod")
print(f"Found {len(containers)} containers")

# Get container details
for container in containers:
    info = client.inspect_container("prod", container["Id"])
    print(f"Container: {info['Name']} - Status: {info['State']['Status']}")
```

### 3. Async Usage

```python
import asyncio
from snadboy_ssh_docker import SSHDockerClient

async def main():
    client = SSHDockerClient.from_config("hosts.yml")
    client.setup_ssh()

    async with client:
        # List containers asynchronously
        containers = await client.list_containers_async("prod")

        # Execute commands in parallel
        tasks = [
            client.execute_command_async("prod", "ps -a"),
            client.execute_command_async("staging", "images")
        ]
        results = await asyncio.gather(*tasks)

asyncio.run(main())
```

## Docker Operations

### Container Management

```python
# List all containers
containers = client.list_containers("prod")

# List only running containers
running = client.list_containers("prod", filters={"status": "running"})

# Filter by labels
web_containers = client.list_containers("prod", filters={
    "label": ["app=web", "env=production"]
})

# Get detailed container information
container_info = client.inspect_container("prod", "container_id")

# Execute commands in containers
result = client.execute_in_container("prod", "container_id", "ls -la /app")

# Get container logs
logs = client.get_container_logs("prod", "container_id", tail=100)

# Container lifecycle
client.start_container("prod", "container_id")
client.stop_container("prod", "container_id")
client.restart_container("prod", "container_id")
```

### Image Management

```python
# List images
images = client.list_images("prod")

# Pull an image
client.pull_image("prod", "nginx:latest")

# Remove image
client.remove_image("prod", "old-image:tag")
```

### Network Operations

```python
# List networks
networks = client.list_networks("prod")

# Create network
client.create_network("prod", "my-network", driver="bridge")

# Remove network
client.remove_network("prod", "my-network")
```

### Volume Management

```python
# List volumes
volumes = client.list_volumes("prod")

# Create volume
client.create_volume("prod", "my-volume")

# Remove volume
client.remove_volume("prod", "my-volume")
```

## Docker Compose Integration

Compare your compose files with running containers:

```python
from pathlib import Path

# Analyze compose deployment
compose_file = Path("docker-compose.yml")
analysis = client.analyze_compose_deployment("prod", compose_file)

print(f"Services defined: {len(analysis.services)}")
print(f"Missing containers: {len(analysis.missing_containers)}")
print(f"Extra containers: {len(analysis.extra_containers)}")
print(f"Config mismatches: {len(analysis.config_mismatches)}")

# Get detailed mismatch information
for mismatch in analysis.config_mismatches:
    print(f"Service {mismatch.service}: {mismatch.field} differs")
    print(f"  Expected: {mismatch.expected}")
    print(f"  Actual: {mismatch.actual}")
```

## Event Streaming

Monitor Docker events in real-time:

```python
import asyncio

async def monitor_events():
    client = SSHDockerClient.from_config("hosts.yml")
    client.setup_ssh()

    async with client:
        # Start event stream
        await client.start_event_stream("prod")

        # Process events
        async for event in client.get_events("prod"):
            print(f"Event: {event['Action']} on {event['Type']} {event['Actor']['Attributes']['name']}")

asyncio.run(monitor_events())
```

## Advanced Configuration

### Multiple Hosts with Defaults

```yaml
defaults:
  username: deploy
  port: 22
  enabled: true

hosts:
  # Inherits defaults
  prod1:
    hostname: prod1.tail-scale.ts.net
    description: "Primary production server"

  # Override defaults
  prod2:
    hostname: prod2.tail-scale.ts.net
    username: admin      # Different user
    port: 2222          # Different port
    description: "Secondary production server"

  # Disabled host
  maintenance:
    hostname: maint.tail-scale.ts.net
    enabled: false      # Temporarily disabled
```

### Filtering and Searching

```python
# Complex filtering
containers = client.list_containers("prod", filters={
    "status": "running",
    "label": ["env=production", "app=web"],
    "name": "nginx"
})

# Search across multiple hosts
all_containers = []
for host in ["prod", "staging"]:
    containers = client.list_containers(host)
    all_containers.extend(containers)
```

## Synchronous API

For simpler use cases, use the synchronous methods:

```python
# All async methods have sync equivalents with _sync suffix
containers = client.list_containers_sync("prod")
info = client.inspect_container_sync("prod", "container_id")
```

## Use Cases

### Docker Compose File Editor/UI
Build applications that help manage Docker Compose deployments across multiple environments.

### Infrastructure Monitoring
Monitor container health, resource usage, and deployment status across your fleet.

### Automated Deployment
Create deployment scripts that can push updates to multiple Docker hosts.

### Container Orchestration
Build custom orchestration logic for specific use cases.

## Benefits of Tailscale Integration

- **No SSH key management** - Authentication handled by Tailscale
- **Zero-config setup** - Just specify hostname and user
- **Enhanced security** - Leverages Tailscale's encrypted mesh network
- **Simplified deployment** - No need to distribute SSH keys
- **Cross-platform** - Works seamlessly across different operating systems

## Error Handling

The library provides detailed error handling:

```python
from snadboy_ssh_docker.exceptions import (
    SSHConnectionError,
    DockerCommandError,
    HostNotFoundError,
    ConfigurationError
)

try:
    containers = client.list_containers("nonexistent-host")
except HostNotFoundError:
    print("Host not found in configuration")
except SSHConnectionError:
    print("Failed to connect via SSH")
except DockerCommandError:
    print("Docker command failed")
```

## Testing

Run the test suite:

```bash
pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.