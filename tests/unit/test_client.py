"""Unit tests for SSHDockerClient."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from snadboy_ssh_docker.client import SSHDockerClient
from snadboy_ssh_docker.exceptions import ConfigurationError, HostNotFoundError, DockerCommandError
from snadboy_ssh_docker.models import ContainerInfo


class TestFilterShortcuts:
    """Test cases for filter shortcut expansion."""

    def test_expand_filter_shortcuts_with_compose_shortcuts(self, test_hosts_config):
        """Test expansion of Docker Compose shortcuts."""
        client = SSHDockerClient(hosts_config=test_hosts_config)
        
        # Test individual shortcuts to avoid dict key conflicts
        filters = {"SERVICE": "web"}
        expanded = client._expand_filter_shortcuts(filters)
        assert expanded == {"label": "com.docker.compose.service=web"}
        
        filters = {"PROJECT": "myapp"}
        expanded = client._expand_filter_shortcuts(filters)
        assert expanded == {"label": "com.docker.compose.project=myapp"}
        
        filters = {"COMPOSE_FILE": "/path/to/compose.yml"}
        expanded = client._expand_filter_shortcuts(filters)
        assert expanded == {"label": "com.docker.compose.config-file=/path/to/compose.yml"}

    def test_expand_filter_shortcuts_with_common_shortcuts(self, test_hosts_config):
        """Test expansion of common Docker shortcuts."""
        client = SSHDockerClient(hosts_config=test_hosts_config)
        
        filters = {
            "STATUS": "running",
            "IMAGE": "nginx",
            "NETWORK": "bridge",
            "VOLUME": "data"
        }
        
        expanded = client._expand_filter_shortcuts(filters)
        
        assert expanded == {
            "status": "running",
            "ancestor": "nginx", 
            "network": "bridge",
            "volume": "data"
        }

    def test_expand_filter_shortcuts_with_name_shortcuts(self, test_hosts_config):
        """Test expansion of name shortcuts."""
        client = SSHDockerClient(hosts_config=test_hosts_config)
        
        filters = {
            "NAME": "web-container",
            "ID": "abc123"
        }
        
        expanded = client._expand_filter_shortcuts(filters)
        
        assert expanded == {
            "name": "web-container",
            "id": "abc123"
        }

    def test_expand_filter_shortcuts_preserves_lowercase(self, test_hosts_config):
        """Test that lowercase keys are preserved unchanged."""
        client = SSHDockerClient(hosts_config=test_hosts_config)
        
        filters = {
            "name": "existing-filter",
            "STATUS": "running"  # This should be expanded
        }
        
        expanded = client._expand_filter_shortcuts(filters)
        
        assert expanded == {
            "status": "running",
            "name": "existing-filter"
        }

    def test_expand_filter_shortcuts_mixed_case_ignored(self, test_hosts_config):
        """Test that mixed case keys are treated as regular filters."""
        client = SSHDockerClient(hosts_config=test_hosts_config)
        
        filters = {
            "Service": "web",  # Mixed case - should not expand
            "service": "api"   # Lowercase - should not expand
        }
        
        expanded = client._expand_filter_shortcuts(filters)
        
        assert expanded == {
            "Service": "web",
            "service": "api"
        }

    def test_expand_filter_shortcuts_none_input(self, test_hosts_config):
        """Test that None input returns None."""
        client = SSHDockerClient(hosts_config=test_hosts_config)
        
        expanded = client._expand_filter_shortcuts(None)
        
        assert expanded is None

    def test_expand_filter_shortcuts_empty_dict(self, test_hosts_config):
        """Test that empty dict returns empty dict."""
        client = SSHDockerClient(hosts_config=test_hosts_config)
        
        expanded = client._expand_filter_shortcuts({})
        
        assert expanded == {}


class TestSSHDockerClient:
    """Test cases for SSHDockerClient class."""

    def test_init_with_config_file(self, temp_config_file):
        """Test client initialization with config file."""
        client = SSHDockerClient(config_file=temp_config_file)
        assert client.hosts_config is not None
        assert "test-host" in client.hosts_config.hosts
        assert "test-host-2" in client.hosts_config.hosts

    def test_init_with_hosts_config(self, test_hosts_config):
        """Test client initialization with hosts config object."""
        client = SSHDockerClient(hosts_config=test_hosts_config)
        assert client.hosts_config == test_hosts_config

    def test_init_without_config_raises_error(self):
        """Test that initialization without config raises ConfigurationError."""
        with pytest.raises(ConfigurationError):
            SSHDockerClient()

    def test_from_config_classmethod(self, temp_config_file):
        """Test creating client from config file using classmethod."""
        client = SSHDockerClient.from_config(temp_config_file)
        assert client.hosts_config is not None
        assert "test-host" in client.hosts_config.hosts

    def test_setup_ssh(self, ssh_docker_client):
        """Test client SSH setup."""
        ssh_docker_client.setup_ssh()
        assert ssh_docker_client._setup_complete

    @pytest.mark.asyncio
    async def test_close(self, ssh_docker_client, mock_connection_pool):
        """Test client close."""
        await ssh_docker_client.close()
        mock_connection_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_containers_success(self, ssh_docker_client, mock_connection_pool, sample_docker_ps_output):
        """Test successful container listing."""
        mock_connection_pool.execute_docker_command = AsyncMock(return_value=sample_docker_ps_output)

        containers = await ssh_docker_client.list_containers("test-host")
        
        assert len(containers) == 2
        assert containers[0]['host'] == "test-host"
        assert 'host_info' in containers[0]

    @pytest.mark.asyncio
    async def test_list_containers_host_not_found(self, ssh_docker_client, mock_connection_pool):
        """Test listing containers for non-existent host."""
        from snadboy_ssh_docker.exceptions import HostNotFoundError
        mock_connection_pool.execute_docker_command = AsyncMock(side_effect=HostNotFoundError("Host not found"))
        
        # The client prints the error and continues, doesn't raise
        containers = await ssh_docker_client.list_containers("non-existent-host")
        assert containers == []

    @pytest.mark.asyncio
    async def test_list_containers_docker_error(self, ssh_docker_client, mock_connection_pool):
        """Test listing containers when Docker command fails."""
        from snadboy_ssh_docker.exceptions import DockerCommandError
        mock_connection_pool.execute_docker_command = AsyncMock(side_effect=DockerCommandError("Docker daemon not running"))

        # The client prints the error and continues, doesn't raise
        containers = await ssh_docker_client.list_containers("test-host")
        assert containers == []

    @pytest.mark.asyncio
    async def test_inspect_container_success(self, ssh_docker_client, mock_connection_pool, sample_docker_inspect_output):
        """Test successful container inspection."""
        mock_connection_pool.execute_docker_command = AsyncMock(return_value=sample_docker_inspect_output)

        container = await ssh_docker_client.inspect_container("test-host", "abc123def456")
        
        assert container is not None
        assert isinstance(container, dict)

    @pytest.mark.asyncio
    async def test_execute_success(self, ssh_docker_client, mock_connection_pool):
        """Test successful Docker command execution."""
        mock_connection_pool.execute_docker_command = AsyncMock(return_value="Hello World")

        result = await ssh_docker_client.execute("echo 'Hello World'", "test-host")
        
        assert result == "Hello World"
        mock_connection_pool.execute_docker_command.assert_called_once_with(
            "test-host", "echo 'Hello World'", timeout=None
        )

    @pytest.mark.asyncio
    async def test_context_manager(self, test_hosts_config):
        """Test client as context manager."""
        with patch('snadboy_ssh_docker.client.ConnectionPool') as mock_pool_class:
            mock_pool = AsyncMock()
            mock_pool_class.return_value = mock_pool
            
            async with SSHDockerClient(hosts_config=test_hosts_config) as client:
                assert client._setup_complete
                
            mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_containers_all_hosts(self, ssh_docker_client, mock_connection_pool, sample_docker_ps_output):
        """Test listing containers from all hosts (host=None)."""
        mock_connection_pool.execute_docker_command = AsyncMock(return_value=sample_docker_ps_output)

        containers = await ssh_docker_client.list_containers()  # host=None means all hosts
        
        # Should get containers from both enabled hosts
        assert len(containers) >= 2  # At least 2 containers per host
        # All containers should have host info
        for container in containers:
            assert 'host' in container
            assert 'host_info' in container

    @pytest.mark.asyncio
    async def test_list_containers_with_all_flag(self, ssh_docker_client, mock_connection_pool, sample_docker_ps_output):
        """Test listing containers with all_containers flag."""
        mock_connection_pool.execute_docker_command = AsyncMock(return_value=sample_docker_ps_output)

        containers = await ssh_docker_client.list_containers("test-host", all_containers=True)
        
        # Should call docker ps with -a flag
        mock_connection_pool.execute_docker_command.assert_called_once()
        call_args = mock_connection_pool.execute_docker_command.call_args[0]
        assert "ps --format '{{json .}}' -a" in call_args[1]

    @pytest.mark.asyncio
    async def test_list_containers_with_filters(self, ssh_docker_client, mock_connection_pool, sample_docker_ps_output):
        """Test listing containers with filters."""
        mock_connection_pool.execute_docker_command = AsyncMock(return_value=sample_docker_ps_output)

        filters = {
            "label": "com.docker.compose.service=web",
            "name": "myapp"
        }
        
        containers = await ssh_docker_client.list_containers("test-host", filters=filters)
        
        # Should call docker ps with filter flags
        mock_connection_pool.execute_docker_command.assert_called_once()
        call_args = mock_connection_pool.execute_docker_command.call_args[0]
        command = call_args[1]
        
        assert '--filter "label=com.docker.compose.service=web"' in command
        assert '--filter "name=myapp"' in command

    @pytest.mark.asyncio
    async def test_list_containers_with_shortcuts(self, ssh_docker_client, mock_connection_pool, sample_docker_ps_output):
        """Test listing containers with filter shortcuts."""
        mock_connection_pool.execute_docker_command = AsyncMock(return_value=sample_docker_ps_output)
        filters = {
            "SERVICE": "web",
            "STATUS": "running"
        }
        
        containers = await ssh_docker_client.list_containers("test-host", filters=filters)
        
        # Should call docker ps with expanded filter flags
        mock_connection_pool.execute_docker_command.assert_called_once()
        call_args = mock_connection_pool.execute_docker_command.call_args[0]
        command = call_args[1]
        
        assert '--filter "label=com.docker.compose.service=web"' in command
        assert '--filter "status=running"' in command
        
        assert len(containers) >= 1
        assert containers[0]['host'] == 'test-host'

    @pytest.mark.asyncio
    async def test_analyze_compose_deployment_no_containers(self, ssh_docker_client, mock_connection_pool):
        """Test analyzing compose deployment with no containers running."""
        compose_content = """
version: '3'
services:
  web:
    image: nginx:latest
  api:
    image: myapp:latest
  db:
    image: postgres:13
"""
        # Mock empty container lists
        mock_connection_pool.execute_docker_command = AsyncMock(return_value="[]")
        
        result = await ssh_docker_client.analyze_compose_deployment(
            host="test-host",
            compose_content=compose_content,
            compose_dir="/home/user/myproject"
        )
        
        # Check structure
        assert "services" in result
        assert "project_name" in result
        assert "actions_available" in result
        assert result["project_name"] == "myproject"
        
        # All services should be not_deployed
        assert len(result["services"]) == 3
        for service_name in ["web", "api", "db"]:
            assert service_name in result["services"]
            assert result["services"][service_name]["state"] == "not_deployed"
            assert result["services"][service_name]["containers"] == []
        
        # Only 'up' action should be available for non-deployed containers
        assert result["actions_available"]["up"] is True
        assert result["actions_available"]["down"] is False
        assert result["actions_available"]["restart"] is False
        assert result["actions_available"]["start"] is False
        assert result["actions_available"]["stop"] is False

    @pytest.mark.asyncio
    async def test_analyze_compose_deployment_all_running(self, ssh_docker_client, mock_connection_pool):
        """Test analyzing compose deployment with all containers running."""
        compose_content = """
version: '3'
services:
  web:
    image: nginx:latest
  api:
    image: myapp:latest
"""
        # Mock containers with compose labels
        all_containers = [
            {
                "ID": "abc123",
                "Names": "myproject_web_1",
                "State": "running",
                "Labels": {
                    "com.docker.compose.project": "myproject",
                    "com.docker.compose.service": "web"
                }
            },
            {
                "ID": "def456",
                "Names": "myproject_api_1", 
                "State": "running",
                "Labels": {
                    "com.docker.compose.project": "myproject",
                    "com.docker.compose.service": "api"
                }
            }
        ]
        
        # Mock returns containers based on the name filter
        def mock_response(host, command):
            if 'myproject_web_1' in command:
                return json.dumps([all_containers[0]])  # web container
            elif 'myproject_api_1' in command:
                return json.dumps([all_containers[1]])  # api container
            else:
                return json.dumps([])  # no containers for other services
        
        mock_connection_pool.execute_docker_command = AsyncMock(side_effect=mock_response)
        
        result = await ssh_docker_client.analyze_compose_deployment(
            host="test-host",
            compose_content=compose_content,
            compose_dir="/home/user/myproject"
        )
        
        # Check project name
        assert result["project_name"] == "myproject"
        
        # All services should be running
        assert result["services"]["web"]["state"] == "running"
        assert result["services"]["api"]["state"] == "running"
        # Check that each service found its container
        web_containers = result["services"]["web"]["containers"]
        api_containers = result["services"]["api"]["containers"]
        assert len(web_containers) == 1
        assert len(api_containers) == 1
        # Verify containers were found
        assert web_containers[0]["Names"] == "myproject_web_1"
        assert api_containers[0]["Names"] == "myproject_api_1"
        
        # Actions available when all running
        assert result["actions_available"]["up"] is True  # 'up' is always available (idempotent)
        assert result["actions_available"]["down"] is True
        assert result["actions_available"]["restart"] is True
        assert result["actions_available"]["start"] is False
        assert result["actions_available"]["stop"] is True

    @pytest.mark.asyncio
    async def test_analyze_compose_deployment_mixed_state(self, ssh_docker_client, mock_connection_pool):
        """Test analyzing compose deployment with mixed container states."""
        compose_content = """
version: '3'
services:
  web:
    image: nginx:latest
  api:
    image: myapp:latest
  db:
    image: postgres:13
"""
        # Mock: web running, api stopped, db not deployed
        all_containers = [
            {
                "ID": "abc123",
                "Names": "myproject_web_1",
                "State": "running",
                "Labels": {
                    "com.docker.compose.project": "myproject",
                    "com.docker.compose.service": "web"
                }
            },
            {
                "ID": "def456",
                "Names": "myproject_api_1", 
                "State": "exited",
                "Labels": {
                    "com.docker.compose.project": "myproject",
                    "com.docker.compose.service": "api"
                }
            }
        ]
        
        def mock_response(host, command):
            # Match specific container names
            if 'myproject_web_1' in command:
                return json.dumps([all_containers[0]])  # web running
            elif 'myproject_api_1' in command:
                return json.dumps([all_containers[1]])  # api stopped  
            elif 'myproject_db_1' in command:
                return json.dumps([])  # db not deployed
            else:
                return json.dumps([])
        
        mock_connection_pool.execute_docker_command = AsyncMock(side_effect=mock_response)
        
        result = await ssh_docker_client.analyze_compose_deployment(
            host="test-host",
            compose_content=compose_content,
            compose_dir="/home/user/myproject"
        )
        
        # Check service states
        assert result["services"]["web"]["state"] == "running"
        assert result["services"]["api"]["state"] == "stopped"
        assert result["services"]["db"]["state"] == "not_deployed"
        
        # Mixed state should enable most actions
        assert result["actions_available"]["up"] is True
        assert result["actions_available"]["down"] is True
        assert result["actions_available"]["restart"] is True
        assert result["actions_available"]["stop"] is True
        # Start is only available when ALL deployed containers are stopped
        assert result["actions_available"]["start"] is False

    @pytest.mark.asyncio
    async def test_analyze_compose_deployment_with_container_name(self, ssh_docker_client, mock_connection_pool):
        """Test analyzing compose deployment with explicit container_name."""
        compose_content = """
version: '3'
services:
  web:
    image: nginx:latest
    container_name: my-custom-web
"""
        # Mock returns container when searching by custom name
        def mock_response(host, command):
            if "my-custom-web" in command:
                return json.dumps([{
                    "ID": "abc123",
                    "Names": "my-custom-web",
                    "State": "running",
                    "Labels": {}
                }])
            return "[]"
        
        mock_connection_pool.execute_docker_command = AsyncMock(side_effect=mock_response)
        
        result = await ssh_docker_client.analyze_compose_deployment(
            host="test-host",
            compose_content=compose_content,
            compose_dir="/home/user/myproject"
        )
        
        # Should find the container by explicit name
        assert result["services"]["web"]["state"] == "running"
        assert len(result["services"]["web"]["containers"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_compose_deployment_directory_name_cleaning(self, ssh_docker_client, mock_connection_pool):
        """Test that directory names are cleaned properly for project names."""
        compose_content = """
version: '3'
services:
  web:
    image: nginx:latest
"""
        mock_connection_pool.execute_docker_command = AsyncMock(return_value="[]")
        
        # Test with directory that needs cleaning
        result = await ssh_docker_client.analyze_compose_deployment(
            host="test-host",
            compose_content=compose_content,
            compose_dir="/home/user/My-Project.2024"
        )
        
        # Should clean to lowercase alphanumeric with dash/underscore
        assert result["project_name"] == "my-project2024"

    @pytest.mark.asyncio
    async def test_analyze_compose_deployment_invalid_compose_dir(self, ssh_docker_client, mock_connection_pool):
        """Test that invalid compose_dir raises ValueError."""
        compose_content = """
version: '3'
services:
  web:
    image: nginx:latest
"""
        
        # Test with empty compose_dir
        with pytest.raises(ValueError, match="compose_dir is required"):
            await ssh_docker_client.analyze_compose_deployment(
                host="test-host",
                compose_content=compose_content,
                compose_dir=""
            )

    @pytest.mark.asyncio 
    async def test_analyze_compose_deployment_invalid_yaml(self, ssh_docker_client, mock_connection_pool):
        """Test analyzing invalid compose file raises ValueError."""
        compose_content = """
services:
  web: [invalid yaml structure
"""
        
        with pytest.raises(ValueError, match="Failed to parse compose file"):
            await ssh_docker_client.analyze_compose_deployment(
                host="test-host",
                compose_content=compose_content,
                compose_dir="/home/user/myproject"
            )