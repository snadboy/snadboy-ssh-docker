"""SSH Docker Client - A Python library for managing Docker over SSH."""

from .client import SSHDockerClient
from .config import HostsConfig, load_hosts_config
from .exceptions import (
    ConfigurationError,
    DockerCommandError,
    HostNotFoundError,
    SSHConnectionError,
    SSHDockerError,
)
from .models import HostConfig, HostDefaults
from .ssh_manager import SSHManager

__version__ = "0.2.1"
__all__ = [
    "SSHDockerClient",
    "SSHManager",
    "HostsConfig",
    "HostConfig",
    "HostDefaults",
    "load_hosts_config",
    "SSHDockerError",
    "SSHConnectionError",
    "DockerCommandError",
    "HostNotFoundError",
    "ConfigurationError",
]
