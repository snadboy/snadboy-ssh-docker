"""Shared fixtures and test configuration for snadboy-ssh-docker tests."""

import asyncio
import pytest
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from snadboy_ssh_docker.config import HostsConfig
from snadboy_ssh_docker.models import HostConfig
from snadboy_ssh_docker.client import SSHDockerClient
from snadboy_ssh_docker.ssh_manager import SSHManager
from snadboy_ssh_docker.connection import ConnectionPool
from snadboy_ssh_docker.models import ContainerInfo


@pytest.fixture
def test_hosts_config() -> HostsConfig:
    """Create a sample hosts configuration for testing."""
    return HostsConfig(
        hosts={
            "test-host": HostConfig(
                hostname="test.example.com",
                port=22,
                user="testuser",
                key_file="~/.ssh/id_rsa"
            ),
            "test-host-2": HostConfig(
                hostname="test2.example.com", 
                port=2222,
                user="testuser2",
                key_file="~/.ssh/id_rsa"
            )
        }
    )


@pytest.fixture
def mock_ssh_client():
    """Create a mock SSH client."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.exec_command = AsyncMock()
    return client


@pytest.fixture
def mock_ssh_manager(mock_ssh_client):
    """Create a mock SSH manager."""
    manager = AsyncMock(spec=SSHManager)
    manager.get_connection = AsyncMock(return_value=mock_ssh_client)
    manager.close_connection = AsyncMock()
    manager.close_all_connections = AsyncMock()
    return manager


@pytest.fixture
def mock_connection_pool(test_hosts_config, mock_ssh_manager):
    """Create a mock connection pool."""
    pool = AsyncMock(spec=ConnectionPool)
    pool.get_connection = AsyncMock(return_value=mock_ssh_manager)
    pool.close_connection = AsyncMock()
    pool.close_all_connections = AsyncMock()
    return pool


@pytest.fixture
async def ssh_docker_client(test_hosts_config, mock_connection_pool):
    """Create an SSH Docker client with mocked dependencies."""
    with patch('snadboy_ssh_docker.client.ConnectionPool', return_value=mock_connection_pool):
        client = SSHDockerClient(hosts_config=test_hosts_config)
        yield client
        await client.close()


@pytest.fixture
def sample_docker_ps_output() -> str:
    """Sample docker ps JSON output for testing."""
    return '''[
{
  "Command": "\\"docker-entrypoint.s…\\"",
  "CreatedAt": "2023-01-01 12:00:00 +0000 UTC",
  "ID": "abc123def456",
  "Image": "nginx:latest",
  "Labels": "maintainer=NGINX Docker Maintainers",
  "LocalVolumes": "0",
  "Mounts": "",
  "Names": "test-nginx",
  "Networks": "bridge",
  "Ports": "80/tcp, 0.0.0.0:8080->80/tcp",
  "RunningFor": "2 hours ago",
  "Size": "133MB (virtual 187MB)",
  "State": "running",
  "Status": "Up 2 hours"
},
{
  "Command": "\\"python app.py\\"",
  "CreatedAt": "2023-01-01 11:30:00 +0000 UTC", 
  "ID": "def456ghi789",
  "Image": "python:3.9",
  "Labels": "",
  "LocalVolumes": "1",
  "Mounts": "/app",
  "Names": "test-python-app",
  "Networks": "bridge",
  "Ports": "5000/tcp",
  "RunningFor": "2 hours ago",
  "Size": "45MB (virtual 897MB)",
  "State": "running",
  "Status": "Up 2 hours"
}]'''


@pytest.fixture
def sample_docker_inspect_output() -> str:
    """Sample docker inspect JSON output for testing."""
    return '''[{
    "Id": "abc123def456789",
    "Created": "2023-01-01T12:00:00.000000000Z",
    "Path": "docker-entrypoint.sh",
    "Args": ["nginx", "-g", "daemon off;"],
    "State": {
        "Status": "running",
        "Running": true,
        "Paused": false,
        "Restarting": false,
        "OOMKilled": false,
        "Dead": false,
        "Pid": 12345,
        "ExitCode": 0,
        "Error": "",
        "StartedAt": "2023-01-01T12:00:01.000000000Z",
        "FinishedAt": "0001-01-01T00:00:00Z"
    },
    "Image": "sha256:abcdef123456",
    "ResolvConfPath": "/var/lib/docker/containers/abc123def456/resolv.conf",
    "HostnamePath": "/var/lib/docker/containers/abc123def456/hostname",
    "HostsPath": "/var/lib/docker/containers/abc123def456/hosts",
    "LogPath": "/var/lib/docker/containers/abc123def456/abc123def456-json.log",
    "Name": "/test-nginx",
    "RestartCount": 0,
    "Driver": "overlay2",
    "Platform": "linux",
    "MountLabel": "",
    "ProcessLabel": "",
    "AppArmorProfile": "docker-default",
    "Config": {
        "Hostname": "abc123def456",
        "Domainname": "",
        "User": "",
        "AttachStdin": false,
        "AttachStdout": false,
        "AttachStderr": false,
        "ExposedPorts": {"80/tcp": {}},
        "Tty": false,
        "OpenStdin": false,
        "StdinOnce": false,
        "Env": ["PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"],
        "Cmd": ["nginx", "-g", "daemon off;"],
        "Image": "nginx:latest",
        "Volumes": null,
        "WorkingDir": "",
        "Entrypoint": ["docker-entrypoint.sh"],
        "OnBuild": null,
        "Labels": {"maintainer": "NGINX Docker Maintainers"}
    },
    "NetworkSettings": {
        "Bridge": "",
        "SandboxID": "sandbox123",
        "HairpinMode": false,
        "LinkLocalIPv6Address": "",
        "LinkLocalIPv6PrefixLen": 0,
        "Ports": {
            "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]
        },
        "SandboxKey": "/var/run/docker/netns/sandbox123",
        "SecondaryIPAddresses": null,
        "SecondaryIPv6Addresses": null,
        "EndpointID": "endpoint123",
        "Gateway": "172.17.0.1",
        "GlobalIPv6Address": "",
        "GlobalIPv6PrefixLen": 0,
        "IPAddress": "172.17.0.2",
        "IPPrefixLen": 16,
        "IPv6Gateway": "",
        "MacAddress": "02:42:ac:11:00:02",
        "Networks": {
            "bridge": {
                "IPAMConfig": null,
                "Links": null,
                "Aliases": null,
                "NetworkID": "network123",
                "EndpointID": "endpoint123",
                "Gateway": "172.17.0.1",
                "IPAddress": "172.17.0.2",
                "IPPrefixLen": 16,
                "IPv6Gateway": "",
                "GlobalIPv6Address": "",
                "GlobalIPv6PrefixLen": 0,
                "MacAddress": "02:42:ac:11:00:02",
                "DriverOpts": null
            }
        }
    }
}]'''


@pytest.fixture
def sample_container_info() -> ContainerInfo:
    """Create a sample ContainerInfo object for testing."""
    return ContainerInfo(
        id="abc123def456",
        name="test-nginx",
        image="nginx:latest",
        status="running",
        host="test-host",
        ports={"80/tcp": "0.0.0.0:8080"},
        labels={"maintainer": "NGINX Docker Maintainers"}
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
    key_file: ~/.ssh/id_rsa
    
  test-host-2:
    hostname: test2.example.com
    port: 2222
    user: testuser2
    key_file: ~/.ssh/id_rsa
"""
    
    config_file.write_text(config_content.strip())
    return config_file


@pytest.fixture
def mock_command_result():
    """Create a mock command result tuple."""
    def _create_result(stdout: str = "", stderr: str = "", exit_code: int = 0):
        return MagicMock(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code
        )
    return _create_result