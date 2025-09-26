"""SSH connection management for Tailscale."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import HostsConfig, load_hosts_config
from .exceptions import SSHConnectionError


class SSHManager:
    """Manages Tailscale SSH connections for Docker hosts."""

    def __init__(self):
        """Initialize SSH manager."""
        self.hosts_config: Optional[HostsConfig] = None

    def setup_from_config(self, config_file: Path) -> None:
        """Load hosts configuration from YAML file.

        Args:
            config_file: Path to hosts.yml configuration file
        """
        self.hosts_config = load_hosts_config(config_file)

    def get_ssh_alias(self, host_alias: str) -> str:
        """Get SSH connection string for a host.

        Args:
            host_alias: Host alias from configuration

        Returns:
            SSH connection string (user@hostname)

        Raises:
            SSHConnectionError: If host not found
        """
        if not self.hosts_config:
            raise SSHConnectionError("No hosts configuration loaded")

        host = self.hosts_config.get_host_config(host_alias)
        return f"{host.user}@{host.hostname}"

    def test_connections(self) -> List[Dict[str, Any]]:
        """Test SSH connections to all enabled hosts.

        Returns:
            List of connection test results
        """
        if not self.hosts_config:
            return []

        results = []
        enabled_hosts = self.hosts_config.get_enabled_hosts()

        for alias, host_config in enabled_hosts.items():
            ssh_alias = f"{host_config.user}@{host_config.hostname}"

            print(f"Testing connection to {host_config.hostname}:{host_config.port}")

            try:
                # Test with a simple command
                result = subprocess.run(
                    ["ssh", ssh_alias, "echo", "OK"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                success = result.returncode == 0 and result.stdout.strip() == "OK"

                results.append({
                    "alias": alias,
                    "ssh_alias": ssh_alias,
                    "port": host_config.port,
                    "connected": success,
                    "error": result.stderr if not success else None,
                })

                if success:
                    print(f"✓ Successfully connected to {host_config.hostname} (Tailscale)")
                else:
                    print(
                        f"✗ Failed to connect to {host_config.hostname}: {result.stderr}"
                    )

            except subprocess.TimeoutExpired:
                results.append({
                    "alias": alias,
                    "ssh_alias": ssh_alias,
                    "port": host_config.port,
                    "connected": False,
                    "error": "Connection timeout",
                })
                print(f"✗ Connection timeout to {host_config.hostname}")
            except Exception as e:
                results.append({
                    "alias": alias,
                    "ssh_alias": ssh_alias,
                    "port": host_config.port,
                    "connected": False,
                    "error": str(e),
                })
                print(f"✗ Error connecting to {host_config.hostname}: {e}")

        return results

    def execute_ssh_command(
        self, host_alias: str, command: str, timeout: int = 30
    ) -> subprocess.CompletedProcess:
        """Execute SSH command on a host.

        Args:
            host_alias: Host alias from configuration
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Completed process result

        Raises:
            SSHConnectionError: If connection fails
        """
        ssh_alias = self.get_ssh_alias(host_alias)

        try:
            result = subprocess.run(
                ["ssh", ssh_alias, command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result
        except subprocess.TimeoutExpired:
            raise SSHConnectionError(f"Command timeout after {timeout} seconds")
        except Exception as e:
            raise SSHConnectionError(f"Failed to execute command: {e}")