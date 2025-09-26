"""Configuration management for SSH Docker Client."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel, ValidationError, field_validator

from .exceptions import ConfigurationError
from .models import HostConfig, HostDefaults


class HostsConfig(BaseModel):
    """Hosts configuration container."""

    hosts: Dict[str, HostConfig] = {}
    defaults: Optional[HostDefaults] = None

    @field_validator("hosts")
    def validate_hosts(cls, v: Dict[str, HostConfig]) -> Dict[str, HostConfig]:
        """Validate hosts dictionary."""
        if not isinstance(v, dict):
            raise ValueError("Hosts must be a dictionary")

        if not v:
            raise ValueError("At least one host must be configured")

        # Validate host aliases
        for alias in v.keys():
            if not isinstance(alias, str) or not alias:
                raise ValueError("Host alias must be a non-empty string")

            # Check for valid alias format
            alias_regex = r"^[a-zA-Z0-9_\-]+$"
            if not re.match(alias_regex, alias):
                raise ValueError(f"Host alias '{alias}' contains invalid characters")

        return v

    def get_host_config(self, alias: str) -> HostConfig:
        """Get host configuration with defaults applied."""
        if alias not in self.hosts:
            raise ValueError(f"Host '{alias}' not found in configuration")

        host = self.hosts[alias]

        # Apply defaults if they exist
        if self.defaults:
            # Create a new HostConfig with defaults applied where needed
            config_dict = host.model_dump()
            defaults_dict = self.defaults.model_dump()

            # Apply defaults only for fields that weren't explicitly set
            for field, default_value in defaults_dict.items():
                if field not in config_dict or config_dict[field] is None:
                    config_dict[field] = default_value

            return HostConfig(**config_dict)

        return host

    def get_enabled_hosts(self) -> Dict[str, HostConfig]:
        """Get only enabled hosts with defaults applied."""
        enabled_hosts = {}
        for alias, host in self.hosts.items():
            config = self.get_host_config(alias)
            if config.enabled:
                enabled_hosts[alias] = config
        return enabled_hosts

    def to_docker_hosts_format(self) -> List[Tuple[str, str, int]]:
        """Convert to legacy Docker hosts format for backward compatibility.

        Returns list of (alias, hostname, port) tuples.
        """
        hosts = []
        for alias, host_config in self.get_enabled_hosts().items():
            # Create SSH alias for the host
            ssh_alias = host_config.get_ssh_alias()
            hosts.append((ssh_alias, host_config.hostname, host_config.port))
        return hosts

    def get_host_by_hostname(self, hostname: str) -> Optional[Tuple[str, HostConfig]]:
        """Find host by hostname.

        Returns tuple of (alias, HostConfig) or None if not found.
        """
        for alias, host in self.hosts.items():
            if host.hostname == hostname:
                return (alias, self.get_host_config(alias))
        return None


def load_hosts_config(config_file: Path) -> HostsConfig:
    """Load hosts configuration from YAML file.

    Args:
        config_file: Path to hosts.yml configuration file

    Returns:
        Loaded and validated hosts configuration

    Raises:
        ConfigurationError: If configuration is invalid
    """
    # Ensure config file exists
    if not config_file.exists():
        raise ConfigurationError(f"Configuration file not found: {config_file}")

    # Load YAML
    try:
        with open(config_file, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Failed to parse YAML: {e}")

    # Validate data structure
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration must be a dictionary")

    # Process hosts
    hosts_data = data.get("hosts", {})
    if not hosts_data:
        raise ConfigurationError("No hosts defined in configuration")

    # Process defaults if present
    defaults_data = data.get("defaults", {})
    if defaults_data:
        # Apply common defaults to hosts that don't have explicit values
        for host_alias, host_config in hosts_data.items():
            if isinstance(host_config, dict):
                # Apply defaults for missing fields
                for key, value in defaults_data.items():
                    if key not in host_config:
                        host_config[key] = value

    # Create and validate configuration
    try:
        hosts_config = HostsConfig(**data)
    except ValidationError as e:
        raise ConfigurationError(f"Invalid configuration: {e}")

    return hosts_config


def save_hosts_config(config: HostsConfig, config_file: Path) -> None:
    """Save hosts configuration to YAML file.

    Args:
        config: Hosts configuration to save
        config_file: Path to save configuration to
    """
    # Convert to dictionary
    config_dict = config.model_dump(exclude_none=True)

    # Write YAML
    with open(config_file, "w") as f:
        yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)


def create_example_config(output_file: Path) -> None:
    """Create an example hosts configuration file.

    Args:
        output_file: Path to write example configuration to
    """
    example_config = """# SSH Docker Client Configuration
# This file defines Docker hosts accessible via Tailscale SSH

# Default values for all hosts (can be overridden per host)
defaults:
  user: deploy
  port: 22
  enabled: true

# Host definitions
hosts:
  # Tailscale host using MagicDNS name
  prod:
    hostname: prod.tail-scale.ts.net
    description: "Production Docker host"

  # Tailscale host with custom settings
  staging:
    hostname: staging.tail-scale.ts.net
    user: docker-admin   # Override default user
    port: 2222          # Custom SSH port
    description: "Staging environment"

  # Disabled host (temporarily unavailable)
  dev:
    hostname: dev.tail-scale.ts.net
    enabled: false  # Disable this host
    description: "Development environment (currently offline)"

  # Another production server
  prod2:
    hostname: prod2.tail-scale.ts.net
    description: "Secondary production server"
"""

    # Write example configuration
    output_file.write_text(example_config.strip())
    print(f"Example configuration written to: {output_file}")