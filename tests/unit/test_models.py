"""Unit tests for data models."""

import pytest
from datetime import datetime

from snadboy_ssh_docker.models import ContainerInfo, HostConfig, HostDefaults, DockerCommand


class TestHostConfig:
    """Test cases for HostConfig model."""

    def test_host_config_creation(self):
        """Test creating HostConfig with valid data."""
        config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            port=22,
            key_file="~/.ssh/id_rsa",
            description="Test server",
            enabled=True
        )
        
        assert config.hostname == "test.example.com"
        assert config.user == "testuser"
        assert config.port == 22
        assert config.key_file.endswith("id_rsa")  # Expands ~
        assert config.description == "Test server"
        assert config.enabled is True

    def test_host_config_defaults(self):
        """Test HostConfig default values."""
        config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            key_file="~/.ssh/id_rsa"
        )
        
        assert config.port == 22
        assert config.description == ""
        assert config.enabled is True

    def test_host_config_validation_hostname_empty(self):
        """Test HostConfig validation for empty hostname."""
        with pytest.raises(ValueError, match="Hostname must be a non-empty string"):
            HostConfig(
                hostname="",
                user="testuser",
                key_file="~/.ssh/id_rsa"
            )

    def test_host_config_validation_hostname_too_long(self):
        """Test HostConfig validation for hostname too long."""
        with pytest.raises(ValueError, match="Hostname must be 253 characters or less"):
            HostConfig(
                hostname="a" * 254,
                user="testuser",
                key_file="~/.ssh/id_rsa"
            )

    def test_host_config_validation_hostname_invalid_chars(self):
        """Test HostConfig validation for invalid hostname characters."""
        with pytest.raises(ValueError, match="contains invalid characters"):
            HostConfig(
                hostname="test@example.com",
                user="testuser",
                key_file="~/.ssh/id_rsa"
            )

    def test_host_config_validation_user_empty(self):
        """Test HostConfig validation for empty user."""
        with pytest.raises(ValueError, match="User must be a non-empty string"):
            HostConfig(
                hostname="test.example.com",
                user="",
                key_file="~/.ssh/id_rsa"
            )

    def test_host_config_validation_user_too_long(self):
        """Test HostConfig validation for user too long."""
        with pytest.raises(ValueError, match="Username must be 32 characters or less"):
            HostConfig(
                hostname="test.example.com",
                user="a" * 33,
                key_file="~/.ssh/id_rsa"
            )

    def test_host_config_validation_user_invalid_chars(self):
        """Test HostConfig validation for invalid user characters."""
        with pytest.raises(ValueError, match="contains invalid characters"):
            HostConfig(
                hostname="test.example.com",
                user="test@user",
                key_file="~/.ssh/id_rsa"
            )

    def test_host_config_validation_port_out_of_range(self):
        """Test HostConfig validation for port out of range."""
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=0,
                key_file="~/.ssh/id_rsa"
            )
        
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=65536,
                key_file="~/.ssh/id_rsa"
            )

    def test_host_config_validation_key_file_empty(self):
        """Test HostConfig validation for empty key file."""
        with pytest.raises(ValueError, match="Key file path must be a non-empty string"):
            HostConfig(
                hostname="test.example.com",
                user="testuser",
                key_file=""
            )

    def test_host_config_get_ssh_alias(self):
        """Test generating SSH alias from host config."""
        config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            port=2222,
            key_file="~/.ssh/id_rsa"
        )
        
        alias = config.get_ssh_alias()
        assert alias == "docker-test-example-com-2222"

    def test_host_config_key_file_expansion(self):
        """Test that ~ in key file path gets expanded."""
        config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            key_file="~/custom/key"
        )
        
        assert not config.key_file.startswith("~")
        assert "custom/key" in config.key_file


class TestHostDefaults:
    """Test cases for HostDefaults model."""

    def test_host_defaults_creation(self):
        """Test creating HostDefaults with default values."""
        defaults = HostDefaults()
        
        assert defaults.user == "root"
        assert defaults.port == 22
        assert defaults.key_file.endswith("id_rsa")
        assert defaults.enabled is True

    def test_host_defaults_custom_values(self):
        """Test creating HostDefaults with custom values."""
        defaults = HostDefaults(
            user="custom-user",
            port=2222,
            key_file="~/.ssh/custom_key",
            enabled=False
        )
        
        assert defaults.user == "custom-user"
        assert defaults.port == 2222
        assert defaults.key_file.endswith("custom_key")
        assert defaults.enabled is False

    def test_host_defaults_validation_user(self):
        """Test HostDefaults user validation."""
        with pytest.raises(ValueError, match="Default user must be a non-empty string"):
            HostDefaults(user="")
        
        with pytest.raises(ValueError, match="Default username must be 32 characters or less"):
            HostDefaults(user="a" * 33)
        
        with pytest.raises(ValueError, match="contains invalid characters"):
            HostDefaults(user="invalid@user")

    def test_host_defaults_validation_port(self):
        """Test HostDefaults port validation."""
        with pytest.raises(ValueError, match="Default port must be between 1 and 65535"):
            HostDefaults(port=0)
        
        with pytest.raises(ValueError, match="Default port must be between 1 and 65535"):
            HostDefaults(port=65536)

    def test_host_defaults_validation_key_file(self):
        """Test HostDefaults key file validation."""
        with pytest.raises(ValueError, match="Default key file path must be a non-empty string"):
            HostDefaults(key_file="")


class TestDockerCommand:
    """Test cases for DockerCommand model."""

    def test_docker_command_creation(self):
        """Test creating DockerCommand with all fields."""
        cmd = DockerCommand(
            command="ps -a",
            host="test-host",
            timeout=30
        )
        
        assert cmd.command == "ps -a"
        assert cmd.host == "test-host"
        assert cmd.timeout == 30

    def test_docker_command_minimal(self):
        """Test creating DockerCommand with minimal fields."""
        cmd = DockerCommand(command="ps")
        
        assert cmd.command == "ps"
        assert cmd.host is None
        assert cmd.timeout is None

    def test_docker_command_validation_empty_command(self):
        """Test DockerCommand validation for empty command."""
        with pytest.raises(ValueError, match="Command must be a non-empty string"):
            DockerCommand(command="")
        
        with pytest.raises(ValueError, match="Command cannot be empty"):
            DockerCommand(command="   ")

    def test_docker_command_validation_timeout(self):
        """Test DockerCommand timeout validation."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            DockerCommand(command="ps", timeout=0)
        
        with pytest.raises(ValueError, match="Timeout must be positive"):
            DockerCommand(command="ps", timeout=-10)

    def test_docker_command_strips_whitespace(self):
        """Test that DockerCommand strips whitespace from command."""
        cmd = DockerCommand(command="  ps -a  ")
        assert cmd.command == "ps -a"


class TestContainerInfo:
    """Test cases for ContainerInfo model."""

    def test_container_info_creation_minimal(self):
        """Test creating ContainerInfo with minimal required fields."""
        container = ContainerInfo(
            id="abc123def456",
            name="test-container",
            image="nginx:latest",
            status="running",
            host="test-host"
        )
        
        assert container.id == "abc123def456"
        assert container.name == "test-container"
        assert container.image == "nginx:latest"
        assert container.status == "running"
        assert container.host == "test-host"
        
        # Check default values
        assert container.labels == {}
        assert container.ports == {}

    def test_container_info_creation_full(self):
        """Test creating ContainerInfo with all fields."""
        labels = {"maintainer": "test", "version": "1.0"}
        ports = {"80/tcp": "0.0.0.0:8080", "443/tcp": None}
        
        container = ContainerInfo(
            id="abc123def456789",
            name="test-container",
            image="nginx:latest",
            status="running",
            host="test-host",
            labels=labels,
            ports=ports
        )
        
        assert container.labels == labels
        assert container.ports == ports

    def test_container_info_short_id(self):
        """Test ContainerInfo short_id property."""
        container = ContainerInfo(
            id="abc123def456789xyz",
            name="test-container",
            image="nginx:latest",
            status="running",
            host="test-host"
        )
        
        assert container.short_id == "abc123def456"
        
        # Test with short ID
        short_container = ContainerInfo(
            id="abc123",
            name="test-container",
            image="nginx:latest",
            status="running",
            host="test-host"
        )
        
        assert short_container.short_id == "abc123"

    def test_container_info_allows_empty_fields(self):
        """Test ContainerInfo allows empty required fields (Pydantic default behavior)."""
        # Test empty ID is allowed
        container = ContainerInfo(
            id="",
            name="test",
            image="nginx",
            status="running",
            host="host"
        )
        assert container.id == ""
        
        # Test empty name is allowed
        container = ContainerInfo(
            id="abc123",
            name="",
            image="nginx",
            status="running",
            host="host"
        )
        assert container.name == ""

    def test_container_info_dict_conversion(self):
        """Test converting ContainerInfo to dict."""
        container = ContainerInfo(
            id="abc123def456",
            name="test-container",
            image="nginx:latest",
            status="running",
            host="test-host",
            labels={"env": "prod"},
            ports={"80/tcp": "8080"}
        )
        
        container_dict = container.model_dump()
        
        assert container_dict["id"] == "abc123def456"
        assert container_dict["name"] == "test-container"
        assert container_dict["image"] == "nginx:latest"
        assert container_dict["status"] == "running"
        assert container_dict["host"] == "test-host"
        assert container_dict["labels"] == {"env": "prod"}
        assert container_dict["ports"] == {"80/tcp": "8080"}

    def test_container_info_from_dict(self):
        """Test creating ContainerInfo from dict."""
        data = {
            "id": "abc123def456",
            "name": "test-container",
            "image": "nginx:latest",
            "status": "running",
            "host": "test-host",
            "labels": {"env": "prod"},
            "ports": {"80/tcp": "8080"}
        }
        
        container = ContainerInfo(**data)
        
        assert container.id == "abc123def456"
        assert container.name == "test-container"
        assert container.labels["env"] == "prod"
        assert container.ports["80/tcp"] == "8080"