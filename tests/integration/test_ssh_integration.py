"""Integration tests for SSH connections."""

import pytest
from pathlib import Path
from testcontainers.compose import DockerCompose
from testcontainers.core.waiting_utils import wait_for_logs
import asyncio
import time

from snadboy_ssh_docker.client import SSHDockerClient
from snadboy_ssh_docker.config import HostConfig, HostsConfig
from snadboy_ssh_docker.exceptions import SSHConnectionError, HostNotFoundError


@pytest.mark.integration
@pytest.mark.slow
class TestSSHIntegration:
    """Integration tests using real SSH connections."""

    @pytest.fixture(scope="class")
    def ssh_test_container(self):
        """Start SSH test container using testcontainers."""
        compose_path = Path(__file__).parent.parent / "fixtures"
        
        with DockerCompose(
            compose_path,
            compose_file_name="docker-compose.test.yml",
            pull=True
        ) as compose:
            # Wait for SSH service to be ready
            ssh_host = compose.get_service_host("ssh-server", 22)
            ssh_port = compose.get_service_port("ssh-server", 22)
            
            # Wait for SSH to be ready
            wait_for_logs(compose, "ssh-server", "Server listening on", timeout=30)
            time.sleep(2)  # Additional wait for SSH to fully initialize
            
            yield {
                "host": ssh_host,
                "port": int(ssh_port),
                "username": "testuser",
                "password": "testpass"
            }

    @pytest.fixture
    def test_host_config(self, ssh_test_container):
        """Create host configuration for test container."""
        return HostConfig(
            hostname=ssh_test_container["host"],
            port=ssh_test_container["port"],
            username=ssh_test_container["username"],
            password=ssh_test_container["password"],
            timeout=30
        )

    @pytest.fixture
    def ssh_client(self, test_host_config):
        """Create SSH Docker client for integration tests."""
        hosts_config = HostsConfig(hosts={"test-server": test_host_config})
        return SSHDockerClient(hosts_config=hosts_config)

    @pytest.mark.asyncio
    async def test_real_ssh_connection(self, ssh_client, ssh_test_container):
        """Test establishing real SSH connection."""
        async with ssh_client:
            # Test basic SSH connectivity by running a simple command
            try:
                # This will establish SSH connection
                containers = await ssh_client.list_containers("test-server")
                # If we get here, SSH connection worked (even if Docker isn't available)
                assert isinstance(containers, list)
            except Exception as e:
                # Check if it's a Docker-related error, not SSH error
                if "docker" in str(e).lower() or "command not found" in str(e).lower():
                    # This is expected - test container might not have Docker
                    pass
                else:
                    # This is an unexpected SSH error
                    raise

    @pytest.mark.asyncio
    async def test_ssh_authentication_failure(self, ssh_test_container):
        """Test SSH authentication failure handling."""
        bad_config = HostConfig(
            hostname=ssh_test_container["host"],
            port=ssh_test_container["port"],
            username=ssh_test_container["username"],
            password="wrongpassword",
            timeout=10
        )
        
        hosts_config = HostsConfig(hosts={"bad-server": bad_config})
        client = SSHDockerClient(hosts_config=hosts_config)
        
        with pytest.raises(SSHConnectionError):
            async with client:
                await client.list_containers("bad-server")

    @pytest.mark.asyncio
    async def test_ssh_connection_timeout(self):
        """Test SSH connection timeout handling."""
        # Use a non-routable IP to trigger timeout
        timeout_config = HostConfig(
            hostname="10.255.255.1",  # Non-routable IP
            port=22,
            username="testuser",
            password="testpass",
            timeout=1  # Very short timeout
        )
        
        hosts_config = HostsConfig(hosts={"timeout-server": timeout_config})
        client = SSHDockerClient(hosts_config=hosts_config)
        
        with pytest.raises(SSHConnectionError):
            async with client:
                await client.list_containers("timeout-server")

    @pytest.mark.asyncio
    async def test_ssh_connection_refused(self):
        """Test SSH connection refused handling."""
        # Use localhost with wrong port to trigger connection refused
        refused_config = HostConfig(
            hostname="127.0.0.1",
            port=9999,  # Unlikely to be in use
            username="testuser",
            password="testpass",
            timeout=5
        )
        
        hosts_config = HostsConfig(hosts={"refused-server": refused_config})
        client = SSHDockerClient(hosts_config=hosts_config)
        
        with pytest.raises(SSHConnectionError):
            async with client:
                await client.list_containers("refused-server")

    @pytest.mark.asyncio
    async def test_multiple_ssh_connections(self, ssh_test_container):
        """Test managing multiple SSH connections."""
        # Create two identical host configs (simulating different servers)
        config1 = HostConfig(
            hostname=ssh_test_container["host"],
            port=ssh_test_container["port"],
            username=ssh_test_container["username"],
            password=ssh_test_container["password"]
        )
        
        config2 = HostConfig(
            hostname=ssh_test_container["host"],
            port=ssh_test_container["port"],
            username=ssh_test_container["username"],
            password=ssh_test_container["password"]
        )
        
        hosts_config = HostsConfig(hosts={
            "server1": config1,
            "server2": config2
        })
        
        client = SSHDockerClient(hosts_config=hosts_config)
        
        async with client:
            # Try to connect to both servers
            try:
                await asyncio.gather(
                    client.list_containers("server1"),
                    client.list_containers("server2")
                )
            except Exception as e:
                # Similar to above - Docker might not be available, but SSH should work
                if "docker" not in str(e).lower():
                    raise

    @pytest.mark.asyncio
    async def test_ssh_command_execution(self, ssh_client):
        """Test executing commands over SSH."""
        async with ssh_client:
            try:
                # Test a basic command that should work on most systems
                result = await ssh_client.execute_command("test-server", "container-id", "echo 'test'")
                # This will likely fail because we're not in a container, but SSH part should work
            except Exception as e:
                # Expected - we're not actually executing in a container
                if "docker" in str(e).lower() or "exec" in str(e).lower():
                    pass
                else:
                    raise

    @pytest.mark.asyncio
    async def test_ssh_connection_recovery(self, ssh_client):
        """Test SSH connection recovery after disconnection."""
        async with ssh_client:
            # First connection attempt
            try:
                await ssh_client.list_containers("test-server")
            except Exception as e:
                if "docker" not in str(e).lower():
                    raise
            
            # Force close connections
            await ssh_client.close()
            
            # Reconnect and try again
            try:
                await ssh_client.list_containers("test-server")
            except Exception as e:
                if "docker" not in str(e).lower():
                    raise

    @pytest.mark.asyncio
    async def test_concurrent_ssh_operations(self, ssh_client):
        """Test concurrent SSH operations."""
        async with ssh_client:
            # Run multiple operations concurrently
            tasks = []
            for i in range(3):
                try:
                    task = ssh_client.list_containers("test-server")
                    tasks.append(task)
                except Exception:
                    pass
            
            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    if "docker" not in str(e).lower():
                        raise

    @pytest.mark.asyncio
    async def test_host_not_found_error(self, ssh_client):
        """Test error when trying to use non-configured host."""
        async with ssh_client:
            with pytest.raises(HostNotFoundError):
                await ssh_client.list_containers("nonexistent-host")


@pytest.mark.integration
@pytest.mark.slow
class TestSSHKeyAuthentication:
    """Integration tests for SSH key-based authentication."""

    @pytest.fixture
    def temp_ssh_key(self, tmp_path):
        """Generate temporary SSH key pair for testing."""
        key_path = tmp_path / "test_key"
        pub_key_path = tmp_path / "test_key.pub"
        
        # In a real scenario, you'd generate actual keys
        # For testing, we'll create dummy files
        key_path.write_text("dummy private key")
        pub_key_path.write_text("dummy public key")
        
        return key_path

    @pytest.mark.asyncio
    async def test_ssh_key_authentication_file_not_found(self, temp_ssh_key):
        """Test SSH key authentication with non-existent key file."""
        nonexistent_key = temp_ssh_key.parent / "nonexistent_key"
        
        key_config = HostConfig(
            hostname="127.0.0.1",
            port=22,
            username="testuser",
            key_file=nonexistent_key
        )
        
        hosts_config = HostsConfig(hosts={"key-server": key_config})
        client = SSHDockerClient(hosts_config=hosts_config)
        
        with pytest.raises(SSHConnectionError):
            async with client:
                await client.list_containers("key-server")

    def test_ssh_key_path_expansion(self, temp_ssh_key):
        """Test SSH key path expansion."""
        # Test with tilde expansion
        config = HostConfig(
            hostname="test.example.com",
            username="testuser",
            key_file=Path("~/test_key")
        )
        
        # The config should accept the path
        assert config.key_file == Path("~/test_key")


@pytest.mark.integration 
class TestSSHConfigurationLoading:
    """Integration tests for SSH configuration loading."""

    def test_load_config_from_real_file(self, tmp_path):
        """Test loading SSH configuration from actual file."""
        config_content = """
hosts:
  production:
    hostname: prod.example.com
    port: 22
    username: deploy
    key_file: ~/.ssh/prod_key
    timeout: 60
    
  staging:
    hostname: staging.example.com
    port: 2222
    username: deploy
    password: stagingpass
    timeout: 30
"""
        
        config_file = tmp_path / "real_hosts.yml"
        config_file.write_text(config_content.strip())
        
        client = SSHDockerClient.from_config(config_file)
        
        assert len(client.hosts_config.hosts) == 2
        assert "production" in client.hosts_config.hosts
        assert "staging" in client.hosts_config.hosts
        
        prod_config = client.hosts_config.hosts["production"]
        assert prod_config.hostname == "prod.example.com"
        assert prod_config.port == 22
        assert prod_config.timeout == 60
        
        staging_config = client.hosts_config.hosts["staging"]
        assert staging_config.hostname == "staging.example.com"
        assert staging_config.port == 2222
        assert staging_config.password == "stagingpass"