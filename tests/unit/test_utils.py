"""Unit tests for utility functions."""

import json
import pytest
from unittest.mock import patch

from snadboy_ssh_docker.utils import (
    parse_docker_ps_json,
    parse_docker_inspect,
    parse_docker_events_json,
    parse_container_labels,
    format_container_ports,
    safe_get_nested,
    escape_shell_arg,
    parse_docker_version,
    parse_compose_services
)
from snadboy_ssh_docker.models import ContainerInfo
from snadboy_ssh_docker.exceptions import DockerCommandError


class TestParseDockerPsJson:
    """Test cases for parse_docker_ps_json function."""

    def test_parse_valid_docker_ps_output(self, sample_docker_ps_output):
        """Test parsing valid docker ps JSON output."""
        containers = parse_docker_ps_json(sample_docker_ps_output)
        
        assert len(containers) == 2
        
        # Test first container
        container1 = containers[0]
        assert container1["ID"] == "abc123def456"
        assert container1["Names"] == "test-nginx"
        assert container1["Image"] == "nginx:latest"
        assert container1["State"] == "running"
        assert container1["Command"] == '"docker-entrypoint.s…"'
        
        # Test second container
        container2 = containers[1]
        assert container2["ID"] == "def456ghi789"
        assert container2["Names"] == "test-python-app"
        assert container2["Image"] == "python:3.9"

    def test_parse_empty_docker_ps_output(self):
        """Test parsing empty docker ps output."""
        containers = parse_docker_ps_json("[]")
        assert len(containers) == 0

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        containers = parse_docker_ps_json("invalid json")
        assert containers == []

    def test_parse_docker_ps_missing_fields(self):
        """Test parsing docker ps output with missing fields."""
        incomplete_output = '[{"ID": "abc123", "Names": "test-container"}]'
        
        containers = parse_docker_ps_json(incomplete_output)
        assert len(containers) == 1
        
        container = containers[0]
        assert container["ID"] == "abc123"
        assert container["Names"] == "test-container"
        # Missing fields won't be present in dict
        assert "Image" not in container
        assert "Status" not in container

    def test_parse_docker_ps_with_ports(self):
        """Test parsing docker ps output with port mappings."""
        output_with_ports = '''[{
            "ID": "abc123",
            "Names": "web-server",
            "Image": "nginx:latest",
            "Status": "Up 1 hour",
            "State": "running",
            "Ports": "0.0.0.0:8080->80/tcp, 0.0.0.0:8443->443/tcp",
            "Command": "nginx",
            "CreatedAt": "2023-01-01 12:00:00 +0000 UTC",
            "Labels": ""
        }]'''
        
        containers = parse_docker_ps_json(output_with_ports)
        container = containers[0]
        assert "0.0.0.0:8080->80/tcp" in container["Ports"]


class TestParseDockerInspect:
    """Test cases for parse_docker_inspect function."""

    def test_parse_valid_inspect_output(self, sample_docker_inspect_output):
        """Test parsing valid docker inspect output."""
        container = parse_docker_inspect(sample_docker_inspect_output)
        
        assert container["Id"] == "abc123def456789"
        assert container["Name"] == "/test-nginx"
        assert container["Image"] == "sha256:abcdef123456"
        assert container["State"]["Status"] == "running"
        assert container["Created"] == "2023-01-01T12:00:00.000000000Z"

    def test_parse_inspect_output_multiple_containers(self):
        """Test parsing inspect output for multiple containers."""
        multi_container_output = '''[
            {
                "Id": "container1",
                "Name": "/test1",
                "State": {"Status": "running"},
                "Config": {"Image": "nginx:latest"},
                "Created": "2023-01-01T12:00:00.000000000Z"
            },
            {
                "Id": "container2", 
                "Name": "/test2",
                "State": {"Status": "stopped"},
                "Config": {"Image": "python:3.9"},
                "Created": "2023-01-01T13:00:00.000000000Z"
            }
        ]'''
        
        # Should return first container
        container = parse_docker_inspect(multi_container_output)
        assert container["Id"] == "container1"
        assert container["Name"] == "/test1"

    def test_parse_invalid_inspect_json(self):
        """Test parsing invalid inspect JSON returns None."""
        result = parse_docker_inspect("invalid json")
        assert result is None

    def test_parse_empty_inspect_output(self):
        """Test parsing empty inspect output returns empty list."""
        result = parse_docker_inspect("[]")
        assert result == []

    def test_parse_inspect_missing_fields(self):
        """Test parsing inspect output with missing fields."""
        minimal_output = '''[{
            "Id": "abc123",
            "Name": "/minimal",
            "State": {},
            "Config": {},
            "Created": "2023-01-01T12:00:00.000000000Z"
        }]'''
        
        container = parse_docker_inspect(minimal_output)
        assert container["Id"] == "abc123"
        assert container["Name"] == "/minimal"
        assert container["State"] == {}  # Empty state dict
        assert container["Config"] == {}   # Empty config dict


class TestParseDockerEventsJson:
    """Test cases for parse_docker_events_json function."""

    def test_parse_valid_event(self):
        """Test parsing valid Docker event JSON."""
        event_json = '{"status":"start","id":"abc123","Type":"container","Action":"start"}'
        result = parse_docker_events_json(event_json)
        assert result is not None
        assert result["status"] == "start"
        assert result["id"] == "abc123"

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        result = parse_docker_events_json("invalid json")
        assert result is None


class TestParseContainerLabels:
    """Test cases for parse_container_labels function."""

    def test_parse_single_label(self):
        """Test parsing single label."""
        labels = parse_container_labels("app=myapp")
        assert labels == {"app": "myapp"}

    def test_parse_multiple_labels(self):
        """Test parsing multiple labels."""
        labels = parse_container_labels("app=myapp,version=1.0,env=prod")
        assert labels == {"app": "myapp", "version": "1.0", "env": "prod"}

    def test_parse_empty_labels(self):
        """Test parsing empty labels string."""
        labels = parse_container_labels("")
        assert labels == {}

    def test_parse_labels_with_spaces(self):
        """Test parsing labels with spaces."""
        labels = parse_container_labels("app = myapp , version = 1.0")
        assert labels == {"app": "myapp", "version": "1.0"}

    def test_parse_labels_with_special_values(self):
        """Test parsing labels with special characters in values."""
        labels = parse_container_labels("path=/usr/bin,url=http://example.com")
        assert labels == {"path": "/usr/bin", "url": "http://example.com"}


class TestFormatContainerPorts:
    """Test cases for format_container_ports function."""

    def test_format_single_port(self):
        """Test formatting single port."""
        ports = format_container_ports("80/tcp")
        assert ports == ["80/tcp"]

    def test_format_multiple_ports(self):
        """Test formatting multiple ports."""
        ports = format_container_ports("80/tcp, 443/tcp, 3000/tcp")
        assert ports == ["80/tcp", "443/tcp", "3000/tcp"]

    def test_format_port_mappings(self):
        """Test formatting port mappings."""
        ports = format_container_ports("0.0.0.0:8080->80/tcp, 0.0.0.0:8443->443/tcp")
        assert ports == ["0.0.0.0:8080->80/tcp", "0.0.0.0:8443->443/tcp"]

    def test_format_empty_ports(self):
        """Test formatting empty ports string."""
        ports = format_container_ports("")
        assert ports == []

    def test_format_ports_with_extra_spaces(self):
        """Test formatting ports with extra spaces."""
        ports = format_container_ports("  80/tcp  ,   443/tcp  ")
        assert ports == ["80/tcp", "443/tcp"]


class TestSafeGetNested:
    """Test cases for safe_get_nested function."""

    def test_get_simple_value(self):
        """Test getting simple nested value."""
        data = {"a": {"b": {"c": "value"}}}
        result = safe_get_nested(data, "a", "b", "c")
        assert result == "value"

    def test_get_missing_key(self):
        """Test getting missing key returns default."""
        data = {"a": {"b": {}}}
        result = safe_get_nested(data, "a", "b", "c", default="default")
        assert result == "default"

    def test_get_none_default(self):
        """Test getting missing key returns None by default."""
        data = {"a": {}}
        result = safe_get_nested(data, "a", "b", "c")
        assert result is None

    def test_get_from_non_dict(self):
        """Test getting from non-dict returns default."""
        data = {"a": "string"}
        result = safe_get_nested(data, "a", "b", default="default")
        assert result == "default"

    def test_get_empty_keys(self):
        """Test getting with no keys returns original data."""
        data = {"a": "value"}
        result = safe_get_nested(data)
        assert result == data


class TestEscapeShellArg:
    """Test cases for escape_shell_arg function."""

    def test_escape_simple_string(self):
        """Test escaping simple string."""
        result = escape_shell_arg("hello")
        assert result == "hello"

    def test_escape_single_quotes(self):
        """Test escaping single quotes."""
        result = escape_shell_arg("hello'world")
        assert result == "hello'\"'\"'world"

    def test_escape_multiple_quotes(self):
        """Test escaping multiple single quotes."""
        result = escape_shell_arg("'hello' 'world'")
        assert "'\"'\"'" in result

    def test_escape_empty_string(self):
        """Test escaping empty string."""
        result = escape_shell_arg("")
        assert result == ""


class TestParseDockerVersion:
    """Test cases for parse_docker_version function."""

    def test_parse_full_version_output(self):
        """Test parsing full docker version output."""
        output = """Client:
 Version:           20.10.17
 API version:       1.41
 Go version:        go1.17.11

Server:
 Version:          20.10.17
 API version:      1.41 (minimum version 1.12)
 Go version:       go1.17.11
"""
        result = parse_docker_version(output)
        assert result["client_version"] == "20.10.17"
        assert result["client_api_version"] == "1.41"
        assert result["server_version"] == "20.10.17"
        assert "server_api_version" in result

    def test_parse_client_only_version(self):
        """Test parsing client-only version output."""
        output = """Client:
 Version:           20.10.17
 API version:       1.41
"""
        result = parse_docker_version(output)
        assert result["client_version"] == "20.10.17"
        assert result["client_api_version"] == "1.41"
        assert "server_version" not in result

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_docker_version("")
        assert result == {}

    def test_parse_malformed_output(self):
        """Test parsing malformed output."""
        output = "Some random text\nWithout proper format"
        result = parse_docker_version(output)
        # Should handle gracefully without errors
        assert isinstance(result, dict)


class TestParseComposeServices:
    """Test cases for parse_compose_services function."""
    
    def test_parse_v3_compose(self):
        """Test parsing a version 3 compose file."""
        compose_content = """
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
  api:
    image: myapp:latest
    container_name: myapp-api
    labels:
      app: myapp
      tier: backend
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: myapp
volumes:
  db-data:
networks:
  backend:
"""
        services = parse_compose_services(compose_content)
        
        assert len(services) == 3
        assert 'web' in services
        assert 'api' in services
        assert 'db' in services
        
        # Check web service
        assert services['web']['image'] == 'nginx:latest'
        assert services['web']['container_name'] is None
        
        # Check api service
        assert services['api']['image'] == 'myapp:latest'
        assert services['api']['container_name'] == 'myapp-api'
        assert services['api']['labels'] == {'app': 'myapp', 'tier': 'backend'}
        
        # Check db service
        assert services['db']['image'] == 'postgres:13'
    
    def test_parse_v2_compose(self):
        """Test parsing a version 2 compose file."""
        compose_content = """
version: '2'
services:
  app:
    build: .
    scale: 3
networks:
  default:
"""
        services = parse_compose_services(compose_content)
        
        assert len(services) == 1
        assert 'app' in services
        assert services['app']['build'] == '.'
        assert services['app']['scale'] == 3
        assert services['app']['replicas'] == 3
    
    def test_parse_v1_compose(self):
        """Test parsing a version 1 compose file (no version, services at root)."""
        compose_content = """
web:
  image: nginx
  ports:
    - "80:80"
db:
  image: mysql:5.7
  environment:
    MYSQL_ROOT_PASSWORD: secret
"""
        services = parse_compose_services(compose_content)
        
        assert len(services) == 2
        assert 'web' in services
        assert 'db' in services
        assert services['web']['image'] == 'nginx'
        assert services['db']['image'] == 'mysql:5.7'
    
    def test_parse_with_deploy_replicas(self):
        """Test parsing compose with deploy.replicas (v3 swarm mode)."""
        compose_content = """
version: '3.8'
services:
  worker:
    image: myapp:worker
    deploy:
      replicas: 5
      placement:
        constraints:
          - node.role == worker
"""
        services = parse_compose_services(compose_content)
        
        assert 'worker' in services
        assert services['worker']['replicas'] == 5
        assert services['worker']['deploy']['replicas'] == 5
    
    def test_parse_invalid_yaml(self):
        """Test parsing invalid YAML raises ValueError."""
        compose_content = """
services:
  web:
    image: nginx
    ports: [80:80  # Missing closing bracket
"""
        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_compose_services(compose_content)
    
    def test_parse_not_dict(self):
        """Test parsing non-dict YAML raises ValueError."""
        compose_content = """
- item1
- item2
"""
        with pytest.raises(ValueError, match="must be a YAML dictionary"):
            parse_compose_services(compose_content)
    
    def test_parse_empty_services(self):
        """Test parsing compose file with no services."""
        compose_content = """
version: '3'
services:
networks:
  backend:
"""
        services = parse_compose_services(compose_content)
        assert services == {}
    
    def test_parse_with_non_dict_service(self):
        """Test parsing with non-dict service definition (should skip)."""
        compose_content = """
version: '3'
services:
  web: nginx:latest  # Invalid - should be a dict
  api:
    image: myapp
"""
        services = parse_compose_services(compose_content)
        
        # Should only get the valid service
        assert len(services) == 1
        assert 'api' in services
        assert 'web' not in services