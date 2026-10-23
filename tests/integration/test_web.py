from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from contextcraft import ContextCraft, ContextCraftError
from web.app import _clone_and_compile_github_repo, app

client = TestClient(app)


@pytest.fixture(autouse=True)
def web_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("web.app._LOCAL_REPOSITORY_ROOT", tmp_path)
    return tmp_path


def test_web_health_and_index_page() -> None:
    """Verify `/api/health` and `/` HTML rendering."""
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    index_resp = client.get("/?budget=8k&focus=auth")
    assert index_resp.status_code == 200
    assert "ContextCraft" in index_resp.text


def test_web_template_escapes_user_input() -> None:
    payload = '"><script>alert(1)</script>'
    response = client.get("/", params={"source": payload})

    assert response.status_code == 200
    assert payload not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def test_web_api_compile_local_repository(sample_repo: Path) -> None:
    """Verify `POST /api/compile` compiles a local repository within token budget."""
    resp = client.post(
        "/api/compile",
        json={
            "source": str(sample_repo),
            "budget": "1.5k",
            "focus_query": "JWT verify_token",
            "output_format": "markdown",
            "redact_secrets": True,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["stats"]["compressed_tokens"] <= 1500
    assert payload["stats"]["secrets_redacted"] >= 1
    assert "sk-proj-1234567890" not in payload["content"]
    assert "src/auth/models.py" in {file["rel_path"] for file in payload["files"]}


def test_web_url_swap_route_and_invalid_inputs(sample_repo: Path) -> None:
    """Verify `GET /{owner}/{repo}` URL-swap page and invalid budget error handling."""
    swap_resp = client.get("/tiangolo/fastapi?budget=32k&focus=routing")
    assert swap_resp.status_code == 200
    assert "https://github.com/tiangolo/fastapi" in swap_resp.text

    bad_resp = client.post(
        "/api/compile",
        json={
            "source": str(sample_repo),
            "budget": "invalid-budget",
        },
    )
    assert bad_resp.status_code == 400


def test_web_relative_paths_use_the_configured_root(sample_repo: Path) -> None:
    response = client.post("/api/compile", json={"source": sample_repo.name, "budget": "1k"})

    assert response.status_code == 200
    assert response.json()["stats"]["compressed_tokens"] <= 1000
    assert any(file["rel_path"] == "src/auth/models.py" for file in response.json()["files"])


@pytest.mark.parametrize(
    "kind", ["absolute", "traversal", "normalized_traversal", "parent", "prefix_collision"]
)
def test_web_rejects_paths_outside_the_configured_root(web_root: Path, kind: str) -> None:
    sources = {
        "absolute": str(web_root.parent / "outside"),
        "traversal": "../outside",
        "normalized_traversal": "missing/../../outside",
        "parent": "..",
        "prefix_collision": str(web_root) + "-outside",
    }
    with (
        patch("web.app.Path") as construct_path,
        patch("web.app.ContextCraft.compile") as compile_repository,
    ):
        response = client.post("/api/compile", json={"source": sources[kind]})

    assert response.status_code == 403
    construct_path.assert_not_called()
    compile_repository.assert_not_called()
    assert str(web_root) not in response.json()["detail"]


def test_web_rejects_symlinks_that_escape_the_configured_root(web_root: Path) -> None:
    (web_root / "escape").symlink_to(web_root.parent, target_is_directory=True)
    with patch("web.app.ContextCraft.compile") as compile_repository:
        response = client.post("/api/compile", json={"source": "escape"})

    assert response.status_code == 403
    compile_repository.assert_not_called()


def test_web_allows_symlinks_within_the_configured_root(web_root: Path, sample_repo: Path) -> None:
    (web_root / "repo-link").symlink_to(sample_repo, target_is_directory=True)

    response = client.post("/api/compile", json={"source": "repo-link", "budget": "1k"})

    assert response.status_code == 200
    assert response.json()["stats"]["compressed_tokens"] <= 1000


def test_web_rejects_invalid_path_values() -> None:
    with (
        patch("web.app.Path") as construct_path,
        patch("web.app.ContextCraft.compile") as compile_repository,
    ):
        response = client.post("/api/compile", json={"source": "invalid\x00path"})

    assert response.status_code == 400
    construct_path.assert_not_called()
    compile_repository.assert_not_called()


def test_web_clones_github_repositories_into_a_fixed_destination(web_root: Path) -> None:
    destinations: list[Path] = []

    def clone(command: list[str], **kwargs: object) -> None:
        destination = Path(command[-1])
        assert destination.name == "repository"
        assert not destination.is_relative_to(web_root)
        destination.mkdir()
        (destination / "main.py").write_text("def run():\n    return 1\n", encoding="utf-8")
        destinations.append(destination)

    with (
        patch("web.app.shutil.which", return_value="git"),
        patch("web.app.subprocess.run", side_effect=clone) as clone_process,
    ):
        response = client.post(
            "/api/compile", json={"source": "https://github.com/example/my-repo", "budget": "1k"}
        )

    assert response.status_code == 200
    assert [file["rel_path"] for file in response.json()["files"]] == ["main.py"]
    clone_process.assert_called_once()
    assert destinations
    assert not destinations[0].exists()


@pytest.mark.parametrize(
    "owner,repo",
    [
        ("example", "."),
        ("example", ".."),
        (".", "repo"),
        ("..", "repo"),
        ("example", "repo\n"),
        ("example\n", "repo"),
        ("example", "../repo"),
    ],
)
def test_web_rejects_unsafe_github_slugs(owner: str, repo: str) -> None:
    with (
        patch("web.app.subprocess.run") as clone_process,
        pytest.raises(ContextCraftError, match="Invalid GitHub repository slug"),
    ):
        _clone_and_compile_github_repo(ContextCraft(), owner=owner, repo=repo)

    clone_process.assert_not_called()


def test_web_normalizes_relative_paths_inside_the_root(sample_repo: Path) -> None:
    source = f"{sample_repo.name}/../{sample_repo.name}"

    response = client.post("/api/compile", json={"source": source, "budget": "1k"})

    assert response.status_code == 200
    assert any(file["rel_path"] == "src/auth/models.py" for file in response.json()["files"])


def test_web_expands_home_paths_inside_the_root(
    web_root: Path, sample_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(web_root))
    monkeypatch.setenv("USERPROFILE", str(web_root))

    response = client.post("/api/compile", json={"source": f"~/{sample_repo.name}", "budget": "1k"})

    assert response.status_code == 200
    assert any(file["rel_path"] == "src/auth/models.py" for file in response.json()["files"])


def test_web_rejects_paths_on_another_drive_before_constructing_a_path() -> None:
    with (
        patch("web.app.os.path.relpath", side_effect=ValueError("different drives")),
        patch("web.app.Path") as construct_path,
        patch("web.app.ContextCraft.compile") as compile_repository,
    ):
        response = client.post("/api/compile", json={"source": "another-drive"})

    assert response.status_code == 403
    construct_path.assert_not_called()
    compile_repository.assert_not_called()
