from importlib.metadata import PackageNotFoundError, version

import pytest

from contextcraft import __version__, utils


def test_get_version_uses_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def distribution_version(name: str) -> str:
        assert name == "contextcraft-ai"
        return "1.2.3"

    monkeypatch.setattr(utils, "version", distribution_version)

    assert utils.get_version() == "1.2.3"


def test_get_version_without_distribution_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def distribution_version(name: str) -> str:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(utils, "version", distribution_version)

    assert utils.get_version() == "0.0.0"


def test_package_version_matches_distribution() -> None:
    assert __version__ == version("contextcraft-ai")
