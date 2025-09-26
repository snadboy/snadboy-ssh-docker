"""Data models for SSH Docker client."""

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, field_validator


class HostConfig(BaseModel):
    """Individual host configuration for Tailscale SSH."""

    hostname: str
    user: str
    port: int = 22
    description: str = ""
    enabled: bool = True

    @field_validator("hostname")
    def validate_hostname(cls, v: str) -> str:
        """Validate hostname format."""
        if not v or not isinstance(v, str):
            raise ValueError("Hostname must be a non-empty string")

        v = v.strip()

        # Basic hostname validation
        if len(v) > 253:
            raise ValueError("Hostname must be 253 characters or less")

        # Check for valid hostname format
        hostname_regex = r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$"
        if not re.match(hostname_regex, v):
            raise ValueError(f"Hostname '{v}' contains invalid characters")

        return v

    @field_validator("user")
    def validate_user(cls, v: str) -> str:
        """Validate username format."""
        if not v or not isinstance(v, str):
            raise ValueError("User must be a non-empty string")

        v = v.strip()

        # Basic username validation
        if len(v) > 32:
            raise ValueError("Username must be 32 characters or less")

        # Check for valid username format (alphanumeric, underscore, hyphen)
        username_regex = r"^[a-zA-Z0-9_\-]+$"
        if not re.match(username_regex, v):
            raise ValueError(f"Username '{v}' contains invalid characters")

        return v

    @field_validator("port")
    def validate_port(cls, v: int) -> int:
        """Validate port number."""
        if not isinstance(v, int):
            raise ValueError("Port must be an integer")

        if v < 1 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")

        return v

    @field_validator("description")
    def validate_description(cls, v: str) -> str:
        """Validate description field."""
        if v is None:
            return ""
        if not isinstance(v, str):
            raise ValueError("Description must be a string")
        return v.strip()

    def get_ssh_alias(self) -> str:
        """Generate SSH connection string for this host.

        Returns:
            SSH connection string (user@hostname)
        """
        return f"{self.user}@{self.hostname}"


class HostDefaults(BaseModel):
    """Default configuration values for hosts."""

    user: str = "root"
    port: int = 22
    enabled: bool = True

    @field_validator("user")
    def validate_user(cls, v: str) -> str:
        """Validate default username format."""
        if not v or not isinstance(v, str):
            raise ValueError("Default user must be a non-empty string")

        v = v.strip()

        # Basic username validation
        if len(v) > 32:
            raise ValueError("Default username must be 32 characters or less")

        # Check for valid username format (alphanumeric, underscore, hyphen)
        username_regex = r"^[a-zA-Z0-9_\-]+$"
        if not re.match(username_regex, v):
            raise ValueError(f"Default username '{v}' contains invalid characters")

        return v

    @field_validator("port")
    def validate_port(cls, v: int) -> int:
        """Validate default port number."""
        if not isinstance(v, int):
            raise ValueError("Default port must be an integer")

        if v < 1 or v > 65535:
            raise ValueError("Default port must be between 1 and 65535")

        return v


class DockerCommand(BaseModel):
    """Docker command to execute."""

    command: str
    host: Optional[str] = None
    timeout: Optional[int] = None


class DockerContainer(BaseModel):
    """Docker container information."""

    id: str
    name: str
    image: str
    status: str
    created: str
    ports: List[str] = []
    labels: Dict[str, str] = {}


class DockerImage(BaseModel):
    """Docker image information."""

    id: str
    repository: str
    tag: str
    created: str
    size: str


class DockerNetwork(BaseModel):
    """Docker network information."""

    id: str
    name: str
    driver: str
    scope: str
    containers: List[str] = []


class DockerVolume(BaseModel):
    """Docker volume information."""

    name: str
    driver: str
    mountpoint: str
    labels: Dict[str, str] = {}
    scope: str