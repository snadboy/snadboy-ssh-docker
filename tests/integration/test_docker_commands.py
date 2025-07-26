"""Integration tests for Docker command execution."""

import pytest
import json
from pathlib import Path
from testcontainers.compose import DockerCompose
from testcontainers.core.waiting_utils import wait_for_logs
import asyncio
import time

from snadboy_ssh_docker.client import SSHDockerClient
from snadboy_ssh_docker.config import HostConfig, HostsConfig
from snadboy_ssh_docker.exceptions import DockerCommandError


@pytest.mark.integration
@pytest.mark.slow
class TestDockerIntegration:
    """Integration tests using real Docker commands over SSH."""

    @pytest.fixture(scope="class")
    def docker_ssh_container(self):
        """Start SSH container with Docker-in-Docker for testing."""
        compose_path = Path(__file__).parent.parent / "fixtures"
        
        with DockerCompose(
            compose_path,
            compose_file_name="docker-compose.docker.yml",
            pull=True
        ) as compose:
            # Wait for both SSH and Docker to be ready
            ssh_host = compose.get_service_host("docker-ssh", 22)
            ssh_port = compose.get_service_port("docker-ssh", 22)
            
            # Wait for SSH service
            wait_for_logs(compose, "docker-ssh", "Server listening on", timeout=60)
            # Wait for Docker daemon
            wait_for_logs(compose, "docker-ssh", "API listen on", timeout=60)
            time.sleep(5)  # Additional wait for full initialization
            
            yield {
                "host": ssh_host,
                "port": int(ssh_port),
                "username": "root",
                "password": "testpass"
            }

    @pytest.fixture
    def docker_host_config(self, docker_ssh_container):
        """Create host configuration for Docker-enabled test container."""
        return HostConfig(
            hostname=docker_ssh_container["host"],
            port=docker_ssh_container["port"],
            username=docker_ssh_container["username"],
            password=docker_ssh_container["password"],
            timeout=60
        )

    @pytest.fixture
    def docker_ssh_client(self, docker_host_config):
        """Create SSH Docker client for Docker integration tests."""
        hosts_config = HostsConfig(hosts={"docker-server": docker_host_config})
        return SSHDockerClient(hosts_config=hosts_config)

    @pytest.mark.asyncio
    async def test_docker_version_check(self, docker_ssh_client):
        """Test Docker version check over SSH."""
        async with docker_ssh_client:
            # First ensure Docker is working by checking version
            ssh_manager = docker_ssh_client.ssh_manager
            connection = await docker_ssh_client.connection_pool.get_connection("docker-server")
            
            stdout, stderr, exit_code = await ssh_manager.execute_command(
                "docker-server", "docker version --format json"
            )
            
            if exit_code == 0:
                version_info = json.loads(stdout)
                assert "Client" in version_info
                assert "Server" in version_info

    @pytest.mark.asyncio
    async def test_list_containers_empty(self, docker_ssh_client):
        """Test listing containers when no containers are running."""
        async with docker_ssh_client:
            containers = await docker_ssh_client.list_containers("docker-server")
            assert isinstance(containers, list)
            # Initially should be empty or contain only system containers

    @pytest.mark.asyncio
    async def test_run_and_list_container(self, docker_ssh_client):
        """Test running a container and then listing it."""
        async with docker_ssh_client:
            # Pull a small test image
            ssh_manager = docker_ssh_client.ssh_manager
            
            # Pull hello-world image
            stdout, stderr, exit_code = await ssh_manager.execute_command(
                "docker-server", "docker pull hello-world"
            )
            assert exit_code == 0, f"Failed to pull image: {stderr}"
            
            # Run a container that exits immediately
            stdout, stderr, exit_code = await ssh_manager.execute_command(
                "docker-server", "docker run --name test-container hello-world"
            )
            assert exit_code == 0, f"Failed to run container: {stderr}"
            
            # List all containers (including stopped)
            containers = await docker_ssh_client.list_containers(
                "docker-server", 
                filters={"all": True}
            )
            
            # Should find our test container
            test_containers = [c for c in containers if c.name == "test-container"]
            assert len(test_containers) > 0
            
            test_container = test_containers[0]
            assert test_container.image == "hello-world"
            assert test_container.status in ["exited", "stopped"]

    @pytest.mark.asyncio
    async def test_container_lifecycle(self, docker_ssh_client):
        """Test complete container lifecycle: run, stop, start, remove."""
        async with docker_ssh_client:
            ssh_manager = docker_ssh_client.ssh_manager
            container_name = "lifecycle-test"
            
            try:
                # Pull nginx image
                stdout, stderr, exit_code = await ssh_manager.execute_command(
                    "docker-server", "docker pull nginx:alpine"
                )
                assert exit_code == 0, f"Failed to pull nginx: {stderr}"
                
                # Run nginx container in background
                stdout, stderr, exit_code = await ssh_manager.execute_command(
                    "docker-server", 
                    f"docker run -d --name {container_name} nginx:alpine"
                )
                assert exit_code == 0, f"Failed to run nginx: {stderr}"
                container_id = stdout.strip()
                
                # Wait a moment for container to start
                time.sleep(2)
                
                # List running containers
                containers = await docker_ssh_client.list_containers("docker-server")
                nginx_containers = [c for c in containers if container_name in c.name]
                assert len(nginx_containers) > 0
                
                nginx_container = nginx_containers[0]
                assert nginx_container.status == "running"
                assert "nginx" in nginx_container.image
                
                # Get detailed container info
                container_info = await docker_ssh_client.get_container_info(
                    "docker-server", container_id
                )
                assert container_info.status == "running"
                
                # Stop the container
                success = await docker_ssh_client.stop_container(
                    "docker-server", container_id
                )
                assert success
                
                # Verify it's stopped
                stopped_info = await docker_ssh_client.get_container_info(
                    "docker-server", container_id
                )
                assert stopped_info.status in ["stopped", "exited"]
                
                # Start it again
                success = await docker_ssh_client.start_container(
                    "docker-server", container_id
                )
                assert success
                
                # Verify it's running again
                running_info = await docker_ssh_client.get_container_info(
                    "docker-server", container_id
                )
                assert running_info.status == "running"
                
                # Remove the container (force remove to stop and remove)
                success = await docker_ssh_client.remove_container(
                    "docker-server", container_id, force=True
                )
                assert success
                
            except Exception as e:
                # Cleanup in case of failure
                try:
                    await ssh_manager.execute_command(
                        "docker-server", f"docker rm -f {container_name}"
                    )
                except:
                    pass
                raise

    @pytest.mark.asyncio
    async def test_execute_command_in_container(self, docker_ssh_client):
        """Test executing commands inside a running container."""
        async with docker_ssh_client:
            ssh_manager = docker_ssh_client.ssh_manager
            container_name = "exec-test"
            
            try:
                # Run an alpine container that sleeps
                stdout, stderr, exit_code = await ssh_manager.execute_command(
                    "docker-server", "docker pull alpine:latest"
                )
                assert exit_code == 0
                
                stdout, stderr, exit_code = await ssh_manager.execute_command(
                    "docker-server", 
                    f"docker run -d --name {container_name} alpine:latest sleep 30"
                )
                assert exit_code == 0
                container_id = stdout.strip()
                
                # Wait for container to be running
                time.sleep(2)
                
                # Execute a command in the container
                stdout, stderr, exit_code = await docker_ssh_client.execute_command(
                    "docker-server", container_id, "echo 'Hello from container'"
                )
                
                assert exit_code == 0
                assert "Hello from container" in stdout
                
                # Execute another command
                stdout, stderr, exit_code = await docker_ssh_client.execute_command(
                    "docker-server", container_id, "ls /"
                )
                
                assert exit_code == 0
                assert "bin" in stdout  # Standard Linux directories
                assert "etc" in stdout
                
            finally:
                # Cleanup
                try:
                    await ssh_manager.execute_command(
                        "docker-server", f"docker rm -f {container_name}"
                    )
                except:
                    pass

    @pytest.mark.asyncio
    async def test_get_container_logs(self, docker_ssh_client):
        """Test retrieving container logs."""
        async with docker_ssh_client:
            ssh_manager = docker_ssh_client.ssh_manager
            container_name = "logs-test"
            
            try:
                # Run a container that produces logs
                stdout, stderr, exit_code = await ssh_manager.execute_command(
                    "docker-server", 
                    f"docker run --name {container_name} alpine:latest "
                    "sh -c 'echo \"Log line 1\"; echo \"Log line 2\"; echo \"Log line 3\"'"
                )
                assert exit_code == 0
                
                # Get container logs
                logs = await docker_ssh_client.get_container_logs(
                    "docker-server", container_name
                )
                
                assert "Log line 1" in logs
                assert "Log line 2" in logs
                assert "Log line 3" in logs
                
            finally:
                # Cleanup
                try:
                    await ssh_manager.execute_command(
                        "docker-server", f"docker rm -f {container_name}"
                    )
                except:
                    pass

    @pytest.mark.asyncio
    async def test_container_stats(self, docker_ssh_client):
        """Test getting container statistics."""
        async with docker_ssh_client:
            ssh_manager = docker_ssh_client.ssh_manager
            container_name = "stats-test"
            
            try:
                # Run a long-running container
                stdout, stderr, exit_code = await ssh_manager.execute_command(
                    "docker-server", 
                    f"docker run -d --name {container_name} alpine:latest sleep 60"
                )
                assert exit_code == 0
                container_id = stdout.strip()
                
                # Wait for container to be fully running
                time.sleep(3)
                
                # Get container stats
                stats = await docker_ssh_client.get_container_stats(
                    "docker-server", container_id
                )
                
                # Stats should contain memory and CPU information
                assert isinstance(stats, dict)
                # Note: Stats format depends on Docker version and platform
                
            finally:
                # Cleanup
                try:
                    await ssh_manager.execute_command(
                        "docker-server", f"docker rm -f {container_name}"
                    )
                except:
                    pass

    @pytest.mark.asyncio
    async def test_list_containers_with_filters(self, docker_ssh_client):
        """Test listing containers with various filters."""
        async with docker_ssh_client:
            ssh_manager = docker_ssh_client.ssh_manager
            
            try:
                # Create multiple containers with different states
                await ssh_manager.execute_command(
                    "docker-server", "docker pull alpine:latest"
                )
                
                # Running container
                stdout, stderr, exit_code = await ssh_manager.execute_command(
                    "docker-server", 
                    "docker run -d --name filter-test-running alpine:latest sleep 60"
                )
                assert exit_code == 0
                
                # Stopped container
                stdout, stderr, exit_code = await ssh_manager.execute_command(
                    "docker-server", 
                    "docker run --name filter-test-stopped alpine:latest echo 'done'"
                )
                assert exit_code == 0
                
                time.sleep(2)  # Wait for states to stabilize
                
                # Test filter by status
                running_containers = await docker_ssh_client.list_containers(
                    "docker-server", 
                    filters={"status": "running"}
                )
                
                running_names = [c.name for c in running_containers]
                assert "filter-test-running" in running_names
                assert "filter-test-stopped" not in running_names
                
                # Test listing all containers
                all_containers = await docker_ssh_client.list_containers(
                    "docker-server",
                    filters={"all": True}
                )
                
                all_names = [c.name for c in all_containers]
                assert "filter-test-running" in all_names
                assert "filter-test-stopped" in all_names
                
            finally:
                # Cleanup
                try:
                    await ssh_manager.execute_command(
                        "docker-server", "docker rm -f filter-test-running filter-test-stopped"
                    )
                except:
                    pass

    @pytest.mark.asyncio
    async def test_error_handling_invalid_container(self, docker_ssh_client):
        """Test error handling for invalid container operations."""
        async with docker_ssh_client:
            # Try to get info for non-existent container
            with pytest.raises(DockerCommandError):
                await docker_ssh_client.get_container_info(
                    "docker-server", "nonexistent-container-id"
                )
            
            # Try to stop non-existent container
            with pytest.raises(DockerCommandError):
                await docker_ssh_client.stop_container(
                    "docker-server", "nonexistent-container-id"
                )
            
            # Try to execute command in non-existent container
            with pytest.raises(DockerCommandError):
                await docker_ssh_client.execute_command(
                    "docker-server", "nonexistent-container-id", "echo test"
                )

    @pytest.mark.asyncio
    async def test_concurrent_docker_operations(self, docker_ssh_client):
        """Test concurrent Docker operations."""
        async with docker_ssh_client:
            ssh_manager = docker_ssh_client.ssh_manager
            
            # Pull image first
            await ssh_manager.execute_command(
                "docker-server", "docker pull alpine:latest"
            )
            
            # Run multiple containers concurrently
            container_names = ["concurrent-1", "concurrent-2", "concurrent-3"]
            
            try:
                # Start containers concurrently
                start_tasks = []
                for name in container_names:
                    task = ssh_manager.execute_command(
                        "docker-server",
                        f"docker run -d --name {name} alpine:latest sleep 30"
                    )
                    start_tasks.append(task)
                
                results = await asyncio.gather(*start_tasks, return_exceptions=True)
                
                # Check that most succeeded
                successful = sum(1 for r in results if not isinstance(r, Exception))
                assert successful >= 2  # At least 2 should succeed
                
                time.sleep(2)  # Wait for containers to start
                
                # List containers concurrently
                list_tasks = [
                    docker_ssh_client.list_containers("docker-server")
                    for _ in range(3)
                ]
                
                list_results = await asyncio.gather(*list_tasks, return_exceptions=True)
                
                # All list operations should succeed
                for result in list_results:
                    if isinstance(result, Exception):
                        raise result
                    assert isinstance(result, list)
                
            finally:
                # Cleanup all containers
                for name in container_names:
                    try:
                        await ssh_manager.execute_command(
                            "docker-server", f"docker rm -f {name}"
                        )
                    except:
                        pass