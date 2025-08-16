"""
Docker service utilities for integration tests.

This module provides utilities to check if required Docker services
are running before executing integration tests.
"""
import asyncio
import json
import logging
import os
import subprocess
import time
from typing import Dict, List, Optional, Set

import docker
import httpx
import pytest

logger = logging.getLogger(__name__)

# Docker compose configuration
DOCKER_COMPOSE_FILE = "docker-compose.dev.yml"
REQUIRED_SERVICES = {
    "localstack",
    "whisper",
    "api",
    "rss-worker",
    "download-worker",
    "summarize-worker",
    "email-worker"
}

# Service health check endpoints and configurations
SERVICE_HEALTH_CHECKS = {
    "localstack": {
        "url": "http://localhost:4566/health",
        "expected_services": ["s3", "sqs", "ses", "dynamodb"],
        "timeout": 30
    },
    "api": {
        "url": "http://localhost:8000/health",
        "timeout": 10
    },
    "whisper": {
        # Whisper service doesn't expose HTTP endpoint by default
        # We'll check if container is running and healthy
        "container_check": True,
        "timeout": 10
    }
}

class DockerServiceError(Exception):
    """Exception raised when Docker services are not available."""
    pass

class DockerClient:
    """Docker client wrapper for service management."""

    def __init__(self):
        try:
            self.client = docker.from_env()
        except docker.errors.DockerException as e:
            raise DockerServiceError(f"Docker is not available: {e}")

    def get_running_containers(self) -> List[str]:
        """Get list of running container names."""
        try:
            containers = self.client.containers.list()
            return [container.name for container in containers]
        except docker.errors.DockerException as e:
            logger.error(f"Error getting container list: {e}")
            return []

    def is_container_running(self, name_pattern: str) -> bool:
        """Check if a container with name pattern is running."""
        running_containers = self.get_running_containers()
        return any(name_pattern in name for name in running_containers)

    def get_container_by_pattern(self, name_pattern: str) -> Optional[docker.models.containers.Container]:
        """Get container by name pattern."""
        try:
            containers = self.client.containers.list()
            for container in containers:
                if name_pattern in container.name:
                    return container
        except docker.errors.DockerException:
            pass
        return None

    def is_container_healthy(self, name_pattern: str) -> bool:
        """Check if container is running and healthy."""
        container = self.get_container_by_pattern(name_pattern)
        if not container:
            return False

        # Check if container is running
        if container.status != "running":
            return False

        # Check health status if available
        health = container.attrs.get("State", {}).get("Health", {})
        if health:
            return health.get("Status") == "healthy"

        # If no health check defined, consider running as healthy
        return True

async def check_http_service(url: str, timeout: int = 10) -> bool:
    """Check if HTTP service is responding."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            return response.status_code in [200, 404]  # 404 is OK for some endpoints
    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.debug(f"HTTP check failed for {url}: {e}")
        return False

async def check_localstack_health() -> bool:
    """Check LocalStack health and required services."""
    health_config = SERVICE_HEALTH_CHECKS["localstack"]

    try:
        async with httpx.AsyncClient(timeout=health_config["timeout"]) as client:
            response = await client.get(health_config["url"])

            if response.status_code != 200:
                return False

            health_data = response.json()
            services = health_data.get("services", {})

            # Check if all required services are running
            for service in health_config["expected_services"]:
                if services.get(service) != "running":
                    logger.warning(f"LocalStack service {service} is not running")
                    return False

            return True

    except Exception as e:
        logger.debug(f"LocalStack health check failed: {e}")
        return False

async def check_service_health(service_name: str) -> bool:
    """Check health of a specific service."""
    if service_name == "localstack":
        return await check_localstack_health()

    health_config = SERVICE_HEALTH_CHECKS.get(service_name)
    if not health_config:
        # For services without specific health check, just check if container is running
        docker_client = DockerClient()
        return docker_client.is_container_healthy(service_name)

    if health_config.get("container_check"):
        docker_client = DockerClient()
        return docker_client.is_container_healthy(service_name)

    if "url" in health_config:
        return await check_http_service(
            health_config["url"],
            health_config.get("timeout", 10)
        )

    return False

async def wait_for_service(service_name: str, max_wait: int = 60) -> bool:
    """Wait for a service to become healthy."""
    logger.info(f"Waiting for service {service_name} to become healthy...")

    start_time = time.time()
    while time.time() - start_time < max_wait:
        if await check_service_health(service_name):
            logger.info(f"Service {service_name} is healthy")
            return True

        await asyncio.sleep(2)

    logger.error(f"Service {service_name} did not become healthy within {max_wait}s")
    return False

async def wait_for_all_services(max_wait: int = 120) -> bool:
    """Wait for all required services to become healthy."""
    logger.info("Waiting for all Docker services to become healthy...")

    # Check services in order of dependency
    service_order = ["localstack", "api", "whisper", "rss-worker", "download-worker", "summarize-worker", "email-worker"]

    for service in service_order:
        if service in REQUIRED_SERVICES:
            if not await wait_for_service(service, max_wait // len(service_order)):
                return False

    logger.info("All Docker services are healthy")
    return True

def get_docker_compose_status() -> Dict[str, str]:
    """Get status of docker-compose services."""
    try:
        result = subprocess.run(
            ["docker-compose", "-f", DOCKER_COMPOSE_FILE, "ps", "--format", "json"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )

        if result.returncode != 0:
            logger.error(f"docker-compose ps failed: {result.stderr}")
            return {}

        services = {}
        if result.stdout.strip():
            # Handle both single JSON object and newline-separated JSON objects
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    try:
                        service_info = json.loads(line)
                        service_name = service_info.get("Service", "unknown")
                        state = service_info.get("State", "unknown")
                        services[service_name] = state
                    except json.JSONDecodeError:
                        continue

        return services

    except FileNotFoundError:
        logger.error("docker-compose command not found")
        return {}
    except Exception as e:
        logger.error(f"Error getting docker-compose status: {e}")
        return {}

def start_docker_services() -> bool:
    """Start docker-compose services."""
    try:
        logger.info("Starting Docker services...")
        result = subprocess.run(
            ["docker-compose", "-f", DOCKER_COMPOSE_FILE, "up", "-d"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )

        if result.returncode == 0:
            logger.info("Docker services started successfully")
            return True
        else:
            logger.error(f"Failed to start Docker services: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error starting Docker services: {e}")
        return False

def check_required_services() -> Set[str]:
    """Check which required services are missing."""
    docker_client = DockerClient()
    running_containers = docker_client.get_running_containers()

    missing_services = set()
    for service in REQUIRED_SERVICES:
        if not any(service in container for container in running_containers):
            missing_services.add(service)

    return missing_services

async def ensure_docker_services() -> bool:
    """Ensure all required Docker services are running."""
    # First check if services are already running
    missing_services = check_required_services()

    if not missing_services:
        # All containers are running, check health
        if await wait_for_all_services(max_wait=30):
            return True

    # Some services are missing, try to start them
    logger.info(f"Missing services: {missing_services}")

    if not start_docker_services():
        return False

    # Wait for services to become healthy
    return await wait_for_all_services(max_wait=120)

# Pytest fixtures for integration tests
@pytest.fixture(scope="session", autouse=True)
async def ensure_docker_services_fixture():
    """Pytest fixture to ensure Docker services are running."""
    if not await ensure_docker_services():
        pytest.skip("Required Docker services are not available")

@pytest.fixture(scope="session")
def docker_services_health():
    """Pytest fixture that provides service health status."""
    async def _check_health():
        health_status = {}
        for service in REQUIRED_SERVICES:
            health_status[service] = await check_service_health(service)
        return health_status

    return _check_health

def require_docker_services(services: List[str]):
    """Decorator to require specific Docker services for a test."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            missing = []
            for service in services:
                if not await check_service_health(service):
                    missing.append(service)

            if missing:
                pytest.skip(f"Required services not available: {missing}")

            return await func(*args, **kwargs)

        return wrapper
    return decorator

# Service-specific utilities
class WhisperServiceClient:
    """Client for interacting with the Whisper service container."""

    def __init__(self):
        self.docker_client = DockerClient()

    def is_available(self) -> bool:
        """Check if Whisper service is available."""
        return self.docker_client.is_container_healthy("whisper")

    async def transcribe_file(self, audio_file_path: str) -> Dict[str, any]:
        """Transcribe audio file using the Whisper service container."""
        if not self.is_available():
            raise DockerServiceError("Whisper service is not available")

        # Get the whisper container
        container = self.docker_client.get_container_by_pattern("whisper")
        if not container:
            raise DockerServiceError("Whisper container not found")

        try:
            # Copy file to container
            container_path = f"/tmp/{os.path.basename(audio_file_path)}"

            # Create a tar archive of the file
            import tarfile
            import io

            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tar.add(audio_file_path, arcname=os.path.basename(audio_file_path))
            tar_stream.seek(0)

            # Put the file in the container
            container.put_archive("/tmp", tar_stream)

            # Execute transcription
            result = container.exec_run([
                "python", "-c",
                f"""
import whisper
import json
import os

model = whisper.load_model(os.environ.get('WHISPER_MODEL_SIZE', 'tiny'))
result = model.transcribe('{container_path}')
print(json.dumps({{
    'text': result['text'],
    'language': result.get('language', 'unknown'),
    'segments': result.get('segments', [])
}}))
"""
            ])

            if result.exit_code != 0:
                raise DockerServiceError(f"Whisper transcription failed: {result.output.decode()}")

            # Parse result
            transcription_result = json.loads(result.output.decode().strip())

            # Clean up file in container
            container.exec_run(["rm", container_path])

            return transcription_result

        except Exception as e:
            raise DockerServiceError(f"Error during Whisper transcription: {e}")

# Utility function for getting service URLs
def get_service_url(service_name: str, default_port: Optional[int] = None) -> str:
    """Get the URL for a service."""
    if service_name == "api":
        return "http://localhost:8000"
    elif service_name == "localstack":
        return "http://localhost:4566"
    else:
        # For other services, they might not expose HTTP endpoints
        # Return a placeholder or container-based URL
        return f"http://localhost:{default_port}" if default_port else ""
