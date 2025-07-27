"""Utility functions for SSH Docker Client."""

import json
from typing import Any, Dict, List, Optional, Union

import yaml


def parse_docker_ps_json(output: str) -> List[Dict[str, Any]]:
    """Parse JSON output from docker ps command.

    Args:
        output: Raw output from docker ps --format json

    Returns:
        List of container dictionaries
    """
    output = output.strip()
    if not output:
        return []

    # Try to parse as JSON array first
    try:
        data = json.loads(output)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Otherwise parse as newline-delimited JSON
    containers = []
    for line in output.split("\n"):
        if not line:
            continue

        try:
            container = json.loads(line)
            containers.append(container)
        except json.JSONDecodeError:
            # Skip invalid lines
            continue

    return containers


def parse_docker_inspect(output: str) -> Union[Dict[str, Any], List[Any], None]:
    """Parse docker inspect output.

    Args:
        output: Raw JSON output from docker inspect

    Returns:
        Container information dictionary or None
    """
    try:
        data = json.loads(output)
        if isinstance(data, list):
            if data:
                return data[0] if isinstance(data[0], dict) else None
            else:
                return []  # Return empty list for "[]" input
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def parse_docker_events_json(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single Docker event JSON line.

    Args:
        line: Single line from docker events --format json

    Returns:
        Event dictionary or None if invalid
    """
    try:
        data = json.loads(line.strip())
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def parse_container_labels(labels_str: str) -> Dict[str, str]:
    """Parse container labels from comma-separated string.

    Args:
        labels_str: Comma-separated labels (key=value,key2=value2)

    Returns:
        Dictionary of labels
    """
    labels: Dict[str, str] = {}

    if not labels_str:
        return labels

    for label in labels_str.split(","):
        if "=" in label:
            key, value = label.split("=", 1)
            labels[key.strip()] = value.strip()

    return labels


def format_container_ports(ports_str: str) -> List[str]:
    """Parse and format container ports string.

    Args:
        ports_str: Raw ports string from docker ps

    Returns:
        List of formatted port mappings
    """
    if not ports_str:
        return []

    ports = []
    for port_mapping in ports_str.split(","):
        port_mapping = port_mapping.strip()
        if port_mapping:
            ports.append(port_mapping)

    return ports


def safe_get_nested(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary values.

    Args:
        data: Dictionary to search
        *keys: Sequence of keys to traverse
        default: Default value if key not found

    Returns:
        Value at nested key path or default
    """
    current = data

    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default

    return current


def escape_shell_arg(arg: str) -> str:
    """Escape shell argument for safe execution.

    Args:
        arg: Argument to escape

    Returns:
        Escaped argument
    """
    # Simple escaping - for more complex cases, use shlex.quote
    return arg.replace("'", "'\"'\"'")


def parse_docker_version(output: str) -> Dict[str, str]:
    """Parse docker version output.

    Args:
        output: Raw output from docker version

    Returns:
        Dictionary with version information
    """
    version_info = {}
    current_section = None

    for line in output.split("\n"):
        line = line.strip()

        if not line:
            continue

        if line.endswith(":") and not " " in line:
            current_section = line[:-1].lower()
        elif ":" in line and current_section:
            key, value = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()

            if current_section == "client":
                version_info[f"client_{key}"] = value
            elif current_section == "server":
                version_info[f"server_{key}"] = value
            else:
                version_info[key] = value

    return version_info


def parse_compose_services(compose_content: str) -> Dict[str, Dict[str, Any]]:
    """Parse docker-compose.yml content and extract service definitions.

    Args:
        compose_content: Content of docker-compose.yml file

    Returns:
        Dictionary mapping service names to their configurations

    Raises:
        ValueError: If compose content is invalid YAML
    """
    try:
        compose_data = yaml.safe_load(compose_content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in compose file: {e}")

    if not isinstance(compose_data, dict):
        raise ValueError("Compose file must be a YAML dictionary")

    # Handle both v1 (services at root) and v2/v3 (services under 'services' key)
    services = {}

    if "services" in compose_data:
        # v2/v3 format
        services_data = compose_data.get("services", {})
        # Handle case where services key exists but is None or not a dict
        if not isinstance(services_data, dict):
            services_data = {}
    else:
        # v1 format - services at root level
        # Exclude known non-service keys
        non_service_keys = {"version", "networks", "volumes", "configs", "secrets"}
        services_data = {
            k: v
            for k, v in compose_data.items()
            if k not in non_service_keys and isinstance(v, dict)
        }

    for service_name, service_config in services_data.items():
        if not isinstance(service_config, dict):
            continue

        # Extract relevant information
        service_info = {
            "image": service_config.get("image"),
            "container_name": service_config.get("container_name"),
            "build": service_config.get("build"),
            "labels": service_config.get("labels", {}),
            "deploy": service_config.get("deploy", {}),
            "scale": service_config.get("scale", 1),  # For v1 compatibility
        }

        # Handle deploy.replicas for v3
        if "deploy" in service_config and "replicas" in service_config["deploy"]:
            service_info["replicas"] = service_config["deploy"]["replicas"]
        else:
            service_info["replicas"] = service_info["scale"]

        services[service_name] = service_info

    return services
