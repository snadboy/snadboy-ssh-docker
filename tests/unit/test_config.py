"""Unit tests for configuration loading and validation."""

import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from snadboy_ssh_docker.config import HostsConfig, load_hosts_config
from snadboy_ssh_docker.models import HostConfig
from snadboy_ssh_docker.exceptions import ConfigurationError


class TestHostsConfig:
    """Test cases for HostsConfig class."""

    def test_hosts_config_creation(self):
        """Test creating HostsConfig with multiple hosts."""
        host1 = HostConfig(
            hostname="host1.example.com",
            user="user1",
            key_file="~/.ssh/id_rsa"
        )
        host2 = HostConfig(
            hostname="host2.example.com",
            user="user2",
            key_file="~/.ssh/id_rsa"
        )
        
        config = HostsConfig(hosts={"host1": host1, "host2": host2})
        
        assert len(config.hosts) == 2
        assert "host1" in config.hosts
        assert "host2" in config.hosts
        assert config.hosts["host1"] == host1
        assert config.hosts["host2"] == host2

    def test_hosts_config_empty_raises_error(self):
        """Test creating empty HostsConfig raises validation error."""
        with pytest.raises(ValueError, match="At least one host must be configured"):
            HostsConfig(hosts={})

    def test_hosts_config_get_host_config(self):
        """Test getting host configuration by name."""
        host_config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            key_file="~/.ssh/id_rsa"
        )
        config = HostsConfig(hosts={"test-host": host_config})
        
        retrieved = config.get_host_config("test-host")
        assert retrieved.hostname == host_config.hostname
        assert retrieved.user == host_config.user

    def test_hosts_config_get_nonexistent_host_raises_error(self):
        """Test getting non-existent host raises error."""
        host_config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            key_file="~/.ssh/id_rsa"
        )
        config = HostsConfig(hosts={"test-host": host_config})
        
        with pytest.raises(ValueError, match="Host 'nonexistent' not found"):
            config.get_host_config("nonexistent")

    def test_hosts_config_get_enabled_hosts(self):
        """Test getting only enabled hosts."""
        host1 = HostConfig(
            hostname="host1.example.com",
            user="user1",
            key_file="~/.ssh/id_rsa",
            enabled=True
        )
        host2 = HostConfig(
            hostname="host2.example.com",
            user="user2",
            key_file="~/.ssh/id_rsa",
            enabled=False
        )
        
        config = HostsConfig(hosts={"host1": host1, "host2": host2})
        enabled = config.get_enabled_hosts()
        
        assert len(enabled) == 1
        assert "host1" in enabled
        assert "host2" not in enabled

    def test_hosts_config_validate_ssh_keys(self):
        """Test validating SSH keys returns missing key files."""
        host1 = HostConfig(
            hostname="host1.example.com",
            user="user1",
            key_file="/nonexistent/key1"
        )
        host2 = HostConfig(
            hostname="host2.example.com",
            user="user2",
            key_file="/nonexistent/key2"
        )
        
        config = HostsConfig(hosts={"host1": host1, "host2": host2})
        
        with patch('pathlib.Path.exists', return_value=False):
            missing = config.validate_ssh_keys()
            assert len(missing) == 2
            assert "host1: /nonexistent/key1" in missing
            assert "host2: /nonexistent/key2" in missing

    def test_hosts_config_get_host_config(self):
        """Test getting host config object."""
        host_config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            key_file="~/.ssh/id_rsa"
        )
        config = HostsConfig(hosts={"test-host": host_config})
        
        retrieved = config.get_host_config("test-host")
        assert retrieved == host_config

    def test_hosts_config_get_host_config_not_found(self):
        """Test getting host config raises error for non-existent host."""
        host_config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            key_file="~/.ssh/id_rsa"
        )
        config = HostsConfig(hosts={"test-host": host_config})
        
        with pytest.raises(ValueError, match="Host 'nonexistent' not found"):
            config.get_host_config("nonexistent")


class TestLoadHostsConfig:
    """Test cases for load_hosts_config function."""

    def test_load_valid_config_file(self, temp_config_file):
        """Test loading a valid configuration file."""
        config = load_hosts_config(temp_config_file)
        
        assert isinstance(config, HostsConfig)
        assert len(config.hosts) == 2
        assert "test-host" in config.hosts
        assert "test-host-2" in config.hosts
        
        host1 = config.hosts["test-host"]
        assert host1.hostname == "test.example.com"
        assert host1.port == 22
        assert host1.user == "testuser"
        assert host1.key_file.endswith("id_rsa")
        
        host2 = config.hosts["test-host-2"]
        assert host2.hostname == "test2.example.com"  
        assert host2.port == 2222
        assert host2.user == "testuser2"

    def test_load_nonexistent_file(self):
        """Test loading non-existent configuration file raises error."""
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            load_hosts_config(Path("/nonexistent/file.yml"))

    def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML raises error."""
        config_file = tmp_path / "invalid.yml"
        config_file.write_text("invalid: yaml: content: [")
        
        with pytest.raises(ConfigurationError, match="Invalid YAML format"):
            load_hosts_config(config_file)

    def test_load_missing_hosts_key(self, tmp_path):
        """Test loading config without 'hosts' key raises error."""
        config_file = tmp_path / "no_hosts.yml"
        config_file.write_text("settings:\n  debug: true")
        
        with pytest.raises(ConfigurationError, match="Configuration must contain 'hosts' section"):
            load_hosts_config(config_file)

    def test_load_empty_hosts_raises_error(self, tmp_path):
        """Test loading config with empty hosts raises error."""
        config_file = tmp_path / "empty_hosts.yml"
        config_file.write_text("hosts: {}")
        
        with pytest.raises(ConfigurationError, match="Invalid configuration"):
            load_hosts_config(config_file)

    def test_load_config_with_minimal_host(self, tmp_path):
        """Test loading config with minimal host configuration."""
        config_content = """
hosts:
  minimal-host:
    hostname: minimal.example.com
    user: minimaluser
    key_file: ~/.ssh/id_rsa
"""
        config_file = tmp_path / "minimal.yml"
        config_file.write_text(config_content.strip())
        
        config = load_hosts_config(config_file)
        assert len(config.hosts) == 1
        
        host = config.hosts["minimal-host"]
        assert host.hostname == "minimal.example.com"
        assert host.user == "minimaluser"
        assert host.key_file.endswith("id_rsa")
        assert host.port == 22  # default
        assert host.enabled is True  # default

    def test_load_config_with_defaults(self, tmp_path):
        """Test loading config with defaults section."""
        config_content = """
defaults:
  user: defaultuser
  port: 2222
  key_file: ~/.ssh/default_key

hosts:
  host1:
    hostname: host1.example.com
  host2:
    hostname: host2.example.com
    user: customuser
"""
        config_file = tmp_path / "with_defaults.yml"
        config_file.write_text(config_content.strip())
        
        config = load_hosts_config(config_file)
        assert len(config.hosts) == 2
        
        # host1 should use defaults
        host1 = config.hosts["host1"]
        assert host1.hostname == "host1.example.com"
        assert host1.user == "defaultuser"
        assert host1.port == 2222
        assert host1.key_file.endswith("default_key")
        
        # host2 should override user but use default port and key
        host2 = config.hosts["host2"]
        assert host2.hostname == "host2.example.com"
        assert host2.user == "customuser"
        assert host2.port == 2222
        assert host2.key_file.endswith("default_key")

    def test_load_config_with_disabled_host(self, tmp_path):
        """Test loading config with disabled host."""
        config_content = """
hosts:
  enabled-host:
    hostname: enabled.example.com
    user: user1
    key_file: ~/.ssh/id_rsa
    enabled: true
  disabled-host:
    hostname: disabled.example.com
    user: user2
    key_file: ~/.ssh/id_rsa
    enabled: false
"""
        config_file = tmp_path / "with_disabled.yml"
        config_file.write_text(config_content.strip())
        
        config = load_hosts_config(config_file)
        assert len(config.hosts) == 2
        assert config.hosts["enabled-host"].enabled is True
        assert config.hosts["disabled-host"].enabled is False

    def test_load_config_invalid_host_config(self, tmp_path):
        """Test loading config with invalid host configuration."""
        config_content = """
hosts:
  invalid-host:
    hostname: invalid@hostname.com
    user: invaliduser
    key_file: ~/.ssh/id_rsa
"""
        config_file = tmp_path / "invalid_host.yml"
        config_file.write_text(config_content.strip())
        
        with pytest.raises(ConfigurationError, match="Invalid configuration"):
            load_hosts_config(config_file)

    def test_load_config_path_object(self, temp_config_file):
        """Test loading config with Path object."""
        config = load_hosts_config(temp_config_file)
        assert isinstance(config, HostsConfig)
        assert len(config.hosts) == 2

    def test_load_empty_config_file(self, tmp_path):
        """Test loading empty configuration file."""
        config_file = tmp_path / "empty.yml"
        config_file.write_text("")
        
        with pytest.raises(ConfigurationError, match="Configuration file is empty"):
            load_hosts_config(config_file)

    def test_load_config_not_dict(self, tmp_path):
        """Test loading config that's not a dictionary."""
        config_file = tmp_path / "not_dict.yml"
        config_file.write_text("- item1\n- item2")
        
        with pytest.raises(ConfigurationError, match="Configuration must be a dictionary"):
            load_hosts_config(config_file)


# Import patch for testing
from unittest.mock import patch