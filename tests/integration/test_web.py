from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from web.app import app

client = TestClient(app)


def test_web_health_and_index_page() -> None:
    """Verify `/api/health` and `/` HTML rendering."""
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    index_resp = client.get("/?budget=8k&focus=auth")
    assert index_resp.status_code == 200
    assert "ContextCraft" in index_resp.text


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
    assert len(payload["files"]) >= 5


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
