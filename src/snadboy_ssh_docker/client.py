"""Main client interface for SSH Docker Client."""

import asyncio
import os
import re
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from .config import HostsConfig, load_hosts_config
from .connection import ConnectionPool
from .exceptions import ConfigurationError, DockerCommandError
from .ssh_manager import SSHManager
from .utils import parse_compose_services, parse_docker_inspect, parse_docker_ps_json


class SSHDockerClient:
    """Client for managing Docker over SSH on remote hosts."""

    def __init__(
        self,
        config_file: Optional[Path] = None,
        hosts_config: Optional[HostsConfig] = None,
    ):
        """Initialize SSH Docker client.

        Args:
            config_file: Path to hosts.yml configuration file
            hosts_config: Pre-loaded hosts configuration

        Raises:
            ConfigurationError: If no configuration provided
        """
        if config_file:
            self.hosts_config = load_hosts_config(config_file)
        elif hosts_config:
            self.hosts_config = hosts_config
        else:
            raise ConfigurationError(
                "Either config_file or hosts_config must be provided"
            )

        self.ssh_manager = SSHManager()
        self.connection_pool = ConnectionPool(self.hosts_config, self.ssh_manager)
        self._setup_complete = False

    @classmethod
    def from_config(cls, config_file: Union[str, Path], **kwargs) -> "SSHDockerClient":
        """Create client from configuration file.

        Args:
            config_file: Path to hosts.yml configuration file
            **kwargs: Additional arguments for client initialization

        Returns:
            SSHDockerClient instance
        """
        return cls(config_file=Path(config_file), **kwargs)

    def setup_ssh(self) -> None:
        """Initialize SSH manager with hosts configuration.

        Since we only use Tailscale, no SSH config generation is needed.
        """
        if self._setup_complete:
            return

        # Pass the hosts config to SSH manager
        self.ssh_manager.hosts_config = self.hosts_config

        # Count enabled hosts for informational output
        enabled_hosts = self.hosts_config.get_enabled_hosts()
        if enabled_hosts:
            print(f"Found {len(enabled_hosts)} Tailscale hosts configured")

        self._setup_complete = True

    async def __aenter__(self) -> "SSHDockerClient":
        """Async context manager entry."""
        self.setup_ssh()
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close all connections."""
        await self.connection_pool.close()

    # Async methods

    def _expand_filter_shortcuts(
        self, filters: Optional[Dict[str, str]]
    ) -> Optional[Dict[str, str]]:
        """Expand uppercase shortcut keys to Docker filter syntax.

        Args:
            filters: Original filters dict with potential shortcuts

        Returns:
            Expanded filters dict with Docker syntax
        """
        if not filters:
            return filters

        # Define shortcut mappings
        shortcuts = {
            # Docker Compose shortcuts
            "SERVICE": lambda v: ("label", f"com.docker.compose.service={v}"),
            "PROJECT": lambda v: ("label", f"com.docker.compose.project={v}"),
            "COMPOSE_FILE": lambda v: ("label", f"com.docker.compose.config-file={v}"),
            # Common Docker shortcuts
            "STATUS": lambda v: ("status", v),
            "IMAGE": lambda v: ("ancestor", v),
            "NETWORK": lambda v: ("network", v),
            "VOLUME": lambda v: ("volume", v),
            # Name shortcuts
            "NAME": lambda v: ("name", v),
            "ID": lambda v: ("id", v),
        }

        expanded = {}

        for key, value in filters.items():
            if key in shortcuts:
                # Expand shortcut
                new_key, new_value = shortcuts[key](value)
                expanded[new_key] = new_value
            else:
                # Keep original filter
                expanded[key] = value

        return expanded

    async def list_containers(
        self,
        host: Optional[str] = None,
        all_containers: bool = False,
        filters: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """List Docker containers.

        Args:
            host: Optional host alias (None for all hosts)
            all_containers: Include stopped containers
            filters: Optional filters to apply (e.g., {"label": "com.docker.compose.service=web"})

        Returns:
            List of container dictionaries
        """
        self.setup_ssh()

        # Expand filter shortcuts
        expanded_filters = self._expand_filter_shortcuts(filters)

        # Build docker ps command
        cmd = "ps --format '{{json .}}'"
        if all_containers:
            cmd += " -a"

        # Add filters
        if expanded_filters:
            for key, value in expanded_filters.items():
                cmd += f' --filter "{key}={value}"'

        containers = []

        # Get containers from specified host or all hosts
        hosts_to_check = (
            [host] if host else list(self.hosts_config.get_enabled_hosts().keys())
        )

        for host_alias in hosts_to_check:
            try:
                output = await self.connection_pool.execute_docker_command(
                    host_alias, cmd
                )

                host_containers = parse_docker_ps_json(output)

                # Add host information
                for container in host_containers:
                    container["host"] = host_alias
                    container["host_info"] = self.hosts_config.get_host_config(
                        host_alias
                    ).model_dump()

                containers.extend(host_containers)

            except Exception as e:
                print(f"Error listing containers on {host_alias}: {e}")
                continue

        return containers

    async def inspect_container(
        self, host: str, container_id: str
    ) -> Optional[Dict[str, Any]]:
        """Inspect a Docker container.

        Args:
            host: Host alias
            container_id: Container ID or name

        Returns:
            Container details or None if not found
        """
        self.setup_ssh()

        try:
            output = await self.connection_pool.execute_docker_command(
                host, f"inspect {container_id}"
            )

            return parse_docker_inspect(output)

        except DockerCommandError as e:
            if "No such object" in str(e):
                return None
            raise

    async def execute(
        self, command: str, host: str, timeout: Optional[int] = None
    ) -> str:
        """Execute arbitrary Docker command.

        Args:
            command: Docker command to execute
            host: Host alias
            timeout: Command timeout in seconds

        Returns:
            Command output
        """
        self.setup_ssh()

        return await self.connection_pool.execute_docker_command(
            host, command, timeout=timeout
        )

    async def docker_events(
        self, host: str, filters: Optional[Dict[str, str]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream Docker events from a host.

        Args:
            host: Host alias
            filters: Optional event filters

        Yields:
            Docker event dictionaries
        """
        self.setup_ssh()

        # Expand filter shortcuts
        expanded_filters = self._expand_filter_shortcuts(filters)

        async for event in self.connection_pool.stream_docker_events(
            host, expanded_filters
        ):
            yield event

    async def analyze_compose_deployment(
        self, host: str, compose_content: str, compose_dir: str
    ) -> Dict[str, Any]:
        """Analyze the deployment state of a compose file.

        Compares services defined in a docker-compose.yml file with actually
        running containers on a remote host. Uses Docker Compose's default
        naming convention based on the directory name.

        Args:
            host: SSH host alias
            compose_content: Content of docker-compose.yml file
            compose_dir: Directory path where the compose file is located
                         (used to determine project name)

        Returns:
            Dictionary containing:
            - project_name: Project name derived from compose_dir
            - services: Service definitions and their container states
            - actions_available: Available docker-compose actions based on state
              (up is always available since docker-compose up is idempotent)

        Raises:
            ValueError: If compose content is invalid or compose_dir is invalid
            HostNotFoundError: If host is not found in configuration
        """
        # Parse compose file to get service definitions
        try:
            services = parse_compose_services(compose_content)
        except ValueError as e:
            raise ValueError(f"Failed to parse compose file: {e}")

        # Derive project name from directory
        if not compose_dir:
            raise ValueError("compose_dir is required")

        project_name = os.path.basename(compose_dir.rstrip("/"))
        # Clean project name to match Docker's rules (lowercase, alphanumeric, dash, underscore)
        project_name = project_name.lower()
        project_name = re.sub(r"[^a-z0-9_-]", "", project_name)

        if not project_name:
            raise ValueError(f"Invalid compose_dir: {compose_dir}")

        # Initialize result structure
        result = {
            "project_name": project_name,
            "services": {},
            "actions_available": {
                "up": False,
                "down": False,
                "restart": False,
                "start": False,
                "stop": False,
            },
        }

        # Track container states
        any_running = False
        any_stopped = False
        any_not_deployed = False

        # Analyze each service
        for service_name, service_config in services.items():
            service_info = {
                "defined": True,
                "config": service_config,
                "containers": [],
                "state": "not_deployed",
            }

            # Look for container matching this service
            if service_config.get("container_name"):
                # Explicit container name specified in compose file
                containers = await self.list_containers(
                    host=host,
                    all_containers=True,
                    filters={"name": service_config["container_name"]},
                )
            else:
                # Default naming pattern: project_service_1
                container_name = f"{project_name}_{service_name}_1"
                containers = await self.list_containers(
                    host=host, all_containers=True, filters={"name": container_name}
                )

            # Should have at most one container with exact name match
            if containers:
                service_info["containers"] = [containers[0]]

                # Determine service state
                if containers[0].get("State", "").lower() == "running":
                    service_info["state"] = "running"
                    any_running = True
                else:
                    service_info["state"] = "stopped"
                    any_stopped = True
            else:
                service_info["state"] = "not_deployed"
                any_not_deployed = True

            result["services"][service_name] = service_info

        # Determine available actions
        # 'up' is always available since docker-compose up is idempotent and safe
        result["actions_available"]["up"] = True
        
        if any_running:
            result["actions_available"]["down"] = True
            result["actions_available"]["restart"] = True
            result["actions_available"]["stop"] = True

        if any_stopped and not any_not_deployed:
            result["actions_available"]["start"] = True

        return result

    # Sync methods

    def list_containers_sync(
        self,
        host: Optional[str] = None,
        all_containers: bool = False,
        filters: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Synchronous version of list_containers."""
        self.setup_ssh()

        # Build docker ps command
        cmd = "ps --format '{{json .}}'"
        if all_containers:
            cmd += " -a"

        # Add filters
        if filters:
            for key, value in filters.items():
                cmd += f' --filter "{key}={value}"'

        containers = []

        # Get containers from specified host or all hosts
        hosts_to_check = (
            [host] if host else list(self.hosts_config.get_enabled_hosts().keys())
        )

        for host_alias in hosts_to_check:
            try:
                output = self.connection_pool.execute_docker_command_sync(
                    host_alias, cmd
                )

                host_containers = parse_docker_ps_json(output)

                # Add host information
                for container in host_containers:
                    container["host"] = host_alias
                    container["host_info"] = self.hosts_config.get_host_config(
                        host_alias
                    ).model_dump()

                containers.extend(host_containers)

            except Exception as e:
                print(f"Error listing containers on {host_alias}: {e}")
                continue

        return containers

    def inspect_container_sync(
        self, host: str, container_id: str
    ) -> Optional[Dict[str, Any]]:
        """Synchronous version of inspect_container."""
        self.setup_ssh()

        try:
            output = self.connection_pool.execute_docker_command_sync(
                host, f"inspect {container_id}"
            )

            return parse_docker_inspect(output)

        except DockerCommandError as e:
            if "No such object" in str(e):
                return None
            raise

    def execute_sync(
        self, command: str, host: str, timeout: Optional[int] = None
    ) -> str:
        """Synchronous version of execute."""
        self.setup_ssh()

        return self.connection_pool.execute_docker_command_sync(
            host, command, timeout=timeout
        )

    # Utility methods

    def test_connections(self) -> Dict[str, Dict[str, Any]]:
        """Test SSH connections to all hosts.

        Returns:
            Connection status for each host
        """
        self.setup_ssh()
        return self.ssh_manager.test_connections()

    def get_hosts(self) -> Dict[str, Any]:
        """Get all configured hosts.

        Returns:
            Dictionary of host configurations
        """
        return {
            alias: config.model_dump()
            for alias, config in self.hosts_config.get_enabled_hosts().items()
        }

    def add_host(self, alias: str, **kwargs) -> None:
        """Add a new host to configuration.

        Args:
            alias: Host alias
            **kwargs: Host configuration parameters
        """
        from .models import HostConfig

        host_config = HostConfig(**kwargs)
        self.hosts_config.hosts[alias] = host_config

        # Regenerate SSH config
        self.ssh_manager.add_host(alias, host_config)
