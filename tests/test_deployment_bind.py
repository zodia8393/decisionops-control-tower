from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_compose_and_docker_smoke_bind_only_to_loopback():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    docker_smoke = (ROOT / "scripts/verify_docker_deployment.sh").read_text(encoding="utf-8")

    assert '"127.0.0.1:${PORT:-8093}:8093"' in compose
    assert '-p "127.0.0.1:${PORT}:8093"' in docker_smoke
    assert 'CONTAINER_NAME="${CONTAINER_NAME:-decisionops-control-tower-smoke-$$}"' in docker_smoke
    assert 'DOCKER_CLEANUP="${DOCKER_CLEANUP:-1}"' in docker_smoke
    assert 'published="$(docker_cmd port "$CONTAINER_NAME" 8093/tcp)"' in docker_smoke


def test_smoke_images_are_isolated_from_the_running_demo_image():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "image: ${IMAGE_NAME:-decisionops-control-tower:local}" in compose
    for relative, default_name, cleanup_flag in (
        (
            "scripts/verify_docker_deployment.sh",
            "decisionops-control-tower:docker-smoke-$$",
            "DOCKER_CLEANUP",
        ),
        (
            "scripts/verify_compose_deployment.sh",
            "decisionops-control-tower:compose-smoke-$$",
            "COMPOSE_CLEANUP",
        ),
    ):
        script = (ROOT / relative).read_text(encoding="utf-8")
        assert f'DEFAULT_IMAGE_NAME="{default_name}"' in script
        assert 'docker_cmd image rm "$IMAGE_NAME"' in script
        assert f'"${cleanup_flag}" == "1"' in script


def test_docker_command_failure_status_is_preserved():
    for relative in (
        "scripts/verify_docker_deployment.sh",
        "scripts/verify_compose_deployment.sh",
    ):
        script = (ROOT / relative).read_text(encoding="utf-8")
        assert "else\n    direct_status=$?" in script
        assert "local direct_status=$?" not in script
