"""Test fixtures for SSH Docker client."""

import asyncio
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from snadboy_ssh_docker.config import HostsConfig
from snadboy_ssh_docker.models import HostConfig


# Test configuration fixture
@pytest.fixture
def test_hosts_config() -> HostsConfig:
    """Create a test hosts configuration."""
    return HostsConfig(
        hosts={
            "test-host": HostConfig(
                hostname="test.example.com",
                port=22,
                user="testuser"
            ),
            "test-host-2": HostConfig(
                hostname="test2.example.com",
                port=2222,
                user="testuser2"
            ),
            "tailscale-host": HostConfig(
                hostname="myhost.tail-scale.ts.net",
                port=22,
                user="tailscale-user"
            )
        }
    )


@pytest.fixture
def mock_ssh_connection():
    """Mock SSH connection for tests."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "test output"
        mock_run.return_value.stderr = ""
        yield mock_run


@pytest.fixture
def mock_docker_command():
    """Mock Docker command execution."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '{"test": "data"}'
        mock_run.return_value.stderr = ""
        yield mock_run


@pytest.fixture
def mock_async_subprocess():
    """Mock async subprocess for tests."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = asyncio.coroutine(lambda: (b"test output", b""))
        mock_process.wait = asyncio.coroutine(lambda: None)
        mock_exec.return_value = mock_process
        yield mock_exec


# Docker container test data
@pytest.fixture
def docker_container_data():
    """Sample Docker container data."""
    return {
        "Id": "abc123",
        "Names": ["/test-container"],
        "Image": "nginx:latest",
        "State": "running",
        "Status": "Up 2 hours",
        "Created": "2024-01-01T00:00:00Z",
        "Labels": {
            "app": "test",
            "env": "development"
        },
        "Ports": [
            {"PrivatePort": 80, "PublicPort": 8080, "Type": "tcp"}
        ]
    }


@pytest.fixture
def docker_image_data():
    """Sample Docker image data."""
    return {
        "Id": "sha256:xyz789",
        "RepoTags": ["nginx:latest"],
        "Created": "2024-01-01T00:00:00Z",
        "Size": 142000000
    }


@pytest.fixture
def docker_network_data():
    """Sample Docker network data."""
    return {
        "Id": "net123",
        "Name": "bridge",
        "Driver": "bridge",
        "Scope": "local",
        "Containers": {
            "abc123": {
                "Name": "test-container",
                "IPv4Address": "172.17.0.2/16"
            }
        }
    }


@pytest.fixture
def docker_volume_data():
    """Sample Docker volume data."""
    return {
        "Name": "test-volume",
        "Driver": "local",
        "Mountpoint": "/var/lib/docker/volumes/test-volume/_data",
        "Labels": {"env": "test"},
        "Scope": "local"
    }


# Docker Compose test data
@pytest.fixture
def docker_compose_config():
    """Sample Docker Compose configuration."""
    return {
        "version": "3.8",
        "services": {
            "web": {
                "image": "nginx:latest",
                "ports": ["80:80"],
                "labels": {
                    "com.docker.compose.project": "test",
                    "com.docker.compose.service": "web"
                }
            },
            "db": {
                "image": "postgres:13",
                "environment": {
                    "POSTGRES_DB": "test",
                    "POSTGRES_USER": "test"
                },
                "volumes": ["db-data:/var/lib/postgresql/data"],
                "labels": {
                    "com.docker.compose.project": "test",
                    "com.docker.compose.service": "db"
                }
            }
        },
        "volumes": {
            "db-data": {}
        }
    }


# SSH Manager fixtures
@pytest.fixture
def ssh_manager():
    """Create SSH manager instance for tests."""
    from snadboy_ssh_docker.ssh_manager import SSHManager
    return SSHManager()


@pytest.fixture
def connection_pool(test_hosts_config, ssh_manager):
    """Create connection pool for tests."""
    from snadboy_ssh_docker.connection import ConnectionPool
    ssh_manager.hosts_config = test_hosts_config
    return ConnectionPool(test_hosts_config, ssh_manager)


# Client fixtures
@pytest.fixture
def ssh_docker_client(test_hosts_config, mock_ssh_connection):
    """Create SSH Docker client for tests."""
    from snadboy_ssh_docker.client import SSHDockerClient
    return SSHDockerClient(hosts_config=test_hosts_config)


# Async test support
@pytest.fixture
async def async_ssh_docker_client(test_hosts_config, mock_async_subprocess):
    """Create async SSH Docker client for tests."""
    from snadboy_ssh_docker.client import SSHDockerClient
    client = SSHDockerClient(hosts_config=test_hosts_config)
    return client


# Mock Docker responses
@pytest.fixture
def mock_docker_ps_response():
    """Mock docker ps response."""
    return """[
        {
            "Id": "abc123",
            "Names": ["test-container"],
            "Image": "nginx:latest",
            "State": "running",
            "Status": "Up 2 hours"
        }
    ]"""


@pytest.fixture
def mock_docker_images_response():
    """Mock docker images response."""
    return """[
        {
            "Id": "sha256:xyz789",
            "RepoTags": ["nginx:latest"],
            "Created": "2024-01-01T00:00:00Z",
            "Size": 142000000
        }
    ]"""


# Test utilities
@pytest.fixture
def capture_output():
    """Capture stdout/stderr output."""
    import io
    import sys

    captured = {"stdout": "", "stderr": ""}

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()

    yield captured

    captured["stdout"] = sys.stdout.getvalue()
    captured["stderr"] = sys.stderr.getvalue()

    sys.stdout = old_stdout
    sys.stderr = old_stderr


# Event loop configuration for async tests
@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Temporary config file fixture
@pytest.fixture
def temp_config_file(tmp_path, test_hosts_config):
    """Create a temporary config file for testing."""
    config_file = tmp_path / "test_hosts.yml"

    config_content = """
hosts:
  test-host:
    hostname: test.example.com
    port: 22
    user: testuser

  test-host-2:
    hostname: test2.example.com
    port: 2222
    user: testuser2

  tailscale-host:
    hostname: myhost.tail-scale.ts.net
    port: 22
    user: tailscale-user
"""

    config_file.write_text(config_content.strip())
    return config_file