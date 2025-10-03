"""Connection management for SSH Docker client."""

import asyncio
import json
import shlex
import subprocess
from typing import Any, Dict, Optional

from .config import HostsConfig
from .exceptions import (
    DockerCommandError,
    HostNotFoundError,
    SSHConnectionError,
)
from .ssh_manager import SSHManager


class ConnectionPool:
    """Manages SSH connections to Docker hosts."""

    def __init__(self, hosts_config: HostsConfig, ssh_manager: SSHManager):
        """Initialize connection pool.

        Args:
            hosts_config: Hosts configuration
            ssh_manager: SSH connection manager
        """
        self.hosts_config = hosts_config
        self.ssh_manager = ssh_manager
        self._event_streams: Dict[str, asyncio.subprocess.Process] = {}

    async def execute_docker_command(
        self, host_alias: str, command: str, timeout: int = 30
    ) -> str:
        """Execute a Docker command on a specific host.

        Args:
            host_alias: Host alias from configuration
            command: Docker command to execute
            timeout: Command timeout in seconds

        Returns:
            Command output

        Raises:
            HostNotFoundError: If host not found in configuration
            SSHConnectionError: If SSH connection fails
            DockerCommandError: If Docker command fails
        """
        if host_alias not in self.hosts_config.hosts:
            raise HostNotFoundError(f"Host '{host_alias}' not found in configuration")

        host_config = self.hosts_config.get_host_config(host_alias)

        # Build command based on whether this is a local or remote host
        if not command.strip().startswith("docker"):
            command = f"docker {command}"

        try:
            if host_config.is_local:
                # Localhost: Use docker directly (uses /var/run/docker.sock)
                cmd_parts = shlex.split(command)
                process = await asyncio.create_subprocess_exec(
                    *cmd_parts,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                # Remote: Use docker -H ssh://user@host
                docker_host = f"ssh://{host_config.user}@{host_config.hostname}"
                cmd_parts = shlex.split(command)
                # Insert -H flag after 'docker'
                cmd_parts.insert(1, "-H")
                cmd_parts.insert(2, docker_host)

                process = await asyncio.create_subprocess_exec(
                    *cmd_parts,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            # Wait for command with timeout
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            # Check for errors
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                if not host_config.is_local and ("ssh:" in error_msg.lower() or "connection" in error_msg.lower()):
                    raise SSHConnectionError(f"SSH connection failed: {error_msg}")
                raise DockerCommandError(f"Docker command failed: {error_msg}")

            return stdout.decode().strip()

        except asyncio.TimeoutError:
            if process:
                process.kill()
                await process.wait()
            raise DockerCommandError(f"Command timeout after {timeout} seconds")
        except Exception as e:
            if isinstance(e, (SSHConnectionError, DockerCommandError)):
                raise
            raise SSHConnectionError(f"Failed to execute command: {e}")

    async def execute_docker_command_json(
        self, host_alias: str, command: str, timeout: int = 30
    ) -> Any:
        """Execute a Docker command and parse JSON output.

        Args:
            host_alias: Host alias from configuration
            command: Docker command to execute
            timeout: Command timeout in seconds

        Returns:
            Parsed JSON output

        Raises:
            HostNotFoundError: If host not found in configuration
            SSHConnectionError: If SSH connection fails
            DockerCommandError: If Docker command fails or output is not valid JSON
        """
        output = await self.execute_docker_command(host_alias, command, timeout)

        if not output:
            return []

        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            raise DockerCommandError(f"Failed to parse JSON output: {e}")

    async def start_event_stream(self, host_alias: str) -> None:
        """Start Docker event stream for a host.

        Args:
            host_alias: Host alias from configuration

        Raises:
            HostNotFoundError: If host not found
            SSHConnectionError: If connection fails
        """
        # Stop existing event stream if any
        await self.stop_event_stream(host_alias)

        host_config = self.hosts_config.get_host_config(host_alias)

        # Build docker events command based on host type
        if host_config.is_local:
            # Localhost: docker events --format {{json .}}
            cmd = ["docker", "events", "--format", "{{json .}}"]
        else:
            # Remote: docker -H ssh://user@host events --format {{json .}}
            docker_host = f"ssh://{host_config.user}@{host_config.hostname}"
            cmd = ["docker", "-H", docker_host, "events", "--format", "{{json .}}"]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._event_streams[host_alias] = process

        except Exception as e:
            raise SSHConnectionError(f"Failed to start event stream: {e}")

    async def stop_event_stream(self, host_alias: str) -> None:
        """Stop Docker event stream for a host.

        Args:
            host_alias: Host alias from configuration
        """
        if host_alias in self._event_streams:
            process = self._event_streams[host_alias]
            process.kill()
            await process.wait()
            del self._event_streams[host_alias]

    async def get_event_stream(
        self, host_alias: str
    ) -> Optional[asyncio.subprocess.Process]:
        """Get event stream process for a host.

        Args:
            host_alias: Host alias from configuration

        Returns:
            Event stream process or None
        """
        return self._event_streams.get(host_alias)

    async def cleanup(self) -> None:
        """Clean up all active connections and event streams."""
        # Stop all event streams
        for host_alias in list(self._event_streams.keys()):
            await self.stop_event_stream(host_alias)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    # Synchronous methods for backward compatibility

    def execute_docker_command_sync(
        self, host_alias: str, command: str, timeout: int = 30
    ) -> str:
        """Synchronous version of execute_docker_command.

        Args:
            host_alias: Host alias from configuration
            command: Docker command to execute
            timeout: Command timeout in seconds

        Returns:
            Command output
        """
        # Get host configuration
        host_config = self.hosts_config.get_host_config(host_alias)

        # Build docker command
        docker_cmd = command if command.startswith("docker") else f"docker {command}"
        cmd_parts = shlex.split(docker_cmd)

        # Build command based on host type
        if host_config.is_local:
            # Localhost: docker <args>
            cmd = cmd_parts
        else:
            # Remote: docker -H ssh://user@host <args>
            docker_host = f"ssh://{host_config.user}@{host_config.hostname}"
            cmd_parts.insert(1, "-H")
            cmd_parts.insert(2, docker_host)
            cmd = cmd_parts

        # Execute command
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                if not host_config.is_local and ("ssh:" in error_msg.lower() or "connection" in error_msg.lower()):
                    raise SSHConnectionError(f"SSH connection failed: {error_msg}")
                raise DockerCommandError(f"Docker command failed: {error_msg}")

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise DockerCommandError(f"Command timeout after {timeout} seconds")
        except Exception as e:
            if isinstance(e, (SSHConnectionError, DockerCommandError)):
                raise
            raise SSHConnectionError(f"Failed to execute command: {e}")

    def execute_docker_command_json_sync(
        self, host_alias: str, command: str, timeout: int = 30
    ) -> Any:
        """Synchronous version of execute_docker_command_json.

        Args:
            host_alias: Host alias from configuration
            command: Docker command to execute
            timeout: Command timeout in seconds

        Returns:
            Parsed JSON output
        """
        output = self.execute_docker_command_sync(host_alias, command, timeout)

        if not output:
            return []

        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            raise DockerCommandError(f"Failed to parse JSON output: {e}")