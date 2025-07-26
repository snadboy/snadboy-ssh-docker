"""Unit tests for SSH manager."""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call

from snadboy_ssh_docker.ssh_manager import SSHManager
from snadboy_ssh_docker.models import HostConfig
from snadboy_ssh_docker.config import HostsConfig
from snadboy_ssh_docker.exceptions import SSHConnectionError, ConfigurationError


class TestSSHManager:
    """Test cases for SSHManager class."""

    def test_init_default_ssh_dir(self):
        """Test SSHManager initialization with default SSH directory."""
        manager = SSHManager()
        assert manager.ssh_dir == Path.home() / ".ssh"
        assert manager.config_file == Path.home() / ".ssh" / "config"

    def test_init_custom_ssh_dir(self):
        """Test SSHManager initialization with custom SSH directory."""
        custom_dir = Path("/custom/ssh/dir")
        manager = SSHManager(ssh_dir=custom_dir)
        assert manager.ssh_dir == custom_dir
        assert manager.config_file == custom_dir / "config"

    def test_init_ssh_options(self):
        """Test SSHManager initializes with default SSH options."""
        manager = SSHManager()
        assert "PasswordAuthentication" in manager.ssh_options
        assert "StrictHostKeyChecking" in manager.ssh_options
        assert "ControlMaster" in manager.ssh_options

    @patch('snadboy_ssh_docker.ssh_manager.Path.mkdir')
    def test_ensure_ssh_directory(self, mock_mkdir):
        """Test ensuring SSH directory exists with proper permissions."""
        manager = SSHManager()
        manager._ensure_ssh_directory()
        
        # Should create both SSH dir and control dir
        assert mock_mkdir.call_count == 2
        mock_mkdir.assert_any_call(mode=0o700, exist_ok=True)

    def test_add_host(self):
        """Test adding a host to SSH configuration."""
        manager = SSHManager()
        # Create initial hosts config with at least one host
        initial_host = HostConfig(
            hostname="initial.example.com",
            user="initialuser", 
            key_file="~/.ssh/id_rsa"
        )
        manager.hosts_config = HostsConfig(hosts={"initial": initial_host})
        
        host_config = HostConfig(
            hostname="test.example.com",
            user="testuser",
            port=22,
            key_file="~/.ssh/id_rsa"
        )
        
        with patch.object(manager, '_generate_ssh_config'):
            manager.add_host("test-host", host_config)
            
        assert "test-host" in manager.hosts_config.hosts
        assert manager.hosts_config.hosts["test-host"] == host_config

    @patch('snadboy_ssh_docker.ssh_manager.Path.exists')
    @patch('snadboy_ssh_docker.ssh_manager.Path.write_text')
    @patch('snadboy_ssh_docker.ssh_manager.os.chmod')
    def test_generate_ssh_config(self, mock_chmod, mock_write_text, mock_exists):
        """Test generating SSH config file."""
        mock_exists.return_value = False
        
        manager = SSHManager()
        hosts_config = HostsConfig(hosts={
            "test-host": HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=22,
                key_file="~/.ssh/id_rsa"
            )
        })
        manager.hosts_config = hosts_config
        
        manager._generate_ssh_config()
        
        # Should write config
        mock_write_text.assert_called_once()
        written_config = mock_write_text.call_args[0][0]
        
        # Check config content
        assert "Host docker-test-example-com-22" in written_config
        assert "HostName test.example.com" in written_config
        assert "User testuser" in written_config
        assert "Port 22" in written_config
        assert "IdentityFile" in written_config and "id_rsa" in written_config

    def test_get_ssh_alias(self):
        """Test getting SSH alias for a host."""
        manager = SSHManager()
        hosts_config = HostsConfig(hosts={
            "test-host": HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=22,
                key_file="~/.ssh/id_rsa"
            )
        })
        manager.hosts_config = hosts_config
        
        alias = manager.get_ssh_alias("test-host")
        assert alias == "docker-test-example-com-22"

    def test_get_ssh_alias_no_config(self):
        """Test getting SSH alias without configuration raises error."""
        manager = SSHManager()
        
        with pytest.raises(ConfigurationError, match="No hosts configuration loaded"):
            manager.get_ssh_alias("test-host")

    def test_get_ssh_alias_host_not_found(self):
        """Test getting SSH alias for non-existent host raises error."""
        manager = SSHManager()
        # Create hosts config with one host, but request different host
        dummy_host = HostConfig(
            hostname="dummy.example.com",
            user="dummy",
            key_file="~/.ssh/id_rsa"
        )
        manager.hosts_config = HostsConfig(hosts={"dummy": dummy_host})
        
        with pytest.raises(ConfigurationError, match="Host 'test-host' not found"):
            manager.get_ssh_alias("test-host")

    def test_get_docker_command_with_docker_prefix(self):
        """Test building Docker command that already starts with 'docker'."""
        manager = SSHManager()
        hosts_config = HostsConfig(hosts={
            "test-host": HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=22,
                key_file="~/.ssh/id_rsa"
            )
        })
        manager.hosts_config = hosts_config
        
        cmd = manager.get_docker_command("test-host", "docker ps -a")
        assert cmd == ["ssh", "docker-test-example-com-22", "docker ps -a"]

    def test_get_docker_command_without_docker_prefix(self):
        """Test building Docker command without 'docker' prefix."""
        manager = SSHManager()
        hosts_config = HostsConfig(hosts={
            "test-host": HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=22,
                key_file="~/.ssh/id_rsa"
            )
        })
        manager.hosts_config = hosts_config
        
        cmd = manager.get_docker_command("test-host", "ps -a")
        assert cmd == ["ssh", "docker-test-example-com-22", "docker ps -a"]

    @patch('subprocess.run')
    def test_execute_ssh_command_success(self, mock_run):
        """Test successful SSH command execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "command output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        manager = SSHManager()
        hosts_config = HostsConfig(hosts={
            "test-host": HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=22,
                key_file="~/.ssh/id_rsa"
            )
        })
        manager.hosts_config = hosts_config
        
        result = manager.execute_ssh_command("test-host", "echo test")
        
        assert result.returncode == 0
        assert result.stdout == "command output"
        mock_run.assert_called_once_with(
            ["ssh", "docker-test-example-com-22", "echo test"],
            capture_output=True,
            text=True,
            timeout=None
        )

    @patch('subprocess.run')
    def test_execute_ssh_command_failure(self, mock_run):
        """Test SSH command execution with connection failure."""
        mock_result = MagicMock()
        mock_result.returncode = 255
        mock_result.stdout = ""
        mock_result.stderr = "ssh: connect to host test.example.com port 22: Connection refused"
        mock_run.return_value = mock_result
        
        manager = SSHManager()
        hosts_config = HostsConfig(hosts={
            "test-host": HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=22,
                key_file="~/.ssh/id_rsa"
            )
        })
        manager.hosts_config = hosts_config
        
        with pytest.raises(SSHConnectionError, match="SSH connection failed"):
            manager.execute_ssh_command("test-host", "echo test")

    @patch('subprocess.run')
    def test_execute_ssh_command_timeout(self, mock_run):
        """Test SSH command execution with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ssh"], timeout=10)
        
        manager = SSHManager()
        hosts_config = HostsConfig(hosts={
            "test-host": HostConfig(
                hostname="test.example.com",
                user="testuser",
                port=22,
                key_file="~/.ssh/id_rsa"
            )
        })
        manager.hosts_config = hosts_config
        
        with pytest.raises(SSHConnectionError, match="Command timeout after 10 seconds"):
            manager.execute_ssh_command("test-host", "echo test", timeout=10)

    @patch('subprocess.run')
    def test_test_connections(self, mock_run):
        """Test testing SSH connections to all hosts."""
        # Mock successful connection
        success_result = MagicMock()
        success_result.returncode = 0
        success_result.stdout = "OK\n"
        success_result.stderr = ""
        
        # Mock failed connection
        fail_result = MagicMock()
        fail_result.returncode = 255
        fail_result.stdout = ""
        fail_result.stderr = "Connection refused"
        
        mock_run.side_effect = [success_result, fail_result]
        
        manager = SSHManager()
        hosts_config = HostsConfig(hosts={
            "host1": HostConfig(
                hostname="host1.example.com",
                user="user1",
                port=22,
                key_file="~/.ssh/id_rsa"
            ),
            "host2": HostConfig(
                hostname="host2.example.com",
                user="user2",
                port=2222,
                key_file="~/.ssh/id_rsa"
            )
        })
        manager.hosts_config = hosts_config
        
        results = manager.test_connections()
        
        assert len(results) == 2
        assert results["host1.example.com"]["connected"] is True
        assert results["host2.example.com"]["connected"] is False
        assert results["host2.example.com"]["error"] == "Connection refused"

    @patch('snadboy_ssh_docker.ssh_manager.Path.exists')
    @patch('snadboy_ssh_docker.ssh_manager.Path.stat')
    @patch('snadboy_ssh_docker.ssh_manager.os.chmod')
    def test_ensure_key_permissions(self, mock_chmod, mock_stat, mock_exists):
        """Test ensuring SSH key has proper permissions."""
        mock_exists.return_value = True
        
        # Mock stat to return permissions with group/other access
        mock_stat_result = MagicMock()
        mock_stat_result.st_mode = 0o644  # Has group/other read permissions
        mock_stat.return_value = mock_stat_result
        
        manager = SSHManager()
        key_path = Path("/tmp/test_key")
        
        manager._ensure_key_permissions(key_path)
        
        # Should fix permissions to 600
        import stat
        mock_chmod.assert_called_once_with(key_path, stat.S_IRUSR | stat.S_IWUSR)

    @patch('snadboy_ssh_docker.ssh_manager.Path.exists')
    @patch('snadboy_ssh_docker.ssh_manager.Path.read_text')
    def test_read_existing_config(self, mock_read_text, mock_exists):
        """Test reading existing SSH config and removing managed section."""
        mock_exists.return_value = True
        existing_config = """Host myserver
    HostName myserver.com
    User myuser

# BEGIN SSH DOCKER CLIENT MANAGED HOSTS
Host docker_old
    HostName old.com
# END SSH DOCKER CLIENT MANAGED HOSTS

Host another
    HostName another.com"""
        
        mock_read_text.return_value = existing_config
        
        manager = SSHManager()
        result = manager._read_existing_config()
        
        # Should remove managed section
        assert "BEGIN SSH DOCKER CLIENT" not in result
        assert "docker_old" not in result
        assert "Host myserver" in result
        assert "Host another" in result

    @patch('snadboy_ssh_docker.ssh_manager.Path.exists')
    @patch('snadboy_ssh_docker.ssh_manager.Path.read_text')
    @patch('snadboy_ssh_docker.ssh_manager.Path.write_text')
    @patch('snadboy_ssh_docker.ssh_manager.os.chmod')
    def test_setup_from_config(self, mock_chmod, mock_write_text, mock_read_text, mock_exists):
        """Test setting up SSH configuration from YAML file."""
        mock_exists.return_value = False
        
        with patch('snadboy_ssh_docker.ssh_manager.load_hosts_config') as mock_load:
            mock_load.return_value = HostsConfig(hosts={
                "test": HostConfig(
                    hostname="test.com",
                    user="user",
                    port=22,
                    key_file="~/.ssh/id_rsa"
                )
            })
            
            manager = SSHManager()
            manager.setup_from_config(Path("/tmp/hosts.yml"))
            
            assert manager.hosts_config is not None
            mock_write_text.assert_called_once()

    def test_ssh_options_defaults(self):
        """Test default SSH options are set correctly."""
        manager = SSHManager()
        
        assert manager.ssh_options["PasswordAuthentication"] == "no"
        assert manager.ssh_options["StrictHostKeyChecking"] == "accept-new"
        assert manager.ssh_options["ServerAliveInterval"] == "60"
        assert manager.ssh_options["ServerAliveCountMax"] == "3"
        assert manager.ssh_options["ControlMaster"] == "auto"
        assert manager.ssh_options["ControlPersist"] == "10m"
        assert manager.ssh_options["ConnectTimeout"] == "30"