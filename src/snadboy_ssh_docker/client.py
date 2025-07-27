"""Main client interface for SSH Docker Client."""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, AsyncIterator, AsyncContextManager
from contextlib import asynccontextmanager

from .config import HostsConfig, load_hosts_config
from .connection import ConnectionPool
from .exceptions import ConfigurationError, HostNotFoundError, DockerCommandError
from .models import ContainerInfo
from .ssh_manager import SSHManager
from .utils import parse_docker_ps_json, parse_docker_inspect, parse_compose_services


class SSHDockerClient:
    """Client for managing Docker over SSH on remote hosts."""
    
    def __init__(
        self,
        config_file: Optional[Path] = None,
        hosts_config: Optional[HostsConfig] = None,
        ssh_dir: Optional[Path] = None
    ):
        """Initialize SSH Docker client.
        
        Args:
            config_file: Path to hosts.yml configuration file
            hosts_config: Pre-loaded hosts configuration
            ssh_dir: SSH directory path (defaults to ~/.ssh)
            
        Raises:
            ConfigurationError: If no configuration provided
        """
        if config_file:
            self.hosts_config = load_hosts_config(config_file)
        elif hosts_config:
            self.hosts_config = hosts_config
        else:
            raise ConfigurationError("Either config_file or hosts_config must be provided")
        
        self.ssh_manager = SSHManager(ssh_dir=ssh_dir)
        self.connection_pool = ConnectionPool(self.hosts_config, self.ssh_manager)
        self._setup_complete = False
    
    @classmethod
    def from_config(cls, config_file: Union[str, Path], **kwargs) -> 'SSHDockerClient':
        """Create client from configuration file.
        
        Args:
            config_file: Path to hosts.yml configuration file
            **kwargs: Additional arguments for client initialization
            
        Returns:
            SSHDockerClient instance
        """
        return cls(config_file=Path(config_file), **kwargs)
    
    def setup_ssh(self) -> None:
        """Set up SSH configuration for all hosts."""
        if self._setup_complete:
            return
        
        # Pass the hosts config to SSH manager
        self.ssh_manager.hosts_config = self.hosts_config
        self.ssh_manager._ensure_ssh_directory()
        self.ssh_manager._generate_ssh_config()
        self.ssh_manager._validate_ssh_keys()
        
        self._setup_complete = True
    
    async def __aenter__(self) -> 'SSHDockerClient':
        """Async context manager entry."""
        self.setup_ssh()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def close(self) -> None:
        """Close all connections."""
        await self.connection_pool.close()
    
    # Async methods
    
    def _expand_filter_shortcuts(self, filters: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
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
        filters: Optional[Dict[str, str]] = None
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
        hosts_to_check = [host] if host else list(self.hosts_config.get_enabled_hosts().keys())
        
        for host_alias in hosts_to_check:
            try:
                output = await self.connection_pool.execute_docker_command(
                    host_alias, 
                    cmd
                )
                
                host_containers = parse_docker_ps_json(output)
                
                # Add host information
                for container in host_containers:
                    container['host'] = host_alias
                    container['host_info'] = self.hosts_config.get_host_config(host_alias).model_dump()
                
                containers.extend(host_containers)
                
            except Exception as e:
                print(f"Error listing containers on {host_alias}: {e}")
                continue
        
        return containers
    
    async def inspect_container(
        self,
        host: str,
        container_id: str
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
                host,
                f"inspect {container_id}"
            )
            
            return parse_docker_inspect(output)
            
        except DockerCommandError as e:
            if "No such object" in str(e):
                return None
            raise
    
    async def execute(
        self,
        command: str,
        host: str,
        timeout: Optional[int] = None
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
            host,
            command,
            timeout=timeout
        )
    
    async def docker_events(
        self,
        host: str,
        filters: Optional[Dict[str, str]] = None
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
        
        async for event in self.connection_pool.stream_docker_events(host, expanded_filters):
            yield event
    
    async def analyze_compose_deployment(
        self,
        host: str,
        compose_content: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze the deployment state of a compose file.
        
        Compares services defined in a docker-compose.yml file with actually
        running containers on a remote host.
        
        Args:
            host: SSH host alias
            compose_content: Content of docker-compose.yml file
            project_name: Optional project name to filter by. If not provided,
                         will attempt to detect from running containers.
                         
        Returns:
            Dictionary containing:
            - services: Service definitions and their container states
            - detected_project_names: List of detected compose project names
            - actions_available: Available docker-compose actions based on state
            
        Raises:
            ValueError: If compose content is invalid
            HostNotFoundError: If host is not found in configuration
        """
        # Parse compose file to get service definitions
        try:
            services = parse_compose_services(compose_content)
        except ValueError as e:
            raise ValueError(f"Failed to parse compose file: {e}")
        
        # Initialize result structure
        result = {
            "services": {},
            "detected_project_names": [],
            "actions_available": {
                "up": False,
                "down": False,
                "restart": False,
                "start": False,
                "stop": False
            }
        }
        
        # First, detect project names if not provided
        if not project_name:
            # Get all containers with compose labels
            compose_containers = await self.list_containers(
                host=host,
                all_containers=True,
                filters={"label": "com.docker.compose.project"}
            )
            
            # Extract unique project names
            project_names = set()
            for container in compose_containers:
                labels = container.get('Labels', {})
                if 'com.docker.compose.project' in labels:
                    project_names.add(labels['com.docker.compose.project'])
            
            result["detected_project_names"] = list(project_names)
        else:
            result["detected_project_names"] = [project_name]
        
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
                "state": "not_deployed"
            }
            
            # Look for containers matching this service
            matching_containers = []
            
            # Method 1: If project_name is known, use label filters
            if project_name:
                # Note: We need to make two calls since we can't have duplicate keys
                # First get all containers for the project
                project_containers = await self.list_containers(
                    host=host,
                    all_containers=True,
                    filters={"label": f"com.docker.compose.project={project_name}"}
                )
                # Then filter for the specific service
                for container in project_containers:
                    labels = container.get('Labels', {})
                    if labels.get('com.docker.compose.service') == service_name:
                        matching_containers.append(container)
            
            # Method 2: Look for containers by name pattern (only if Method 1 didn't find anything)
            if not matching_containers:
                if service_config.get('container_name'):
                    # Explicit container name
                    containers = await self.list_containers(
                        host=host,
                        all_containers=True,
                        filters={"name": service_config['container_name']}
                    )
                    matching_containers.extend(containers)
                else:
                    # Default naming pattern
                    for detected_project in result["detected_project_names"]:
                        # Try common patterns: project_service_1, project-service-1
                        for separator in ['_', '-']:
                            pattern = f"{detected_project}{separator}{service_name}"
                            containers = await self.list_containers(
                                host=host,
                                all_containers=True,
                                filters={"name": pattern}
                            )
                            matching_containers.extend(containers)
            
            # Deduplicate containers by ID
            seen_ids = set()
            unique_containers = []
            for container in matching_containers:
                if container['ID'] not in seen_ids:
                    seen_ids.add(container['ID'])
                    unique_containers.append(container)
            
            service_info["containers"] = unique_containers
            
            # Determine service state
            if not unique_containers:
                service_info["state"] = "not_deployed"
                any_not_deployed = True
            else:
                running_count = sum(1 for c in unique_containers 
                                  if c.get('State', '').lower() == 'running')
                stopped_count = len(unique_containers) - running_count
                
                if running_count == len(unique_containers):
                    service_info["state"] = "running"
                    any_running = True
                elif stopped_count == len(unique_containers):
                    service_info["state"] = "stopped"
                    any_stopped = True
                else:
                    service_info["state"] = "mixed"
                    any_running = True
                    any_stopped = True
            
            result["services"][service_name] = service_info
        
        # Determine available actions
        if any_running:
            result["actions_available"]["down"] = True
            result["actions_available"]["restart"] = True
            result["actions_available"]["stop"] = True
        
        if any_stopped or any_not_deployed:
            result["actions_available"]["up"] = True
        
        if any_stopped and not any_not_deployed:
            result["actions_available"]["start"] = True
        
        return result
    
    # Sync methods
    
    def list_containers_sync(
        self,
        host: Optional[str] = None,
        all_containers: bool = False,
        filters: Optional[Dict[str, str]] = None
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
        hosts_to_check = [host] if host else list(self.hosts_config.get_enabled_hosts().keys())
        
        for host_alias in hosts_to_check:
            try:
                output = self.connection_pool.execute_docker_command_sync(
                    host_alias,
                    cmd
                )
                
                host_containers = parse_docker_ps_json(output)
                
                # Add host information
                for container in host_containers:
                    container['host'] = host_alias
                    container['host_info'] = self.hosts_config.get_host_config(host_alias).model_dump()
                
                containers.extend(host_containers)
                
            except Exception as e:
                print(f"Error listing containers on {host_alias}: {e}")
                continue
        
        return containers
    
    def inspect_container_sync(
        self,
        host: str,
        container_id: str
    ) -> Optional[Dict[str, Any]]:
        """Synchronous version of inspect_container."""
        self.setup_ssh()
        
        try:
            output = self.connection_pool.execute_docker_command_sync(
                host,
                f"inspect {container_id}"
            )
            
            return parse_docker_inspect(output)
            
        except DockerCommandError as e:
            if "No such object" in str(e):
                return None
            raise
    
    def execute_sync(
        self,
        command: str,
        host: str,
        timeout: Optional[int] = None
    ) -> str:
        """Synchronous version of execute."""
        self.setup_ssh()
        
        return self.connection_pool.execute_docker_command_sync(
            host,
            command,
            timeout=timeout
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