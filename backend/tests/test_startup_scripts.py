from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import start_backend, wait_for_db


def test_wait_for_db_uses_configured_database_url(monkeypatch):
    calls: list[str] = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def execute(self, _statement):
            calls.append("execute")

    class FakeEngine:
        def connect(self):
            calls.append("connect")
            return FakeConnection()

        def dispose(self):
            calls.append("dispose")

    monkeypatch.setattr(wait_for_db, "create_engine", lambda *args, **kwargs: FakeEngine())

    wait_for_db.main()

    assert calls == ["connect", "execute", "dispose"]


def test_start_backend_bootstraps_before_uvicorn(monkeypatch):
    commands: list[list[str]] = []

    monkeypatch.setattr(
        start_backend.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command),
    )

    start_backend.main()

    assert commands == [
        [sys.executable, "scripts/wait_for_db.py"],
        [sys.executable, "scripts/bootstrap_db.py"],
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    ]


def test_backend_requirements_include_cryptography_for_mysql_auth():
    requirements = Path("backend/requirements.txt").read_text(encoding="utf-8")

    assert "cryptography" in requirements


def test_docker_compose_does_not_force_legacy_mysql_auth_compatibility():
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "docker/mysql-init" not in compose_text
    assert "mysql_native_password" not in compose_text
    assert "mysql-native-password=ON" not in compose_text


def test_docker_compose_supports_proxy_build_and_runtime_configuration():
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "DOCKER_BUILD_HTTP_PROXY" in compose_text
    assert "DOCKER_BUILD_HTTPS_PROXY" in compose_text
    assert "DOCKER_BUILD_NO_PROXY" in compose_text
    assert "args:" in compose_text


def test_env_example_documents_optional_proxy_settings():
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "DOCKER_BUILD_HTTP_PROXY=" in env_example
    assert "DOCKER_BUILD_HTTPS_PROXY=" in env_example
    assert "DOCKER_BUILD_NO_PROXY=" in env_example


def test_docker_proxy_helper_script_exists():
    script_text = Path("scripts/configure_docker_desktop_proxy.ps1").read_text(
        encoding="utf-8"
    )

    assert "settings-store.json" in script_text
    assert "OverrideProxyHTTP" in script_text
    assert "OverrideProxyHTTPS" in script_text
