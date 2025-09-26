"""Unit tests for data models."""

import pytest

from snadboy_ssh_docker.models import HostConfig, HostDefaults, DockerCommand


class TestHostConfig:
    """Test cases for HostConfig model."""

    def test_host_config_creation(self):
        """Test creating HostConfig with all fields."""
        config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            port=2222,
            description="Test server",
            enabled=True
        )

        assert config.hostname == "test.example.com"
        assert config.user == "testuser"
        assert config.port == 2222
        assert config.description == "Test server"
        assert config.enabled is True

    def test_host_config_defaults(self):
        """Test HostConfig default values."""
        config = HostConfig(
            hostname="test.example.com",
            user="testuser"
        )

        assert config.port == 22
        assert config.description == ""
        assert config.enabled is True

    def test_host_config_validation_hostname_empty(self):
        """Test HostConfig validation for empty hostname."""
        with pytest.raises(ValueError, match="Hostname must be a non-empty string"):
            HostConfig(
                hostname="",
                user="testuser"
            )

    def test_host_config_validation_hostname_too_long(self):
        """Test HostConfig validation for hostname too long."""
        with pytest.raises(ValueError, match="Hostname must be 253 characters or less"):
            HostConfig(
                hostname="a" * 254,
                user="testuser"
            )

    def test_host_config_validation_hostname_invalid_chars(self):
        """Test HostConfig validation for invalid hostname characters."""
        with pytest.raises(ValueError, match="contains invalid characters"):
            HostConfig(
                hostname="test@example.com",
                user="testuser"
            )

    def test_host_config_validation_user_empty(self):
        """Test HostConfig validation for empty user."""
        with pytest.raises(ValueError, match="User must be a non-empty string"):
            HostConfig(
                hostname="test.example.com",
                user=""
            )

    def test_host_config_validation_user_too_long(self):
        """Test HostConfig validation for user too long."""
        with pytest.raises(ValueError, match="Username must be 32 characters or less"):
            HostConfig(
                hostname="test.example.com",
                user="a" * 33
            )

    def test_host_config_validation_user_invalid_chars(self):
        """Test HostConfig validation for invalid user characters."""
        with pytest.raises(ValueError, match="contains invalid characters"):
            HostConfig(
                hostname="test.example.com",
                user="invalid@user"
            )

    def test_host_config_validation_port(self):
        """Test HostConfig validation for port."""
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=0
            )

        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=65536
            )

    def test_host_config_get_ssh_alias(self):
        """Test generating SSH alias from host config."""
        config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            port=2222
        )

        expected = "testuser@test.example.com"
        assert config.get_ssh_alias() == expected

    def test_host_config_get_ssh_alias_tailscale(self):
        """Test generating SSH alias for Tailscale host."""
        config = HostConfig(
            hostname="myhost.tail-scale.ts.net",
            user="deploy"
        )

        expected = "deploy@myhost.tail-scale.ts.net"
        assert config.get_ssh_alias() == expected


class TestHostDefaults:
    """Test cases for HostDefaults model."""

    def test_host_defaults_creation(self):
        """Test creating HostDefaults with all fields."""
        defaults = HostDefaults(
            user="admin",
            port=2222,
            enabled=False
        )

        assert defaults.user == "admin"
        assert defaults.port == 2222
        assert defaults.enabled is False

    def test_host_defaults_minimal(self):
        """Test creating HostDefaults with minimal fields."""
        defaults = HostDefaults()

        assert defaults.user == "root"
        assert defaults.port == 22
        assert defaults.enabled is True

    def test_host_defaults_validation_user_empty(self):
        """Test HostDefaults validation for empty user."""
        with pytest.raises(ValueError, match="Default user must be a non-empty string"):
            HostDefaults(user="")

    def test_host_defaults_validation_user_too_long(self):
        """Test HostDefaults validation for user too long."""
        with pytest.raises(ValueError, match="Default username must be 32 characters or less"):
            HostDefaults(user="a" * 33)

    def test_host_defaults_validation_user_invalid_chars(self):
        """Test HostDefaults validation for invalid user characters."""
        with pytest.raises(ValueError, match="contains invalid characters"):
            HostDefaults(user="invalid@user")

    def test_host_defaults_validation_port(self):
        """Test HostDefaults port validation."""
        with pytest.raises(ValueError, match="Default port must be between 1 and 65535"):
            HostDefaults(port=0)

        with pytest.raises(ValueError, match="Default port must be between 1 and 65535"):
            HostDefaults(port=65536)


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